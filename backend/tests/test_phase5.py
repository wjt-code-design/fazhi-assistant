"""阶段5 测试：条文时效治理（纯函数 / BM25 谓词 / API 契约 / 检索端到端排除）。

- 纯函数与 BM25：不落库，快速。
- API 契约：仿 test_phase3 的 client fixture（内存 DB + 真实 vectorstore），落库用例必须 finally 自清理。
- 端到端排除：真实 vectorstore，唯一 source="test_phase5_tmp"，断言后按 source 删除（不依赖 add_text 返回 ids）。
"""

import pytest
from langchain_core.documents import Document

import retrieval_core as rc


def test_valid_by_time_amended_window_pin_per_owner_ruling():
    """钉住 2026-09-25 Owner 裁决"给 `已修改` 的旧版补 `effective_to`"所依赖的两件事。

    用真实数据（劳动合同法 2008 原文 / (2012修正) 施行 2013-07-01，见
    docs/corpus-time-meta-ticket-20260925.md §4b）而非抽象日期：那条裁决说"旧版填
    替代版施行日**前一天**"，而它成立的前提正是本谓词的边界语义是"最后有效日**含**当日"——
    差一天就会造成两版重叠（同问题两版同命中）或有一天无版本可答。
    """
    # ① 今天这个洞是真的：`已修改` 不在任何 fail-closed 分支里 ⇒ 缺日期时任何查询日都算有效。
    #    （若将来把它也判死，这条会红——红了说明**改了口径**，要去数据票 §3-A/G 同步。）
    assert rc.is_valid_by_time({"status": "已修改"}, "2026-08-01") is True
    assert rc.is_valid_by_time({"status": "已修改"}, "1990-01-01") is True
    amended = {"status": "已修改", "effective_from": "2008-01-01", "effective_to": "2013-06-30"}
    # ② 补了日期之后，"前一天"这个算法刚好让新旧两版不重叠也不留缝。
    assert rc.is_valid_by_time(amended, "2013-06-30") is True  # 最后有效日含当日
    assert rc.is_valid_by_time(amended, "2013-07-01") is False  # 修正版施行日当天旧版退场
    assert rc.is_valid_by_time(amended, "2007-12-31") is False  # 未施行


# ---------- is_valid_by_time 纯函数矩阵 ----------
def test_valid_by_time_matrix():
    assert rc.is_valid_by_time({"status": "现行"}, "2026-08-01") is True  # 无日期限制
    assert rc.is_valid_by_time({"status": "现行", "effective_from": "", "effective_to": ""}, "2026-08-01") is True
    assert rc.is_valid_by_time({"status": "已废止"}, "2026-08-01") is False
    assert (
        rc.is_valid_by_time(
            {"status": "已废止", "effective_from": "1999-10-01", "effective_to": "2020-12-31"},
            "2000-01-01",
        )
        is True
    )  # 当前虽已废止，但在历史有效期内仍应可检索
    assert rc.is_valid_by_time({"status": "已废止", "effective_to": "2020-12-31"}, "2021-01-01") is False
    assert rc.is_valid_by_time({"status": "现行", "effective_to": "2020-12-31"}, "2026-08-01") is False  # 已过废止日
    assert (
        rc.is_valid_by_time({"status": "现行", "effective_to": "2020-12-31"}, "2020-12-31") is True
    )  # 废止日当天仍有效
    assert rc.is_valid_by_time({"status": "现行", "effective_to": "2020-12-31"}, "2021-01-01") is False
    assert (
        rc.is_valid_by_time({"status": "即将施行", "effective_from": "2027-01-01"}, "2026-08-01") is False
    )  # 尚未施行
    assert (
        rc.is_valid_by_time({"status": "即将施行", "effective_from": "2027-01-01"}, "2027-01-01") is True
    )  # 施行日当天生效
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
def test_admin_knowledge_add_contract_with_time_fields(monkeypatch, double_embeddings):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from auth import hash_password
    from models import Base, User

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
            docs = c.get("/api/admin/knowledge?source=test_phase5_tmp", headers=headers).json()["items"]
            mine = [d for d in docs if d["metadata"].get("source") == "test_phase5_tmp"]
            assert mine, "手动添加后应能在知识库列表查到"
            md = mine[0]["metadata"]
            assert md["effective_from"] == "2026-01-01"
            assert md["effective_to"] == "2030-12-31"
            assert md["status"] == "即将施行"
            assert md["version_id"].startswith("lv-")
            assert len(md["source_document_sha256"]) == 64
        finally:
            from rag_chain import vectorstore

            ids = vectorstore._collection.get(where={"source": "test_phase5_tmp"})["ids"]
            if ids:
                vectorstore._collection.delete(ids=ids)


