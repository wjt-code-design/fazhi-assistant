"""Independent deterministic verification for evidence-bounded Agent drafts."""

from __future__ import annotations

import hashlib
import hmac
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import LegalAgentState, LegalValidity, SourceType
from .writer import (
    DraftAnswer,
    DraftClaim,
    DraftClaimCheck,
    build_writer_payload,
    canonical_citations,
    canonical_citations_in_order,
    derive_claim_id,
    has_noncanonical_citation,
    numeric_tokens,
)


class VerificationVerdict(StrEnum):
    PASS = "PASS"
    REWRITE = "REWRITE"
    RESEARCH_MORE = "RESEARCH_MORE"
    FAIL_SAFE = "FAIL_SAFE"


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: VerificationVerdict
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    reason_code: str = ""
    draft_digest: str | None = None
    state_digest: str | None = None
    claim_checks: tuple[DraftClaimCheck, ...] = ()
    # 争点级部分交付（2026-09-15）：service 的豁免集合随结果传递，供 render_verified
    # 的 fresh 二次验证使用同一豁免（否则二次验证用默认空集会再次拦下部分交付）。
    # 不参与 digest（digest 只绑定 state/draft 内容）。
    covered_issues_exempt: frozenset[str] = Field(default_factory=frozenset)

    @model_validator(mode="after")
    def pass_requires_bound_artifacts(self) -> VerificationResult:
        if self.verdict is VerificationVerdict.PASS and (
            not self.draft_digest or not self.state_digest or not self.claim_checks
        ):
            raise ValueError("PASS must be bound to the verified draft and state")
        return self


_OVERCONFIDENT_MARKERS = ("一定", "必然", "保证胜诉", "绝对", "100%", "百分之百")


def _claims(draft: DraftAnswer) -> list[DraftClaim]:
    return [*draft.conclusion, *draft.issue_analysis, *draft.risks]


