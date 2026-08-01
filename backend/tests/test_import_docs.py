"""import_docs 集成测试（审查#10）。

- short_source：source 短名归一（seed 取代匹配键，关键纯逻辑）。
- import_one 端到端：临时 Chroma collection + fixture 法文本，断言
  片段数 / source 短名 / article 落库 / seed 碎片被取代 / file_hash 幂等。
临时 collection 隔离生产库；cwd 保存恢复防测试顺序污染。
"""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "scripts"))

from dotenv import load_dotenv

load_dotenv(os.path.join(BACKEND, ".env"))

import pytest  # noqa: E402


@pytest.fixture
def mod():
    cwd = os.getcwd()
    import import_docs as m

    yield m
    os.chdir(cwd)  # 抵消脚本模块级 os.chdir(BACKEND) 的副作用


def test_short_source(mod):
    assert mod.short_source("中华人民共和国劳动合同法_20121228.txt") == "劳动合同法"
    assert mod.short_source("中华人民共和国民法典_20200528.txt") == "民法典"
    assert mod.short_source("中华人民共和国宪法（1982年）_19821204.txt") == "宪法（1982年）"
    assert mod.short_source("行政法规制定程序条例_20260515.txt") == "行政法规制定程序条例"
    assert mod.short_source("中华人民共和国刑法_20201226.txt") == "刑法"


@pytest.fixture
def tmp_collection(monkeypatch, tmp_path):
    """临时 Chroma 向量库：把 import_docs 与 knowledge_service 的 vectorstore 引用
    整体替换为独立 PersistentClient 上的临时 Chroma（避免与生产客户端单例冲突）。

    add_chunks 走 vectorstore.add_documents、_col()/_collection() 走 vectorstore._collection，
    替换 vectorstore 引用后两者都落到临时库。
    """
    import chromadb
    from langchain_chroma import Chroma
    from rag_chain import embeddings
    import import_docs as id_mod
    import knowledge_service as ks_mod

    client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=chromadb.Settings(anonymized_telemetry=False),
    )
    vs = Chroma(
        collection_name="test_import_docs_tmp",
        embedding_function=embeddings,
        client=client,
    )
    monkeypatch.setattr(id_mod, "vectorstore", vs)
    monkeypatch.setattr(ks_mod, "vectorstore", vs)
    return vs


FIXTURE_LAW = "第一章 总则\n\n第一条 为了保护合法权益，制定本法。\n\n第二条 本法的适用范围。\n"


def test_import_one_end_to_end(mod, tmp_collection, monkeypatch, tmp_path):
    from langchain_core.documents import Document

    # 预置一个 origin=seed 的碎片（应被整法取代）
    tmp_collection.add_documents(
        [Document(page_content="第一条 旧种子碎片", metadata={"source": "测试法", "article": "第一条", "origin": "seed"})]
    )
    # fixture 法文件写入临时 CLEAN_DIR
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    (clean_dir / "中华人民共和国测试法_20200101.txt").write_text(FIXTURE_LAW, encoding="utf-8")
    monkeypatch.setattr(mod, "CLEAN_DIR", str(clean_dir))

    r = mod.import_one("中华人民共和国测试法_20200101.txt", dry_run=False)
    assert r["source"] == "测试法"
    assert r["chunks"] == 2  # 第一条 + 第二条
    assert r["seed_replaced"] == 1  # 旧种子第一条被取代

    col = tmp_collection._collection
    # seed 碎片已被取代（origin=seed 的第一条 == 0）
    seed_left = col.get(where={"$and": [{"source": "测试法"}, {"origin": "seed"}]})["ids"]
    assert len(seed_left) == 0
    # upload 片段就位，article 正确
    up = col.get(where={"$and": [{"source": "测试法"}, {"origin": "upload"}]}, include=["metadatas"])
    arts = {m["article"] for m in up["metadatas"]}
    assert arts == {"第一条", "第二条"}


def test_import_one_idempotent_by_hash(mod, tmp_collection, monkeypatch, tmp_path):
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    (clean_dir / "中华人民共和国测试法_20200101.txt").write_text(FIXTURE_LAW, encoding="utf-8")
    monkeypatch.setattr(mod, "CLEAN_DIR", str(clean_dir))

    r1 = mod.import_one("中华人民共和国测试法_20200101.txt", dry_run=False)
    assert r1["chunks"] == 2
    # 第二次同内容：file_hash 幂等跳过
    r2 = mod.import_one("中华人民共和国测试法_20200101.txt", dry_run=False)
    assert r2["skipped_hash"] is True
    assert r2["chunks"] == 0
    # 库中仍只有 2 个 upload 片段（未翻倍）
    n = len(tmp_collection._collection.get(where={"source": "测试法"})["ids"])
    assert n == 2
