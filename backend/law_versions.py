"""Pure helpers for immutable, traceable law-version metadata."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import date
from typing import NamedTuple

# 「版本化之前的遗留副本」允许被新版取代的来源。`seed` 不在里面 —— 它归 `knowledge_base.py` 重建管。
_LEGACY_REPLACEABLE_ORIGINS = ("upload", "manual")


def _norm_text(text: str) -> str:
    """去空白归一化。

    ⚠️ `\\s` 在 Python 3 里**本来就覆盖全角空格 U+3000**，所以 `\\u3000` 只是写给人看的意图注释，
    删掉它不是行为变化（实测：`re.match(r'\\s','　')` 为 True）。别把它当可测性 —— 票 T1 判据 5 的
    前一个版本就因为这条假变异作废过。
    """
    return re.sub(r"[\s　]+", "", text or "")


def _same_article_body(stored_text: str, new_content: str, meta: dict[str, object]) -> bool:
    """Only known chapter/article prefixes may differ from the replacement body."""
    article = _norm_text(str(meta.get("article") or ""))
    lines = stored_text.strip().splitlines()
    chapter = _norm_text(str(meta.get("chapter") or ""))
    if chapter and lines and _norm_text(lines[0]) == chapter:
        lines.pop(0)
    old_text = _norm_text("\n".join(lines))
    new_text = _norm_text(new_content)
    if not article or not old_text.startswith(article):
        return False
    if new_text.startswith(article):
        new_text = new_text[len(article) :]
    return bool(new_text) and old_text[len(article) :] == new_text


def _periods_do_not_overlap(old_from: str, old_to: str, new_from: str, new_to: str) -> bool:
    """A known end before the other start proves separation, even if another bound is unknown."""
    try:
        old_start = date.fromisoformat(old_from) if old_from else None
        new_start = date.fromisoformat(new_from) if new_from else None
        old_end = date.fromisoformat(old_to) if old_to else None
        new_end = date.fromisoformat(new_to) if new_to else None
    except ValueError:
        return False
    if (old_start and old_end and old_end < old_start) or (new_start and new_end and new_end < new_start):
        return False
    return bool((old_end and new_start and old_end < new_start) or (new_end and old_start and new_end < old_start))


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


class ReplacementPlan(NamedTuple):
    """One-pass classification; coexist includes both compatible and conflicting old versions."""

    same_version: list[str]
    legacy_undated: list[str]
    coexist: list[str]
    compatible_versions: list[str]

    @property
    def replaceable(self) -> list[str]:
        return [*self.same_version, *self.legacy_undated]

    @property
    def conflicts(self) -> list[str]:
        compatible = set(self.compatible_versions)
        return [doc_id for doc_id in self.coexist if doc_id not in compatible]


def replaceable_version_ids(
    ids: Sequence[str],
    metadatas: Sequence[dict[str, object] | None],
    *,
    version_id: str,
    effective_from: str,
    effective_to: str = "",
    documents: Sequence[str | None] = (),
    new_content: str = "",
) -> ReplacementPlan:
    """一次遍历判定可替换、可安全并存与需人工判定的旧块。

    此前只返回"可替换"一个列表 ⇒ 并存那一半在预检里**完全静默**（票 T2 要的就是它）。

    - `same_version`：非种子块，非空生效日相同，且版本标识相同或旧块无标识。
      空标识单独不能证明同版本；空日期或仅标识相同但日期不明也不能证明。
    - `legacy_undated`：无版本号与时效、来源可替换，且去掉元数据所指的章节/条号前缀后正文完整一致。
      只认包含会把残缺新文当替代并删掉完整旧文。
    - `coexist`：其余均保留；其中已知日期界值能证明区间不重叠的进入 `compatible_versions`，
      其余由 `conflicts` 报给预检阻断。无法证明安全时不猜。
    """
    plan = ReplacementPlan([], [], [], [])
    docs = list(documents)
    for i, (doc_id, metadata) in enumerate(zip(ids, metadatas, strict=False)):
        meta = metadata or {}
        stored_version_id = str(meta.get("version_id") or "").strip()
        stored_effective_from = str(meta.get("effective_from") or "").strip()
        stored_effective_to = str(meta.get("effective_to") or "").strip()
        origin = str(meta.get("origin") or "").strip()
        if (
            origin != "seed"
            and effective_from
            and stored_effective_from == effective_from
            and (stored_version_id == version_id or not stored_version_id)
        ):
            plan.same_version.append(doc_id)
            continue
        # 正文优先取 `documents`，回退 Chroma 塞进 metadata 的那份（`chroma:document`）。
        stored_text = docs[i] if i < len(docs) else meta.get("chroma:document")
        undated = not stored_effective_from and not stored_effective_to
        same_body = _same_article_body(str(stored_text or ""), new_content, meta)
        if not stored_version_id and undated and origin in _LEGACY_REPLACEABLE_ORIGINS and same_body:
            plan.legacy_undated.append(doc_id)
        else:
            plan.coexist.append(doc_id)
            if _periods_do_not_overlap(stored_effective_from, stored_effective_to, effective_from, effective_to):
                plan.compatible_versions.append(doc_id)
    return plan