def draft_digest(draft: DraftAnswer) -> str:
    canonical = json.dumps(
        draft.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _state_digest(state: LegalAgentState) -> str:
    payload = build_writer_payload(state)
    canonical = json.dumps(
        {
            "payload": payload.model_dump(mode="json"),
            "conflicts": [
                conflict.model_dump(mode="json")
                for conflict in sorted(
                    state.conflicts,
                    key=lambda item: (item.issue_id, item.conflict_id),
                )
            ],
            "verifier_research_returns": state.verifier_research_returns,
            "max_verifier_research_returns": state.budgets.max_verifier_research_returns,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_SIX_SECTION_TITLES = (
    "已确认事实",
    "尚不确定的事实",
    "核心法律争点",
    "法律依据",
    "分情形分析",
    "可执行建议与风险提示",
)


def _render_draft_text(state: LegalAgentState, draft: DraftAnswer) -> str:
    """任务书 §3.4 六段式渲染：从 state（事实/争点/证据）+ draft（分析/建议）组装。

    安全约束：不输出 issue_id/fact_id/evidence_id 等内部标识；证据以《》书名号+条号展示，
    与项目引用纪律一致（禁方括号）。
    """
    blocks: list[str] = []
    # 1 已确认事实（issues[].facts）
    facts = [fact.statement for issue in state.issues for fact in issue.facts]
    blocks.append("已确认事实：\n" + ("\n".join(f"- {f}" for f in facts) if facts else "- （暂无）"))
    # 2 尚不确定的事实（state unknown_facts + draft missing_information）
    unknowns = [u.statement for issue in state.issues for u in issue.unknown_facts]
    unknowns.extend(draft.missing_information)
    seen_unknown = set()
    uniq_unknowns = []
    for u in unknowns:
        if u not in seen_unknown:
            seen_unknown.add(u)
            uniq_unknowns.append(u)
    blocks.append("尚不确定的事实：\n" + ("\n".join(f"- {u}" for u in uniq_unknowns) if uniq_unknowns else "- （无）"))
    # 3 核心法律争点（issues[].question）
    questions = [issue.question for issue in state.issues]
    blocks.append("核心法律争点：\n" + "\n".join(f"- {q}" for q in questions))
    # 4 法律依据（T2，2026-09-16 收窄）：只列 claim 正文**实际引用**且已绑定的条文——
    # 交集 = canonical_citations(claim.text) ∩ canonical_citations(该 claim 绑定证据的 source_ref)。
    # 绑定但正文未引用的不展示（1e9 实测冗余 8/13、4/5 条消除）；正文引用但未绑定的
    # 仍由 verify() 的 FABRICATED_CITATION 拦截（不放宽安全边界，B3）。
    # 顺序 = claim 顺序 × 正文首次引用顺序（canonical_citations_in_order，与核验同一解析真源）；
    # 跨 claim 按条目去重。展示 label 复用 source_ref 形态（KB 为《法名》第X条或 法名#第X条）。
    # 不从整篇答案提取（防法律依据自身自匹配）、不做全局引文集匹配、无模型调用。
    evidence_by_id = {ev.evidence_id: ev for ev in state.evidence}
    seen_refs: set[str] = set()
    refs: list[str] = []
    for claim in (*draft.conclusion, *draft.issue_analysis, *draft.risks):
        bound_keys: set[tuple[str, str, str]] = set()
        bound_labels: dict[tuple[str, str, str], str] = {}
        for evidence_id in claim.evidence_ids:
            ev = evidence_by_id.get(evidence_id)
            if ev is None:
                continue
            src, _, art = ev.source_ref.partition("#")
            label = f"- 《{src}》{art}" if art else f"- {src}"
            for key in canonical_citations_in_order(ev.source_ref):
                bound_keys.add(key)
                bound_labels.setdefault(key, label)
        for key in canonical_citations_in_order(claim.text):
            if key not in bound_keys:
                continue
            label = bound_labels[key]
            if label in seen_refs:
                continue
            seen_refs.add(label)
            refs.append(label)
    blocks.append("法律依据：\n" + ("\n".join(refs) if refs else "- （无）"))
    # 5 分情形分析（issue_analysis claims）
    blocks.append(
        "分情形分析：\n"
        + ("\n".join(claim.text for claim in draft.issue_analysis) if draft.issue_analysis else "- （无）")
    )
    # 6 可执行建议与风险提示（conclusion + risks）
    advice: list[str] = []  # 解冻配套（2026-09-16）：补注解替代原 var-annotated override
    advice.extend(claim.text for claim in draft.conclusion)
    advice.extend(f"风险提示：{claim.text}" for claim in draft.risks)
    blocks.append("可执行建议与风险提示：\n" + ("\n".join(advice) if advice else "- （无）"))
    return "\n\n".join(blocks)


def render_verified(
    state: LegalAgentState,
    draft: DraftAnswer,
    verification: VerificationResult,
) -> str | None:
    """Reveal text only when a fresh deterministic verification matches PASS."""

    if verification.verdict is not VerificationVerdict.PASS:
        return None
    fresh = DeterministicVerifier().verify(state, draft, covered_issues_exempt=verification.covered_issues_exempt)
    if fresh.verdict is not VerificationVerdict.PASS:
        return None
    if not hmac.compare_digest(verification.draft_digest or "", fresh.draft_digest or ""):
        return None
    if not hmac.compare_digest(verification.state_digest or "", fresh.state_digest or ""):
        return None
    if (
        verification.claim_checks != fresh.claim_checks
        or verification.unsupported_claim_ids != fresh.unsupported_claim_ids
        or verification.reason_code != fresh.reason_code
    ):
        return None
    return _render_draft_text(state, draft)


class DeterministicVerifier:
    def verify(
        self,
        state: LegalAgentState,
        draft: DraftAnswer,
        *,
        covered_issues_exempt: frozenset[str] = frozenset(),
    ) -> VerificationResult:
        """确定性验证（schema/绑定/引用/覆盖率）。

        `covered_issues_exempt`（2026-09-15 争点级部分交付）：调用方（service）在开启
        `agent_partial_delivery_enabled` 时，把**已知未覆盖的争点**传进来，本方法对这些争点
        **跳过**「须有绑生效成文法的 claim」判定 —— 否则部分交付必然被覆盖率门禁拦下。
        **默认空集 ⇒ 行为逐字不变**；判定逻辑仍**只在本方法**（单一真源，不在 service 复制一份）。
        ⚠️ 豁免只影响"是否因此失败"，**不影响**该争点的验收结论：未覆盖争点在评测中仍记 FAIL/REVIEW。
        """
        try:
            payload = build_writer_payload(state)
        except ValueError:
            return self._result(VerificationVerdict.FAIL_SAFE, [], "STATE_INTEGRITY_FAILURE")

        issue_ids = {issue.issue_id for issue in payload.issues}
        evidence_by_id = {}
        evidence_issues: dict[str, set[str]] = {}
        for issue in payload.issues:
            for evidence in issue.evidence:
                evidence_by_id[evidence.evidence_id] = evidence
                evidence_issues.setdefault(evidence.evidence_id, set()).add(issue.issue_id)
        fact_by_id = {fact.fact_id: (issue.issue_id, fact) for issue in payload.issues for fact in issue.facts}
        claims = _claims(draft)
        claim_ids = [claim.claim_id for claim in claims]
        if len(claim_ids) != len(set(claim_ids)):
            return self._result(VerificationVerdict.FAIL_SAFE, claim_ids, "DRAFT_INTEGRITY_FAILURE")

        expected_sections = (
            (draft.conclusion, "conclusion"),
            (draft.issue_analysis, "issue_analysis"),
            (draft.risks, "risk"),
        )
        for section_claims, expected_section in expected_sections:
            if any(claim.section != expected_section for claim in section_claims):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id for claim in section_claims],
                    "DRAFT_INTEGRITY_FAILURE",
                )

        known_missing = {statement for issue in payload.issues for statement in issue.unknown_facts}
        if len(draft.missing_information) != len(set(draft.missing_information)) or not set(
            draft.missing_information
        ).issubset(known_missing):
            return self._result(VerificationVerdict.FAIL_SAFE, [], "FABRICATED_MISSING_INFORMATION")

        for claim in claims:
            if claim.issue_id not in issue_ids or not claim.evidence_ids:
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "FABRICATED_CLAIM_PROVENANCE",
                )
            expected_claim_id = derive_claim_id(
                claim.issue_id,
                claim.text,
                claim.evidence_ids,
                claim.fact_ids,
            )
            if claim.claim_id != expected_claim_id:
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "FABRICATED_CLAIM_ID",
                )
            bound_evidence_text: list[str] = []
            bound_fact_text: list[str] = []
            for evidence_id in claim.evidence_ids:
                linked_evidence = evidence_by_id.get(evidence_id)
                if linked_evidence is None or claim.issue_id not in evidence_issues[evidence_id]:
                    return self._result(
                        VerificationVerdict.FAIL_SAFE,
                        [claim.claim_id],
                        "FABRICATED_EVIDENCE_BINDING",
                    )
                if (
                    linked_evidence.source_type is SourceType.STATUTE
                    and linked_evidence.legal_validity is not LegalValidity.EFFECTIVE
                ):
                    return self._result(
                        VerificationVerdict.FAIL_SAFE,
                        [claim.claim_id],
                        "INVALID_STATUTE_EVIDENCE",
                    )
                bound_evidence_text.extend((linked_evidence.source_ref, linked_evidence.snippet))
            for fact_id in claim.fact_ids:
                linked_fact = fact_by_id.get(fact_id)
                if linked_fact is None or linked_fact[0] != claim.issue_id:
                    return self._result(
                        VerificationVerdict.FAIL_SAFE,
                        [claim.claim_id],
                        "FABRICATED_FACT_BINDING",
                    )
                bound_fact_text.append(linked_fact[1].statement)
            bound_numeric_text = "\n".join((*bound_fact_text, *bound_evidence_text))
            if not numeric_tokens(claim.text).issubset(numeric_tokens(bound_numeric_text)):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "FABRICATED_NUMERIC_TOKEN",
                )
            if has_noncanonical_citation(claim.text):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "NON_CANONICAL_CITATION",
                )
            if not canonical_citations(claim.text).issubset(canonical_citations("\n".join(bound_evidence_text))):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "FABRICATED_CITATION",
                )

        # Writer cannot sign its own support verdict; only Verifier emits checks.
        if draft.claim_checks:
            return self._result(VerificationVerdict.FAIL_SAFE, claim_ids, "CLAIM_AUDIT_CORRUPTION")

        unsupported: set[str] = set()
        deficient = False
        for issue_id in sorted(issue_ids):
            issue_claims = [claim for claim in claims if claim.issue_id == issue_id]
            has_effective_statute = any(
                evidence_by_id[evidence_id].source_type is SourceType.STATUTE
                and evidence_by_id[evidence_id].legal_validity is LegalValidity.EFFECTIVE
                for claim in issue_claims
                for evidence_id in claim.evidence_ids
            )
            if issue_claims and has_effective_statute:
                continue
            if issue_id in covered_issues_exempt:
                # 该争点由 service 判定为"未覆盖"（writer 校验不过）→ 已显式标注于终稿，
                # 不作为本轮失败原因（见 verify docstring 的边界说明）。
                continue
            deficient = True
            unsupported.update(claim.claim_id for claim in issue_claims)

        for conflict in state.conflicts:
            if conflict.critical and not conflict.resolved:
                deficient = True
                unsupported.update(claim.claim_id for claim in claims if claim.issue_id == conflict.issue_id)

        if deficient:
            verdict = (
                VerificationVerdict.RESEARCH_MORE
                if state.verifier_research_returns < state.budgets.max_verifier_research_returns
                else VerificationVerdict.FAIL_SAFE
            )
            return self._result(verdict, unsupported, "EVIDENCE_COVERAGE_DEFICIENT")

        overconfident = sorted(
            claim.claim_id for claim in claims if any(marker in claim.text for marker in _OVERCONFIDENT_MARKERS)
        )
        if overconfident:
            return self._result(
                VerificationVerdict.REWRITE,
                overconfident,
                "OVERCONFIDENT_WORDING",
            )

        return self._result(
            VerificationVerdict.PASS,
            [],
            "VERIFIED",
            draft=draft,
            covered_issues_exempt=covered_issues_exempt,
            state=state,
        )

    @staticmethod
    def _result(
        verdict: VerificationVerdict,
        unsupported_claim_ids,
        reason_code: str,
        *,
        draft: DraftAnswer | None = None,
        state: LegalAgentState | None = None,
        covered_issues_exempt: frozenset[str] = frozenset(),
    ) -> VerificationResult:
        return VerificationResult(
            verdict=verdict,
            unsupported_claim_ids=sorted(set(unsupported_claim_ids)),
            reason_code=reason_code,
            covered_issues_exempt=covered_issues_exempt,
            draft_digest=draft_digest(draft) if draft is not None else None,
            state_digest=_state_digest(state) if state is not None else None,
            claim_checks=(
                tuple(
                    DraftClaimCheck(
                        claim=claim.text,
                        supported=True,
                        evidence_ids=claim.evidence_ids,
                        rationale="deterministic_verifier_pass",
                    )
                    for claim in _claims(draft)
                )
                if verdict is VerificationVerdict.PASS and draft is not None
                else ()
            ),
        )
