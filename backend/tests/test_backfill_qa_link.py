"""票 W06-BACKFILL 的验收判据 A1–A6（`backend/scripts/backfill_qa_link.py`）。

写法纪律（本仓被这些形状烧过）：
 · **每条判据都真跑**：A1 真取 sha256、A2 真分类三条合成候选、A4②/A5 真调 `main._qa_direct_return`，
   没有一条是「读代码说说」。能红的地方都在断言里，不在 docstring 里。
 · **正对照**：任何「扫出来是 0」的判据都配一条「同一台仪器在别处扫得出非 0」，
   否则扫描器瞎了也照样绿（设计卡 §11 第 4 条同款事故）。
 · **不许拿「候选集不变」当成绩**：A4② 的断言方向是「apply 之后确实少了几条」；
   「无链记录本脚本摘不掉」这一事实被写成**带原因的限制腿**，不藏。
 · 隔离：临时 SQLite（`db`）＋ conftest 的临时 `CHROMA_DIR` ＋ `double_embeddings`（确定性伪向量）；
   不碰真实 `app.db`、不碰真实语料、不加载真权重、不出网。
 · **用例之间不共用题面**：`qa_pairs` 集合是**会话级**临时目录（conftest 只按 PID 分道），
   跨用例累加。所以每只用例的题面都带自己的 tag，计划输入再按「本用例自己写进去的题面」过滤——
   否则 A3/A4 那种「计数等于几」会被上一只用例留下的记录改成恒不成立或恒成立。
"""

import ast
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import models  # noqa: E402
import retrieval  # noqa: E402
from scripts import backfill_qa_link as bf  # noqa: E402

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backfill_qa_link.py"

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _lane(db) -> tuple[Path, Path]:
    """本条判据用的临时 DB 路径与临时向量目录（conftest 已把两者隔离出真实路径）。"""
    return Path(str(db.bind.engine.url.database)), Path(os.environ["CHROMA_DIR"])


