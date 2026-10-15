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
from types import SimpleNamespace

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
        [
            {
                "source": "受控测试法",
                "article": "第一千二百六十条",
                "chapter": "第十章　建筑物和物件损害责任",
                "origin": "upload",
            }
        ],
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
    assert "未判定冲突" in line1 and line1.startswith("  ✗"), line1


def test_overlapping_dated_version_is_reported_as_time_conflict():
    from law_versions import replaceable_version_ids

    plan = replaceable_version_ids(
        ["overlap"],
        [{"version_id": "lv-old", "effective_from": "2020-01-01", "effective_to": "2021-12-31"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        new_content=NEW_TEXT,
    )
    lines = _load_script().preflight_lines("受控测试法", "第一千二百六十条", plan)
    assert any("时效重叠或不明" in line for line in lines)
    assert all("互不包含" not in line for line in lines)


def test_no_warning_when_only_same_version_matches():
    """控制腿：同版本重传（现网最常见形态）⇒ 只有一行"将替换"，不许有 ⚠️。

    没有这条，上面那条 ⚠️ 可能只是因为"任何替换都会报"。
    """
    from law_versions import replaceable_version_ids

    plan = replaceable_version_ids(
        ["same"],
        [{"version_id": "lv-new", "effective_from": "2021-01-01", "origin": "upload"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        documents=[NEW_TEXT],
        new_content=NEW_TEXT,
    )
    lines = _load_script().preflight_lines("受控测试法", "第一千二百六十条", plan)
    assert lines == ["  将替换 1 旧片段 + 新增：受控测试法 第一千二百六十条"]


# 同版本重传的"改错字"形状：法名/条号/生效日都不动 ⇒ `derive_version_id` 不变 ⇒ 判据落在
# `same_version` 支（可替换），与"正文包含不含"无关（票 T5）。
SAME_VERSION_OLD = "第一千二百六十条　本法自2021年1月1日起施行。订正前的旧文本。"


def test_same_version_retransmit_really_removes_the_old_block(monkeypatch, tmp_path, tmp_collection, capsys):
    """票 T5：`origin="import"` 的删旧接线跑到**真写库**那一步，旧块确实消失。

    分工要说清（不是"此前无人守"）：删旧**行为**在 `add_text` 层已有一条非 slow 对照腿守着
    （`test_knowledge_service.py::test_version_judgment_crash_keeps_old_chunk_and_stays_visible`
    的"判据正常时旧块应被替换"那一腿，变异 M1 同时杀它与本用例）。本用例补的是**从脚本走进那条
    接线**的端到端腿 —— 此前只有 `test_import_docs.py` 的 slow 用例沾边，而那两条删的是
    `import_docs` 自己的 seed 碎片与 file_hash 重传，压根不经过 `import_laws.main()`。

    真跑 `main()`（不带 `--dry-run`）→ 真写进临时 Chroma → 断言旧 id 不在集合里。

    删"干净"不等于删"对"：所以活着的那一条要按**新块自己的指纹**钉，而不是只数条目数 ——
    只数条目的话，"删了新留了旧"同样绿。同理，播报行（"将替换 1 旧片段"）在删旧接线断开时
    **仍然会打印**，所以它不能当判据，只当"确实走到了分类"的前置证据。
    """
    import knowledge_service as ks_mod
    from law_versions import derive_version_id, source_document_sha256

    title, article = "受控测试法", "第一千二百六十条"
    vid = derive_version_id(title, article, "2021-01-01")
    _seed(
        tmp_collection,
        SAME_VERSION_OLD,
        {
            "source": title,
            "article": article,
            "origin": "import",
            "version_id": vid,
            "effective_from": "2021-01-01",
            "effective_to": "",
        },
    )
    monkeypatch.setattr(ks_mod, "vectorstore", tmp_collection)
    old_id = tmp_collection._collection.get(where={"$and": [{"source": title}, {"article": article}]})["ids"][0]

    mod = _run_main(monkeypatch, tmp_path, [_entry(NEW_TEXT)])
    mod.main()  # 不抛 SystemExit ⇒ rc=0
    out = capsys.readouterr().out
    assert "将替换 1 旧片段" in out, out

    left = tmp_collection._collection.get(
        where={"$and": [{"source": title}, {"article": article}]}, include=["metadatas", "documents"]
    )
    assert old_id not in left["ids"], f"旧块没被删，还在库里：{old_id} ∈ {left['ids']}"
    assert len(left["ids"]) == 1, f"同版本重传留下了双胞胎：{left['ids']}"
    assert left["metadatas"][0]["source_document_sha256"] == source_document_sha256(NEW_TEXT), (
        "活着的那一条不是新块（删错了对象）"
    )
    assert left["metadatas"][0]["version_id"] == vid
    assert left["metadatas"][0]["effective_from"] == "2021-01-01"
    assert left["metadatas"][0]["origin"] == "import"
    assert left["documents"] == [NEW_TEXT], "库里活着的那条正文不是新文本"


@pytest.mark.parametrize("origin", ["seed", "upload"])
def test_seed_conflict_is_named_and_kept_out_of_the_batch(monkeypatch, tmp_path, tmp_collection, capsys, origin):
    """票 T5：seed 冲突跳过路径缺测试 —— 补上，并配一条只差 `origin` 的对照腿。

    两腿的旧块除 `origin` 外逐字相同（同 version_id、同生效日），所以"跳过 / 不跳过"这个差别
    **只能由 `_seed_conflict` 认 seed 产生**。没有 upload 那一腿，"跳过 1 条"可能只是因为
    脚本压根不进分类循环。

    ⚠️ 关于"没有写入"：`--dry-run` 下任何一条都不写 ⇒ 单看条目数没有信息量。本用例钉的是
    "被跳过的条目不进新增清单"（`新增 0 条` vs 对照腿的 `新增 1 条`）；"整批不写入"那种
    实跑形状由 `test_non_contained_blocks_the_whole_batch_without_writing` 的 boom 桩负责。

    rc 先记下再断言（不让 `SystemExit` 直接穿出）：pytest 只报**第一条**失败断言，
    裸 `SystemExit: 1` 说不出"是哪条规则红了"，换成有名字的 rc 断言才归因得清。
    """
    import knowledge_service as ks_mod
    from law_versions import derive_version_id

    title, article = "受控测试法", "第一千二百六十条"
    _seed(
        tmp_collection,
        NEW_TEXT,
        {
            "source": title,
            "article": article,
            "origin": origin,
            "version_id": derive_version_id(title, article, "2021-01-01"),
            "effective_from": "2021-01-01",
            "effective_to": "",
        },
    )
    monkeypatch.setattr(ks_mod, "vectorstore", tmp_collection)
    before = tmp_collection._collection.get()["ids"]

    mod = _run_main(monkeypatch, tmp_path, [_entry(NEW_TEXT)], extra_argv=("--dry-run",))
    rc = 0
    try:
        mod.main()
    except SystemExit as ex:
        rc = ex.code
    out = capsys.readouterr().out

    skip_line = f"  跳过（与种子冲突，请改 laws.json 后重建）：{title} {article}"
    if origin == "seed":
        assert rc == 0, f"seed 冲突该被点名跳过、不阻断整批，却退出 rc={rc}：\n{out}"
        assert skip_line in out, f"seed 冲突没被点名跳过（缺法名/条号）：\n{out}"
        assert "新增 0 条" in out and "跳过 1 条" in out, out
        assert "将替换" not in out, f"跳过的条目又被送去分类了：{out}"
    else:
        assert rc == 0, f"只差 origin 的对照腿被阻断了（rc={rc}）⇒ 跳过判定不认 origin：\n{out}"
        assert skip_line not in out, f"非 seed 的旧块也被点名跳过了：\n{out}"
        assert "新增 1 条" in out and "跳过 0 条" in out, out
        assert "将替换 1 旧片段" in out, out
    assert tmp_collection._collection.get()["ids"] == before, "dry-run 动了知识库"


def test_seed_conflict_finds_seed_after_upload():
    matches = {"upload-id": {"origin": "upload"}, "seed-id": {"origin": "seed"}}

    def get(*, where=None, ids=None, include=None):
        found = ["upload-id", "seed-id"] if where is not None else ids
        return {"ids": found, "metadatas": [matches[item] for item in found]}

    vectorstore = SimpleNamespace(_collection=SimpleNamespace(get=get))
    assert _load_script()._seed_conflict(vectorstore, "受控测试法", "第一千二百六十条")


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
    _seed(
        tmp_collection,
        LEGACY_OLD,
        {
            "source": "受控测试法",
            "article": "第一千二百六十条",
            "chapter": "第十章　建筑物和物件损害责任",
            "origin": "upload",
        },
    )
    mod = _run_main(monkeypatch, tmp_path, [_entry(NEW_TEXT)], extra_argv=("--dry-run",))
    mod.main()  # 不抛 SystemExit ⇒ rc=0
    out = capsys.readouterr().out
    assert "⚠️ 与 1 条无时效旧块并存（将被 T1 取代）" in out, out
    assert "互不包含" not in out, out


def test_writer_keeps_complete_legacy_article_when_new_text_is_truncated(monkeypatch, tmp_collection):
    import knowledge_service as ks_mod

    title, article = "受控测试法", "第一千二百六十条"
    old = f"{article} 本法自2021年1月1日起施行。附则另有规定。"
    new = f"{article} 本法自2021年1月1日起施行。"
    _seed(tmp_collection, old, {"source": title, "article": article, "origin": "upload"})
    old_id = tmp_collection._collection.get()["ids"][0]
    monkeypatch.setattr(ks_mod, "vectorstore", tmp_collection)

    assert (
        ks_mod.add_text(
            new, source=title, article=article, origin="import", extra_meta={"effective_from": "2021-01-01"}
        )
        == 1
    )
    left = tmp_collection._collection.get(where={"$and": [{"source": title}, {"article": article}]})["ids"]
    assert old_id in left
    assert len(left) == 2


@pytest.mark.parametrize(
    ("old_start", "old_end", "new_start", "new_end"),
    [
        ("2020-01-01", "2020-12-31", "2021-01-01", ""),
        ("2021-01-01", "", "2020-01-01", "2020-12-31"),
    ],
)
def test_dry_run_keeps_nonoverlapping_historical_version(
    monkeypatch, tmp_path, tmp_collection, capsys, old_start, old_end, new_start, new_end
):
    _seed(
        tmp_collection,
        NEW_TEXT,
        {
            "source": "受控测试法",
            "article": "第一千二百六十条",
            "origin": "import",
            "version_id": "lv-old",
            "effective_from": old_start,
            "effective_to": old_end,
        },
    )
    mod = _run_main(
        monkeypatch,
        tmp_path,
        [_entry(NEW_TEXT, effective_from=new_start, effective_to=new_end)],
        extra_argv=("--dry-run",),
    )
    mod.main()
    out = capsys.readouterr().out
    assert "保留 1 条不重叠历史版本" in out
    assert "互不包含" not in out
    assert len(tmp_collection.get()["ids"]) == 1


@pytest.mark.parametrize("second_start", ["2020-01-01", "2021-01-01"])
def test_same_article_batch_duplicate_or_overlap_blocks_before_writing(
    monkeypatch, tmp_path, tmp_collection, capsys, second_start
):
    import knowledge_service as ks_mod

    def unexpected_write(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("冲突批次不应开始写入")

    monkeypatch.setattr(ks_mod, "add_text", unexpected_write)
    entries = [_entry(NEW_TEXT, effective_from="2020-01-01"), _entry(OTHER_TEXT, effective_from=second_start)]
    mod = _run_main(monkeypatch, tmp_path, entries)
    with pytest.raises(SystemExit) as ex:
        mod.main()
    assert ex.value.code == 1
    assert tmp_collection._collection.count() == 0
    assert "整批未写入任何内容" in capsys.readouterr().out


def test_same_article_batch_with_separate_periods_passes_dry_run(monkeypatch, tmp_path, tmp_collection, capsys):
    entries = [
        _entry(NEW_TEXT, effective_from="2020-01-01", effective_to="2020-12-31"),
        _entry(OTHER_TEXT, effective_from="2021-01-01"),
    ]
    mod = _run_main(monkeypatch, tmp_path, entries, extra_argv=("--dry-run",))
    mod.main()
    assert "预检完成" in capsys.readouterr().out
    assert tmp_collection._collection.count() == 0


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
    assert (seen[0]["extra_meta"] or {}).get("effective_from") == "2021-01-01", (
        f"脚本没把算好的版本元数据交给写入器：extra_meta={seen[0]['extra_meta']!r}"
    )