# ---------- 检索端到端：当前排除失效版本 / 历史 cutoff 恢复当时有效版本 / 管理端可见 ----------
@pytest.mark.slow
def test_retrieval_excludes_expired_but_admin_test_sees_it():
    """⚠️ C15 分流（2026-10-16）：本条走 `slow` 是**因为它的判据本身依赖真实语义排序**——
    它断言 `retrieval.retrieve(...)` 在 cutoff 分支上正向命中第九条。换成伪向量
    （`_fake_embeddings` 按文本哈希造随机向量）后相似度毫无意义，那条正向断言会退化成
    "看运气"，那是把判据删掉换一面绿旗，不是修用例。
    """
    import retrieval
    from rag_chain import vectorstore

    source = "test_phase5_tmp"
    c1 = "合同当事人应当按照约定全面履行自己的义务。阶段5测试已废止条文甲。"
    c2 = "合同履行应当遵循诚实信用原则。阶段5测试已过期条文乙。"
    from knowledge_service import add_text

    add_text(
        c1,
        source=source,
        article="第八条",
        origin="manual",
        extra_meta={
            "effective_from": "1999-10-01",
            "effective_to": "2020-12-31",
            "status": "已废止",
            "category": "民法",
        },
    )
    add_text(
        c2,
        source=source,
        article="第九条",
        origin="manual",
        extra_meta={"effective_from": "1999-10-01", "effective_to": "2020-12-31", "status": "现行", "category": "民法"},
    )
    try:
        # 今天检索：两条都已超过 effective_to，不应命中。
        today_docs = retrieval.retrieve(c2[:40], k=4)
        assert not any(d.metadata.get("source") == source for d in today_docs), "失效条文不应进入用户问答检索"
        # 废止日之前（历史视角）：两条在当时均有效，当前 status 不得抹掉历史版本。
        past_docs = retrieval.retrieve(c2[:40], k=4, cutoff="2000-01-01")
        assert any(d.metadata.get("article") == "第九条" for d in past_docs), "cutoff 在废止日前应命中已过期条文"
        historical_c1 = retrieval.retrieve(c1[:40], k=4, cutoff="2000-01-01")
        assert any(d.metadata.get("article") == "第八条" for d in historical_c1), "历史 cutoff 应恢复当时有效版本"
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


