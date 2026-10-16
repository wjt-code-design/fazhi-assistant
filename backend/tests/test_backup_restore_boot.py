"""W12 第四剧本：恢复出来的副本**把应用起来**，五面都经产品自己的读径查得动（全合成，不碰真实库）。

执行书 W12 票原文（`docs/superpowers/plans/2026-10-15-full-scope-remediation-and-closeout-execution-plan.md`
第 436 行；⚠️ 该文件在本仓**未纳入版本控制**，裸写 `plan:436` 在交付树里解析不出来，所以这里把句子抄全）：

> 合成SQLite含WAL、Chroma、元数据、媒体、配额一并备份→恢复→启动合成验证；校验中途失败不落假manifest、
> 恢复后语义/数据一致。没有恢复实测不算备份门PASS；不接真实备份。

分工要说准，别把自己抬过头：

- `tests/test_backup_data.py`（`--collect-only` 现量 16 条）钉失败关闭契约；
- `tests/test_backup_restore_drill.py`（7 条）钉**包内语义**——它确实打开恢复出的 SQLite 取回原文行、
  读配额数字、对恢复出的向量库做 `query` 并把命中与包内 `chroma_index.json` 对齐。
- **缺的那一格是"经过应用这一层"**：上面两只都直接对着 `sqlite3` / `chromadb` 取证，没有任何一条把
  FastAPI 的装配（`retrieval` / `knowledge_service` / `knowledge_base` / `main` 的 import 期绑名、
  `SessionLocal`、`MEDIA_DIR`、`quota_store.DB_PATH`）接到恢复目录上跑一遍。本文件钉的就是这一格。

四条判据 + 一条名单对账，各管一个不同的失败方向（都能红，逐只变异见同轮报告 §2）：

1. `test_app_boots_on_the_restored_package_and_serves_the_sentinel`——起得来、登得进、会话与条文回得来。
2. `test_restored_media_and_quota_ledger_are_served_through_product_readers`——
   媒体走真路由 `/api/media/{path}`（含 BOLA 归属守卫），配额走产品自己的 `quota_store.used_map()`。
3. `test_the_sentinel_answer_comes_from_the_restored_vectors_not_from_somewhere_else`——
   只从**恢复副本**里删掉哨兵，同一条链必须查不到它。
4. `test_every_consumer_module_reads_the_restored_store`——断言的是**各消费模块自己那个名字**与恢复库
   对象的**身份**（`is`），不是断言我 fixture 里造的那个对象。前一版写的正是后者，那是恒真：
   把 `retrieval` 从换绑循环里删掉它照样绿。这条同时钉住"没换绑的那一支"，免得有人把它读成
   "整套应用都在恢复副本上"——`knowledge_service._qa_store` 仍指测试 lane，因为备份包里本来就没有
   `qa_pairs` 集合，硬接等于在恢复目录里静默新建一只空集合。
5. `test_binding_surface_list_matches_the_source`——换绑名单从盘上源码现量对账，不许靠我记得。
   漏一处的后果不是"测试不够严"，而是**那一路在恢复演练里根本没被换过**。

边界（写清楚，不装作已验）：

- 是**进程内 `TestClient`**，不是 uvicorn 子进程；子进程那条要在恢复库上付真实模型加载，本机不可测。
- `/healthz` 的 `vector=True` 只证"打得开"、不证"有数据"；第 3 条里显式断言它仍为 True。
  ⇒ 推论：半途恢复（包里缺 `chroma_db`）时 `/healthz` 一样报 ok，这是产品的已知局限，本文件只钉不修。
- 合成向量走 `langchain_chroma.Chroma.add_documents` + 显式 cosine `collection_metadata`，
  与 `conftest._prepare_test_chroma` 同一理由：空目录新建是 l2，会跑到生产不走的那条分数分支上。
- 业务库用 `Base.metadata.create_all` 建，产品真启动走 `migrations.run_migrations()`；
  两条路径的表集合是否逐项相同**本文件没有证**，断言只覆盖我用到的三张表。
"""

from __future__ import annotations

