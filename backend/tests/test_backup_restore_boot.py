"""W12 四剧本的第四只：恢复出来的副本**能把应用起来并查得动**（合成数据，全程不碰真实库）。

`test_backup_data.py`（15 条失败关闭契约）与 `test_backup_restore_drill.py`（7 条包内语义）
把「备份→恢复」钉住了，但执行书 plan:436 要的是 **备份→恢复→启动**：前两只量到的是
"包里的文件能被打开、能按 dest 放回去"，没有一条量到
"应用照这份恢复结果启动后，用户真的查得到那条条文"。缺口在这里，不在断言强度上。

三条判据的形状（一绿两钉，都能红）：

1. `test_app_boots_on_the_restored_package_and_serves_the_sentinel`——绿腿：
   应用绑到**恢复目录**里的 SQLite/Chroma，登录、会话列表、法条搜索都返回哨兵。
   哨兵只存在于"合成源→产品自己造包→按清单恢复"这一条链上，接线错了就直接查不到。
2. `test_the_sentinel_answer_comes_from_the_restored_vectors_not_from_somewhere_else`——反证腿：
   恢复后把哨兵那条从**恢复副本**里删掉再走同一条链，搜索不得再返回它。
   这条防的是"绿腿其实从别处（测试 lane 库/缓存）拿到的答案"。
3. `test_boot_reads_the_restored_copy_not_the_test_lane_store`——接线钉子：
   断言应用实际在用的那个向量对象 `_persist_directory` 就是恢复目录，且不等于测试 lane 的
   `CHROMA_DIR`。`retrieval.py:27` 是 `from rag_chain import vectorstore`（import 期绑名），
   只改 `rag_chain.vectorstore` 是**空**的——这条就是防这个。

边界：不接真实备份、不读真实库；模型一律用 `double_embeddings`（768 维、跨进程确定），
不加载真实权重也不出网。`/healthz` 在向量成员缺失时仍报 ok（它量的是"打得开"不是"有数据"），
这一点在第 2 条里显式断言下来，别让它以后被当成"恢复被健康检查保护住了"。
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import chromadb
import pytest

SENTINEL_LAW = "中华人民共和国合同法"
SENTINEL_ARTICLE = "第一百九十七条"
SENTINEL_TEXT = "合同的订立，应当遵循诚实信用原则。本节为合成演练文本，非真实条文。"
SENTINEL_QUESTION = "恢复演练哨兵会话：合同条文从哪条开始"
BOOT_USER = "boot-drill-user"
BOOT_PASSWORD = "password123"
# ids 由产品写入路径生成（见 _seed_chroma），这里只留内容三元组
DOCS = [
    {"text": SENTINEL_TEXT, "source": SENTINEL_LAW + SENTINEL_ARTICLE, "article": SENTINEL_ARTICLE},
    {
        "text": "借款人应当按照约定的期限支付利息。合成演练文本。",
        "source": "中华人民共和国民法典第六百七十四条",
        "article": "第六百七十四条",
    },
]


def _seed_sqlite(main_db: Path) -> None:
    """合成业务库用**产品自己的 metadata** 建表——手工拼表会得到一只"能打开但应用不认"的库。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import auth
    from models import Base, Conversation, User

    url = "sqlite:///" + main_db.as_posix()
    eng = create_engine(url)
    Base.metadata.create_all(eng)
    with eng.begin() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    eng.dispose()

    # WAL 必须是**前置自检**而不是顺手一设：演练声称源库是 WAL 形状（backup API 的卖点），
    # 设不成 WAL 时后面的断言就描述了一个不存在的形状。
    con = sqlite3.connect(main_db)
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    if mode != "wal":
        raise AssertionError("合成源库没开成 WAL，实际 " + str(mode))

    sm = sessionmaker(bind=create_engine(url))
    with sm() as s:
        u = User(username=BOOT_USER, password_hash=auth.hash_password(BOOT_PASSWORD), role="user", is_active=True)
        s.add(u)
        s.flush()
        s.add(Conversation(user_id=u.id, question=SENTINEL_QUESTION, title=SENTINEL_QUESTION, message_count=1))
        s.commit()