def test_admin_knowledge_test_endpoint_contract_shape(monkeypatch, double_embeddings):
    """把 `/api/admin/knowledge/test` 的**端点契约**留在 CI 里（C15 分流的收尾，2026-10-16）。

    上面那条真实检索用例被标了 slow（它的判据是排序与召回，替身证不了），于是这个端点在 CI 里
    一度完全没有覆盖。本条只钉四件与排序无关的事：未授权进不来、授权后 200、返回是 list、
    每个条目带 article/status/effective_to/source 四个键。

    ⚠️ 它**不**证明"该命中的条文命中了"——那一半仍只在 slow lane，写在这里免得被误读成已覆盖。
    也不能写成"返回 list"就算覆盖：库空时 `[]` 会让形状断言整段空转（第一版就是这样，被复核打回）。
    所以本条先塞一条自己的条文进去，再要求 `1 <= len(rows) <= 5`：端点若返回空或超限都会红。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from auth import hash_password
    from models import Base, User

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    db = sm()
    db.add(User(username="adminkt", password_hash=hash_password("password123"), role="admin"))
    db.commit()
    db.close()

    with TestClient(main.app) as c:
        monkeypatch.setattr(main.limiter, "enabled", False, raising=False)
        denied = c.post("/api/admin/knowledge/test", json={"query": "试用期最长多久"})
        assert denied.status_code in (401, 403), f"未授权应被挡，实测 {denied.status_code}"

        tok = c.post("/api/auth/login", json={"username": "adminkt", "password": "password123"}).json()["token"]
        headers = {"Authorization": f"Bearer {tok}"}

        # 先写一条自己的条文：没有这一步，替身库里可能是空的，`rows=[]` 会让下面所有形状断言空转
        seeded = c.post(
            "/api/admin/knowledge",
            json={
                "title": "test_phase5_kt_contract",
                "article": "第一条",
                "content": "端点契约用例自带条文，仅用于让返回集非空。",
                "effective_from": "2020-01-01",
                "status": "现行",
            },
            headers=headers,
        )
        assert seeded.status_code == 200, f"前置写入失败：{seeded.status_code} {seeded.text[:120]}"
        try:
            resp = c.post("/api/admin/knowledge/test", json={"query": "试用期最长多久"}, headers=headers)
            assert resp.status_code == 200, f"实测 {resp.status_code}：{resp.text[:160]}"
            rows = resp.json()
            assert isinstance(rows, list), f"应返回 list，实际 {type(rows).__name__}"
            assert 1 <= len(rows) <= 5, f"库里已有至少一条，端点却返回 {len(rows)} 条；上限 5 是 main.py 里写死的 k"
            for row in rows[:3]:
                assert {"article", "status", "effective_to", "source"} <= set(row), f"字段形状漂移：{sorted(row)}"
        finally:
            ids = [
                d["id"]
                for d in c.get("/api/admin/knowledge?source=test_phase5_kt_contract", headers=headers).json()["items"]
            ]
            for rid in ids:
                c.delete(f"/api/admin/knowledge/{rid}", headers=headers)
            import retrieval

            retrieval.invalidate()


# ---------- W1 端点契约：有条号缺生效日 ⇒ 先拒绝、后写库（零新增块） ----------
def test_admin_knowledge_rejects_undated_article_before_writing_any_chunk(monkeypatch, double_embeddings):
    """钉住"**先拒绝再写库**"这个顺序，而不只是"会返回校验错误"。

    判据本身由 `test_law_versions.py` 与 schema 单测覆盖；本条补的是它们都够不到的
    端点层（`version-safety-review-findings-20260927.md` §2 中-1 点名"没有任何测试覆盖
    端点这一层"）。只断言 422 是不够的——那既可能是"校验前拦下"，也可能是"写完了才报错"，
    而后者正是会造成**无日期双胞胎块永久并存**的那条路径。所以关键断言是拒绝之后
    该 source 下**一个块都没有**。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from auth import hash_password
    from models import Base, User

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    db = sm()
    db.add(User(username="adminw1", password_hash=hash_password("password123"), role="admin"))
    db.commit()
    db.close()

    from rag_chain import vectorstore

    def blocks(source: str) -> list:
        return vectorstore._collection.get(where={"source": source})["ids"]

    src_undated = "test_phase5_w1_undated"
    src_general = "test_phase5_w1_general"
    with TestClient(main.app) as c:
        tok = c.post("/api/auth/login", json={"username": "adminw1", "password": "password123"}).json()["token"]
        headers = {"Authorization": f"Bearer {tok}"}
        try:
            assert blocks(src_undated) == [], "夹具不干净：起点就该是零块"

            r = c.post(
                "/api/admin/knowledge",
                json={
                    "title": src_undated,
                    "article": "第一〇一条",
                    "content": "W1 端点契约：有条号但不给施行日期，应在写库前被拒。",
                },
                headers=headers,
            )
            assert r.status_code == 422, r.text
            # 断言"是哪条规则红的"：钉 施行日期 这条判据，而不是任何一次 422
            # （否则 title/content 之类的校验失败会替它把这条用例做绿）。
            assert "施行日期" in r.text, r.text
            assert blocks(src_undated) == [], f"校验错误必须发生在写库之前，实际留下 {len(blocks(src_undated))} 块"

            # 边界不变：无条号的一般知识仍允许不填日期——
            # 若哪天把"缺日期"一刀切到所有输入，这条会红。
            r2 = c.post(
                "/api/admin/knowledge",
                json={
                    "title": src_general,
                    "article": "",
                    "content": "W1 端点契约：无条号的一般知识，不填生效日仍应可存。",
                },
                headers=headers,
            )
            assert r2.status_code == 200, r2.text
            assert r2.json()["added_chunks"] >= 1
            assert len(blocks(src_general)) >= 1
        finally:
            for src in (src_undated, src_general):
                ids = vectorstore._collection.get(where={"source": src})["ids"]
                if ids:
                    vectorstore._collection.delete(ids=ids)


