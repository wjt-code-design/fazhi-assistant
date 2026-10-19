"""票 C20（形状①）：读侧按**向量 doc id** 回查候选链——把已签的 C03=P 真正接上。

本轮实测钉住的事实（不是猜测）：读出口拿资格靠 `search_qa` 把向量 metadata 里的 `qa_candidate_id`
带出来（`knowledge_service.py:420`），而现网 `qa_pairs` 279 条记录 **0 条带这个键**；回填脚本按票面
红线只写 SQL ⇒ 同一批题面在"未回填"与"已 apply"两份生产等价副本上直返命中逐字相同
（`evidence/W06-BACKFILL-measure-{before,after}-corpus.json`：277 → 277，两次 `linked` 都是 0）。
⇒ Owner 已签的那句"未核订存量退出直返与注入"停在半截。

本票的改法：链的**权威存放处改成 SQL**（`qa_candidates.vector_doc_id`），向量 metadata 那份降级成快路径
——metadata 有链就用它，没有就按 doc id 回查一次。写侧一行没动、向量字节一行没动 ⇒ 回退＝撤掉这半截回查。

先红后绿：`test_sql_only_chain_makes_unknown_provenance_exit_direct_return` 在修之前必须是红的，
而且红在那条**行为**断言上（今天它会直返），不是红在"函数不存在"。
"""

import json
import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import main  # noqa: E402
import qa_eligibility as qe  # noqa: E402
import retrieval  # noqa: E402

EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
ANSWER = (
    "《劳动合同法》第十九条对试用期上限作了分层规定：合同期限三个月以上不满一年的，试用期不得超过一个月；"
    "同一用人单位与同一劳动者只能约定一次试用期。"
)

Q_UNKNOWN = "C20甲：向量没链、SQL 那行来源未知，还该不该被直返？"
Q_HUMAN = "C20乙：同样没有 metadata 链，但 SQL 那行是人工核订过的呢？"
Q_SEED = "C20丙：两侧都没有链的种子语料，还按旧口径服务吗？"
DOC_UNKNOWN = "c20unknownrow0000000000000000000001"
DOC_HUMAN = "c20humanrow000000000000000000000001"
DOC_SEED = "c20seedrow00000000000000000000000001"


def _kb_has_article(monkeypatch, docs):
    """与邻面同一打桩口径：时效判据读 `retrieval.exact_article_lookup`，直返历史上也读过 main 侧同名全局。"""
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art: docs)
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art: docs)


def _pre(q: str, hit) -> dict:
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": q,
        "user_text": q,
        "summary": "",
        "qa_hit": hit,
        "context": "",
        "sources": [],
        "image_rel": None,
        "thumb_rel": None,
        "is_exam": False,
        "has_options": False,
        "contract_data": None,
    }


def _seed_vector_without_chain(question: str, doc_id: str):
    """写一条**没有候选链**的向量记录——种子/生成脚本今天的真实形状（`add_qa_pair` 不传 cand_id）。"""
    ks.add_qa_pair(question, ANSWER, EVIDENCE, doc_id=doc_id)


