"""V2-T1（2026-09-09）：R1–R12 独立复核 sidecar 的校验与聚合。

对应主规划书 T1 与教学手册第六课：冻结判分器（gate5_judge.py）原样保留，本模块只
新增"人工/独立复核"记录格式与聚合口径——补齐"失败"与"尚未证明"的区分，不发明
宽松判分器，不覆盖机械指标。

聚合口径（ADR-02）：
- INVALID：结构无效（schema 版本、占位哈希、run/哈希不匹配、未知规则、重复规则）；
- FAILED：存在显式 FAIL；
- PENDING_REVIEW：无 FAIL 但存在 REVIEW、缺项或占位记录（未证明 ≠ 通过）；
- REVIEWED_CLOSURE：全部必需规则均得到独立验证（PASS + 非占位复核人 + 证据引用）。

必需规则集合来自冻结判分器 full_case_verdict 的键（R1–R12）；复合规则 R6 保留两个
子项（R6_six_sections_header / R6_content_match），不能只数 12 行。机械项同样需要
复核记录（可引用冻结 judge 的机械诊断作为证据），但不以"自动通过"顶替独立复核。

合成正例仅证明聚合逻辑可达（同材料可重算），不构成产品成功或法律结论正确的证明；
真实复核必须由独立复核者基于逐 claim 语义支撑完成（不得只搜 evidence ID 文本）。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1
REVIEW_STATUSES = ("PASS", "FAIL", "REVIEW")

# 必需复核规则集合：冻结 judge full_case_verdict 的全部键（R6 复合规则保留两个子项）。
REQUIRED_REVIEW_RULES: frozenset[str] = frozenset(
    {
        "R1_primary_facts_first_round",
        "R2_specific_prompt",
        "R3_no_repeat",
        "R4_correction_handling",
        "R5_max_two_rounds",
        "R6_six_sections_header",
        "R6_content_match",
        "R7_all_required_issues",
        "R8_required_statutes",
        "R9_claim_evidence_binding",
        "R10_no_unconfirmed_as_fact",
        "R11_actionable_advice",
        "R12_redlines",
    }
)

# 模板占位标记：出现在 reviewer/reason/evidence 中即视为未真实复核（不得计通过）。
PLACEHOLDER_MARKERS: tuple[str, ...] = ("待填", "待复核", "tbd", "placeholder", "todo", "占位")

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class ReviewEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule: str = Field(min_length=1)
    status: Literal["PASS", "FAIL", "REVIEW"]
    reviewer: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)


class ReviewSidecar(BaseModel):
    """单 case 的独立复核记录；schema 见模块 docstring 与教学手册第六课。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    run_id: str = Field(min_length=1)
    sessions_sha256: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    reviews: list[ReviewEntry] = Field(min_length=1)


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return (not lowered) or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _has_real_evidence(entry: ReviewEntry) -> bool:
    return bool(entry.evidence_refs) and not any(_is_placeholder(ref) for ref in entry.evidence_refs)


def validate_sidecar(
    sidecar: ReviewSidecar,
    *,
    expected_run_id: str | None = None,
    expected_sessions_sha256: str | None = None,
    required_rules: frozenset[str] = REQUIRED_REVIEW_RULES,
) -> list[str]:
    """结构级校验：返回问题清单（空=结构有效）。绑定不匹配/规则集问题均记入问题。"""
    problems: list[str] = []
    if sidecar.schema_version != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    if not _SHA256_HEX_RE.match(sidecar.sessions_sha256):
        problems.append("sessions_sha256 must be a lowercase sha256 hex digest")
    if _is_placeholder(sidecar.run_id):
        problems.append("run_id is a placeholder")
    if _is_placeholder(sidecar.case_id):
        problems.append("case_id is a placeholder")
    if expected_run_id is not None and sidecar.run_id != expected_run_id:
        problems.append(f"run_id mismatch: expected {expected_run_id!r}")
    if expected_sessions_sha256 is not None and sidecar.sessions_sha256 != expected_sessions_sha256:
        problems.append("sessions_sha256 mismatch with the audited artifact")

    seen: dict[str, int] = {}
    for entry in sidecar.reviews:
        seen[entry.rule] = seen.get(entry.rule, 0) + 1
        if entry.rule not in required_rules:
            problems.append(f"unknown review rule: {entry.rule}")
    for rule, count in seen.items():
        if count > 1:
            problems.append(f"duplicate review rule: {rule} x{count}")
    for rule in sorted(required_rules - seen.keys()):
        problems.append(f"missing required review rule: {rule}")
    return problems


