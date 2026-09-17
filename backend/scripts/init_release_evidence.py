"""Create a new BLOCKED Legal Agent release-evidence directory from safe templates."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_TEMPLATE_NAMES = (
    "release-manifest.template.json",
    "release-policy.template.json",
    "capture-protocol.template.json",
    "agent-audit.template.json",
)


def _template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "docs" / "release-evidence"


def initialize_release_evidence(output: Path, *, release_id: str) -> list[Path]:
    """Create templates only; the result is intentionally not release-valid evidence."""
    if not _RELEASE_ID.fullmatch(release_id):
        raise ValueError("release_id must be an opaque identifier of at most 100 ASCII characters")
    if output.exists():
        raise FileExistsError(output)
    template_dir = _template_dir()
    source_files = [template_dir / name for name in _TEMPLATE_NAMES]
    if any(not path.is_file() for path in source_files):
        raise ValueError("release-evidence templates are unavailable")
    output.mkdir(parents=True)
    created: list[Path] = []
    replacements = {
        "release-manifest.template.json": ("release-manifest.json", "legal-agent-v1-YYYYMMDD-NNN"),
        "release-policy.template.json": ("release-policy.json", "legal-agent-v1-YYYYMMDD-NNN"),
        "capture-protocol.template.json": ("capture-protocol.json", "legal-agent-dual-run-YYYYMMDD-NNN"),
        "agent-audit.template.json": ("agent-audit.json", None),
    }
    for source in source_files:
        destination_name, placeholder = replacements[source.name]
        content = source.read_text(encoding="utf-8")
        if placeholder is not None:
            content = content.replace(placeholder, release_id)
        destination = output / destination_name
        destination.write_text(content, encoding="utf-8", newline="\n")
        created.append(destination)
    status = output / "STATUS.md"
    status.write_text(
        "# BLOCKED — template directory only\n\n"
        "This directory contains placeholders, not release evidence. Do not run a release check or claim approval "
        "until a human has provided the frozen cases, de-identified answers, real hashes, and independent audit.\n",
        encoding="utf-8",
        newline="\n",
    )
    created.append(status)
    return created


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new BLOCKED Legal Agent evidence template directory.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--release-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        created = initialize_release_evidence(args.output, release_id=args.release_id)
    except (FileExistsError, ValueError, OSError) as exc:
        print(f"cannot initialize release evidence: {exc}", file=sys.stderr)
        return 2
    print("\n".join(str(path) for path in created))
    return 0


if __name__ == "__main__":
    sys.exit(main())