def _attach_sql_row(db, question: str, doc_id: str, *, approval_source: str):
    """造一条 approved 候选，只把链留在 **SQL 这一侧**（`vector_doc_id`），向量 metadata 里没有。"""
    row = ks.QaCandidate(
        question=question,
        answer=ANSWER,
        grounded_score=0.95,
        evidence=EVIDENCE,
        status="approved",
        approval_source=approval_source,
        eligibility="ok",
        vector_doc_id=doc_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ==================== ①主判据：SQL-only 链 + 未知来源 ⇒ 退出直返（修前必红） ====================


def test_sql_only_chain_makes_unknown_provenance_exit_direct_return(db, double_embeddings, monkeypatch):
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    _seed_vector_without_chain(Q_UNKNOWN, DOC_UNKNOWN)
    _attach_sql_row(db, Q_UNKNOWN, DOC_UNKNOWN, approval_source="unknown")

    hit = ks.search_qa(Q_UNKNOWN)
    assert hit is not None, "search_qa 读不回这条 ⇒ 本判据没有对象"
    assert main._qa_direct_return(_pre(Q_UNKNOWN, hit)) is None, (
        "SQL 那行是「来源未知」却仍被直返 ⇒ C03=P 的『未核订存量退出直返』还没发生（本票要修的就是这一格）"
    )
    # 链的解析必须发生在判据内部，不许靠给 DTO 加新键（加键会打穿「qa_hit 与手搓 dict 相等」那一族接缝判据）
    assert "vector_doc_id" not in hit and "qa_candidate_id_resolved" not in hit, f"DTO 被加键污染：{sorted(hit)}"
    assert qe.resolve_candidate_id(hit) is not None, "上面那条 None 是空跑出来的 ⇒ 回查其实没解析到候选 id"


# ==================== ②反对照：可证来源的存量不许被回查一起砍掉 ====================


def test_control_sql_only_chain_with_human_row_still_serves(db, double_embeddings, monkeypatch):
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    _seed_vector_without_chain(Q_HUMAN, DOC_HUMAN)
    _attach_sql_row(db, Q_HUMAN, DOC_HUMAN, approval_source="human")

    hit = ks.search_qa(Q_HUMAN)
    assert hit is not None
    assert main._qa_direct_return(_pre(Q_HUMAN, hit)) == ANSWER, (
        "人工核订过的存量语料也被撤下 ⇒ 回查被写成了「没有 metadata 链就一律拒」，那不是 C03=P 的口径"
    )


def test_control_vector_with_no_sql_row_defers_to_provenance_leg(db, double_embeddings, monkeypatch):
    """两侧都无链＝真种子形状 ⇒ 解析不到候选就**不判状态轴**（那条放行面被两只既有对照腿钉着）。"""
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    _seed_vector_without_chain(Q_SEED, DOC_SEED)

    hit = ks.search_qa(Q_SEED)
    assert hit is not None
    assert qe.resolve_candidate_id(hit) is None, "SQL 里没有这行却解析出了 id ⇒ 回查在乱配"
    assert qe.evaluate_revocation_state(hit).allow is True, (
        "无链记录被状态轴拦下 ⇒ 打掉了『无链⇒按来源/时效判定』的放行面"
    )


# ==================== ③成本判据：同一条 hit 只发一条回查 SELECT（三出口共用） ====================


def test_resolution_is_memoized_one_select_per_hit(db, double_embeddings, monkeypatch):
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    _seed_vector_without_chain(Q_UNKNOWN, DOC_UNKNOWN)
    _attach_sql_row(db, Q_UNKNOWN, DOC_UNKNOWN, approval_source="unknown")
    hit = ks.search_qa(Q_UNKNOWN)

    calls = {"n": 0}
    real = qe._select_candidate_id_by_doc_id

    def counting(doc_id):
        calls["n"] += 1
        return real(doc_id)

    monkeypatch.setattr(qe, "_select_candidate_id_by_doc_id", counting)
    for _ in range(3):  # 直返／prompt 注入／回答缓存复核三处各判一次
        qe.evaluate_revocation_state(hit)
    assert calls["n"] <= 1, f"同一条 hit 发了 {calls['n']} 次回查 SELECT ⇒ N+1（每个问题都多跑几次全表/索引扫）"


# ==================== ④索引判据：回查走带索引的那一列，不是全表扫 ====================


def test_vector_doc_id_is_indexed_for_the_reverse_lookup(db):
    with db.get_bind().connect() as conn:
        rows = conn.execute(text("PRAGMA index_list(qa_candidates)")).fetchall()
        indexed = set()
        for r in rows:
            for part in conn.execute(text(f"PRAGMA index_info('{r[1]}')")).fetchall():
                indexed.add(part[2])
    assert "vector_doc_id" in indexed, f"缺 vector_doc_id 上的索引（现有：{sorted(indexed)}）⇒ 每次命中都是全表扫"


# ==================== ⑥升级面判据：现网那种旧库（列是 ALTER 补的）也必须长出索引 ====================


def test_migrated_legacy_db_gets_the_reverse_lookup_index(tmp_path):
    """`create_all` 只给**它新建的表**建索引；现网 `qa_candidates` 早就在，列是 ALTER 补出来的 ⇒
    模型上写了 `index=True` 也不会凭空长出索引。这一条钉的是 `migrations` 的第三步。"""
    import sqlite3

    from sqlalchemy import create_engine

    import migrations

    db_file = tmp_path / "legacy.db"
    raw = sqlite3.connect(db_file.as_posix())
    # 手工搭"部署态"形状：有那六列（10d1dc0 之后），但**没有** vector_doc_id 的索引
    raw.executescript(
        "create table qa_candidates ("
        " id INTEGER primary key, question TEXT, answer TEXT, grounded_score FLOAT, evidence TEXT,"
        " status VARCHAR(16), approval_source VARCHAR(32) DEFAULT 'unknown', reviewed_by INTEGER,"
        " reviewed_at DATETIME, eligibility VARCHAR(16) DEFAULT 'ok', eligibility_version INTEGER DEFAULT 1,"
        " vector_doc_id VARCHAR(64), created_at DATETIME);"
    )
    raw.commit()
    raw.close()

    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    from sqlalchemy.orm import sessionmaker

    import database

    real_engine, real_factory = database.engine, database.SessionLocal
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine)
    try:
        migrations.run_migrations(engine)
        with engine.connect() as conn:
            rows = conn.execute(text("PRAGMA index_list(qa_candidates)")).fetchall()
            indexed = set()
            for r in rows:
                for part in conn.execute(text(f"PRAGMA index_info('{r[1]}')")).fetchall():
                    indexed.add(part[2])
    finally:
        database.engine, database.SessionLocal = real_engine, real_factory
    assert "vector_doc_id" in indexed, f"升级后的旧库仍缺索引（现有：{sorted(indexed)}）⇒ 回查在生产上是全表扫"