import json
import re
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
QUOTA_KEY = "probe-model-a"
QUOTA_USED = 17
# `image_ref` 存的是**相对 backend/** 的路径（models.py:56 原话），路由也照这个拼（main.py:423），
# 所以必须是 "media/<文件名>"；只给文件名会被判成非法路径。
MEDIA_REF = "media/upload-1.txt"
MEDIA_TEXT = "合成上传件"
# ids 由产品写入路径生成（见 _seed_chroma），这里只留内容三元组
DOCS = [
    {"text": SENTINEL_TEXT, "source": SENTINEL_LAW + SENTINEL_ARTICLE, "article": SENTINEL_ARTICLE},
    {
        "text": "借款人应当按照约定的期限支付利息。合成演练文本。",
        "source": "中华人民共和国民法典第六百七十四条",
        "article": "第六百七十四条",
    },
]

# import 期就把 `vectorstore` 绑进自己命名空间的产品模块（`rag_chain` 是生产者，不算消费点）。
# 少绑一处 = 那一路仍读测试 lane 的库；名单由第 5 条从盘上源码现量对账，不许漂移。
VECTOR_PRODUCER = "rag_chain"
VECTOR_CONSUMER_MODULES = (VECTOR_PRODUCER, "retrieval", "main", "knowledge_service", "knowledge_base")
_IMPORT_BINDING = re.compile(r"^from rag_chain import [^\n]*\bvectorstore\b", re.M)