# ---------- W1 补漏：条号只填空格 ⇒ 端点与写库谓词不一致，曾被放行 ----------
def test_admin_knowledge_rejects_whitespace_only_article_without_date(monkeypatch, double_embeddings):
    """钉住端点与写库对"算不算填了条号"用同一个谓词。

    原先 `KnowledgeAddIn._valid_version_period` 判 `self.article.strip()`（schemas.py:185），
    写库侧 `add_text` 判裸真值 `and article`（knowledge_service.py:184/:204）⇒ `article=" "`
    在端点算"没填"（放行）、在写库算"填了"（走版本判定并派生 version_id）；两次无日期重传即
    造出同一 version_id 的双胞胎，且无日期可判 ⇒ 事后清不掉，与
    `version-safety-review-findings-20260927.md` §2 中-1 是**同一个终态**（W1 的①封不住）。

    判据是"同一 payload 只改日期一栏"：缺日期必 422 且零块，补日期必 200——对照腿用来证明
    那条 422 的成因是缺日期，而不是端点对这条 payload 一律拒绝。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database
    import main
    from auth import hash_password
    from models import Base, User

    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "SessionLocal", sm)
    monkeypatch.setattr(main, "SessionLocal", sm)
    from fastapi.testclient import TestClient

    db = sm()
    db.add(User(username="adminw1blank", password_hash=hash_password("password123"), role="admin"))
    db.commit()
    db.close()

    from rag_chain import vectorstore

    def blocks(source: str) -> list:
        return vectorstore._collection.get(where={"source": source})["ids"]

    src = "test_phase5_w1_blank"
    body = {
        "title": src,
        "article": " ",
        "content": "W1 补漏：条号只填空格且不给施行日期，应在写库前被拒。",
    }
    with TestClient(main.app) as c:
        tok = c.post("/api/auth/login", json={"username": "adminw1blank", "password": "password123"}).json()["token"]
        headers = {"Authorization": f"Bearer {tok}"}
        try:
            assert blocks(src) == [], "夹具不干净：起点就该是零块"

            r = c.post("/api/admin/knowledge", json=body, headers=headers)
            assert r.status_code == 422, f"条号只填空格且无生效日应被拒，实际 {r.status_code}：{r.text}"
            # 钉"是哪条规则红的"，而不是"随便一次 422"（title/content 的校验失败会替它做绿）。
            assert "施行日期" in r.text, r.text
            assert blocks(src) == [], f"校验错误必须发生在写库之前，实际留下 {len(blocks(src))} 块"

            # 对照腿：同一 payload 只补日期一栏 ⇒ 200。证明那条 422 的成因是缺日期本身。
            r2 = c.post("/api/admin/knowledge", json={**body, "effective_from": "2026-01-01"}, headers=headers)
            assert r2.status_code == 200, r2.text
            assert len(blocks(src)) >= 1
        finally:
            ids = vectorstore._collection.get(where={"source": src})["ids"]
            if ids:
                vectorstore._collection.delete(ids=ids)