def _kb_has_article(monkeypatch, docs):
    """把「条文还在库里」钉成给定读数（两处同名全局都要打，理由见 `test_qa_revocation_lifecycle.py`）。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def _add_candidate(db, question, answer, score, *, status="approved", audit_admin=None):
    row = models.QaCandidate(question=question, answer=answer, grounded_score=score, evidence=EVIDENCE, status=status)
    db.add(row)
    db.commit()
    db.refresh(row)
    if audit_admin is not None:
        db.add(models.AuditLog(admin_id=audit_admin, action="qa.approved", target=str(row.id), detail=""))
        db.commit()
    return row


def _old_auto_row(db, question):
    """合成一条**旧式自动收录行**——代表**旧存量**，**不由 `create_candidate` 产生**。

    W06-P0 后 `create_candidate` 一律 `pending`、不写向量 ⇒ 旧「自动收录」的可服务记录只能直接构造：
    approved + `approval_source="auto_by_score_inferred"` + 显式向量链（`cand_id`/`doc_id` 双向闭合）。
    分类仍由 backfill 按**审计行/分数**判定（`classify_row`），与这一列无关 ⇒ 分数仍取 0.95。
    """
    doc_id = uuid.uuid4().hex
    row = models.QaCandidate(
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


def _plan(db_path: Path, chroma_dir: Path, only_doc_ids: set[str] | None = None):
    """在**本用例自己写进去的那些向量记录**上跑计划。

    `qa_pairs` 集合是会话级共享的（conftest 只按 PID 分道，跨用例累加），所以过滤键用 **doc id**
    而不是题面：两个用例撞同名题面时，按题面过滤会把别人写的记录一起拉进来，
    于是「孤儿 1 条／重复 1 组」这种断言会变成跑单条绿、合跑红——那是仪器的错，不是产品的错。
    doc id 要么由用例显式指定，要么从产品自己写回的 `vector_doc_id` 读。
    """
    con = bf.connect_read_only(db_path)
    try:
        candidates = bf.read_candidates(con)
        audit, null_admin = bf.read_audit_index(con)
        admins = bf.read_known_admin_ids(con)
    finally:
        con.close()
    vectors = bf.read_vector_records_readonly(chroma_dir, "qa_pairs")
    if only_doc_ids is not None:
        vectors = [r for r in vectors if str(r["id"]) in only_doc_ids]
    return bf.build_plan(candidates, vectors, audit, bf.resolve_threshold(), null_admin, admins)


def _served(question: str) -> bool:
    """真码读数：`search_qa` 命中后交给 `main._qa_direct_return`，看它到底答不答。"""
    hit = ks.search_qa(question)
    if hit is None:
        return False
    return main._qa_direct_return({"qa_hit": hit, "rewritten": question}) is not None


# ==================== A1：dry-run 不改字节 ====================
def test_a1_dry_run_changes_no_bytes_on_the_lane(db, double_embeddings, tmp_path):
    """A1：对副本 `app.db` 与 `chroma.sqlite3` 各取 sha256，dry-run 前后必须逐字相同。

    正对照（防「什么都没读也算没改」）：这一趟必须真读到东西——候选行数与向量记录数都 ≥ 1，
    且 unknown 名单非空。
    """
    tag = "甲"
    q_auto = f"A1{tag}：自动收录腿的题面？"
    q_low = f"A1{tag}：低分已批准但没人核订的题面？"
    _old_auto_row(db, q_auto)  # 旧存量形状（含显式向量链；不由 create_candidate 产生）
    _add_candidate(db, q_low, ANSWER, 0.55)
    db_path, chroma_dir = _lane(db)
    assert ks.search_qa(q_auto) is not None, "临时向量集合没落地 ⇒ 后面的对账失去对象"

    targets = [db_path, chroma_dir / "chroma.sqlite3"]
    before = {str(p): _sha(p) for p in targets}
    out = tmp_path / "a1.json"
    rc = bf.main(
        ["--db", str(db_path), "--chroma", str(chroma_dir), "--collection", "qa_pairs", "--json-out", str(out)]
    )
    assert rc == 0
    after = {str(p): _sha(p) for p in targets}
    assert before == after, "dry-run 改了字节：真实库这条路径就绝不能这么走"

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["mode"] == "dry-run"
    assert payload["counts"]["candidates_total"] == 2
    assert payload["counts"]["vector_records"] >= 1
    assert payload["unknown_list"], "unknown 名单为空 ⇒ 本条正对照没跑起来"
    # 产物里不许出现题干/答案（票面 §2 第②条）
    dumped = out.read_text(encoding="utf-8")
    for text in (q_auto, q_low, ANSWER):
        assert text not in dumped, "读数产物里漏了正文"


# ==================== A2：分类不是猜的 ====================
def test_a2_three_synthetic_candidates_get_three_different_labels(db):
    """A2：三条合成候选 ⇒ human / auto_by_score_inferred / unknown，逐字照设计卡 §5。"""
    tag = "乙"
    hum = _add_candidate(db, f"A2{tag}：有审计行但分数不够的题面？", ANSWER, 0.55, audit_admin=7)
    auto = _add_candidate(db, f"A2{tag}：无审计行高分的题面？", ANSWER, 0.95)
    low = _add_candidate(db, f"A2{tag}：无审计行低分的题面？", ANSWER, 0.5)
    db_path, chroma_dir = _lane(db)

    plan = _plan(db_path, chroma_dir, set())
    by_id = {int(u["id"]): u["classification"] for u in plan.row_updates}
    assert by_id[int(hum.id)] == "human"
    assert by_id[int(auto.id)] == "auto_by_score_inferred"
    assert by_id[int(low.id)] == "unknown"
    assert plan.counts["class:human"] == 1
    assert plan.counts["class:auto_by_score_inferred"] == 1
    assert plan.counts["class:unknown"] == 1
    # 「auto 这档不许标成 proven」是票面逐字要求
    assert "proven" not in json.dumps([u["after"] for u in plan.row_updates], ensure_ascii=False)


def test_a2_nulling_the_audit_admin_id_downgrades_human(db):
    """A2 的负控：把审计行的 `admin_id` 置 NULL ⇒ 同一行必须掉出 human（human 需要可证审批人）。

    两条降级腿都测：分数在阈值上 ⇒ `auto_by_score_inferred`；分数在阈值下 ⇒ `unknown`。
    """
    tag = "丙"
    q_high = f"A2{tag}：高分且有人批的题面？"
    q_low = f"A2{tag}：低分且有人批的题面？"
    high = _add_candidate(db, q_high, ANSWER, 0.95, audit_admin=7)
    low = _add_candidate(db, q_low, ANSWER, 0.5, audit_admin=7)
    db_path, chroma_dir = _lane(db)

    before_plan = _plan(db_path, chroma_dir, set())
    classes_before = {int(u["id"]): u["classification"] for u in before_plan.row_updates}
    assert classes_before[int(high.id)] == "human" and classes_before[int(low.id)] == "human"

    con = sqlite3.connect(db_path.as_posix())
    con.execute("update audit_logs set admin_id = null where action = 'qa.approved'")
    con.commit()
    con.close()
    db.expire_all()

    after_plan = _plan(db_path, chroma_dir, set())
    classes_after = {int(u["id"]): u["classification"] for u in after_plan.row_updates}
    assert classes_after[int(high.id)] == "auto_by_score_inferred"
    assert classes_after[int(low.id)] == "unknown"
    assert after_plan.counts.get("class:human", 0) == 0
    assert after_plan.counts["audit_rows_null_admin"] == 2, "NULL 审批人的行数没进读数 ⇒ 设计卡 §10 第③条那格又是空的"


# ==================== A3：配对只走精确 ====================
def test_a3_near_duplicate_question_does_not_pair(db, double_embeddings):
    """A3：题面差一个字（答案逐字相同）必须**不**配对；同一趟里逐字相同的那条必须配上（正对照）。"""
    tag = "丁"
    q_vec = f"A3{tag}：向量侧唯一的题面原文是什么？"
    q_near = q_vec[:-1] + "呢"  # 只差一个字
    assert q_near != q_vec
    doc_vec = "a3vec0000000000000000000000000001"
    ks.add_qa_pair(q_vec, ANSWER, EVIDENCE, doc_id=doc_vec)
    _add_candidate(db, q_near, ANSWER, 0.55)
    _add_candidate(db, q_vec, ANSWER, 0.55)
    db_path, chroma_dir = _lane(db)

    plan = _plan(db_path, chroma_dir, {doc_vec})
    exact = next(u for u in plan.row_updates if u.get("matched_doc_id"))
    near = next(u for u in plan.row_updates if not u.get("matched_doc_id") and u["has_vector"] is False)
    assert near["has_vector"] is False, "差一个字的题面被配上了 ⇒ 配对走了猜配（票面 A3 禁止）"
    assert exact["has_vector"] is True, "逐字相同都没配上 ⇒ 正对照失效，上一条断言就成了空的"
    assert plan.counts["vector_records"] == 1
    assert plan.counts["matched_pairs"] == 1
    assert plan.counts["unmatched_approved"] == 1
    assert plan.counts["orphan_records"] == 0, "这一组在 SQL 里有逐字相同的行 ⇒ 不该被算成孤儿"
    flagged = sorted(int(u["id"]) for u in plan.unknown_list if not u["has_vector"])
    assert len(flagged) == 1


def test_a3_no_fuzzy_matching_entry_point_exists():
    """A3 的第二条腿：脚本里**没有**任何相似度/模糊配对入口（AST 穷举名字与调用）。

    正对照：同一台仪器在产品代码里扫得到相似度调用（`knowledge_service` 的
    `similarity_search_with_score`），否则「脚本 0 处」会因为仪器瞎了而恒真。
    """
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    banned = {"SequenceMatcher", "get_close_matches", "difflib", "similar", "similarity", "fuzzy", "ratio"}
    assert not (names & banned), f"配对里出现了模糊匹配入口：{sorted(names & banned)}"
    assert not (attrs & banned), f"配对里出现了模糊匹配调用：{sorted(attrs & banned)}"

    ks_src = Path(ks.__file__).read_text(encoding="utf-8")
    ks_attrs = {n.attr for n in ast.walk(ast.parse(ks_src)) if isinstance(n, ast.Attribute)}
    assert "similarity_search_with_score" in ks_attrs, "正对照失效：这台仪器连真码里的相似度调用都扫不到"


# ==================== A4：孤儿与重复分别计数，且没有删向量这条路径 ====================
def test_a4_no_vector_delete_call_site_in_the_script_with_positive_control():
    """A4①：本脚本任何代码路径都不调向量删除入口——AST 穷举（带正对照）。

    解释「同一棵树里为什么本来就没有删点」：脚本对向量目录**只**开 `sqlite3 ...?mode=ro`，
    一次都不 import `chromadb`/`langchain_chroma`，也从不碰 `_qa_store` ⇒ 拿不到集合句柄，
    结构上就不存在 `.delete()` 的调点（不是「找到了但没调用」）。
    正对照：同一台仪器扫 `knowledge_service.py` 必须扫得到 delete 调点（条文库那两处），
    否则「本脚本 0 处」不算读数。
    """

    def delete_calls(source: str) -> list[str]:
        out = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"delete", "delete_documents", "deletes"}:
                    out.append(ast.unparse(node.func))
        return out

    script_src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert delete_calls(script_src) == [], "脚本里出现了向量删除调点"

    imported: set[str] = set()
    for node in ast.walk(ast.parse(script_src)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "chromadb" not in imported and "langchain_chroma" not in imported, "脚本自己开了 chroma 句柄 ⇒ 只读红线破了"
    attrs = {n.attr for n in ast.walk(ast.parse(script_src)) if isinstance(n, ast.Attribute)}
    assert "_qa_store" not in attrs, "脚本碰了 _qa_store ⇒ 结构上就有了删点的入口"

    ks_deletes = delete_calls(Path(ks.__file__).read_text(encoding="utf-8"))
    assert ks_deletes, "正对照失效：这台仪器连产品代码里的条文库删除都扫不出来，上面的 0 不算读数"


def test_a4_orphans_and_duplicates_are_counted_separately(db, double_embeddings):
    """A4：孤儿（向量有 SQL 无）与重复（同 (q,a) 多条向量）**各自计数、互不合并**，且都走登记不删。"""
    tag = "戊"
    q_orphan = f"A4{tag}：向量有 SQL 无的孤儿题面？"
    q_dup = f"A4{tag}：同一条题面写了两遍的题面？"
    d_orph, d_dup1, d_dup2 = (
        "a4orph0000000000000000000000000001",
        "a4dup000000000000000000000000000001",
        "a4dup000000000000000000000000000002",
    )
    ks.add_qa_pair(q_orphan, ANSWER, EVIDENCE, doc_id=d_orph)
    _add_candidate(db, q_dup, ANSWER, 0.95)
    ks.add_qa_pair(q_dup, ANSWER, EVIDENCE, doc_id=d_dup1)
    ks.add_qa_pair(q_dup, ANSWER, EVIDENCE, doc_id=d_dup2)
    db_path, chroma_dir = _lane(db)

    plan = _plan(db_path, chroma_dir, {d_orph, d_dup1, d_dup2})
    assert plan.counts["vector_records"] == 3
    assert plan.counts["orphan_records"] == 1
    assert plan.counts["duplicate_groups"] == 1
    assert plan.counts["superseded_records"] == 1
    kinds = [n["register_kind"] for n in plan.new_rows]
    assert kinds.count("orphan") == 1 and kinds.count("superseded") == 1
    assert plan.orphans[0]["doc_id"] != plan.superseded[0]["doc_id"]
    assert plan.orphans[0]["has_chain"] is False
    # 隔离落点（修订三）：孤儿登记成 unknown/quarantined；重复的非保留条登记成 unknown/revoked
    orphan_row = next(n for n in plan.new_rows if n["register_kind"] == "orphan")
    superseded_row = next(n for n in plan.new_rows if n["register_kind"] == "superseded")
    assert (orphan_row["approval_source"], orphan_row["eligibility"]) == ("unknown", "quarantined")
    assert (superseded_row["approval_source"], superseded_row["eligibility"]) == ("unknown", "revoked")
    dumped = json.dumps(bf.plan_json(plan), ensure_ascii=False)
    for text in (q_orphan, q_dup, ANSWER):
        assert text not in dumped, "产物里漏了正文"


def test_a4_registered_rows_are_written_at_all_on_the_copy(db, double_embeddings, tmp_path):
    """设计卡 §7 的「迁移幂等」那条：同一份副本连跑两次 apply ⇒ 第二次分类计数与第一次**逐字相同**。

    幂等靠内容键（`vector_doc_id` 已登记过就不再插），不靠预分配 id。
    这条也顺带证「登记行真的写进了库」——只出计划不落库的写法在这里会红。
    """
    tag = "丑"
    q_orphan = f"A幂等{tag}：连跑两次会不会插重？"
    q_other = f"A幂等{tag}：第二条孤儿记录？"
    d1, d2 = "idemorph00000000000000000000000001", "idemorph00000000000000000000000002"
    ks.add_qa_pair(q_orphan, ANSWER, EVIDENCE, doc_id=d1)
    ks.add_qa_pair(q_other, ANSWER, EVIDENCE, doc_id=d2)
    db_path, chroma_dir = _lane(db)

    def state() -> list[tuple]:
        con = sqlite3.connect(db_path.as_posix())
        rows = [
            tuple(r)
            for r in con.execute(
                "select id, status, approval_source, eligibility, vector_doc_id from qa_candidates order by id"
            )
        ]
        con.close()
        return rows

    def counts_after_apply() -> tuple[dict, dict]:
        plan = _plan(db_path, chroma_dir, {d1, d2})
        stats = bf.apply_plan(db_path, plan, tmp_path / f"snap-{time.time_ns()}.json")
        return plan.counts, stats

    first, stats1 = counts_after_apply()
    assert first["orphan_records"] == 2, "两条孤儿都没登记出来 ⇒ 第二次的「不重复」没有对照物"
    after1 = state()
    assert len(after1) == 2, f"登记行没落库：期望 2 行，实际 {len(after1)}"
    assert int(stats1["inserted_rows"]) == 2

    second, stats2 = counts_after_apply()
    after2 = state()
    # 幂等的正确说法是**写面为空＋库是定点**，不是「每个计数一模一样」：
    # 第一次登记出来的两行在第二次**已经是候选**（candidates_total 由 0 变 2、orphan_records 归 0），
    # 这恰恰是登记成功了的样子。定点判据是：行数与每行的资格列逐字不变、第二次一条都不再写。
    assert after2 == after1, "第二次 apply 改了行状态 ⇒ 不是定点（前后两批行状态见上）"
    assert int(stats2["inserted_rows"]) == 0, "第二次又插了登记行 ⇒ 登记不幂等"
    assert int(stats2["updated_rows"]) == 0, "第二次又改了既有行 ⇒ 分类没收敛"
    assert second["registered_rows_to_insert"] == 0
    assert second["class:unknown"] == 2, "登记行在第二次被读成别的档 ⇒ 分类与落库不一致"


def test_a4_emitted_rows_carry_only_the_whitelist_keys(db, double_embeddings):
    """落盘形状：登记行往外写**只**带标识与资格列。

    这条是现量抓出来的：第一轮真库读数里 `evidence`（法名＋条号）跟着登记行进过 JSON——
    它既不是题干也不是答案，黑名单式「摘掉 question/answer」就漏了它。
    票面 §2 第②条要的是「只有 id ＋ 一条数 ＋ 一个布尔」，所以改成白名单投影并钉住。
    """
    tag = "寅"
    q = f"A形状{tag}：登记行落盘时带不带语料内容？"
    doc = "shapeorph00000000000000000000000001"
    ks.add_qa_pair(
        q,
        json.dumps([{"source": "消费者权益保护法", "article": "第二十五条"}], ensure_ascii=False),
        EVIDENCE,
        doc_id=doc,
    )
    db_path, chroma_dir = _lane(db)
    plan = _plan(db_path, chroma_dir, {doc})
    emitted = json.dumps(bf.plan_json(plan), ensure_ascii=False)
    assert "消费者权益保护法" not in emitted, "语料内容（evidence）跟着登记行落了盘"
    assert q not in emitted
    for row in bf.plan_json(plan)["registered_rows"]:
        assert set(row) <= set(bf._EMIT_KEYS), f"登记行写出了白名单外的键：{sorted(set(row) - set(bf._EMIT_KEYS))}"


def test_a4_two_apply_actually_strips_the_classified_linked_rows(db, double_embeddings, monkeypatch):
    """A4②·真行为腿（不是 AST）：apply 之后**带链**记录的直返候选集条数真的少。

    两条腿一起跑，方向不许反：
     · 人工采纳留下的带链记录（无审计行、分数不够阈值 ⇒ 判 unknown）apply 后必须 miss；
     · 自动收录留下的带链记录（⇒ 判 auto_by_score_inferred）apply 后**仍**命中——
       少了这一条对照，「全部摘光」也会让上一条看起来对，那正是假绿。
    """
    tag = "己"
    q_auto = f"A4②{tag}：自动收录的带链记录？"
    q_hum = f"A4②{tag}：人工采纳但没留审计行的带链记录？"
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    auto = _old_auto_row(db, q_auto)  # 旧存量形状（含显式向量链；不由 create_candidate 产生）
    hum = _add_candidate(db, q_hum, ANSWER, 0.55)
    ks.decide_candidate(db, hum.id, "approved", reviewed_by=7)  # 写向量时带上 cand_id ⇒ 有链
    db_path, chroma_dir = _lane(db)
    own_docs = {str(auto.vector_doc_id), str(hum.vector_doc_id)}
    assert all(d != "None" for d in own_docs), "产品没把 vector_doc_id 写回 ⇒ 这条腿的过滤键不存在"

    hit = ks.search_qa(q_hum)
    assert hit is not None and hit["qa_candidate_id"] == hum.id, "链没闭合 ⇒ 状态轴对这条不适用，本条判据失去对象"
    assert _served(q_auto) and _served(q_hum), "回填前两条都该在候选集里 ⇒ 后面的差值断言没有对象"

    plan = _plan(db_path, chroma_dir, own_docs)
    stats = bf.apply_plan(db_path, plan, db_path.parent / "a4-snapshot.json")
    assert stats["updated_rows"] >= 1

    assert not _served(q_hum), "apply 之后已标 unknown/quarantined 的带链记录仍被直返 ⇒ 隔离没落到读侧"
    assert _served(q_auto), "auto_by_score_inferred 被一起摘掉了 ⇒ 判据把两档合成了一档"


def test_a4_two_unlinked_records_are_outside_the_scripts_reach(db, double_embeddings, monkeypatch):
    """A4②·限制腿（写明谁去摘）：无链记录（真库存量的形状）**不是本脚本能摘的**。

    本脚本对向量目录只读、不给记录写 metadata ⇒ 无链记录进不了状态轴。摘它的是修订三 gate③
    （生产面，另派）。gate③ 已落地时这条必须断言「无链记录被直返拒」；还没落地时**带原因跳过**，
    既不假装已经隔离，也不拿「候选集不变」当成绩。
    """
    tag = "庚"
    q_orphan = f"A4②{tag}：无链也没 SQL 行的孤儿记录？"
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    doc_orph = "a4borph00000000000000000000000001"
    ks.add_qa_pair(q_orphan, ANSWER, EVIDENCE, doc_id=doc_orph)

    hit = ks.search_qa(q_orphan)
    assert hit is not None and hit["qa_candidate_id"] is None, "正对照失效：这条记录不是无链形状"
    gate3_in_effect = main._qa_direct_return({"qa_hit": hit, "rewritten": q_orphan}) is None
    # 同一台仪器两个入口要回同一个答案（F3 的口径）：`_served` 为真 ⇔ gate③ 没把无链记录拦下
    assert _served(q_orphan) is (not gate3_in_effect)

    db_path, chroma_dir = _lane(db)
    before = _sha(chroma_dir / "chroma.sqlite3")
    plan = _plan(db_path, chroma_dir, {doc_orph})
    assert plan.counts["orphan_records"] == 1
    bf.apply_plan(db_path, plan, db_path.parent / "a4b-snapshot.json")
    assert _sha(chroma_dir / "chroma.sqlite3") == before, "apply 之后向量目录字节变了 ⇒ 只读红线破了"

    if not gate3_in_effect:
        pytest.skip(
            "gate③（无链⇒不进直返候选集）尚未进本树（当前 head 的 `_state_axis` 对无链返回「不适用」）。"
            "本脚本摘不掉无链记录这条已由上面的字节断言与跳过原因写实；真库的无链面读数见 "
            "evidence/W06-BACKFILL-CLASSIFY-counts-real-dryrun.json 的 vector_records_unlinked。"
        )
    assert not _served(q_orphan), "gate③ 已落地却仍直返无链记录 ⇒ 孤儿这一类漏隔离"


# ==================== A5：回滚可证 ====================
def test_a5_restore_from_snapshot_returns_the_same_direct_return_set(db, double_embeddings, monkeypatch):
    """A5：apply 让候选集变小 ⇒ 按快照把资格改回 `ok` 后**候选集大小回到原值**（真跑，不是声明）。

    回退不依赖删除：整趟跑完向量记录条数一条都不能少（`count()` 前后相等）。
    """
    tag = "辛"
    q_auto = f"A5{tag}：自动收录腿的候选？"
    q_hum = f"A5{tag}：人工采纳但没留审计行的候选？"
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    auto = _old_auto_row(db, q_auto)  # 旧存量形状（含显式向量链；不由 create_candidate 产生）
    hum = _add_candidate(db, q_hum, ANSWER, 0.55)
    ks.decide_candidate(db, hum.id, "approved", reviewed_by=7)
    db_path, chroma_dir = _lane(db)
    own_docs = {str(auto.vector_doc_id), str(hum.vector_doc_id)}
    qa_count_before = ks._qa_store._collection.count()
    questions = [q_auto, q_hum]

    def size() -> int:
        return sum(1 for q in questions if _served(q))

    before_size = size()
    assert before_size == 2, "回填前候选集不是 2 条 ⇒ 下面的差值断言失去对象"

    plan = _plan(db_path, chroma_dir, own_docs)
    snap = db_path.parent / "a5-snapshot.json"
    bf.apply_plan(db_path, plan, snap)
    assert size() < before_size, "apply 没让候选集变小 ⇒ 这条回滚判据在测一个空差"

    out = bf.restore_from_snapshot(db_path, snap)
    assert out["restored_rows"] >= 1
    assert size() == before_size, "回退后候选集大小没回到原值 ⇒ A5 不成立"
    assert ks._qa_store._collection.count() == qa_count_before, "整趟跑完向量记录少了 ⇒ 有代码路径删了语料"

    snap_text = snap.read_text(encoding="utf-8")
    assert json.loads(snap_text)["before_after"], "快照是空的 ⇒ 回退依据不存在"
    assert q_hum not in snap_text and ANSWER not in snap_text, "快照里落了题干/答案 ⇒ §2 第②条的口径没守到快照上"


# ==================== A6：拒绝守卫 ====================
def _fake_protected_lane(tmp_path: Path) -> tuple[Path, Path]:
    """造一个**形状上**就是 `backend/app.db` ＋ `backend/chroma_db` 的目录（不是真实库，守卫照样该拦）。"""
    backend = tmp_path / "backend"
    backend.mkdir(parents=True, exist_ok=True)
    db = backend / "app.db"
    db.write_bytes(b"shape-only-not-the-real-db")
    chroma = backend / "chroma_db"
    chroma.mkdir(exist_ok=True)
    return db, chroma


@pytest.mark.parametrize("flag", ["--apply", "--restore", "--measure-direct-return"])
def test_a6_write_modes_refuse_protected_shapes_before_touching_anything(tmp_path, flag):
    """A6：写模式指向含 `backend/app.db`／`backend/chroma_db` 的路径 ⇒ **动手之前**非零退出、字节没碰。"""
    db, chroma = _fake_protected_lane(tmp_path)
    db_hash = _sha(db)
    argv = [flag, "--db", str(db), "--chroma", str(chroma)]
    if flag == "--restore":
        argv += ["--snapshot", str(tmp_path / "nope.json")]
    if flag == "--measure-direct-return":
        argv += ["--questions", str(tmp_path / "nope.json")]

    rc = bf.main(argv)
    assert rc != 0, f"{flag} 打受保护形状却返回 0 ⇒ 守卫没生效"
    assert _sha(db) == db_hash, "拒绝之前已经碰过库文件"
    assert not (tmp_path / "nope.json").exists()
    assert list(chroma.iterdir()) == [], "拒绝之前向量目录里已被写出东西"


def test_a6_refuses_the_live_default_paths_of_this_tree(tmp_path):
    """A6 的真形状腿：`--apply` 打**本树的**默认目标（`backend/app.db` ＋ `backend/chroma_db`）也必须拒。

    这条同时钉住「守卫的默认值没被人挪走」——它用的就是脚本自己的 `DEFAULT_DB`/`DEFAULT_CHROMA`。
    """
    db_hash = _sha(bf.DEFAULT_DB) if bf.DEFAULT_DB.exists() else None
    rc = bf.main(
        [
            "--apply",
            "--db",
            str(bf.DEFAULT_DB),
            "--chroma",
            str(bf.DEFAULT_CHROMA),
            "--snapshot",
            str(tmp_path / "s.json"),
        ]
    )
    assert rc != 0
    if db_hash is not None:
        assert _sha(bf.DEFAULT_DB) == db_hash, "被拒之前已经改过本树 app.db 的字节"
    assert not (tmp_path / "s.json").exists()


def test_a6_allows_a_copy_that_keeps_the_production_dir_name(tmp_path):
    """A6 的另一半（守卫必须**可执行**）：副本目录照生产形状命名（`…/lane/chroma_db`）时必须放行。

    为什么这条必须存在：上一条只证「守卫会拦」。拦得太宽（凡是路径里出现过 `chroma_db` 就拒）
    会把**所有副本**一起拦掉 ⇒ `--apply` 在这台机器上永远不可执行，A5 与读数③就没有真跑过的那条腿。
    拦得住与放得开是同一张判据的两条腿，缺一条就是假绿。
    """
    lane = tmp_path / "lane"
    (lane / "chroma_db").mkdir(parents=True)
    db = lane / "app-copy.db"
    seed = sqlite3.connect(db.as_posix())
    seed.execute("create table qa_candidates (id INTEGER PRIMARY KEY, question TEXT, answer TEXT, status TEXT)")
    seed.commit()
    seed.close()
    assert bf.protected_targets(str(db), str(lane / "chroma_db")) == []

    stats = bf.apply_plan(db, bf.Plan(counts={}, new_rows=[]), lane / "snap.json")  # 非受保护 ⇒ 不该抛 RefusalError
    assert stats["inserted_rows"] == 0


def test_a6_write_mode_requires_both_explicit_targets(tmp_path):
    """A6 的补齐面：写模式少一个显式目标就拒（默认值指向真实路径这件事本身不该被依赖）。"""
    lane = tmp_path / "lane.db"
    lane.write_bytes(b"x")
    assert bf.main(["--apply", "--db", str(lane)]) != 0
    assert lane.read_bytes() == b"x", "被拒之前已经动过目标文件"


# ==================== 仪器自证：只读 SQL 读向量是不是真读得对 ====================
def test_vector_reader_returns_the_very_doc_ids_the_product_wrote(db, double_embeddings):
    """只读 SQL 读出的 doc id／正文／metadata 必须与产品写进去的**逐字相同**（非空正对照）。

    为什么这条必须存在：A3/A4 的计数与读数③的记录级腿全建立在这只读取器上；
    它在空集合上返回 `[]` ⇒ 所有计数都「对」，那是最典型的假绿来源。
    """
    tag = "壬"
    q = f"A自证{tag}：产品写进去的 doc id 能不能原样读回？"
    doc_id = "cafeb0ba-dead-beef-0000-0000000000a1"
    ks.add_qa_pair(q, ANSWER, EVIDENCE, basis="2026-09-20", doc_id=doc_id)
    _, chroma_dir = _lane(db)
    recs = bf.read_vector_records_readonly(chroma_dir, "qa_pairs")
    mine = next((r for r in recs if r["id"] == doc_id), None)
    assert mine is not None, f"只读 SQL 没读到产品刚写进去的 doc id（读到 {len(recs)} 条）"
    assert mine["document"] == q
    assert mine["metadata"]["answer"] == ANSWER
    assert mine["metadata"]["law_as_of_basis"] == "2026-09-20"
    assert mine["metadata"]["origin"] == "qa"
    assert mine["metadata"].get("qa_candidate_id") is None, "没传 cand_id 却读出了链 ⇒ 读取器在编字段"


def test_record_level_hit_shape_carries_every_gate_input(db, double_embeddings):
    """记录级腿的 hit 形状必须与 `search_qa` 的返回**键集**逐字相同（少一个键就绕过一道门）。"""
    tag = "癸"
    q = f"A自证{tag}：记录级 hit 的键集与真读取器一致吗？"
    doc_id = "cafeb0ba-dead-beef-0000-0000000000a2"
    ks.add_qa_pair(q, ANSWER, EVIDENCE, basis="2026-09-20", doc_id=doc_id)
    real = ks.search_qa(q)
    assert real is not None, "search_qa 没命中 ⇒ 键集对照失去对象"
    _, chroma_dir = _lane(db)
    rec = next(r for r in bf.read_vector_records_readonly(chroma_dir, "qa_pairs") if r["id"] == doc_id)
    assert set(bf.hit_from_record(rec)) == set(real), "键集分叉 ⇒ 记录级读数绕过了某道门"


def test_script_emits_no_new_log_keys():
    """本票没往 `observability._ACCOUNT_FIELDS` 加键：脚本根本不用 `extra=` 结构化日志。

    正对照：同一台 AST 仪器在 `qa_eligibility.py` 里扫得到 `extra=`，否则「脚本 0 处」是仪器瞎了。
    """
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    extras = [
        kw.arg for node in ast.walk(tree) if isinstance(node, ast.Call) for kw in node.keywords if kw.arg == "extra"
    ]
    assert extras == [], "脚本新增了结构化日志键却没在册子里 ⇒ 会被 JSON formatter 静默丢弃"

    import qa_eligibility as qe

    qe_extras = [
        kw.arg
        for node in ast.walk(ast.parse(Path(qe.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "extra"
    ]
    assert qe_extras, "正对照失效：这台仪器连在册的 extra= 都扫不到"


def test_registered_rows_never_preassign_an_id(db, double_embeddings, monkeypatch):
    """Owner 10-18 的红线：登记行不许 `id=max(id)+1`、不许 `INSERT OR IGNORE`（会静默覆盖既有行）。

    这条是**真跑**的：先埋一条 id 很大的行占住号段，再让脚本插登记行，
    断言 ① 既有行一条没被覆盖（内容与条数都在）、② 新行拿到的 id 由 SQLite 自己发。
    """
    tag = "子"
    q_orphan = f"A自证{tag}：埋了大号行之后还能不能安全登记？"
    doc_id_orph = "idshapeorph00000000000000000001"
    ks.add_qa_pair(q_orphan, ANSWER, EVIDENCE, doc_id=doc_id_orph)
    keeper = _add_candidate(db, f"A自证{tag}：占住号段的既有行？", ANSWER, 0.95, status="pending")
    db_path, chroma_dir = _lane(db)

    con = sqlite3.connect(db_path.as_posix())
    con.execute("update qa_candidates set id = 900000 where id = ?", (keeper.id,))
    con.commit()
    con.close()
    db.expire_all()

    plan = _plan(db_path, chroma_dir, {doc_id_orph})
    assert plan.counts["orphan_records"] == 1
    stats = bf.apply_plan(db_path, plan, db_path.parent / "ids-snapshot.json")
    assert stats["inserted_rows"] == 1

    con = sqlite3.connect(db_path.as_posix())
    con.row_factory = sqlite3.Row
    rows = {int(r["id"]): r["question"] for r in con.execute("select id, question from qa_candidates")}
    con.close()
    assert 900000 in rows, "占位行被覆盖了 ⇒ 脚本在预分配 id 上撞了号"
    assert rows[900000] == f"A自证{tag}：占住号段的既有行？", "既有行的内容被改了"
    assert len(rows) == 2, "行数不对：既有行没保住，或登记行插重了"
    new_id = [i for i in rows if i != 900000]
    assert len(new_id) == 1, f"登记行没拿到自己的行身份：{sorted(rows)}"

    # 只看**代码里的 SQL 字面量**，不看注释/文档（拿全文小写匹配会被自家注释绊倒，那是一条假红）
    sql_literals = [
        str(node.value).lower()
        for node in ast.walk(ast.parse(SCRIPT_PATH.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "insert into qa_candidates" in node.value.lower()
    ]
    assert sql_literals, "正对照失效：没扫到 INSERT 语句本体"
    assert all("or ignore" not in s for s in sql_literals), (
        "登记走了 INSERT OR IGNORE ⇒ 撞号时静默吞掉，既有行的状态没人知道"
    )
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "lastrowid" in src, "登记行没取回 SQLite 发的 id ⇒ 快照指不回它登记的是哪条记录"
    assert 'payload["id"]' not in src, "脚本自己往 INSERT 里塞 id ⇒ 又回到 max(id)+1 那形状"
