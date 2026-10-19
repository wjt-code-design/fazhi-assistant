"""W06-B Task 3 行为测试：不可变 QA 依赖快照 + 缓存读写守（B01–B11、B17）。

隔离：临时 SQLite（`db`，把 `database.SessionLocal` 换到 tmp 引擎）+ conftest 临时 `CHROMA_DIR`
+ `double_embeddings`；不碰真实 `app.db`／真实语料／真权重，不联网、不读 .env 配置。

判据对象是**产品函数**（`qa_eligibility.capture_dependency/validate_dependencies`、
`main._cache_read_deps_ok/_cache_write_deps_ok/_input_qa_dependencies/_generation_input_invalid`），
不是测试自造的等价物。端到端 SSE 逐帧在本文件不跑（由 W06B 报告注明覆盖边界）。
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import answer_cache  # noqa: E402
import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import qa_eligibility as qe  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)
SCOPE_IDS = ["劳动合同法|第十九条"]


@pytest.fixture(autouse=True)
def _clean_cache():
    answer_cache.clear()
    yield
    answer_cache.clear()


def _run(coro):
    return asyncio.run(coro)


def _g_row(db, question, *, approval_source="human"):
    """合成一条可服务候选（approved + 显式向量链，链双向闭合），代表「实际生成用到的 QA」。"""
    doc_id = uuid.uuid4().hex
    row = ks.QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.95,
        evidence=EVIDENCE,
        status="approved",
        approval_source=approval_source,
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    ks.add_qa_pair(question, ANSWER, EVIDENCE, cand_id=row.id, doc_id=doc_id)
    return row


def _revoke_without_clear(db, row):
    """直接落 SQL 撤回（**不经** `decide_candidate`）——模拟另一个进程的撤回，本进程**不** clear。"""
    row_obj = db.get(ks.QaCandidate, row.id)
    row_obj.eligibility = "revoked"
    db.commit()


def _warm_exact(q, dep):
    key = answer_cache.make_key(q, "legal_query", "2026-10-01", SCOPE_IDS)
    answer_cache.put(key, ANSWER, [], qa_dependencies=(dep,))
    return key


def _hit_of(q):
    hit = ks.search_qa(q)
    assert hit is not None and hit.get("qa_candidate_id") is not None, "合成记录没被服务侧读回 ⇒ 判据失去对象"
    return hit


# ==================== 依赖快照：capture / validate（纯判据 + 计数） ====================


def test_capture_dependency_freezes_identity_and_is_internal_only(db, double_embeddings):
    """§4.1：capture 冻结 candidate_id / vector_doc_id / eligibility_version / 记录摘要。"""
    q = "B 依赖快照：capture 到底冻了哪几个字段？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    assert dep is not None
    assert dep.candidate_id == row.id
    assert dep.vector_doc_id == row.vector_doc_id
    assert dep.eligibility_version == 1
    # 摘要只在进程内部核对：不进公开 hit，也不落日志（此处只断言其确定性/非空）
    assert isinstance(dep.record_digest, str) and len(dep.record_digest) == 64
    assert "question" not in dep.record_digest and ANSWER not in dep.record_digest


def test_capture_dependency_none_without_reliable_identity(db, double_embeddings):
    """B08 前置：无 SQL 身份的 QA 取不到快照 ⇒ None（不假签空依赖）。"""
    q = "B 依赖快照：无链记录能给可靠身份吗？"
    ks.add_qa_pair(q, ANSWER, EVIDENCE)  # 无 cand_id / doc_id（种子/生成脚本形状）
    hit = ks.search_qa(q)
    assert hit is not None and hit.get("qa_candidate_id") is None
    assert qe.capture_dependency(hit) is None


def test_validate_dependencies_three_states(db, double_embeddings):
    """三态语义：None=未知不复核放行；空 tuple=已确认无 QA；非空=逐条核。"""
    assert qe.validate_dependencies(None).allow is False
    assert qe.validate_dependencies(None).reason == "unknown"
    assert qe.validate_dependencies(()).allow is True


@pytest.mark.parametrize(
    "break_it,reason",
    [
        ("missing", "missing"),
        ("version", "version"),
        ("doc_id", "identity"),
        ("content", "content"),
        ("revoked", "state"),
    ],
)
def test_validate_dependencies_rejects_every_change(db, double_embeddings, break_it, reason):
    """B04 变体：丢行 / version 变 / doc id 变 / 内容变 / 撤回 逐条 ⇒ 拒绝（异常≠已知无 QA）。"""
    q = f"B04 {break_it}：依赖任一变化都该 miss 吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    assert qe.validate_dependencies((dep,)).allow is True  # 阳性：未变 → 放行

    if break_it == "missing":
        db.delete(db.get(ks.QaCandidate, row.id))
        db.commit()
    else:
        live = db.get(ks.QaCandidate, row.id)
        if break_it == "version":
            live.eligibility_version += 1
        elif break_it == "doc_id":
            live.vector_doc_id = uuid.uuid4().hex
        elif break_it == "content":
            live.answer = "被改写的答案"
        elif break_it == "revoked":
            live.eligibility = "revoked"
        db.commit()

    verdict = qe.validate_dependencies((dep,))
    assert verdict.allow is False and verdict.reason == reason, verdict


def test_validate_dependencies_read_failure_is_not_known_empty(db, double_embeddings, monkeypatch):
    """B04（SQL 异常）：读不动 ⇒ 拒绝（unreadable），绝不当成「没有 QA」。"""
    q = "B04 读异常：查不动依赖会当成空吗？"
    _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))

    def _boom():
        raise RuntimeError("模拟库挂/连接锁死")

    monkeypatch.setattr(qe.database, "SessionLocal", _boom)
    verdict = qe.validate_dependencies((dep,))
    assert verdict.allow is False and verdict.reason == "unreadable"


# ==================== B01 / B02：撤回后精确与相似缓存都不服务 ====================


def test_b01_revoked_dependency_invalidates_warm_exact_cache(db, double_embeddings):
    """B01：暖精确缓存→撤回→同问新请求：不发旧缓存 answer。"""
    q = "B01 暖精确缓存撤回后还发旧答案吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    key = _warm_exact(q, dep)
    entry = answer_cache.get(key)
    assert entry is not None and entry["qa_dependencies"] == (dep,)
    assert _run(main._cache_read_deps_ok(entry)) is True  # 阳性：未撤回时可服务

    _revoke_without_clear(db, row)
    answer_cache.clear()  # 模拟失效后缓存被**另一个进程/旧写入**重新填回同一条
    _warm_exact(q, dep)
    stale = answer_cache.get(key)
    assert stale is not None, "旧写入重新填回 ⇒ 本条判据才有对象"
    assert _run(main._cache_read_deps_ok(stale)) is False, "撤回后仍服务旧缓存 ⇒ B01 未闭合"


def test_b02_revoked_dependency_invalidates_warm_similar_cache(db, double_embeddings):
    """B02：暖相似缓存→撤回后改写请求：先证护栏命中，再证撤回后不服务旧相似答案。"""
    q = "B02 暖相似缓存撤回后还发旧相似答案吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    scope = answer_cache.make_scope("study_aid", "2026-10-01", SCOPE_IDS)
    answer_cache.put("k-sim", ANSWER, [], embedding=[1.0, 0.0], scope=scope, qa_dependencies=(dep,))
    sim = answer_cache.get_similar([1.0, 0.0], scope=scope)
    assert sim is not None, "护栏没命中 ⇒ 后面「不服务旧相似答案」会变成假绿"
    assert _run(main._cache_read_deps_ok(sim)) is True

    _revoke_without_clear(db, row)
    sim2 = answer_cache.get_similar([1.0, 0.0], scope=scope)  # 存储查询仍在，条目没被本进程清
    assert sim2 is not None
    assert _run(main._cache_read_deps_ok(sim2)) is False


# ==================== B03：跨进程撤回（独立合成 SQLite + 子进程，不靠本地 clear） ====================


def test_b03_cross_process_revocation_is_caught_by_sql_dependency(db, double_embeddings):
    """B03：另一进程在合成 SQL 提交撤回；本进程**不 clear** ⇒ 新 SQL 复核拒绝旧依赖。

    用**独立合成 SQLite 文件 + 真子进程**，不用同一 Session 冒充第二进程、不 sleep 赌时序。
    """
    q = "B03 跨进程撤回：只靠进程 generation 能挡住吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    key = _warm_exact(q, dep)
    assert _run(main._cache_read_deps_ok(answer_cache.get(key))) is True

    db.commit()
    db_path = str(db.get_bind().url.database)
    assert db_path and db_path != ":memory:", "本条要求文件型合成库（跨进程可见）"

    script = (
        "import sqlite3\n"
        f"con = sqlite3.connect({db_path!r})\n"
        "con.execute(\"update qa_candidates set eligibility='revoked' where id=?\", ("
        f"{int(row.id)},))\n"
        "con.commit()\n"
        "con.close()\n"
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, f"子进程撤回失败：{proc.stderr}"

    # 本进程没有 clear、没有 generation 变化；读进程用**新 SQL 会话**复核（capture 时冻的 dep）
    entry = answer_cache.get(key)
    assert entry is not None, "本地缓存被清了 ⇒ 本判据测的就不是跨进程那一支"
    assert _run(main._cache_read_deps_ok(entry)) is False, "跨进程撤回没被 SQL 依赖复核挡住 ⇒ 不只靠 generation 不成立"


# ==================== B05：依赖未变，两种命中都可用 ====================


def test_b05_unchanged_dependency_serves_exact_and_similar(db, double_embeddings):
    """B05：未撤回依赖不变 ⇒ 精确与相似命中的依赖门都放行（既有护栏仍需过，此处单测依赖门）。"""
    q = "B05 未撤回：精确与相似都该可用吗？"
    _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    key = _warm_exact(q, dep)
    assert _run(main._cache_read_deps_ok(answer_cache.get(key))) is True

    scope = answer_cache.make_scope("study_aid", "2026-10-01", SCOPE_IDS)
    answer_cache.put("k-sim", ANSWER, [], embedding=[1.0, 0.0], scope=scope, qa_dependencies=(dep,))
    assert _run(main._cache_read_deps_ok(answer_cache.get_similar([1.0, 0.0], scope=scope))) is True


# ==================== B06：旧条目 / None / 形状损坏 都不服务 ====================


def test_b06_entries_without_field_or_none_or_corrupt_are_not_served(db, double_embeddings):
    """B06：旧缓存无依赖字段 / qa_dependencies=None / 字段形状损坏 ⇒ 都不服务。"""
    q = "B06 旧条目：没有依赖字段的条目还能服务吗？"
    _g_row(db, q)

    # ① 旧条目：完全不带该字段（直接放进 LRU，绕过 put）
    answer_cache._cache.put("legacy", {"answer": ANSWER, "sources": []})
    assert _run(main._cache_read_deps_ok(answer_cache.get("legacy"))) is False

    # ② put 默认（qa_dependencies=None）⇒ 未知 ⇒ 不服务
    answer_cache.put("k-none", ANSWER, [])
    assert answer_cache.get("k-none")["qa_dependencies"] is None
    assert _run(main._cache_read_deps_ok(answer_cache.get("k-none"))) is False

    # ③ 形状损坏（不是 QaDependency 的元组）⇒ 复核异常 ⇒ 不服务
    answer_cache.put("k-bad", ANSWER, [], qa_dependencies=("not-a-dependency",))
    assert _run(main._cache_read_deps_ok(answer_cache.get("k-bad"))) is False


# ==================== B07：无 QA 的合法路径显式签空 ====================


def test_b07_no_qa_input_signs_empty_tuple_and_is_allowed(db, double_embeddings):
    """B07：实际 prompt 完全无 QA ⇒ 产生处签空 tuple ⇒ 依赖门允许（旧守卫仍在）。"""
    pre = {"qa_hit": None, "summary": "", "recent": []}
    deps = main._input_qa_dependencies(pre)
    assert deps == (), f"无 QA 且无未追踪历史时必须签已知空，实际 {deps!r}"
    assert _run(main._cache_write_deps_ok(deps)) is True


def test_b07b_untracked_history_cannot_sign_known_empty(db, double_embeddings):
    """B07 反面（§4.1）：有未追踪 summary/assistant 历史时**不许**签已知空 ⇒ None ⇒ 不写缓存。

    口径注记（2026-10-19 Owner 补裁，设计合同 §4.1 同步）：本用例的 `pre` 是**手工构造**的输入——
    真实链路的 `pre` 来自安全投影（`load_model_context_bootstrap`），未知/撤回 assistant 与未核验
    summary 在进入 `pre` **之前**就已被剔除 ⇒ 对真实链路签 `()` 是「投影后实际生成输入确无 QA」的
    事实真话（非洗白）；仅当投影后输入仍含未追踪内容（如本用例的手工形状）时才必须 None。
    """
    with_history = {
        "qa_hit": None,
        "summary": "",
        "recent": [{"role": "assistant", "content": "上一轮结论"}],
    }
    assert main._input_qa_dependencies(with_history) is None
    assert _run(main._cache_write_deps_ok(None)) is False
    with_summary = {"qa_hit": None, "summary": "旧的滚动摘要", "recent": []}
    assert main._input_qa_dependencies(with_summary) is None


# ==================== B08：无链 QA 可生成，但答案不进缓存 ====================


def test_b08_unlinked_qa_generation_continues_but_answer_not_cached(db, double_embeddings):
    """B08：无可靠 SQL 身份的 QA 参与生成 ⇒ 依赖为 None ⇒ 生成可继续、答案**不进**缓存。"""
    q = "B08 无链 QA：生成能继续但不能进缓存吗？"
    ks.add_qa_pair(q, ANSWER, EVIDENCE)
    hit = ks.search_qa(q)
    assert hit is not None and hit.get("qa_candidate_id") is None
    pre = {"qa_hit": hit, "summary": "", "recent": []}
    deps = main._input_qa_dependencies(pre)
    assert deps is None, "无链 QA 的依赖必须未知（None），不能假签空"
    # 生成可继续：\u3000O 门对 None 不判失效
    assert _run(main._generation_input_invalid(deps)) is False
    # 答案不进缓存：W 门对 None 拒绝写入
    assert _run(main._cache_write_deps_ok(deps)) is False


# ==================== B09：当前空 hit 不能洗掉缓存自身依赖 ====================


def test_b09_current_empty_hit_does_not_clear_cache_own_dependency(db, double_embeddings):
    """B09：当前 pre.qa_hit=None，但缓存自身依赖 G 且 G 已撤回 ⇒ 拒旧缓存。"""
    q = "B09 空 hit：当前无 QA 就能放行旧缓存吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))
    key = _warm_exact(q, dep)
    _revoke_without_clear(db, row)
    # 当前请求的 pre 完全没有 QA（qa_hit=None）——读门判的是**缓存条目自身**的依赖，不是当前 hit
    pre = {"qa_hit": None, "summary": "", "recent": []}
    assert main._input_qa_dependencies(pre) == ()
    assert _run(main._cache_read_deps_ok(answer_cache.get(key))) is False


# ==================== B10：generation 拒旧写、新写通过 ====================


def test_b10_old_generation_write_rejected_new_generation_accepted(db, double_embeddings):
    """B10：旧请求持 generation；本进程 clear 后 put ⇒ 旧写被拒、当前写通过原门可写。"""
    old_gen = answer_cache.generation()
    answer_cache.clear()
    answer_cache.put("old", ANSWER, [], qa_dependencies=(), generation=old_gen)
    assert answer_cache.get("old") is None, "旧代次写入没被拒 ⇒ LRU 不变量被打破"
    answer_cache.put("new", ANSWER, [], qa_dependencies=(), generation=answer_cache.generation())
    assert answer_cache.get("new") is not None


# ==================== B11：三个 put 生产点显式传依赖（接线面） ====================


def test_b11_put_points_pass_explicit_dependencies_via_helper(db, double_embeddings):
    """B11 接线面：三处 put 都经 `_input_qa_dependencies` 显式签发；漏传=默认 None ⇒ 不服务。

    逐点端到端（合同/轻量/旗舰 SSE）在本文件不跑（覆盖边界见报告）；这里钉住**签发/落库形状**：
    有 QA ⇒ 非空元组；无 QA ⇒ 空元组；默认（漏接线）⇒ None ⇒ 读门不服务。
    """
    q = "B11 三 put 点：接线漏传会怎样？"
    row = _g_row(db, q)

    with_qa = main._input_qa_dependencies({"qa_hit": _hit_of(q), "summary": "", "recent": []})
    assert isinstance(with_qa, tuple) and len(with_qa) == 1 and with_qa[0].candidate_id == row.id

    # 漏接线的默认形状（put 不带 qa_dependencies）⇒ None ⇒ 读门不服务
    answer_cache.put("k-default", ANSWER, [])
    assert _run(main._cache_read_deps_ok(answer_cache.get("k-default"))) is False

    # 显式传签发值 ⇒ 读门服务
    answer_cache.put("k-explicit", ANSWER, [], qa_dependencies=with_qa)
    assert _run(main._cache_read_deps_ok(answer_cache.get("k-explicit"))) is True


# ==================== B17：W 前拒绝写；W 后竞态写入下次读仍拒 ====================


def test_b17_write_before_w_rejected_after_w_read_rejects(db, double_embeddings):
    """B17：W 复核前撤回 ⇒ 拒绝写；W 通过后（竞态）即便写入，下次读仍拒旧依赖。

    不跨请求复用状态槽：读门用**新 SQL 会话**重核冻结的依赖（不是复用 capture 时那份读数）。
    """
    q = "B17 写点竞态：W 前撤回拒绝写、W 后写回下次读仍拒吗？"
    row = _g_row(db, q)
    dep = qe.capture_dependency(_hit_of(q))

    # W 前撤回 ⇒ 写门拒绝
    _revoke_without_clear(db, row)
    assert _run(main._cache_write_deps_ok((dep,))) is False, "W 前撤回仍放行写入 ⇒ B17 前段未闭合"

    # 「W 后」竞态：旧写入者把快照写进缓存（模拟既成事实）⇒ 下次读必须拒
    answer_cache.put("k-race", ANSWER, [], qa_dependencies=(dep,))
    assert _run(main._cache_read_deps_ok(answer_cache.get("k-race"))) is False
