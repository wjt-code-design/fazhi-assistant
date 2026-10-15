"""The file preflight validates a batch without opening the knowledge base."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_laws.py"
VALID = {
    "title": "受控测试法",
    "article_number": "第一条",
    "content": "受控测试条文内容。",
    "status": "已修改",
    "effective_from": "2020-01-01",
    "effective_to": "2020-12-31",
}


def _validate(tmp_path, entries):
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"entries": entries}, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "CHROMA_DIR": str(tmp_path / "should-not-exist"), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--validate-only", "--input", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    assert not (tmp_path / "should-not-exist").exists()
    return result


def test_file_only_preflight_accepts_valid_entry_without_knowledge_base(tmp_path):
    result = _validate(tmp_path, [VALID])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 条" in result.stdout


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"effective_from": "2026-02-30"}, "effective_from"),
        ({"effective_from": 20260101}, "effective_from"),
        ({"effective_from": "2026-1-1"}, "effective_from"),
        ({"effective_to": ""}, "effective_to"),
        ({"status": "已废止", "effective_to": ""}, "effective_to"),
        ({"status": "未生效", "effective_from": ""}, "effective_from"),
    ],
)
def test_file_only_preflight_rejects_invalid_entry_before_any_write(tmp_path, changes, expected):
    result = _validate(tmp_path, [VALID, {**VALID, **changes}])

    assert result.returncode != 0
    assert "校验通过" not in result.stdout
    assert "校验失败" in result.stdout
    assert expected in result.stdout


def test_file_only_preflight_reports_all_bad_entries(tmp_path):
    result = _validate(tmp_path, [{**VALID, "effective_to": ""}, {**VALID, "content": 42}])

    assert result.returncode != 0
    assert "2 条校验失败" in result.stdout
    assert "effective_to" in result.stdout
    assert "content" in result.stdout


def test_file_only_preflight_refuses_empty_batch(tmp_path):
    result = _validate(tmp_path, [])

    assert result.returncode != 0
    assert "空" in result.stdout


def test_file_only_preflight_reports_non_object_entry(tmp_path):
    result = _validate(tmp_path, [VALID, "不是条文对象"])

    assert result.returncode != 0
    assert "条目必须是对象" in result.stdout