def aggregate_review(
    sidecar: ReviewSidecar,
    *,
    expected_run_id: str | None = None,
    expected_sessions_sha256: str | None = None,
    required_rules: frozenset[str] = REQUIRED_REVIEW_RULES,
) -> dict[str, Any]:
    """单 case 聚合：INVALID > FAILED > PENDING_REVIEW > REVIEWED_CLOSURE（见模块 docstring）。

    缺必需规则项按"未证明"归 PENDING_REVIEW（审计书：缺数据标 NOT_PROVEN，不倒填）；
    绑定不匹配/未知/重复规则才是结构无效（INVALID）。
    """
    problems = validate_sidecar(
        sidecar,
        expected_run_id=expected_run_id,
        expected_sessions_sha256=expected_sessions_sha256,
        required_rules=required_rules,
    )
    base = {"case_id": sidecar.case_id, "run_id": sidecar.run_id, "problems": problems}
    missing_prefix = "missing required review rule: "
    missing_rules = sorted(
        problem.removeprefix(missing_prefix) for problem in problems if problem.startswith(missing_prefix)
    )
    structural_problems = [p for p in problems if not p.startswith(missing_prefix)]
    if structural_problems:
        return {**base, "verdict": "INVALID"}

    failed = [entry.rule for entry in sidecar.reviews if entry.status == "FAIL"]
    if failed:
        return {**base, "verdict": "FAILED", "failed_rules": sorted(failed)}

    # 无 FAIL：任何 REVIEW、占位复核人/理由、无证据的 PASS、缺项都只是"未证明"。
    pending: list[str] = list(missing_rules)
    for entry in sidecar.reviews:
        if entry.status == "REVIEW":
            pending.append(entry.rule)
        elif _is_placeholder(entry.reviewer) or _is_placeholder(entry.reason) or not _has_real_evidence(entry):
            pending.append(entry.rule)
    if pending:
        return {**base, "verdict": "PENDING_REVIEW", "pending_rules": sorted(set(pending))}
    return {**base, "verdict": "REVIEWED_CLOSURE"}


def sessions_sha256_of(sessions_path: str) -> str:
    """审计产物哈希：sidecar 必须引用被复核文件的 sha256（复核与产物绑定）。"""
    digest = hashlib.sha256()
    with open(sessions_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aggregate_run(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """run 级汇总：任一 INVALID/FAILED 即同判；否则任一 PENDING 即 PENDING_REVIEW；
    全部 REVIEWED_CLOSURE 才算 run 级 reviewed closure。空清单按 PENDING_REVIEW（无证据不通过）。"""
    if not case_results:
        return {"verdict": "PENDING_REVIEW", "cases": 0, "reason": "no case results"}
    verdicts = [item["verdict"] for item in case_results]
    if "INVALID" in verdicts:
        run_verdict = "INVALID"
    elif "FAILED" in verdicts:
        run_verdict = "FAILED"
    elif "PENDING_REVIEW" in verdicts:
        run_verdict = "PENDING_REVIEW"
    else:
        run_verdict = "REVIEWED_CLOSURE"
    return {"verdict": run_verdict, "cases": len(case_results)}


def load_sidecar(path: str) -> ReviewSidecar:
    with open(path, encoding="utf-8") as handle:
        return ReviewSidecar.model_validate(json.load(handle))


__all__ = [
    "REQUIRED_REVIEW_RULES",
    "REVIEW_STATUSES",
    "ReviewEntry",
    "ReviewSidecar",
    "aggregate_review",
    "aggregate_run",
    "load_sidecar",
    "sessions_sha256_of",
    "validate_sidecar",
]
