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

    assert replaceable_version_ids(ids, metadatas, version_id="lv-current", effective_from="2024-01-01") == [
        "same",
        "legacy-same-date",
    ]


def test_admin_input_rejects_reversed_validity_period():
    with pytest.raises(ValidationError, match="effective_to 不能早于 effective_from"):
        KnowledgeAddIn(
            title="示例法",
            article="第一条",
            content="条文",
            effective_from="2024-01-02",
            effective_to="2024-01-01",
        )
