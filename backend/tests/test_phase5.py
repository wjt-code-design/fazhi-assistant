"""阶段5 测试：条文时效治理（纯函数 / BM25 谓词 / API 契约 / 检索端到端排除）。

- 纯函数与 BM25：不落库，快速。
- API 契约：仿 test_phase3 的 client fixture（内存 DB + 真实 vectorstore），落库用例必须 finally 自清理。
- 端到端排除：真实 vectorstore，唯一 source="test_phase5_tmp"，断言后按 source 删除（不依赖 add_text 返回 ids）。
"""
from langchain_core.documents import Document

import retrieval_core as rc


# ---------- is_valid_by_time 纯函数矩阵 ----------
def test_valid_by_time_matrix():
    assert rc.is_valid_by_time({"status": "现行"}, "2026-08-01") is True  # 无日期限制
    assert rc.is_valid_by_time({"status": "现行", "effective_from": "", "effective_to": ""}, "2026-08-01") is True
    assert rc.is_valid_by_time({"status": "已废止"}, "2026-08-01") is False
    assert rc.is_valid_by_time({"status": "已废止", "effective_to": "2020-12-31"}, "2000-01-01") is False  # 已废止恒为 False
    assert rc.is_valid_by_time({"status": "现行", "effective_to": "2020-12-31"}, "2026-08-01") is False  # 已过废止日
    assert rc.is_valid_by_time({"status": "现行", "effective_to": "2020-12-31"}, "2020-12-31") is True  # 废止日当天仍有效
    assert rc.is_valid_by_time({"status": "现行", "effective_to": "2020-12-31"}, "2021-01-01") is False
    assert rc.is_valid_by_time({"status": "即将施行", "effective_from": "2027-01-01"}, "2026-08-01") is False  # 尚未施行
    assert rc.is_valid_by_time({"status": "即将施行", "effective_from": "2027-01-01"}, "2027-01-01") is True  # 施行日当天生效
    assert rc.is_valid_by_time({"status": "现行", "effective_from": "2021-01-01"}, "2026-08-01") is True
    assert rc.is_valid_by_time({"status": "草案"}, "2026-08-01") is True  # 未知状态默认有效
    assert rc.is_valid_by_time({}, "2026-08-01") is True  # 缺键视为无限制


# ---------- bm25_top + valid 谓词 ----------
def test_bm25_top_valid_predicate_skips_invalid_top_doc():
    docs = [
        Document(page_content="试用期 不得超过 六个月 劳动合同", metadata={"status": "已废止"}),
        Document(page_content="试用期 不得超过 二个月 劳动合同", metadata={"status": "现行"}),
        Document(page_content="诉讼时效 为 三年", metadata={"status": "现行"}),
    ]
    bm = rc.build_bm25(docs)
    all_top = rc.bm25_top(bm, docs, "试用期 劳动合同", 3)
    assert all_top[0][0].metadata["status"] == "已废止"  # 未过滤时已废止条分最高（前提成立）
    valid_top = rc.bm25_top(bm, docs, "试用期 劳动合同", 3, valid=lambda m: rc.is_valid_by_time(m, "2026-08-01"))
    assert valid_top and all(d.metadata["status"] != "已废止" for d, _ in valid_top)
    assert len(valid_top) <= 3


def test_bm25_top_valid_predicate_all_invalid_returns_empty():
    docs = [
        Document(page_content="a 合同 有效", metadata={"status": "已废止"}),
        Document(page_content="b 合同 无效", metadata={"status": "已废止"}),
    ]
    bm = rc.build_bm25(docs)
    assert rc.bm25_top(bm, docs, "合同", 3, valid=lambda m: rc.is_valid_by_time(m, "2026-08-01")) == []


