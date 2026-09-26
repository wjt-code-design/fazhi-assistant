"""S0-b 写侧止血：`现行` 不再是任何路径的默认值，只能是显式签出的断言。

票组 §S0-b。动机：`status='现行'` 曾在**四处**被当默认值写入
（`knowledge_service.add_chunks`、`scripts/import_docs.py`、`scripts/import_laws.py`、`law_versions.version_metadata`），
其中 `add_chunks` 那处最深 ⇒ 任何调用方不传都得到"现行"，于是 10266 条上传语料集体声称自己现行有效。
"""

import os
import pathlib
import sys

import pytest

import retrieval_core as rc

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
_TESTS = pathlib.Path(__file__).resolve().parent
for _p in (str(_BACKEND), str(_TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_whitelist_has_unverified():
    assert "未验证" in rc.STATUS_WHITELIST


def test_no_path_defaults_status_to_current():
    """全仓不许再把 现行 当**缺省值**（比较、白名单成员、测试夹具不算）。

    三种缺省写法都覆盖：`or "现行"`、`.get("status", "现行")`、payload 里的 `"status": "现行"`。
    这条是防"第五处默认值悄悄长回来"——本轮实测默认值站点从票面写的 4 处扩到 8 处。
    """
    needles = ('or "现行"', "or '现行'", 'get("status", "现行")', '"status": "现行"', "'status': '现行'")
    offenders = []
    # 整棵树扫，不是三个目录：docstring 说的是"全仓"，而 `agent/`、`knowledge_base/` 同样在写 metadata
    # （09-26 双轴评审点到旧 glob 只覆盖 `*.py` + scripts + tools ⇒ 那两处新站长回来不会报警）。
    _SKIP = {"venv", "__pycache__", "node_modules"}
    for p in _BACKEND.rglob("*.py"):
        if {x.lower() for x in p.parts} & _SKIP or p.parent.name == "tests":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hit = [n for n in needles if n in text]
        if hit:
            offenders.append(f"{p.relative_to(_BACKEND)}: {hit}")
    assert offenders == [], f"这些文件仍把 现行 当缺省值：{offenders}"


def test_api_schema_accepts_unverified():
    """API 侧第二份白名单必须跟着走，否则 `未验证` 会被 422 挡在门外。"""
    from schemas import KnowledgeAddIn

    assert KnowledgeAddIn(title="测试法", article="第一条", content="正文", status="未验证").status == "未验证"


@pytest.fixture
def tmp_collection(monkeypatch, tmp_path):
    """独立临时 Chroma（FakeEmbeddings，不加载 BGE），只替换内存中的 vectorstore 引用。"""
    import chromadb
    from _fake_embeddings import FakeEmbeddings
    from langchain_chroma import Chroma

    import knowledge_service as ks_mod

    client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=chromadb.Settings(anonymized_telemetry=False),
    )
    vs = Chroma(collection_name="test_unverified_tmp", embedding_function=FakeEmbeddings(), client=client)
    monkeypatch.setattr(ks_mod, "vectorstore", vs)
    return vs


def test_add_chunks_defaults_to_unverified(tmp_collection):
    import knowledge_service as ks

    written = ks.add_chunks(
        [("第一条 测试正文", {"article": "第一条"})],
        source="测试法",
        origin="manual",
    )
    assert written == 1
    got = tmp_collection.get(where={"source": "测试法"})
    assert got["metadatas"][0]["status"] == "未验证"
    assert rc.time_validity_state(got["metadatas"][0]) == "unknown"


def test_add_chunks_keeps_explicit_status(tmp_collection):
    """只有"缺省"才降级为未验证；显式签出的 现行 必须原样落库。"""
    import knowledge_service as ks

    ks.add_chunks(
        [("第一条 测试正文", {"article": "第一条"})],
        source="测试法",
        origin="manual",
        extra_meta={"status": "现行", "effective_from": "2021-01-01"},
    )
    got = tmp_collection.get(where={"source": "测试法"})
    meta = got["metadatas"][0]
    assert meta["status"] == "现行"
    assert rc.time_validity_state(meta) == "verified"


def test_version_metadata_defaults_to_unverified():
    import law_versions

    meta = law_versions.version_metadata(
        {"effective_from": "2021-01-01"}, title="测试法", article="第一条", content="正文"
    )
    assert meta["status"] == "未验证"


def test_validate_entry_requires_explicit_status():
    """批导入侧：省略 status 从"静默按现行"改成整条拒 —— 扩白名单不配这条就会出现无人报警的未验证块。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_il", _BACKEND / "scripts" / "import_laws.py")
    assert spec and spec.loader
    import_laws = importlib.util.module_from_spec(spec)
    # 该脚本 import 期会 os.chdir(BACKEND)，这里把它恢复掉，别给后面的测试留一个漂移的 cwd
    cwd = pathlib.Path.cwd()
    try:
        spec.loader.exec_module(import_laws)
    finally:
        os.chdir(cwd)

    base = {
        "title": "测试法",
        "article_number": "第一条",
        "content": "第一条 正文。",
        "promulgated_at": "2020-05-28",
        "effective_from": "2021-01-01",
        "effective_to": "",
        "reviewed_at": "2026-09-26",
        "source_url": "https://example.invalid/x",
        "source_document_sha256": "a" * 64,
    }
    assert any("status" in e for e in import_laws.validate_entry(dict(base)))
    assert import_laws.validate_entry({**base, "status": "现行"}) == []
    assert import_laws.validate_entry({**base, "status": "未验证"}) == []
