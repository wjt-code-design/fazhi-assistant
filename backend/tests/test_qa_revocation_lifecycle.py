"""W06 特征化（撤回生命周期）：**今天没有任何一条路能让一条已收录的 QA 停止被服务**。

失效模式（全部是本文件现场跑出来的现量，不是推断）：
① 自动收录（≥0.89）先写向量集合、再写 SQL 行；把 SQL 行改成 `rejected` 只动了 SQL 一份 ⇒
   两份拷贝就此各说各话，而**两条读出口都不看 SQL**（`test_qa_approval_read_eligibility.py` 第④条已钉），
   所以"拒绝了"之后：零模型直返照样返回答案，prompt 注入照样把答案递给模型。
② 生命周期里**没有 revoked 这个状态**：`decide_candidate` 只认 approved/rejected，其它一律 ValueError
   （knowledge_service.py:450-471），而行状态保持 `approved` 不动。
③ QA 侧**没有删除入口**：本文件用 AST 穷举 `knowledge_service` 里对 `_qa_store` 的全部属性访问，
   只有 `_collection` / `add_documents` / `similarity_search_with_score` 三个——没有 delete。
   （`_collection()` 那个 delete 属**条文库**（knowledge_service.py:55 绑的是 `vectorstore`），不是 QA。）
④ 写侧非原子：SQL 提交失败 ⇒ 向量记录已经落地且无人知道（孤儿）。
⑤ 采纳不幂等：同一候选采纳两次 ⇒ 向量集合里两条。

**W06-P0（2026-10-18）**：上面①②③④⑤是 **W06-P0 之前**的特征化；写侧已改为 `create_candidate`
一律 `pending`、不写向量（旧式自动批准行只能合成直构），"提交失败仍清缓存"不变量改属 `decide_candidate`。

⇒ 出口条件里那句「批准/拒绝/撤回后，已写 QA、回答缓存及进程缓存的读取资格一致」现在**不成立**，
   「任何旧出口都不能继续返回已失效条目」也没有任何机制保证。
   要闭这一格必须先有 C03 的口径（审核来源/读取资格/撤回契约三问），所以本文件**只钉现状不改行为**。

隔离同上：临时 SQLite（`db`）＋ conftest 的临时 `CHROMA_DIR` ＋ `double_embeddings`；
不碰真实 `app.db`、不碰真实语料、不加载真权重。
"""

import ast
import inspect
import json
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import retrieval  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _hits(question: str) -> int:
    """向量集合里与该题干**逐字**相同的记录条数（临时集合，非真实语料）。"""
    data = ks._qa_store._collection.get(include=["documents"])
    return sum(1 for d in (data.get("documents") or []) if str(d).strip() == question.strip())


