"""法条覆盖闸门（F1，2026-10-27）。

核心条文缺失时，定向补检；仍缺则如实标注缺口，避免模型用总则条文"推导"罪名。

边界（刻意写死）：
- 只管**法条**覆盖。用户事实覆盖在 ``agent/runtime._uncovered_fact_clauses``，勿混。
- 纯函数 + 注入式 lookup，零 LLM、不 import retrieval：单测不拉 BGE/向量库。
- 补检有终止条件：最多 ``MAX_LOOKUP`` 条；lookup 无新增即停止当前条，全部跑完即返回。
- 模式：``off``（默认，行为逐字不变）/ ``warn``（补检 + 报告，不阻断）/ ``enforce``
  （补检 + 报告 + 生成缺口提示行，由调用方拼进 context，用于回放验收）。

数据：``knowledge_base/required_articles.json``（高频罪名/制度 → 必备条文）。
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

DEFAULT_CATALOG_PATH = Path(__file__).with_name("knowledge_base") / "required_articles.json"
MAX_LOOKUP = 8
MODES = ("off", "warn", "enforce")

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}
_ARTICLE_RE = re.compile(r"第?([0-9零〇一二两三四五六七八九十百千]+)条?")
_SOURCE_VERSION_RE = re.compile(r"[（(][^（()）]*[）)]")
_SPACE_RE = re.compile(r"\s+")


def _cn_to_int(text: str) -> int | None:
    """把「二百三十四」/「234」转成整数；无法解析返回 None（不猜）。"""
    text = text.strip()
    if text.isdigit():
        return int(text)
    if not text or any(ch not in _CN_DIGITS and ch not in _CN_UNITS for ch in text):
        return None
    total = 0
    section = 0
    number = 0
    for ch in text:
        if ch in _CN_DIGITS:
            number = _CN_DIGITS[ch]
            continue
        unit = _CN_UNITS[ch]
        section += (number or 1) * unit
        number = 0
    return total + section + number


def article_number(article: str) -> int | None:
    """条号归一：'第二百三十四条' / '234' / '第234条' → 234。"""
    match = _ARTICLE_RE.fullmatch((article or "").strip())
    return _cn_to_int(match.group(1)) if match else None


def source_key(source: str) -> str:
    """法名归一：去版本括注/空白/'中华人民共和国'前缀（只做确定性等价，不做简称表）。"""
    text = _SOURCE_VERSION_RE.sub("", source or "")
    text = _SPACE_RE.sub("", text)
    return text.removeprefix("中华人民共和国")


def _doc_key(document) -> tuple[str, int | None]:
    meta = getattr(document, "metadata", None) or {}
    return source_key(str(meta.get("source", ""))), article_number(str(meta.get("article", "")))


def _requirement_key(requirement: dict) -> tuple[str, int | None]:
    return source_key(str(requirement.get("source", ""))), article_number(str(requirement.get("article", "")))


def load_catalog(path: str | Path | None = None) -> dict:
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def detect_topics(question: str, catalog: dict) -> list[dict]:
    """按触发词命中主题；同一主题只算一次。``exclude`` 命中则跳过该主题。"""
    text = question or ""
    matched: list[dict] = []
    for topic in catalog.get("topics", []):
        if any(pattern and pattern in text for pattern in (topic.get("exclude") or [])):
            continue
        triggers = topic.get("triggers") or []
        if any(trigger and trigger in text for trigger in triggers):
            matched.append(topic)
    return matched


def missing_requirements(documents: Iterable, requirements: Iterable[dict]) -> list[dict]:
    """返回未被 documents 覆盖的必备条文（去重、保持清单顺序）。"""
    present = {_doc_key(document) for document in documents}
    missing: list[dict] = []
    seen: set[tuple[str, int | None]] = set()
    for requirement in requirements:
        key = _requirement_key(requirement)
        if key in present or key in seen:
            continue
        seen.add(key)
        missing.append(requirement)
    return missing


def ensure_coverage(
    question: str,
    documents: list,
    lookup: Callable[[str, str], list],
    *,
    mode: str = "off",
    catalog: dict | None = None,
    max_lookup: int = MAX_LOOKUP,
) -> tuple[list, dict]:
    """检测 + 定向补检。返回 (documents, report)。

    lookup(source, article) -> Document 列表；抛异常按"未取得"计入 report["unresolved"]，
    不向上抛（补检失败不能把主链路打挂）。
    """
    report: dict[str, Any] = {
        "mode": mode,
        "matched_topics": [],
        "required_total": 0,
        "missing_before": [],
        "added": [],
        "unresolved": [],
    }
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in MODES:
        # 配置拼错（WARN/warn 空格/枚举外值）不得让每个法律请求 500：退化为 off 并留痕。
        logging.getLogger("legal.chat").warning(
            "未知 coverage_gate_mode，按 off 处理",
            extra={"kind": "coverage_gate_mode", "detail": str(mode)},
        )
        normalized_mode = "off"
    mode = normalized_mode
    report["mode"] = mode
    if mode == "off":
        return documents, report

    catalog = catalog if catalog is not None else load_catalog()
    topics = detect_topics(question, catalog)
    report["matched_topics"] = [str(topic.get("id", "")) for topic in topics]
    requirements = [item for topic in topics for item in (topic.get("required") or [])]
    report["required_total"] = len(requirements)
    if not requirements:
        return documents, report

    missing = missing_requirements(documents, requirements)
    report["missing_before"] = [f"{item.get('source')}{item.get('article')}" for item in missing]

    added: list = []
    added_keys: set[tuple[str, int | None]] = set()
    lookups_done = 0
    for requirement in missing:
        source = str(requirement.get("source", ""))
        article = str(requirement.get("article", ""))
        if lookups_done >= max_lookup:
            # 上限只限"调用次数"，且被上限挡住的条**必须记为缺口**——静默丢弃等于假装覆盖过。
            report["unresolved"].append(f"{source}{article}（补检上限）")
            continue
        lookups_done += 1
        try:
            found = list(lookup(source, article) or [])
        except Exception as exc:  # noqa: BLE001 —— 补检失败只记录，不阻断生成
            report["unresolved"].append(f"{source}{article}（{type(exc).__name__}）")
            continue
        if not found:
            report["unresolved"].append(f"{source}{article}")
            continue
        for document in found:
            key = _doc_key(document)
            if key in added_keys:
                continue
            added_keys.add(key)
            added.append(document)
        report["added"].append(f"{source}{article}")

    if not added:
        return documents, report
    existing = {_doc_key(document) for document in documents}
    merged = [document for document in added if _doc_key(document) not in existing] + list(documents)
    return merged, report


def gap_notice(report: dict) -> str:
    """enforce 模式下拼进 context 的确定性缺口提示；无缺口返回空串。"""
    unresolved = report.get("unresolved") or []
    if not unresolved:
        return ""
    return (
        "【检索缺口｜确定性提示】本题必备条文未能取得："
        + "、".join(unresolved)
        + "。回答时不得以总则条文替代分则条文推导罪名，不得援引与案情不符的特别条款作间接依据；"
        "应明确说明该缺口，并仅就有依据的部分作条件性分析。"
    )
