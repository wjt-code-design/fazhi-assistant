"""票 T2：预检必须把"版本并存"说出来（报警 + rc 分档），并证明"互不包含 ⇒ 整批不写入"。

票面：`docs/h1-law-version-collision-tickets-20260926.md` §T2。

**为什么判据 1 不许 mock 成空列表**：`include=["metadatas","documents"]` 取回来的东西就是这条分支的
输入；把它桩成空 ⇒ 用例只在"没有旧块"的世界里绿，而那正是它要防的世界。所以本文件的每条报警断言
都吃**真 `replaceable_version_ids` 的产物**（单元腿）或**真 Chroma 里真存在的旧块**（端点腿）。

**rc 分档（Owner 已裁）**：无时效遗留并存 ⇒ 打印 ⚠️、rc=0；互不包含 ⇒ rc=1 且**整批不写入**；
输入违规 ⇒ 整批不写入（既有行为，本文件只钉它没被改坏）。

⚠️ `import_laws.py` 在 import 时会 `os.chdir(BACKEND)` ⇒ 加载它必须还原 cwd，否则会污染同批
其他用例（`test_status_default_unverified.py` 踩过一次）。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "import_laws.py"

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))

from _fake_embeddings import FakeEmbeddings  # noqa: E402

# 形状照 §0 实测的那对旧/新块：旧块带章节行与全角空格，去空白后 新 ⊆ 旧（构造样本，非库内原文）。
LEGACY_OLD = "第十章　建筑物和物件损害责任\n第一千二百六十条　本法自2021年1月1日起施行。"
NEW_TEXT = "第一千二百六十条 本法自2021年1月1日起施行。"
OTHER_TEXT = "第一千二百六十条 本法自2021年1月1日起施行； Maritime 版本文字完全不同。"


def _load_script():
    """按文件路径加载 `import_laws.py`，并还原它 import 时改掉的 cwd。"""
    cwd = os.getcwd()
    spec = importlib.util.spec_from_file_location("_import_laws_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    return mod


def _entry(text: str, **over: str) -> dict:
    e = {
        "title": "受控测试法",
        "article_number": "第一千二百六十条",
        "content": text,
        "status": "现行",
        "effective_from": "2021-01-01",
    }
    e.update(over)
    return e


@pytest.fixture
def tmp_collection(monkeypatch, tmp_path):
    """临时 Chroma：把 `rag_chain.vectorstore` 换掉（预检读的就是这一个对象）。"""
    import chromadb

    import rag_chain

    client = chromadb.PersistentClient(
        path=str(tmp_path / "chroma"),
        settings=chromadb.Settings(anonymized_telemetry=False),
    )
    from langchain_chroma import Chroma

    vs = Chroma(collection_name="test_t2_preflight", embedding_function=FakeEmbeddings(), client=client)
    monkeypatch.setattr(rag_chain, "vectorstore", vs)
    return vs


def _seed(vs, page_content: str, metadata: dict) -> None:
    from langchain_core.documents import Document

    vs.add_documents([Document(page_content=page_content, metadata=metadata)])


# ════════ 单元腿：三个桶各自的措辞（判据 1 的"输入是真判据的产物"） ════════


def test_undated_legacy_coexist_is_warned_but_not_blocked():
    from law_versions import replaceable_version_ids

    plan = replaceable_version_ids(
        ["legacy"],
        [{"source": "受控测试法", "article": "第一千二百六十条", "origin": "upload"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        documents=[LEGACY_OLD],
        new_content=NEW_TEXT,
    )
    lines = _load_script().preflight_lines("受控测试法", "第一千二百六十条", plan)
    assert lines[0] == "  将替换 1 旧片段 + 新增：受控测试法 第一千二百六十条"
    assert lines[1] == "  ⚠️ 与 1 条无时效旧块并存（将被 T1 取代）：受控测试法 第一千二百六十条", lines
    assert len(lines) == 2, f"同版本可替换不该同时报'互不包含'：{lines}"


def test_non_contained_block_is_called_out():
    from law_versions import replaceable_version_ids

    plan = replaceable_version_ids(
        ["other"],
        [{"source": "受控测试法", "article": "第一千二百六十条", "origin": "upload"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        documents=["第九百条 完全不相干的另一套文字。"],
        new_content=NEW_TEXT,
    )
    (line0, line1) = _load_script().preflight_lines("受控测试法", "第一千二百六十条", plan)
    assert line0 == "  将替换 0 旧片段 + 新增：受控测试法 第一千二百六十条"
    assert "互不包含" in line1 and line1.startswith("  ✗"), line1


def test_no_warning_when_only_same_version_matches():
    """控制腿：同版本重传（现网最常见形态）⇒ 只有一行"将替换"，不许有 ⚠️。

    没有这条，上面那条 ⚠️ 可能只是因为"任何替换都会报"。
    """
    from law_versions import replaceable_version_ids

    plan = replaceable_version_ids(
        ["same"],
        [{"version_id": "lv-new", "origin": "upload"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        documents=[NEW_TEXT],
        new_content=NEW_TEXT,
    )
    lines = _load_script().preflight_lines("受控测试法", "第一千二百六十条", plan)
    assert lines == ["  将替换 1 旧片段 + 新增：受控测试法 第一千二百六十条"]


def test_import_laws_holds_no_second_copy_of_the_judgment():
    """判据 4 的机器化：T1 那三条判据的零件不许出现在预检脚本里。

    行号会被本文件的其他改动挤掉 ⇒ 用"符号是否出现"当断言，而不是数行号。
    """
    src = SCRIPT.read_text(encoding="utf-8")
    for needle in ("_LEGACY_REPLACEABLE_ORIGINS", "_norm_text", "stored_effective_from", "chroma:document"):
        assert needle not in src, f"预检里出现了第二份判据的零件：{needle}"


# ════════ 端点腿：真跑 main()，读真 Chroma ════════


def _run_main(monkeypatch, tmp_path, entries, *, extra_argv=()):
    mod = _load_script()
    path = tmp_path / "batch.json"
    path.write_text(json.dumps({"entries": entries}, ensure_ascii=False), encoding="utf-8")
    argv = ["import_laws.py", "--input", str(path), *extra_argv]
    monkeypatch.setattr(sys, "argv", argv)
    return mod


def test_dry_run_warns_and_exits_zero(monkeypatch, tmp_path, tmp_collection, capsys):
    """判据 2：真实形状的无时效遗留块在场 ⇒ 预检打 ⚠️，rc=0（`SystemExit` 不抛出 = 0）。"""
    _seed(tmp_collection, LEGACY_OLD, {"source": "受控测试法", "article": "第一千二百六十条", "origin": "upload"})
    mod = _run_main(monkeypatch, tmp_path, [_entry(NEW_TEXT)], extra_argv=("--dry-run",))
    mod.main()  # 不抛 SystemExit ⇒ rc=0
    out = capsys.readouterr().out
    assert "⚠️ 与 1 条无时效旧块并存（将被 T1 取代）" in out, out
    assert "互不包含" not in out, out


def test_non_contained_blocks_the_whole_batch_without_writing(monkeypatch, tmp_path, tmp_collection, capsys):
    """判据 3：互不包含 ⇒ rc=1，且**一条都不写**。

    "不写"用两只手各钉一遍：①`knowledge_service.add_text` 换成会炸的替身（真被调用就是失败）；
    ②集合条目数在调用前后不变。只钉 ① 的话，"根本没走到写"与"写了但被桩吞掉"分不开。
    """
    import knowledge_service as ks_mod

    _seed(tmp_collection, OTHER_TEXT, {"source": "受控测试法", "article": "第一千二百六十条", "origin": "upload"})
    before = len(tmp_collection.get()["ids"])

    def boom(*a, **k):  # noqa: ARG001
        raise AssertionError("互不包含的批次里居然调用了写入")

    monkeypatch.setattr(ks_mod, "add_text", boom)
    mod = _run_main(monkeypatch, tmp_path, [_entry(NEW_TEXT)])  # 不带 --dry-run：证明实跑模式同样先判后写
    with pytest.raises(SystemExit) as ex:
        mod.main()
    assert ex.value.code == 1, f"退出码不是 1：{ex.value.code}"
    assert len(tmp_collection.get()["ids"]) == before, "预检不通过却改了知识库"
    assert "整批未写入任何内容" in capsys.readouterr().out


def test_control_admitted_batch_reaches_the_writer(monkeypatch, tmp_path, tmp_collection):
    """对照组（防上一条是空枪）：判据全过的批次**确实**会走到写入，且带着算好的 extra。"""
    import knowledge_service as ks_mod

    seen: list[dict] = []
    monkeypatch.setattr(
        ks_mod,
        "add_text",
        lambda content, **kw: (seen.append({"content": content, **kw}), 1)[1],
    )
    mod = _run_main(monkeypatch, tmp_path, [_entry(NEW_TEXT)])
    mod.main()  # 无 SystemExit ⇒ rc=0
    assert seen and seen[0]["origin"] == "import", seen
    assert seen[0]["extra_meta"]["effective_from"] == "2021-01-01"