# ==================== ⑦失败面判据：回查查不动 ⇒ fail-closed，不许退回"无链放行面" ====================


def test_lookup_failure_is_fail_closed_not_deferred_to_provenance(db, double_embeddings, monkeypatch):
    """最坏的一种"看起来安全"：库挂了 ⇒ 解析不到链 ⇒ 走放行面 ⇒ 来源未知的那批照旧被直返。"""
    _kb_has_article(monkeypatch, [{"page_content": "第十九条 试用期……"}])
    _seed_vector_without_chain(Q_UNKNOWN, DOC_UNKNOWN)
    _attach_sql_row(db, Q_UNKNOWN, DOC_UNKNOWN, approval_source="unknown")
    hit = ks.search_qa(Q_UNKNOWN)
    assert hit is not None and hit.get("qa_candidate_id") is None

    def boom(doc_id):
        raise RuntimeError("模拟 SQL 读不动（锁／文件被占用／连接断开）")

    monkeypatch.setattr(qe, "_select_candidate_id_by_doc_id", boom)
    verdict = qe.evaluate_revocation_state(hit)
    assert verdict.allow is False and verdict.reason == "state", (
        f"回查失败被读成『没有链』并放行了：{verdict} ⇒ 状态轴在最该拦的时候失灵"
    )


# ==================== ⑤写侧仍要落链：能回查 ≠ 可以停写 metadata ====================


def test_new_writes_still_put_the_chain_in_metadata(db, double_embeddings):
    """快路径那份链不许因为"反正能回查"就停写——停写会让每次命中都多一条 SELECT（同一份语义退化成两次读）。

    W06-P0（C03=P 写侧）：新写入触发点从「自动收录」改到**人工采纳**——create_candidate 只入 pending、
    不写向量；decide_candidate(approved) 才写，且仍把链落进 metadata（qa_candidate_id 与 vector_doc_id 一致）。
    """
    q = "C20丁：新的自动收录还写不写 metadata 链？"
    row = ks.create_candidate(db, q, ANSWER, 0.95, EVIDENCE)
    assert row.status == "pending", "高分不应再自动批准（W06-P0）"
    ks.decide_candidate(db, row.id, "approved")
    hit = ks.search_qa(q)
    assert hit is not None
    assert hit.get("qa_candidate_id") == row.id, (
        f"新写入不再往 metadata 落链（只剩回查一条路）：期望 {row.id}，实得 {hit.get('qa_candidate_id')}"
    )
