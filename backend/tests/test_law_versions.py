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

    # T1/T2 之后一次返回三个桶；既有"同一版本"语义的**选择结果**逐字不变。
    plan = replaceable_version_ids(ids, metadatas, version_id="lv-current", effective_from="2024-01-01")
    assert plan.replaceable == ["same", "legacy-same-date"]
    assert plan.coexist == ["older-version"]
    # "无 version_id 但日期相同"走的是改动前就有的那条分支，不该被记进遗留桶
    # （否则 T2 会把一次普通重传报成"与无时效旧块并存"）。
    assert plan.legacy_undated == []


# ── 票 T1：整个时效轴缺失的遗留块 ────────────────────────────────────────────────
# 形状照 §0 实测的那两对旧/新块：旧块带**章节行与全角空格**、新块是干净条文
# ⇒ 逐字相等恒 False，而去空白归一化后 新 ⊆ 旧。（构造样本；原文由 E7 那批核过。）
LEGACY_OLD = "第十章　建筑物和物件损害责任\n第一千二百六十条　本法自2021年1月1日起施行。"
LEGACY_NEW = "第一千二百六十条 本法自2021年1月1日起施行。"
LEGACY_META = {
    "source": "民法典",
    "article": "第一千二百六十条",
    "chapter": "第十章　建筑物和物件损害责任",
    "origin": "upload",
}


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
    """无版本日期的 upload 旧块仅多已知章节前缀，完整正文相同才可替换。"""
    plan = _call([dict(LEGACY_META)], docs=[LEGACY_OLD])
    assert plan.replaceable == ["d0"]
    assert plan.coexist == []
    assert plan.legacy_undated == ["d0"], "T2 的 ⚠️ 只数这一桶 ⇒ 落错桶等于不报警"

    # 原始字符串不等，但差异仅为元数据中已知的章节前缀与空白。
    assert LEGACY_NEW != LEGACY_OLD


def test_undated_legacy_copy_is_not_replaced_by_truncated_article():
    old = "第一条 当事人应履行约定义务。法律另有规定的除外。"
    new = "当事人应履行约定义务。"
    plan = _call([{"origin": "upload", "article": "第一条"}], docs=[old], new_content=new)
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_missing_new_date_does_not_bypass_complete_body_check():
    plan = _call(
        [{"origin": "upload", "article": "第一条"}],
        docs=["第一条 当事人应履行约定义务。法律另有规定的除外。"],
        new_content="当事人应履行约定义务。",
        effective_from="",
    )
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_empty_version_ids_do_not_bypass_complete_body_check():
    plan = _call(
        [{"origin": "upload", "article": "第一条"}],
        docs=["第一条 当事人应履行约定义务。法律另有规定的除外。"],
        new_content="当事人应履行约定义务。",
        version_id="",
        effective_from="",
    )
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_derived_version_id_without_dates_does_not_delete_different_body():
    from law_versions import derive_version_id

    version_id = derive_version_id("民法典", "第一条", "")
    plan = _call(
        [{"origin": "manual", "article": "第一条", "version_id": version_id}],
        docs=["第一条 当事人应履行约定义务。法律另有规定的除外。"],
        new_content="第一条 当事人应履行约定义务。",
        version_id=version_id,
        effective_from="",
    )
    assert plan.replaceable == []
    assert plan.conflicts == ["d0"]


