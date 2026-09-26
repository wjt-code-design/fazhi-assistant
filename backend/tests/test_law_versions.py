import pytest
from pydantic import ValidationError

from law_versions import replaceable_version_ids, version_metadata
from schemas import KnowledgeAddIn


def test_version_identity_is_stable_for_transcription_correction():
    first = version_metadata({"effective_from": "2024-01-01"}, title="示例法", article="第一条", content="旧录入文本")
    corrected = version_metadata(
        {"effective_from": "2024-01-01"}, title="示例法", article="第一条", content="修正录入文本"
    )

    assert first["version_id"] == corrected["version_id"]
    assert first["source_document_sha256"] != corrected["source_document_sha256"]


def test_new_effective_date_creates_new_version():
    old = version_metadata({"effective_from": "2020-01-01"}, title="示例法", article="第一条", content="旧法条")
    new = version_metadata({"effective_from": "2024-01-01"}, title="示例法", article="第一条", content="新法条")

    assert old["version_id"] != new["version_id"]


def test_replacement_keeps_other_effective_versions():
    ids = ["same", "legacy-same-date", "older-version"]
    metadatas = [
        {"version_id": "lv-current", "effective_from": "2024-01-01"},
        {"effective_from": "2024-01-01"},
        {"version_id": "lv-old", "effective_from": "2020-01-01"},
    ]

    # 票 T1 之后函数一次返回两半：可替换的 / 需报警的并存。既有"同一版本"语义逐字不变。
    assert replaceable_version_ids(ids, metadatas, version_id="lv-current", effective_from="2024-01-01") == (
        ["same", "legacy-same-date"],
        ["older-version"],
    )


# ── 票 T1：整个时效轴缺失的遗留块 ────────────────────────────────────────────────
# 形状照 §0 实测的那两对旧/新块：旧块带**章节行与全角空格**、新块是干净条文
# ⇒ 逐字相等恒 False，而去空白归一化后 新 ⊆ 旧。（构造样本；原文由 E7 那批核过。）
LEGACY_OLD = "第十章　建筑物和物件损害责任\n第一千二百六十条　本法自2021年1月1日起施行。"
LEGACY_NEW = "第一千二百六十条 本法自2021年1月1日起施行。"
LEGACY_META = {"source": "民法典", "article": "第一千二百六十条", "origin": "upload"}


def _call(metas, docs=(), new_content=LEGACY_NEW, version_id="lv-new", effective_from="2021-01-01"):
    return replaceable_version_ids(
        [f"d{i}" for i in range(len(metas))],
        metas,
        version_id=version_id,
        effective_from=effective_from,
        documents=docs,
        new_content=new_content,
    )


def test_undated_legacy_copy_is_replaceable_when_text_is_contained():
    """判据 1：无 version_id + 两日期皆空 + origin=upload + 新 ⊆ 旧 ⇒ 可替换，且并存列表为空。"""
    replaceable, coexist = _call([dict(LEGACY_META)], docs=[LEGACY_OLD])
    assert replaceable == ["d0"]
    assert coexist == []

    # 这条分支**只能**靠包含成立：旧块带章节行 ⇒ 逐字相等恒 False（票面"已被否掉的想当然修法"）。
    assert LEGACY_NEW != LEGACY_OLD


def test_non_contained_text_is_not_deleted_but_reported():
    """判据 2：正文互不包含 ⇒ 不进可替换，且**必须**出现在并存列表里（不许静默）。"""
    replaceable, coexist = _call([dict(LEGACY_META)], docs=["第一千二百五十九条 别的条文。"])
    assert replaceable == []
    assert coexist == ["d0"]


def test_seed_origin_untouched():
    """判据 3：`origin='seed'` 的无日期旧块不碰（它归 `knowledge_base.py` 重建管）。

    ⚠️ 别和 `_seed_conflict()` 混成一件事：那句主语是"进来的这条要不要处理"，本句是"哪些旧副本可删"。
    """
    replaceable, coexist = _call([{**LEGACY_META, "origin": "seed"}], docs=[LEGACY_OLD])
    assert replaceable == []
    assert coexist == ["d0"]


def test_dated_legacy_with_different_effective_from_still_coexists():
    """判据 4：已有**带日期**旧块且日期不同 ⇒ 仍是"修订版并存"，不因新分支被吞掉（现有语义不许回归）。"""
    replaceable, coexist = _call([{**LEGACY_META, "effective_from": "2018-01-01"}], docs=[LEGACY_OLD])
    assert replaceable == []
    assert coexist == ["d0"]


def test_effective_to_alone_blocks_the_legacy_branch():
    """时效轴的**任一半**存在就不算"整个缺失"：只有 effective_to 的旧块（废止版）也进并存。"""
    replaceable, coexist = _call([{**LEGACY_META, "effective_to": "2020-12-31"}], docs=[LEGACY_OLD])
    assert replaceable == []
    assert coexist == ["d0"]


def test_missing_new_content_fails_safe_to_coexist():
    """调用方没传正文 ⇒ 不许猜"能删"：判不出包含就进并存列表（误删条文比留双胞胎严重）。"""
    replaceable, coexist = _call([dict(LEGACY_META)], docs=[LEGACY_OLD], new_content="")
    assert replaceable == []
    assert coexist == ["d0"]


def test_document_falls_back_to_chroma_metadata_key():
    """不传 `documents` 时回退 Chroma 塞进 metadata 的 `chroma:document`（票面点名的回退源）。"""
    replaceable, coexist = _call([{**LEGACY_META, "chroma:document": LEGACY_OLD}])
    assert (replaceable, coexist) == (["d0"], [])


def test_admin_input_rejects_reversed_validity_period():
    with pytest.raises(ValidationError, match="effective_to 不能早于 effective_from"):
        KnowledgeAddIn(
            title="示例法",
            article="第一条",
            content="条文",
            effective_from="2024-01-02",
            effective_to="2024-01-01",
        )