def _seed_chroma(chroma_dir: Path, collection_name: str, embeddings) -> None:
    """用**产品自己的写入路径**建合成库：`langchain_chroma.Chroma.add_documents` + 替身嵌入。

    两个理由，都不是风格问题：
    - 手搭 `collection.add(embeddings=...)` 会得到一只与生产写入形状不同的库（ids 由我拼、
      文档由我塞），启动腿测的就不是"应用写进去的东西能不能被应用读回来"。
    - `collection_metadata={"hnsw:space": "cosine"}` 必须显式给：langchain 把 None 原样传给
      `get_or_create_collection` ⇒ 空目录新建的是 chromadb 0.4.24 默认的 **l2**，
      而 `retrieval` 的分数分支按 cosine 写（理由逐字见 `conftest._prepare_test_chroma`），
      不预建 cosine 这条腿会跑在生产不走的那一支上。
    """
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    chroma_dir.mkdir(parents=True, exist_ok=True)
    store = Chroma(
        persist_directory=str(chroma_dir),
        embedding_function=embeddings,
        collection_name=collection_name,
        collection_metadata={"hnsw:space": "cosine"},
    )
    store.add_documents(
        [Document(page_content=d["text"], metadata={"source": d["source"], "article": d["article"]}) for d in DOCS]
    )
    assert store._collection.count() == len(DOCS), "合成源向量库没建成，启动腿的前置是空的"
    import retrieval_core as rcore

    assert rcore.is_cosine_space(store._collection), "合成库不是 cosine 空间，启动腿会走错分数分支"


def _drop_sentinel(chroma_dir: Path, collection_name: str) -> None:
    """只从**恢复副本**里按 metadata 删掉哨兵那条——ids 是产品写入路径生成的，不自己拼。"""
    col = chromadb.PersistentClient(path=str(chroma_dir)).get_collection(collection_name)
    col.delete(where={"article": SENTINEL_ARTICLE})
    left = {str((m or {}).get("article", "")) for m in (col.get(include=["metadatas"])["metadatas"] or [])}
    if SENTINEL_ARTICLE in left or len(left) != len(DOCS) - 1:
        raise AssertionError("反证腿的前置没成：恢复副本里哨兵没被干净删掉，剩 " + str(sorted(left)))


def _restore(pkg: Path, dest: Path) -> dict:
    from scripts import backup_data

    manifest = json.loads((pkg / backup_data.MANIFEST_NAME).read_text(encoding="utf-8"))
    dest.mkdir(parents=True, exist_ok=True)
    placed = {}
    for entry in manifest["entries"]:
        src_item, dst_item = pkg / entry["dest"], dest / entry["dest"]
        if entry["kind"] == "dir":
            shutil.copytree(src_item, dst_item)
        else:
            shutil.copyfile(src_item, dst_item)
        placed[entry["dest"]] = dst_item
    return placed


@pytest.fixture()
def boot_world(tmp_path, monkeypatch, double_embeddings):
    """合成源 → `backup_data.main` 造包 → 按清单恢复 → 把应用的三个入口都绑到恢复目录。

    `backup_data` 的隔离不是靠一个 `DATABASE_URL`：CHROMA_DIR / DATA_DIR / MEDIA_DIR /
    QUOTA_SOURCE / DEFAULT_BACKUP_ROOT 全是模块级常量 ⇒ 逐个 patch，漏一个就写到真实目录上。
    """
    import rag_chain
    from scripts import backup_data

    host = tmp_path / "host"
    (host / "data").mkdir(parents=True)
    main_db = host / "app.db"
    _seed_sqlite(main_db)
    make_quota = host / "data" / "quota_used.sqlite"
    con = sqlite3.connect(make_quota)
    with con:
        con.execute("CREATE TABLE quota (model TEXT PRIMARY KEY, used INTEGER, total INTEGER)")
    con.close()
    con = sqlite3.connect(host / "data" / "app.db")
    with con:
        con.execute("CREATE TABLE seedmark (k TEXT)")
    con.close()
    chroma = host / "chroma_db"
    _seed_chroma(chroma, rag_chain.COLLECTION_NAME, rag_chain.embeddings)
    media = host / "media"
    media.mkdir()
    (media / "upload-1.txt").write_text("合成上传件", encoding="utf-8")

    for name, value in (
        ("DB_PATH", str(main_db)),
        ("CHROMA_DIR", str(chroma)),
        ("DATA_DIR", str(host / "data")),
        ("MEDIA_DIR", str(media)),
        ("QUOTA_SOURCE", str(make_quota)),
        ("DEFAULT_BACKUP_ROOT", str(tmp_path / "backups")),
    ):
        monkeypatch.setattr(backup_data, name, value)
    # 先记下测试 lane 自己在用的向量目录（conftest 把 CHROMA_DIR 设成进程私有临时库）：
    # 启动腿要证明读的是恢复副本，就得有一个"不是它"的参照物，而 delenv 之后再问 env 就没了。
    test_lane_chroma = rag_chain.CHROMA_DIR
    monkeypatch.delenv("CHROMA_DIR", raising=False)
    monkeypatch.delenv("QUOTA_DB", raising=False)

    pkg = tmp_path / "pkg"
    assert backup_data.main(["--out", str(pkg)]) == 0, "造包失败，后面的启动判据都是空的"

    return {
        "tmp": tmp_path,
        "pkg": pkg,
        "host": host,
        "chroma": chroma,
        "main_db": main_db,
        "test_lane_chroma": test_lane_chroma,
    }


