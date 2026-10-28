"""Safe release-evidence directory initialization contracts."""

import json

import pytest

from scripts.init_release_evidence import initialize_release_evidence


def test_initializer_creates_only_blocked_templates(tmp_path):
    output = tmp_path / "legal-agent-v1-20260903-001"

    created = initialize_release_evidence(output, release_id="legal-agent-v1-20260903-001")

    assert {path.name for path in created} == {
        "release-manifest.json",
        "release-policy.json",
        "capture-protocol.json",
        "agent-audit.json",
        "STATUS.md",
    }
    assert (
        json.loads((output / "release-manifest.json").read_text(encoding="utf-8"))["release_id"]
        == "legal-agent-v1-20260903-001"
    )
    assert "BLOCKED" in (output / "STATUS.md").read_text(encoding="utf-8")
    assert not (output / "agent-capture.json").exists()


def test_initializer_refuses_existing_directory_and_invalid_id(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()

    with pytest.raises(FileExistsError):
        initialize_release_evidence(output, release_id="legal-agent-v1-20260903-001")
    with pytest.raises(ValueError):
        initialize_release_evidence(tmp_path / "new", release_id="unsafe\nrelease-id")
