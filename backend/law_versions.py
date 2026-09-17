"""Pure helpers for immutable, traceable law-version metadata."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence


def source_document_sha256(content: str) -> str:
    """Hash the exact UTF-8 source text stored for one legal provision."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def derive_version_id(title: str, article: str, effective_from: str) -> str:
    """Return a stable identity for one provision version.

    Content is deliberately excluded: correcting transcription without changing
    the legal effective date must replace that version, not create an overlap.
    """
    identity = "\0".join((title.strip(), article.strip(), effective_from.strip()))
    return "lv-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def version_metadata(entry: dict[str, object], *, title: str, article: str, content: str) -> dict[str, str]:
    """Normalize non-secret provenance fields into Chroma-compatible strings."""
    effective_from = str(entry.get("effective_from") or "").strip()
    return {
        "version_id": str(entry.get("version_id") or derive_version_id(title, article, effective_from)).strip(),
        "promulgated_at": str(entry.get("promulgated_at") or "").strip(),
        "effective_from": effective_from,
        "effective_to": str(entry.get("effective_to") or "").strip(),
        "status": str(entry.get("status") or "现行").strip(),
        "source_url": str(entry.get("source_url") or "").strip(),
        "source_document_sha256": str(entry.get("source_document_sha256") or source_document_sha256(content)).strip(),
        "supersedes_version_id": str(entry.get("supersedes_version_id") or "").strip(),
        "reviewed_at": str(entry.get("reviewed_at") or "").strip(),
    }


def replaceable_version_ids(
    ids: Sequence[str],
    metadatas: Sequence[dict[str, object] | None],
    *,
    version_id: str,
    effective_from: str,
) -> list[str]:
    """Select only the same version, including its pre-versioning legacy copy."""
    replaceable: list[str] = []
    for doc_id, metadata in zip(ids, metadatas, strict=False):
        meta = metadata or {}
        stored_version_id = str(meta.get("version_id") or "").strip()
        stored_effective_from = str(meta.get("effective_from") or "").strip()
        if stored_version_id == version_id or (not stored_version_id and stored_effective_from == effective_from):
            replaceable.append(doc_id)
    return replaceable