def _bind_app(world, monkeypatch, drop_sentinel=False):
    """恢复 + 把 `main` / `retrieval` / `database` 实际消费的名字换绑到恢复目录。"""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database
    import main
    import rag_chain
    import retrieval

    restored = world["tmp"] / "restored"
    placed = _restore(world["pkg"], restored)
    vs_dir = restored / "chroma_db"
    if drop_sentinel:
        _drop_sentinel(vs_dir, rag_chain.COLLECTION_NAME)

    monkeypatch.setattr(rag_chain, "CHROMA_DIR", str(vs_dir))
    vs = rag_chain._build_vectorstore()
    # 三个绑定点都要换：`retrieval`/`main` 在 import 期就 `from rag_chain import vectorstore`
    for mod in (rag_chain, retrieval, main):
        monkeypatch.setattr(mod, "vectorstore", vs)
    # 语料换了一整套 = 知识增删，走产品自己的失效口。不调它，第二条腿读到的是上一条用例
    # 留在进程里的 LRU/BM25（实测 2.6 ms 返回），反证腿就被缓存顶成"假绿"。
    retrieval.invalidate()

    eng = create_engine("sqlite:///" + (restored / "app.db").as_posix())
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    for mod in (database, main):
        monkeypatch.setattr(mod, "SessionLocal", sm)

    client = TestClient(main.app)
    return {"client": client, "vs": vs, "vs_dir": vs_dir, "placed": placed, "restored": restored}


def _login(client):
    r = client.post("/api/auth/login", json={"username": BOOT_USER, "password": BOOT_PASSWORD})
    assert r.status_code == 200, "恢复库里那个哨兵用户登不进去：登录是 SQLite 腿的第一道真消费"
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_app_boots_on_the_restored_package_and_serves_the_sentinel(boot_world, monkeypatch):
    w = _bind_app(boot_world, monkeypatch)
    with w["client"] as client:
        headers = _login(client)

        health = client.get("/healthz")
        assert health.status_code == 200, "恢复包起不来：/healthz " + health.text
        assert health.json()["vector"] is True

        convs = client.get("/api/conversations", headers=headers)
        assert convs.status_code == 200
        items = json.loads(convs.text)
        assert len(items) == 1, "恢复出的会话数不是 1 —— 清单↔dest 的映射与备份内容不一致"
        assert SENTINEL_QUESTION in convs.text, "SQLite 腿：恢复库里的哨兵会话没有回到应用响应里"

        search = client.get("/api/law/search", params={"q": SENTINEL_TEXT}, headers=headers)
        assert search.status_code == 200, "向量腿：/api/law/search 在恢复库上直接失败 " + search.text
        articles = [it.get("article") for it in json.loads(search.text)]
        assert SENTINEL_ARTICLE in articles, "向量腿：恢复出的向量库答不出备份前那条条文"


def test_the_sentinel_answer_comes_from_the_restored_vectors_not_from_somewhere_else(boot_world, monkeypatch):
    """反证腿：把恢复副本里的哨兵删掉，同一条链必须查不到它。

    删的是**恢复目录里的集合**，不是源、不是测试 lane 库 ⇒ 绿腿要是从别处拿的答案，
    这条会一起变绿，从而暴露"绿腿的出处不可信"。
    """
    w = _bind_app(boot_world, monkeypatch, drop_sentinel=True)
    with w["client"] as client:
        headers = _login(client)
        search = client.get("/api/law/search", params={"q": SENTINEL_TEXT}, headers=headers)
        assert search.status_code == 200
        articles = [it.get("article") for it in json.loads(search.text)]
        assert SENTINEL_ARTICLE not in articles, "删掉哨兵还能查到 ⇒ 绿腿的答案不是来自恢复副本"
        # 显式钉住一个已知局限：健康检查量的是"打得开"，不是"有数据"
        assert client.get("/healthz").json()["vector"] is True


def test_boot_reads_the_restored_copy_not_the_test_lane_store(boot_world, monkeypatch):
    """接线钉子：断言被应用实际使用的那个对象的目录，就是恢复目录，且不是测试 lane 那只。"""
    w = _bind_app(boot_world, monkeypatch)
    used = w["vs"]
    assert Path(used._persist_directory).resolve() == w["vs_dir"].resolve()
    lane = Path(boot_world["test_lane_chroma"]).resolve()
    assert Path(used._persist_directory).resolve() != lane, "恢复目录与测试 lane 目录撞在一起，这条腿分不出读的是谁"
