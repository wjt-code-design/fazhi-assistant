import json

import pytest
from pydantic import ValidationError

from scripts.capture_protocol import load_capture_protocol


def _payload():
    return {
        "schema_version": "legal-agent-capture-protocol/v1",
        "protocol_id": "dual-run-001",
        "case_set_sha256": "a" * 64,
        "modes": ["existing_rag", "agent"],
        "controls": {
            "timeout_seconds": 90,
            "total_timeout_seconds": 3600,
            "max_retries": 1,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "offline",
            "max_output_tokens": 4096,
            "max_tool_calls": 8,
            "retain_failure_rows": True,
        },
    }


def test_capture_protocol_freezes_equal_dual_run_controls_and_retains_failures(tmp_path):
    path = tmp_path / "capture-protocol.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")
    protocol, _ = load_capture_protocol(path)
    assert protocol.modes == ["existing_rag", "agent"]
    assert protocol.controls.retain_failure_rows is True


def test_capture_protocol_rejects_silent_failure_exclusion_or_invalid_timeout(tmp_path):
    path = tmp_path / "capture-protocol.json"
    payload = _payload()
    payload["controls"]["retain_failure_rows"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_capture_protocol(path)