# ---------- API 契约：手动添加条文（含时效字段） ----------
def test_admin_knowledge_add_contract_with_time_fields(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from models import Base, User
    from auth import hash_password

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    db = sm()
    db.add(User(username="admin5", password_hash=hash_password("password123"), role="admin"))
    db.commit()
    db.close()

    with TestClient(main.app) as c:
        tok = c.post("/api/auth/login", json={"username": "admin5", "password": "password123"}).json()["token"]
        headers = {"Authorization": f"Bearer {tok}"}
        body = {
            "title": "test_phase5_tmp",
            "article": "第一〇一条",
            "content": "阶段5契约测试条文，测试时效字段写入。",
            "effective_from": "2026-01-01",
            "effective_to": "2030-12-31",
            "status": "即将施行",
        }
        try:
            r = c.post("/api/admin/knowledge", json=body, headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["added_chunks"] >= 1
            docs = c.get("/api/admin/knowledge", headers=headers).json()
            mine = [d for d in docs if d["metadata"].get("source") == "test_phase5_tmp"]
            assert mine, "手动添加后应能在知识库列表查到"
            md = mine[0]["metadata"]
            assert md["effective_from"] == "2026-01-01"
            assert md["effective_to"] == "2030-12-31"
            assert md["status"] == "即将施行"
        finally:
            from rag_chain import vectorstore
            ids = vectorstore._collection.get(where={"source": "test_phase5_tmp"})["ids"]
            if ids:
                vectorstore._collection.delete(ids=ids)


# ---------- 检索端到端：已废止恒排除 / 已过期（未标废止）可被历史 cutoff 命中 / 管理端可见 ----------
# 语义（D2）：status=已废止 是管理员权威标记，恒排除（即使 cutoff 早于废止日）；
# 历史 cutoff 只对「仍标现行但已过 effective_to」的条文生效。
def test_retrieval_excludes_expired_but_admin_test_sees_it():
    from rag_chain import vectorstore
    import retrieval

    source = "test_phase5_tmp"
    c1 = "合同当事人应当按照约定全面履行自己的义务。阶段5测试已废止条文甲。"
    c2 = "合同履行应当遵循诚实信用原则。阶段5测试已过期条文乙。"
    from knowledge_service import add_text

    add_text(c1, source=source, article="第八条", origin="manual",
             extra_meta={"effective_from": "1999-10-01", "effective_to": "2020-12-31", "status": "已废止", "category": "民法"})
    add_text(c2, source=source, article="第九条", origin="manual",
             extra_meta={"effective_from": "1999-10-01", "effective_to": "2020-12-31", "status": "现行", "category": "民法"})
    try:
        # 今天检索：两条都不应命中（已废止恒排除；现行但已过废止日也排除）
        today_docs = retrieval.retrieve(c2[:40], k=4)
        assert not any(d.metadata.get("source") == source for d in today_docs), "失效条文不应进入用户问答检索"
        # 废止日之前（历史视角）：标"现行"但已过期的 c2 应命中；标"已废止"的 c1 恒不命中
        past_docs = retrieval.retrieve(c2[:40], k=4, cutoff="2000-01-01")
        assert any(d.metadata.get("article") == "第九条" for d in past_docs), "cutoff 在废止日前应命中已过期条文"
        assert not any(d.metadata.get("article") == "第八条" for d in past_docs), "已废止标记恒排除"
        # 管理端检索测试：不过滤，且带 status 标注
        hits = retrieval.retrieve_for_test(c2[:40], k=5)
        mine = {h["article"]: h for h in hits if h["source"] == source}
        assert set(mine) == {"第八条", "第九条"}, "管理端检索测试应能看到全部失效条文"
        assert mine["第八条"]["status"] == "已废止"
        assert mine["第九条"]["status"] == "现行"
        assert mine["第八条"]["effective_to"] == "2020-12-31"
    finally:
        ids = vectorstore._collection.get(where={"source": source})["ids"]
        if ids:
            vectorstore._collection.delete(ids=ids)
        retrieval.invalidate()