def _seed_sqlite(main_db: Path) -> None:
    """合成业务库用**产品自己的 metadata** 建表——手工拼表会得到一只"能打开但应用不认"的库。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import auth
    from models import Base, Conversation, Message, User

    url = "sqlite:///" + main_db.as_posix()
    eng = create_engine(url)
    Base.metadata.create_all(eng)
    eng.dispose()

    # WAL 是**前置自检**而不是顺手一设：演练声称源库是 WAL 形状（backup API 的卖点），
    # 设不成 WAL 时后面的断言就描述了一个不存在的形状。
    con = sqlite3.connect(main_db)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    if mode != "wal":
        raise AssertionError("合成源库没开成 WAL，实际 " + str(mode))

    sm = sessionmaker(bind=create_engine(url))
    with sm() as s:
        u = User(username=BOOT_USER, password_hash=auth.hash_password(BOOT_PASSWORD), role="user", is_active=True)
        s.add(u)
        s.flush()
        conv = Conversation(user_id=u.id, question=SENTINEL_QUESTION, title=SENTINEL_QUESTION, message_count=1)
        s.add(conv)
        s.flush()
        # 媒体那条腿要过 BOLA 归属守卫：文件必须挂在"当前用户会话里的消息"上才发得出去
        s.add(Message(conversation_id=conv.id, role="user", content="带附件的一问", image_ref=MEDIA_REF))
        s.commit()


def _seed_quota(quota_db: Path, monkeypatch) -> None:
    """配额账本由**产品自己**建表与写入：它的 schema 是 `(key, used)`，不是我拼的三列。"""
    import quota_store

    quota_db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(quota_store, "DB_PATH", str(quota_db))
    # 双检锁全局：不重置就不会在这只新库上建表（`_ensure()` 见 quota_store.py:31-46）
    monkeypatch.setattr(quota_store, "_inited", False)
    quota_store.set_used(QUOTA_KEY, QUOTA_USED)


def _seed_chroma(chroma_dir: Path, collection_name: str, embeddings) -> None:
    """用**产品自己的写入路径**建合成库（`Chroma.add_documents` + 替身嵌入）。

    - 手搭 `collection.add(embeddings=...)` 会得到一只与生产写入形状不同的库（ids 由我拼、文档由我塞），
      启动腿测的就不是"应用写进去的东西能不能被应用读回来"；
    - `collection_metadata={"hnsw:space": "cosine"}` 必须显式给：langchain 把 None 原样传给
      `get_or_create_collection` ⇒ 空目录新建的是 chromadb 0.4.24 默认的 **l2**，而 `retrieval`
      的分数分支按 cosine 写（理由逐字见 `conftest._prepare_test_chroma`）。
    """
    from langchain_chroma import Chroma
    from langchain_core.documents import Document

    import retrieval_core as rcore

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
    """合成源（五面齐全）→ 产品自己造包 → 按清单恢复到另一个目录。

    `backup_data` 的隔离不是一个 `DATABASE_URL` 就够：CHROMA_DIR / DATA_DIR / MEDIA_DIR /
    QUOTA_SOURCE / DEFAULT_BACKUP_ROOT 全是模块级常量 ⇒ 逐个 patch，漏一个就写到真实目录上。
    """
    import rag_chain
    from scripts import backup_data

    host = tmp_path / "host"
    (host / "data").mkdir(parents=True)
    main_db = host / "app.db"
    _seed_sqlite(main_db)
    _seed_quota(host / "data" / "quota_used.sqlite", monkeypatch)
    plain = host / "data" / "app.db"
    con = sqlite3.connect(plain)
    with con:
        con.execute("CREATE TABLE seedmark (k TEXT)")
    con.close()
    chroma = host / "chroma_db"
    _seed_chroma(chroma, rag_chain.COLLECTION_NAME, rag_chain.embeddings)
    media = host / "media"
    media.mkdir(parents=True, exist_ok=True)
    (media / Path(MEDIA_REF).name).write_text(MEDIA_TEXT, encoding="utf-8")

    for name, value in (
        ("DB_PATH", str(main_db)),
        ("CHROMA_DIR", str(chroma)),
        ("DATA_DIR", str(host / "data")),
        ("MEDIA_DIR", str(media)),
        ("QUOTA_SOURCE", str(host / "data" / "quota_used.sqlite")),
        ("DEFAULT_BACKUP_ROOT", str(tmp_path / "backups")),
    ):
        monkeypatch.setattr(backup_data, name, value)
    # 先记下测试 lane 自己在用的向量目录：接线腿需要一个"不是它"的参照物，delenv 之后就问不到了
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


def _bind_app(world, monkeypatch, drop_sentinel=False, skip_modules=()):
    """恢复 + 把**每一个消费点自己那个名字**换绑到恢复目录。

    `skip_modules` 不是给产品代码留的旁路，是给**变异仪器**用的：拿它抽掉一处换绑，接线腿必须当场变红。
    抽不动接线腿的变异说明那条腿是装饰，不是判据。
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database
    import knowledge_base
    import knowledge_service
    import main
    import multimodal
    import quota_store
    import rag_chain
    import retrieval

    restored = world["tmp"] / "restored"
    placed = _restore(world["pkg"], restored)
    vs_dir = restored / "chroma_db"
    if drop_sentinel:
        _drop_sentinel(vs_dir, rag_chain.COLLECTION_NAME)

    monkeypatch.setattr(rag_chain, "CHROMA_DIR", str(vs_dir))
    vs = rag_chain._build_vectorstore()
    modules = {
        "rag_chain": rag_chain,
        "retrieval": retrieval,
        "main": main,
        "knowledge_service": knowledge_service,
        "knowledge_base": knowledge_base,
    }
    for name in VECTOR_CONSUMER_MODULES:
        if name in skip_modules:
            continue
        monkeypatch.setattr(modules[name], "vectorstore", vs)

    # 媒体与配额的落点是模块级常量——设 env 改不动已经绑好的值（quota_store.py:17 在 import 期读 env）
    monkeypatch.setattr(main, "MEDIA_DIR", str(restored / "media"))
    monkeypatch.setattr(multimodal, "MEDIA_DIR", str(restored / "media"))
    monkeypatch.setattr(quota_store, "DB_PATH", str(restored / "quota_used.sqlite"))
    monkeypatch.setattr(quota_store, "_inited", False)

    eng = create_engine("sqlite:///" + (restored / "app.db").as_posix())
    sm = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    for mod in (database, main):
        monkeypatch.setattr(mod, "SessionLocal", sm)

    # 语料换了一整套 = 知识增删，走产品自己的失效口。不调它，反证腿读到的是上一条用例
    # 留在进程里的 LRU/BM25（实测 2.6 ms 返回缓存），会被顶成"假绿"。
    retrieval.invalidate()

    return {
        "client": TestClient(main.app),
        "vs": vs,
        "vs_dir": vs_dir,
        "placed": placed,
        "restored": restored,
        "modules": modules,
    }


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
        assert len(json.loads(convs.text)) == 1, "恢复出的会话数不是 1 —— 清单↔dest 的映射与备份内容不一致"
        assert SENTINEL_QUESTION in convs.text, "SQLite 腿：恢复库里的哨兵会话没有回到应用响应里"

        search = client.get("/api/law/search", params={"q": SENTINEL_TEXT}, headers=headers)
        assert search.status_code == 200, "向量腿：/api/law/search 在恢复库上直接失败 " + search.text
        articles = [it.get("article") for it in json.loads(search.text)]
        assert SENTINEL_ARTICLE in articles, "向量腿：恢复出的向量库答不出备份前那条条文"