def _kb_has_article(monkeypatch, docs):
    """把"条文还在库里"钉成给定读数：`qa_citations_in_kb` 读 `retrieval.exact_article_lookup`，
    而直返出口历史上也读过 `main` 侧同名全局 ⇒ 两处都打，避免拦截归因到进程私有空库（假红）。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def _synthetic_auto_row(db, question: str):
    """合成一条**旧式自动收录行**——代表**旧存量**，**不由 `create_candidate` 产生**。

    W06-P0 后 `create_candidate` 一律 `pending`、不写向量 ⇒ 旧「自动收录」的可服务记录
    （`status="approved"` + `approval_source="auto_by_score_inferred"` + 显式向量链）只能直接构造：
    链以 `cand_id`/`doc_id` 写入，与 `vector_doc_id` 双向闭合（照抄 `test_qa_approval_read_eligibility.py`
    的 `_synthetic_auto_row` 形态）。
    """
    doc_id = uuid.uuid4().hex
    row = ks.QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.95,
        evidence=EVIDENCE,
        status="approved",
        approval_source="auto_by_score_inferred",
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    ks.add_qa_pair(question, ANSWER, EVIDENCE, cand_id=row.id, doc_id=doc_id)
    return row


def _pre(q: str, hit: dict) -> dict:
    """构造注入出口需要的 `pre`（形状照 `main._build_messages` 的取键，缺一个键就 KeyError）。"""
    return {
        "intent": "legal_query",
        "is_exam": False,
        "summary": "",
        "recent": [],
        "qa_hit": hit,
        "context": "",
        "user_text": q,
        "image": None,
    }


def _prompt_text(messages) -> str:
    out = []
    for m in messages:
        c = getattr(m, "content", m)
        out.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(out)


def test_reject_stops_both_read_exits_without_deleting_the_record(db, double_embeddings, monkeypatch):
    """W06-IMPL 改写（原钉 ①：SQL 说 rejected，两条出口仍服务）：

    现钉新契约——拒绝后两条语料出口都 miss，但向量记录**照旧在服务侧读得回**（形状 P「隔离不删」：
    只置资格、不删数据）。仍**保留**：status=rejected、search_qa 命中、answer 不变（这些今天也成立）。
    """
    q = "撤回生命周期甲：试用期的约定有什么上限？"
    row = _synthetic_auto_row(db, q)  # 旧存量形状：机器自动收录（approved + 链，不由 create_candidate 产生）
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])

    ks.decide_candidate(db, row.id, "rejected")
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().status == "rejected"
    # 新契约的资格位：拒绝 = 置 revoked（不是删行、不是删向量）
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().eligibility == "revoked"

    hit = ks.search_qa(q)
    assert hit is not None, "读侧根本没命中 ⇒ 后面的断言全部失去对象（本条判据空转）"
    assert hit["answer"] == ANSWER
    assert hit["qa_candidate_id"] == row.id, "向量链没闭合 ⇒ 出口无从核验状态"

    # 原钉：`== ANSWER`（直返仍服务）⇒ 现钉：miss（读出口自判 revoked）
    assert main._qa_direct_return({"rewritten": q, "qa_hit": hit}) is None
    prompt = _prompt_text(main._build_messages(_pre(q, hit)))
    # 原钉：`ANSWER in prompt` / `"此前已确认的问答" in prompt`（注入仍发生）⇒ 现钉：都不出现
    assert ANSWER not in prompt
    assert "此前已确认的问答" not in prompt


def test_revocation_is_visible_in_sql_at_the_moment_of_invalidate(db, double_embeddings, monkeypatch):
    """票 W06-FIX V1（F5）：撤回必须**提交可见之后**才清缓存——并发判据，不是「你按顺序调了吗」的断言。

    失效形状（改前现量）：`decide_candidate` 拒绝分支是 `invalidate()` → `commit()`。
    在 invalidate 之后、commit 之前那一段里，**并发请求**仍从 SQL 读到旧资格 `ok`，
    于是它把刚被撤掉的答案**写回回答缓存**（TTL 6 小时，`main.py` 的两处 `answer_cache.put`），
    「撤回即时生效」在这个窗口里被反向击穿；SQLite 单写者 + `timeout=30` 只会把窗口拉长。

    判据怎么把「并发」跑出来（可控钩子，不是顺序断言）：
    把 `retrieval.invalidate` 换成一只**并发读者替身**——它在缓存被清的那一刻
    ① 另开一条 session 读同一行的 `eligibility`（=另一个请求能看到的状态），
    ② 用**生产判据** `qa_eligibility.evaluate_revocation_state` 判这条语料还能不能被服务，
    ③ 若判据放行就**按生产写法把答案 put 回缓存**（这就是事故本身，不是它的比喻）。
    三条断言分别钉住这三步；改前 ①读到 `ok`、②放行、③缓存里重新出现已撤回答案 ⇒ 三条全红。
    顺序断言（「invalidate 的调用序号在 commit 之后」）在本文件里**不作为判据**：
    它换一种写法（先 flush 再 commit、或把 invalidate 塞进 commit 事件）就能绕过，而并发窗口照旧。
    """
    import answer_cache
    import database
    import models
    import qa_eligibility as qe

    q = "撤回并发判据：缓存被清的那一刻，另一个请求读到的是什么资格？"
    row = _synthetic_auto_row(db, q)  # 旧存量形状：可服务带链记录（不由 create_candidate 产生）
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    hit = ks.search_qa(q)
    assert hit is not None and hit["qa_candidate_id"] == row.id, "链没闭合 ⇒ 并发读者无从判状态"

    cache_key = answer_cache.make_key(q, "legal_query", "2026-08-23", ["劳动合同法|第十九条"])
    answer_cache.put(cache_key, ANSWER, [])
    assert answer_cache.get(cache_key) is not None, "预置的缓存条目没写进去 ⇒ 下面三条断言失去对象"

    seen: dict[str, object] = {}
    real_invalidate = retrieval.invalidate

    def concurrent_reader_invalidate():
        """站在 invalidate 那一刻的第二个请求：读 SQL → 跑生产判据 → 按判据决定是否写回缓存。"""
        probe = database.SessionLocal()
        try:
            r = probe.get(models.QaCandidate, row.id)
            seen["eligibility"] = None if r is None else r.eligibility
        finally:
            probe.close()
        seen["predicate_allows"] = qe.evaluate_revocation_state(hit).allow
        if seen["predicate_allows"]:
            answer_cache.put(cache_key, ANSWER, [])  # 事故本体：已撤回的答案被写回缓存
        real_invalidate()

    monkeypatch.setattr(retrieval, "invalidate", concurrent_reader_invalidate)
    ks.decide_candidate(db, row.id, "rejected")

    assert seen, "钩子根本没被调用 ⇒ 本条判据空转（先查写序改动是否把 invalidate 删了）"
    assert seen["eligibility"] == "revoked", (
        f"invalidate 时并发请求读到的仍是 {seen['eligibility']!r} ⇒ 撤回还没提交可见，"
        "窗口内的并发请求会把已撤回答案写回缓存（票 W06-FIX F5 的失效形状）"
    )
    assert seen["predicate_allows"] is False, "生产判据在 invalidate 那一刻仍放行 ⇒ 缓存清完又会被填回去"
    assert answer_cache.get(cache_key) is None, "已撤回的答案重新出现在回答缓存里 ⇒ TTL 内继续零 token 直返"


def test_control_a_rejected_candidate_that_was_never_auto_approved_is_not_served(db, double_embeddings):
    """① 的控制腿：分数在自动阈值**以下**时，拒绝路径确实没有任何东西可服务 ⇒
    上面那条放行来自"自动收录已经写了向量"，而不是来自"拒绝函数本身放行"。"""
    q = "撤回生命周期乙：始终停留在待审的候选会被服务吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.55, EVIDENCE)
    ks.decide_candidate(db, row.id, "rejected")
    assert _hits(q) == 0


def test_there_is_no_revoked_state_at_all(db, double_embeddings):
    """W06-P0 改写（旧「自动收录」契约已合法废除）：现钉**新契约正确行为**＋原判据形状。

    ① 新契约：`create_candidate(0.95)` 只入 `pending`（不再按分数自动批准），那条记录**不进向量**；
    ② 生命周期仍只有 pending/approved/rejected：想标"撤回"直接 ValueError，且原状态一字未动。
    保留原判据：`decide_candidate(..., "revoked")` 抛 ValueError（消息含 approved/rejected）、
    失败后状态不变、行不被删（`revoked` 不是状态，也没有第二个状态生产者）。
    """
    q = "撤回生命周期丙：已收录的候选能被标成 revoked 吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    assert row.status == "pending", f"高分仍被自动批准 ⇒ W06-P0 写侧未落实：status={row.status}"
    with pytest.raises(ValueError) as e:
        ks.decide_candidate(db, row.id, "revoked")
    assert "approved" in str(e.value) and "rejected" in str(e.value)
    # 「revoked」不是状态：决策被拒后行状态一字未动（仍是 pending），行照旧可查
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().status == "pending"
    assert _hits(q) == 0  # 新契约：pending 记录不进向量（旧契约此处为 1；写向量只由人工采纳产生）


def test_no_production_path_can_delete_a_written_qa_record():
    """③ QA 侧没有删除入口：按 **AST 全仓穷举**（backend 下除 tests 之外的每一只 .py）。

    为什么不是只扫 `knowledge_service` 一只文件：独立复核指出——只在一只文件里穷举时，
    在 `main.py` 加一句 `ks._qa_store.delete(...)` 本条仍会绿，那是"没有 X"最坏的假阴性形状。
    现在按 `ast.unparse(node.value).endswith("_qa_store")` 收属性访问，点号别名形式（`ks._qa_store.X`）
    也能撞到。
    正对照（同一台机器现量）：全仓 `delete/deletes` 调用 14 处、QA 侧 0 处——
    没有这半条，"0 处"会因为"扫描器根本没在找东西"而恒真。

    第二半把"确实存在 delete"钉在**条文库**那一侧：两处 delete 的接受者必须逐字是 `_collection()`
    （knowledge_service.py:55 绑的是 `vectorstore`，不是 QA 集合）。
    """
    root = Path(__file__).resolve().parents[1]
    accessed, qa_deletes, total_deletes = set(), [], 0
    for py in sorted(root.rglob("*.py")):
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and ast.unparse(node.value).endswith("_qa_store"):
                accessed.add(node.attr)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr
                in (
                    "delete",
                    "deletes",
                )
            ):
                total_deletes += 1
                if "_qa_store" in ast.unparse(node.func.value):
                    qa_deletes.append(f"{py.name}:{node.lineno}")
    assert accessed == {"_collection", "add_documents", "similarity_search_with_score"}, sorted(accessed)
    assert qa_deletes == [], qa_deletes
    assert total_deletes >= 10, f"全仓 delete 调用只数到 {total_deletes} 条 ⇒ 扫描器打空了，本条不可信"

    tree = ast.parse(inspect.getsource(ks))
    receivers = sorted(
        {
            ast.unparse(c.func.value)
            for c in ast.walk(tree)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("delete", "deletes")
        }
    )
    assert receivers == ["_collection()"], f"条文库/QA 两侧的 delete 接受者形状变了（现量 {receivers}）"
    # 功能面的同一件事在第①条里已经跑过：拒绝之后 QA 记录仍在（不删），但三条出口都不再服务它。


def test_reject_and_auto_approve_both_invalidate_the_answer_cache(db, double_embeddings, monkeypatch):
    """W06-P0 改写（旧「自动收录」契约废除——本条原测它的清缓存行为）：

    票面 :350 点名「已写 QA、**回答缓存**及进程缓存」要一起失效。新契约下**可服务的向量写入只由
    `decide_candidate` 产生**，所以这条不变量落在那两支上：
    ① `create_candidate` 一律 pending、**不写向量、不 invalidate**（无任何可服务状态改变）；
    ② `decide_candidate(approved)`（人工采纳，先写向量再提交）**调 invalidate**；
    ③ `decide_candidate(rejected)`（置资格撤回）同样**调 invalidate** ⇒ 回答缓存出口一起关。
    `invalidate` 内部延迟 import `answer_cache` 一起清（retrieval.py:765-781）——下面用**原件**真跑坐实。
    """
    import answer_cache
    import retrieval

    # 先取**原件**源码：一旦下面把 `retrieval.invalidate` 换成替身，`inspect.getsource` 读到的就是
    # 我这条测试里的 lambda。判据要看的是生产函数，不是我的替身。
    invalidate_src = inspect.getsource(retrieval.invalidate)
    assert "answer_cache" in invalidate_src, "invalidate 不再连带清回答缓存 ⇒ 下面那句因果推理失去依据"

    calls: list[str] = []
    real_invalidate = retrieval.invalidate  # 替身装好之前先把**原件**留住（下面那条真判据要用它）
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))

    q = "撤回生命周期庚：自动收录后又被拒绝，回答缓存会跟着失效吗？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    # 原钉 `calls == ["invalidate"]`（自动收录就清一次）⇒ 现钉 `[]`：
    # pending 创建不写向量、无状态变更 ⇒ 没有该清的（W06-P0 写侧未落实时这条立刻红）。
    assert calls == [], f"pending 创建就清了缓存 ⇒ 自动收录未废除：{calls}"

    calls.clear()
    ks.decide_candidate(db, row.id, "approved")
    # 人工采纳（servable 写入支）必须清一次缓存：新增可服务记录 ⇒ 旧读数要失效。
    assert calls == ["invalidate"], "人工采纳没清缓存 ⇒ 新增的可服务记录没有让旧缓存读数失效"

    calls.clear()
    ks.decide_candidate(db, row.id, "rejected")
    # 拒绝走形状 B，必须调 invalidate 连带清回答缓存（§4 项 1 的第三条出口）。本条原注释要求改写、不删。
    assert calls == ["invalidate"], "拒绝路径没清缓存 ⇒ §4 项 1 的回答缓存出口仍会命中旧答案"

    # 票 W06-FIX F9/V8：**原钉 `assert hasattr(answer_cache, "get")` ⇒ 现钉真判据，理由：恒真**。
    # `answer_cache` 是个模块对象，`hasattr(..., "get")` 在这个模块存在的任何一秒都是 True——
    # 「回答缓存的读侧入口确实存在」要用**行为**判，不是用**属性名存在**判。
    # 现钉：真的写进缓存 ⇒ 真的调**原件** invalidate ⇒ 真的读不回来。
    q_live = "撤回生命周期庚补：invalidate 真的能清掉回答缓存里那一条吗？"
    key = answer_cache.make_key(q_live, "legal_query", "2026-08-23", ["劳动合同法|第十九条"])
    answer_cache.put(key, ANSWER, [])
    hit = answer_cache.get(key) or {}
    assert hit.get("answer") == ANSWER, "写进去的条目读不回来 ⇒ 下面那条 invalidate 判据失去对象"
    real_invalidate()
    assert answer_cache.get(key) is None, "invalidate 没清掉回答缓存 ⇒ 拒绝路径的第三条出口仍然命中旧答案"


def test_sql_commit_failure_leaves_an_orphan_vector_record(db, double_embeddings, monkeypatch):
    """W06-P0 改写（旧「自动收录」契约废除）：④ 写侧非原子现在只属于 `decide_candidate`。

    新契约：`create_candidate` 一律 pending、**不写向量** ⇒ 提交失败**不会**留下孤儿。
    孤儿只可能来自 `decide_candidate(approved)`（先 `add_qa_pair` 写向量、后 `db.commit`）。
    本条两支都钉：① pending 创建提交失败 ⇒ 向量侧零记录；② 人工采纳提交失败 ⇒ 向量已落地（孤儿）。
    """
    real_commit = db.commit
    state = {"boom": False}

    def gated_commit():
        if state["boom"]:
            raise RuntimeError("模拟提交失败（连接锁死／唯一约束／进程被杀都算这一类）")
        real_commit()

    monkeypatch.setattr(db, "commit", gated_commit)

    # ── 支 1：pending 创建（不再自动收录）提交失败 ⇒ 没写向量 ⇒ 没有孤儿
    q = "撤回生命周期戊：待审创建提交失败会不会留下孤儿？"
    state["boom"] = True
    with pytest.raises(RuntimeError):
        ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    assert _hits(q) == 0, "pending 创建提交失败却留下向量记录 ⇒ 自动收录未废除（旧契约此处为 1）"
    db.rollback()
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.question == q).count() == 0

    # ── 支 2：人工采纳（先写向量再提交）提交失败 ⇒ 向量已落地、SQL 未提交 ⇒ 孤儿
    state["boom"] = False
    row = ks.create_candidate(db, "撤回生命周期戊补：人工采纳提交失败会留下孤儿吗？", ANSWER, 0.55, EVIDENCE)
    q2 = row.question
    state["boom"] = True
    with pytest.raises(RuntimeError):
        ks.decide_candidate(db, row.id, "approved")
    assert _hits(q2) == 1, "人工采纳提交失败没留下孤儿 ⇒ 本条判据的对象消失（先查写序还是写侧）"
    db.rollback()
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.id == row.id).one().status == "pending"


def test_r2_commit_failure_still_clears_the_cache_on_both_write_branches(db, double_embeddings, monkeypatch):
    """R2-F7（复核第二轮，本仓**上一轮自己引进**的新静默路径）：提交失败 ⇒ 向量已经写了，缓存却没清。

    `10d1dc0` 把 `invalidate()` 从 commit **之前**挪到之后（那一步是对的：并发读者要在缓存被清之前
    就读到新资格），代价是新增了一条失败路径：`db.commit()` 抛了 ⇒ 一行都不执行 ⇒
    向量里那条 QA 已经存在（`add_qa_pair` 先写），而进程缓存与回答缓存留着**旧**读数。
    改前无条件清，所以这条洞是本轮新挖的。

    W06-P0 改写（旧「自动收录」契约废除）：新契约下**可服务的向量写入只由 `decide_candidate` 产生** ⇒
    「提交失败仍要清缓存」这条不变量现在**只**属于人工采纳支（该支 `try/finally` 语义未改）：
    ① `create_candidate` 一律 pending、不写向量 ⇒ 提交失败无状态变更、**不该清缓存**（旧契约此处为清一次）；
    ② `decide_candidate(approved)` 提交炸 ⇒ 异常照旧上抛，但 `retrieval.invalidate()` **仍被调用**。
    用调用计数器判，不用 `hasattr`（本仓已把「属性存在」类恒真判据改写过一次，见上面 V8 那条）。
    """
    import inspect

    calls: list[str] = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))

    # ⚠️ 这里**不许**用 `monkeypatch.undo()`：本文件的 `db`/`double_embeddings` 等替身都挂在同一个
    # function 级 monkeypatch 对象上，undo 会把 `double_embeddings` 一起卸掉 ⇒ 用例转而加载真实 BGE 权重。
    # 暖缓存（本机）看不出来，冷缓存（CI 的隔离 HF_HOME）就红——2026-10-18 的纯树门 ci_exact 腿就是被这条打中的
    # （`W12-GATES-FROM-COMMIT-480193d.log`：LocalEntryNotFoundError，同批 warm 腿却全绿）。
    # 改法：把「提交要不要炸」做成一个开关，而不是撤掉整批补丁。
    real_commit = db.commit
    state = {"boom": False}

    def gated_commit():
        if state["boom"]:
            raise RuntimeError("模拟提交失败（锁／唯一约束／进程被杀都算这一类）")
        real_commit()

    monkeypatch.setattr(db, "commit", gated_commit)
    # 阳性自证（与 `conftest.double_embeddings` 同一把尺子）：替身内层此刻**仍必须在位**。
    # 写成显式 raise 而不是 assert——判据不该依赖 pytest 的断言重写或 -O。
    import rag_chain
    from tests._fake_embeddings import FakeEmbeddings

    if not isinstance(rag_chain.embeddings._inner, FakeEmbeddings):
        raise AssertionError(
            f"double_embeddings 的替身已被卸掉（内层={type(rag_chain.embeddings._inner).__name__}）"
            "⇒ 本用例会去加载真实 BGE 权重：暖缓存机器假绿，冷缓存（CI 隔离 HF_HOME）直接红"
        )

    # ── 支 1：`create_candidate` 一律 pending、不写向量 ⇒ 提交失败无状态变更、不该清缓存
    q1 = "复核R2戊：待审创建提交失败时缓存清不清？"
    state["boom"] = True
    with pytest.raises(RuntimeError):
        ks.create_candidate(db, q1, ANSWER, 0.95, EVIDENCE)
    assert calls == [], f"pending 创建提交失败却清了缓存 ⇒ 自动收录未废除：{calls}"

    # ── 支 2：`decide_candidate` 的人工采纳（先写向量再提交）——提交失败仍必须清
    calls.clear()
    state["boom"] = False
    row = ks.create_candidate(db, "复核R2戊补：人工采纳这一支提交失败呢？", ANSWER, 0.55, EVIDENCE)
    assert calls == [], f"待审分支不写向量也不该清缓存，这里却清了：{calls}（开关复原失败 ⇒ 支 2 的对照物不成立）"
    state["boom"] = True
    with pytest.raises(RuntimeError):
        ks.decide_candidate(db, row.id, "approved")
    assert calls == ["invalidate"], f"人工采纳这一支提交失败后没清缓存：{calls}"

    # 注释里那句被复核打穿的假话不许留在原地当依据（它现在**是错的**，留着比删掉更坏）
    src = inspect.getsource(ks.create_candidate) + inspect.getsource(ks.decide_candidate)
    assert "没有变更就没有该清的" not in src, "注释仍声称「提交失败就不清缓存」⇒ 那是被击穿的那句原话"


def test_r2_successful_commit_still_clears_the_cache_exactly_once(db, double_embeddings, monkeypatch):
    """R2-F7 的反对照：`try/finally` 不许把正常路改成「清两次」或「每次都清」。

    没有这条对照，上面那条判据会被一个无条件空转的 `finally` 一起骗过去（例如把 invalidate
    挪到函数最外层无条件调用 ⇒ 待审分支也清、成功分支清两遍，读数从此不能当指标）。
    """
    calls: list[str] = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: calls.append("invalidate"))

    ks.create_candidate(db, "复核R2戊再补：待审分支提交成功该不该清缓存？", ANSWER, 0.55, EVIDENCE)
    assert calls == [], f"待审分支不写向量，也不该清缓存：{calls}"

    row = ks.create_candidate(db, "复核R2戊再补：自动收录如今是不是也待审了？", ANSWER, 0.95, EVIDENCE)
    # 新契约（旧契约此处为 ["invalidate"]）：高分创建不再自动收录 ⇒ 提交成功也不清缓存
    assert calls == [], f"高分创建不再自动收录 ⇒ 提交成功也不该清缓存：{calls}"

    ks.decide_candidate(db, row.id, "approved")
    assert calls == ["invalidate"], f"人工采纳成功路径的清理次数漂了：{calls}"


def test_approving_the_same_candidate_twice_writes_two_vector_records(db, double_embeddings):
    """⑤ 采纳不幂等：`add_qa_pair` 每次都是 `add_documents`（无 ID、无 upsert），重复采纳就叠成两条。"""
    q = "撤回生命周期己：同一候选采纳两次，向量侧是一条还是两条？"
    row = ks.create_candidate(db, q, ANSWER, 0.55, EVIDENCE)
    ks.decide_candidate(db, row.id, "approved")
    assert _hits(q) == 1
    ks.decide_candidate(db, row.id, "approved")
    assert _hits(q) == 2, "写侧已经改成幂等 ⇒ 本条特征化要改写成「重复采纳只有一条」"
    # SQL 侧仍只有一行 ⇒ 两份拷贝的数量也开始不一致（这就是"两个独立状态各自判 approved"）
    assert db.query(ks.QaCandidate).filter(ks.QaCandidate.question == q).count() == 1


def test_r2_write_branch_tests_never_call_monkeypatch_undo():
    """R2-F7 用例的**形状钉子**：这两条用例里不许**调用** `monkeypatch.undo()`。

    为什么钉形状而不是只在运行时自查：本文件的替身（`db`、`double_embeddings`…）都挂在同一个
    function 级 monkeypatch 上，`undo()` 会把 `double_embeddings` 一起卸掉 ⇒ 用例转去加载真实 BGE。
    暖缓存机器上这是**假绿**，冷缓存（CI 隔离 `HF_HOME`）上它就红——2026-10-18 的纯树门 ci_exact 腿
    正是这样红的（`evidence/W12-GATES-FROM-COMMIT-480193d.log`：`LocalEntryNotFoundError`，
    同批 warm 腿却全绿；对照产物 `evidence/VERIFY-R2-F7-coldhf-after.log`）。

    走 AST 而不是子串：docstring 里就得提这件事，子串判据会被自己的注释打死（第一轮就是这么红的）。
    变异自证：把 `monkeypatch.undo()` 插回支 2 ⇒ 本条红（`evidence/VERIFY-R2-F7-mutation-undo-restores-real-model.log`）。
    """
    import ast
    import inspect

    def undo_calls(fn) -> list[int]:
        found = []
        for node in ast.walk(ast.parse(inspect.getsource(fn))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "undo"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "monkeypatch"
            ):
                found.append(node.lineno)
        return found

    targets = [
        test_r2_commit_failure_still_clears_the_cache_on_both_write_branches,
        test_r2_successful_commit_still_clears_the_cache_exactly_once,
    ]
    found = {f.__name__: undo_calls(f) for f in targets}
    assert all(not v for v in found.values()), (
        f"R2-F7 用例里出现了 monkeypatch.undo() 调用：{found}⇒ 会连带卸掉 embeddings 替身，冷缓存那条腿必红"
    )
    # 阳性对照：同一个判据必须认得出"含有该调用"的形状，否则上面那条是恒真
    sample = "def f(db, monkeypatch):" + chr(10) + "    monkeypatch.undo()" + chr(10)
    hits = [
        n.lineno
        for n in ast.walk(ast.parse(sample))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "undo"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "monkeypatch"
    ]
    assert hits, "monkeypatch.undo() 这个形状没被认出 ⇒ 上面的 not in 是假判据"


def test_revocation_reaches_an_in_flight_request_at_the_fresh_boundary(db, double_embeddings):
    """R22 残余的**动态证据**：请求**在途**时发生的撤回，必须在阶段边界被拦下。

    背景（票 W06-FIX F9/V8）：两条读出口（注入 prompt / QA 直返）用的是**请求内复用**的状态槽
    ——同一次请求只读一次 SQL；`fresh=True`（清槽新读）刻意只放在**阶段边界**（P/O）与缓存命中后的复核。
    这条分工的判据是**计数替身**（`test_qa_read_eligibility.py::test_one_sql_state_session_per_qa_bearing_request`：
    "一次请求只开 1 条状态 session"）——所以"把两处出口也改成 fresh"是**错的**，那会打红那条判据。

    但这条分工的**后果**此前只有静态论证（台账 R22 残余："在途撤回传播缺动态证据"）。本用例把它钉成动态证据：

      ① 在途：先按非 fresh 读一次 ⇒ 槽里是 `allow`（等同"产生处已判过"）；
      ② 途中撤回提交（`decide_candidate` 拒绝）；
      ③ 非 fresh 仍读到**旧槽** ⇒ 复用本身不会看见撤回（这正是必须有 fresh 边界的原因，不是缺陷）；
      ④ **fresh 边界**（生产里 `main._p_recheck` 就在"发起模型调用前"这一格）必须丢弃该 QA。

    变异自证：把 `main._p_recheck` 里的 `fresh=True` 退化成非 fresh ⇒ ④ 红（旧答案会继续进模型上下文）。
    """
    import asyncio

    import qa_eligibility as qe

    q = "在途撤回传播判据：出答之前候选被撤掉，这条 QA 还进得了模型上下文吗？"
    row = _synthetic_auto_row(db, q)
    hit = ks.search_qa(q)
    assert hit is not None and hit["qa_candidate_id"] == row.id, "链没闭合 ⇒ 下面判不了状态"

    # ① 在途（非 fresh）：填槽，等同产生处已经判过一次
    assert qe.evaluate_revocation_state(hit).allow is True

    # ② 途中撤回（另一条会话提交）
    ks.decide_candidate(db, row.id, "rejected")

    # ③ 复用语义照旧：非 fresh 仍读旧槽（若这里是 False，说明 F9 的复用前提已经变了）
    assert qe.evaluate_revocation_state(hit).allow is True, "非 fresh 应保留请求内旧读数（F9 复用的前提）"

    # ④ 阶段边界的 fresh 复核必须拦下这个在途请求
    dropped = asyncio.run(main._p_recheck(_pre(q, hit)))
    assert dropped["qa_hit"] is None, "在途撤回没有传播到阶段边界 ⇒ 已撤下的答案仍会被注入模型上下文"

    # 对照腿：fresh 直接判也要拒（否则 ④ 的绿可能只是 `_p_recheck` 没跑判据）
    assert qe.evaluate_revocation_state(hit, fresh=True).allow is False