def test_same_version_id_never_deletes_seed():
    plan = _call(
        [{"origin": "seed", "article": "第一条", "version_id": "lv-new", "effective_from": "2021-01-01"}],
        docs=["第一条 原始条文。"],
        new_content="第一条 修改条文。",
    )
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_undated_legacy_copy_requires_known_prefix():
    old = "另一条不能随旧片段删除。\n第一条 当事人应履行约定义务。"
    plan = _call(
        [{"origin": "upload", "article": "第一条"}],
        docs=[old],
        new_content="当事人应履行约定义务。",
    )
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_nonoverlapping_dated_versions_are_compatible():
    plan = replaceable_version_ids(
        ["old"],
        [{"version_id": "lv-old", "effective_from": "2020-01-01", "effective_to": "2020-12-31"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        new_content="同一条文正文",
    )
    assert plan.replaceable == []
    assert plan.coexist == ["old"]
    assert plan.compatible_versions == ["old"]
    assert plan.conflicts == []


def test_old_end_before_new_start_is_compatible_without_old_start():
    plan = replaceable_version_ids(
        ["old"],
        [{"version_id": "lv-old", "effective_to": "2020-12-31"}],
        version_id="lv-new",
        effective_from="2021-01-01",
        new_content="同一条文正文",
    )
    assert plan.replaceable == []
    assert plan.compatible_versions == ["old"]
    assert plan.conflicts == []


@pytest.mark.parametrize("old_end", ["2021-01-01", "2021-12-31", "", "not-a-date", "2019-12-31"])
def test_overlapping_or_unverifiable_dated_versions_still_conflict(old_end):
    plan = replaceable_version_ids(
        ["overlap"],
        [{"version_id": "lv-old", "effective_from": "2020-01-01", "effective_to": old_end}],
        version_id="lv-new",
        effective_from="2021-01-01",
        new_content="同一条文正文",
    )
    assert plan.conflicts == ["overlap"]


def test_replaceable_is_exactly_the_two_replacement_buckets():
    """形状不变量：`replaceable == same_version + legacy_undated`，且与 coexist 不相交。

    拆桶是为了给消费者报数，但**删除面**只能有一个来源 —— 这条守的是"两个桶各删各的/漏一个桶"的漂移。
    """
    plan = _call(
        [
            {"version_id": "lv-new", "effective_from": "2021-01-01"},
            dict(LEGACY_META),
            {"version_id": "lv-x", "origin": "upload"},
        ],
        docs=[LEGACY_NEW, LEGACY_OLD, LEGACY_OLD],
    )
    assert plan.same_version == ["d0"]
    assert plan.legacy_undated == ["d1"]
    assert plan.replaceable == ["d0", "d1"]
    assert plan.coexist == ["d2"]


def test_non_contained_text_is_not_deleted_but_reported():
    """判据 2：正文互不包含 ⇒ 不进可替换，且**必须**出现在并存桶里（不许静默）。"""
    plan = _call([dict(LEGACY_META)], docs=["第一千二百五十九条 别的条文。"])
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_seed_origin_untouched():
    """判据 3：`origin='seed'` 的无日期旧块不碰（它归 `knowledge_base.py` 重建管）。

    ⚠️ 别和 `_seed_conflict()` 混成一件事：那句主语是"进来的这条要不要处理"，本句是"哪些旧副本可删"。
    """
    plan = _call([{**LEGACY_META, "origin": "seed"}], docs=[LEGACY_OLD])
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_dated_legacy_with_different_effective_from_still_coexists():
    """判据 4：已有**带日期**旧块且日期不同 ⇒ 仍是"修订版并存"，不因新分支被吞掉（现有语义不许回归）。"""
    plan = _call([{**LEGACY_META, "effective_from": "2018-01-01"}], docs=[LEGACY_OLD])
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_effective_to_alone_blocks_the_legacy_branch():
    """时效轴的**任一半**存在就不算"整个缺失"：只有 effective_to 的旧块（废止版）也进并存。"""
    plan = _call([{**LEGACY_META, "effective_to": "2020-12-31"}], docs=[LEGACY_OLD])
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_missing_new_content_fails_safe_to_coexist():
    """调用方没传正文 ⇒ 不许猜"能删"：判不出包含就进并存列表（误删条文比留双胞胎严重）。"""
    plan = _call([dict(LEGACY_META)], docs=[LEGACY_OLD], new_content="")
    assert plan.replaceable == []
    assert plan.coexist == ["d0"]


def test_document_falls_back_to_chroma_metadata_key():
    """不传 `documents` 时回退 Chroma 塞进 metadata 的 `chroma:document`（票面点名的回退源）。"""
    plan = _call([{**LEGACY_META, "chroma:document": LEGACY_OLD}])
    assert (plan.replaceable, plan.coexist) == (["d0"], [])


def test_admin_input_rejects_reversed_validity_period():
    with pytest.raises(ValidationError, match="effective_to 不能早于 effective_from"):
        KnowledgeAddIn(
            title="示例法",
            article="第一条",
            content="条文",
            effective_from="2024-01-02",
            effective_to="2024-01-01",
        )


@pytest.mark.parametrize("effective_from", [None, ""])
def test_admin_input_requires_effective_from_for_articles(effective_from):
    with pytest.raises(ValidationError, match="填写条文时必须提供施行日期"):
        KnowledgeAddIn(
            title="示例法",
            article="第一条",
            content="条文",
            effective_from=effective_from,
        )


def test_admin_input_allows_missing_effective_from_without_article():
    assert KnowledgeAddIn(title="一般知识", content="正文").effective_from is None