def test_restored_media_and_quota_ledger_are_served_through_product_readers(boot_world, monkeypatch):
    """436 那句"媒体、配额一并…启动验证"落在这里：媒体走真路由（含归属守卫），配额走产品读径。"""
    import quota_store

    w = _bind_app(boot_world, monkeypatch)
    with w["client"] as client:
        headers = _login(client)
        media = client.get("/api/media/" + MEDIA_REF, headers=headers)
        assert media.status_code == 200, "媒体腿：恢复出的上传件经应用取不回（" + str(media.status_code) + "）"
        assert MEDIA_TEXT in media.content.decode("utf-8"), "媒体腿：发回来的不是备份前那份内容"

    assert quota_store.used_map() == {QUOTA_KEY: QUOTA_USED}, "配额腿：恢复出的账本读不回原来的数字"


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
        # 显式钉住一条已知局限：健康检查量的是"打得开"，不是"有数据"
        assert client.get("/healthz").json()["vector"] is True


def test_every_consumer_module_reads_the_restored_store(boot_world, monkeypatch):
    """接线腿：比的是**各消费模块自己那个名字**的身份，不是我自己造的那个对象。"""
    import knowledge_service
    import rag_chain

    w = _bind_app(boot_world, monkeypatch)
    vs = w["vs"]
    for name in VECTOR_CONSUMER_MODULES:
        bound = w["modules"][name].vectorstore
        assert bound is vs, name + " 的 vectorstore 不是恢复库对象 ⇒ 那一路仍在读测试 lane"
        assert Path(bound._persist_directory).resolve() == w["vs_dir"].resolve()
    assert Path(rag_chain.CHROMA_DIR).resolve() == w["vs_dir"].resolve()
    assert w["vs_dir"].resolve() != Path(boot_world["test_lane_chroma"]).resolve(), (
        "恢复目录与测试 lane 目录撞在一起，这条腿分不出读的是谁"
    )
    # 已知边界：QA 那一支没接恢复副本——备份包里本来就没有 qa_pairs 集合。
    assert knowledge_service._qa_store is not vs


def test_binding_surface_list_matches_the_source():
    """换绑名单从盘上源码现量对账：产品模块里 import 期绑 `vectorstore` 的每一处都必须在名单上。

    用盘上扫描而不是 `git grep`，因为验收树是 `git archive` 出的、没有 `.git`；
    锚 `^from` 也是有意的：脚本里那种**函数内** import 在使用时才取，不受本文件的绑名影响。
    """
    backend = Path(__file__).resolve().parents[1]
    found = {
        f.stem
        for f in sorted(backend.glob("*.py"))
        if f.name != "conftest.py" and _IMPORT_BINDING.search(f.read_text(encoding="utf-8"))
    }
    assert found, "盘上一处都没扫到 import 期绑定点 ⇒ 这条对账是空跑的，判据本身失效"
    assert found == set(VECTOR_CONSUMER_MODULES) - {VECTOR_PRODUCER}, (
        "产品侧 import 期绑定点与名单不一致：源码现量 "
        + str(sorted(found))
        + "，名单写的是 "
        + str(sorted(set(VECTOR_CONSUMER_MODULES) - {VECTOR_PRODUCER}))
    )
