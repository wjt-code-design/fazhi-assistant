"""Pure helpers for immutable, traceable law-version metadata."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

# 「版本化之前的遗留副本」允许被新版取代的来源。`seed` 不在里面 —— 它归 `knowledge_base.py` 重建管。
_LEGACY_REPLACEABLE_ORIGINS = ("upload", "manual")


def _norm_text(text: str) -> str:
    """去空白归一化。

    ⚠️ `\\s` 在 Python 3 里**本来就覆盖全角空格 U+3000**，所以 `\\u3000` 只是写给人看的意图注释，
    删掉它不是行为变化（实测：`re.match(r'\\s','　')` 为 True）。别把它当可测性 —— 票 T1 判据 5 的
    前一个版本就因为这条假变异作废过。
    """
    return re.sub(r"[\s　]+", "", text or "")


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
        "status": str(entry.get("status") or "未验证").strip(),
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
    documents: Sequence[str | None] = (),
    new_content: str = "",
) -> tuple[list[str], list[str]]:
    """一次遍历返回两半：`(可替换的旧块 id, 需报警的并存块 id)`。

    拆成两次遍历必然漂移，所以两半出自同一个判断。此前只返回第一半 ⇒ 第二半在预检里**完全静默**
    （票 T2 要的就是它）。

    可替换 = ①**同一版本**：`version_id` 相同，或"版本化之前的遗留副本"（无 `version_id` 且
    `effective_from` 相同）；②**整个时效轴缺失的遗留块**（票 T1 新增）：无 `version_id`、
    `effective_from` 与 `effective_to` 皆空、`origin ∈ {upload, manual}`，**且**新正文归一化后
    被旧正文包含。
    ②为什么用"包含"而不是"逐字相等"：§0 实测两对旧/新块 `exact_equal` 全 False（旧块带章节行与
    条号前缀）⇒ 精确相等这条分支在本库**永不触发**，等于没修。
    其余（带日期而日期不同、正文互不包含、`origin` 不在白名单）一律进并存列表 ⇒ 不删、但要说。
    """
    replaceable: list[str] = []
    coexist: list[str] = []
    new_norm = _norm_text(new_content)
    docs = list(documents)
    for i, (doc_id, metadata) in enumerate(zip(ids, metadatas, strict=False)):
        meta = metadata or {}
        stored_version_id = str(meta.get("version_id") or "").strip()
        stored_effective_from = str(meta.get("effective_from") or "").strip()
        stored_effective_to = str(meta.get("effective_to") or "").strip()
        if stored_version_id == version_id or (not stored_version_id and stored_effective_from == effective_from):
            replaceable.append(doc_id)
            continue
        # 正文优先取 `documents`，回退 Chroma 塞进 metadata 的那份（`chroma:document`）。
        stored_text = docs[i] if i < len(docs) else meta.get("chroma:document")
        origin = str(meta.get("origin") or "").strip()
        undated = not stored_effective_from and not stored_effective_to
        contained = bool(new_norm) and new_norm in _norm_text(str(stored_text or ""))
        if not stored_version_id and undated and origin in _LEGACY_REPLACEABLE_ORIGINS and contained:
            replaceable.append(doc_id)
        else:
            coexist.append(doc_id)
    return replaceable, coexist
