"""Independent deterministic verification for evidence-bounded Agent drafts."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from settings import settings

from . import limitation_calc, phantom_check
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
    # R15（2026-09-18）：基准日同样随结果传递，供 render_verified 的 fresh 二次验证复用
    # （与上面 covered_issues_exempt 同款理由：二次验证若用 None，开关一开就会走到
    # LAW_TRIPWIRE_NOT_WIRED，把"绊线拦下错答案"变成"整轮静默不交付"）。不参与 digest。
    law_as_of: date | None = None

    @model_validator(mode="after")
    def pass_requires_bound_artifacts(self) -> VerificationResult:
        if self.verdict is VerificationVerdict.PASS and (
            not self.draft_digest or not self.state_digest or not self.claim_checks
        ):
            raise ValueError("PASS must be bound to the verified draft and state")
        return self


_OVERCONFIDENT_MARKERS = ("一定", "必然", "保证胜诉", "绝对", "100%", "百分之百")
# ⚠️ 该常量**保留但不再用于判定的裸子串匹配**：
#   - 下游契约仍引用它：`tests/test_agent_writer.py` 用它校验"脱敏替换词不得含违禁词"
#     （初版替换词「一定期限/一定比例」命中词表 ⇒ 模型忠实复述反被判过度承诺，1e6/1e8 实测回归）。
#   - 但拿它做 `marker in text` 会误伤法律/保险专有名词：实测 24 个高频候选中 **19 个**被字面
#     命中（「绝对免赔额」「一定期限」「必然因果关系」…），其中「绝对免赔额」正是 E04 的
#     终态失败根因（2026-09-18）。判定的正确形态见 `_is_overconfident`。

# 强断言词：本身就是过度承诺，无条件命中。
_OVERCONFIDENT_STRONG_MARKERS = ("保证胜诉", "100%", "百分之百")
# 术语后缀：弱标记 + 下列后缀 = 法律/保险专有名词的构词成分，**一律放行**。
_OVERCONFIDENT_TERMINOLOGY_RE = re.compile(
    r"(?:一定|必然|绝对)"
    r"(?:期限|比例|范围|期间|数额|金额|因果(?:关系)?|结果|免赔(?:额|率)?|责任|权|无效|豁免|不能"
    r"|法律关系|的|影响|条件|情形|情形|情况)"
)
# 断言词：弱标记与下列词搭配 = 真的在打包票。
# 含**断言助动词**（应当/必须/须/要）——「一定应当依法履行」就是把裁量空间说死，
# 实测集成测试用它作 REWRITE 负例（2026-09-18 修正时补入，初版漏了这类）。
_OVERCONFIDENT_ASSERTION_RE = re.compile(
    r"(?:一定|必然|绝对|必定|肯定会)[^。；;！!？?，,]{0,6}?"
    r"(?:胜诉|赢|获赔|获得赔偿|拿到赔偿|得到支持|会支持|支持你的|支持我方|支持我们|能赔|可获|成立"
    r"|适用|认定|构成|承担|享有|驳回|应当|必须|须|要)"
)


def _is_overconfident(text: str) -> bool:
    """claim 是否含过度承诺措辞（弱标记需搭配断言词，防专有名词误伤）。

    为什么不用 `marker in text`：法律/保险术语里「绝对」「一定」「必然」是构词成分
    （绝对免赔额 / 一定期限 / 必然因果关系），裸匹配会把合法陈述判成过度承诺，
    再经 service.py 的 fail-closed 放大成整轮失败（E04，2026-09-18 修正）。

    判定顺序：**术语优先**。文本里只要出现"弱标记+术语后缀"就整段放行（含
    「在一定期限内适用该规定」这类既是术语又带断言动词的句子）。这是**有意的保守取舍**：
    误杀会让整轮 fail-closed（用户看到的是失败），漏判最多让一句措辞过关。
    """
    if any(marker in text for marker in _OVERCONFIDENT_STRONG_MARKERS):
        return True
    if _OVERCONFIDENT_TERMINOLOGY_RE.search(text):
        return False
    return bool(_OVERCONFIDENT_ASSERTION_RE.search(text))


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
    fresh = DeterministicVerifier().verify(
        state,
        draft,
        covered_issues_exempt=verification.covered_issues_exempt,
        law_as_of=verification.law_as_of,
    )
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
    @staticmethod
    def _fact_texts(state: LegalAgentState) -> list[str]:
        """事实+未决事实原文（数字白名单与受控计算共用的输入集）。"""
        return [f.statement for issue in state.issues for f in issue.facts] + [
            u.statement for issue in state.issues for u in issue.unknown_facts
        ]

    @staticmethod
    def _fact_allowlist(state: LegalAgentState) -> set[str]:
        """T-A3 数字白名单（与 writer 同口径单一真源拆两防线）：事实+未决（原值）+ 受控计算。"""
        from . import fee_calc

        allow = numeric_tokens("\n".join(DeterministicVerifier._fact_texts(state)), loose_amounts=True)
        allow |= fee_calc.controlled_fee_tokens(DeterministicVerifier._fact_texts(state))
        return allow

    def verify(
        self,
        state: LegalAgentState,
        draft: DraftAnswer,
        *,
        covered_issues_exempt: frozenset[str] = frozenset(),
        law_as_of: date | None = None,
    ) -> VerificationResult:
        """确定性验证（schema/绑定/引用/覆盖率）。

        `covered_issues_exempt`（2026-09-15 争点级部分交付）：调用方（service）在开启
        `agent_partial_delivery_enabled` 时，把**已知未覆盖的争点**传进来，本方法对这些争点
        **跳过**「须有绑生效成文法的 claim」判定 —— 否则部分交付必然被覆盖率门禁拦下。
        **默认空集 ⇒ 行为逐字不变**；判定逻辑仍**只在本方法**（单一真源，不在 service 复制一份）。
        ⚠️ 豁免只影响"是否因此失败"，**不影响**该争点的验收结论：未覆盖争点在评测中仍记 FAIL/REVIEW。

        `law_as_of`（R15 版本适用绊线）：本次任务适用法律的基准日，由调用方（service）从
        `AgentRun.law_as_of` 透传。**默认 None ⇒ 绊线不可判 ⇒ 不拦**；但开关一开而这里仍是
        None，视为接线丢失并 fail-closed（`LAW_TRIPWIRE_NOT_WIRED`）——静默放行正是该门要防的失败模式。
        """
        # R15 版本适用绊线的接线自检（放在最前：接线断了就先说断，别让别的门把症状盖住）。
        # 判据本身在 limitation_calc.law_version_crosses_watershed（时效真源，此处只消费）。
        if settings.law_version_tripwire_check and law_as_of is None:
            return self._result(VerificationVerdict.FAIL_SAFE, [], "LAW_TRIPWIRE_NOT_WIRED")
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

        # R12 伪调用检测：真实执行记录按争点取一次（同一 claim 不重复扫 observations）。
        _phantom_executions = phantom_check.issue_executions(state.observations) if settings.phantom_tool_check else {}
        # R15 版本适用绊线：事实文本集与 claim 无关，取一次即可（开关关 ⇒ 不做无谓扫描）。
        _tripwire_fact_texts = self._fact_texts(state) if settings.law_version_tripwire_check else []

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
            claim_nums = numeric_tokens(claim.text, loose_amounts=settings.numeric_matching_v2)
            bound_nums = numeric_tokens(bound_numeric_text, loose_amounts=settings.numeric_matching_v2)
            unsupported_v = claim_nums - bound_nums
            if unsupported_v and settings.numeric_matching_v2:
                # T-A3 同口径验算：事实白名单 + 受控计算（受理费），与 writer 一致（单一真源拆两防线）。
                unsupported_v -= self._fact_allowlist(state)
                # R11 受控时效放行集（与 writer 同口径；claim 断言时效结论 + 事实含日期才触发）。
                unsupported_v -= limitation_calc.controlled_limitation_tokens(claim.text, self._fact_texts(state))
            if unsupported_v:
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
            # R12 伪调用检测第二道防线（phantom_tool_check，默认关 = 行为逐字不变）：
            # writer 已在生成侧拦截；这里防"绕过 writer 直接构造 draft"的路径（同
            # 引用/数字校验"单一真源拆两防线"惯例，判定真源在 phantom_check 模块）。
            if settings.phantom_tool_check:
                phantom_categories = phantom_check.phantom_action_categories(
                    claim.text,
                    execution=_phantom_executions.get(claim.issue_id, phantom_check.NO_EXECUTION),
                    clarifications=state.clarifications,
                )
                if phantom_categories:
                    return self._result(
                        VerificationVerdict.FAIL_SAFE,
                        [claim.claim_id],
                        "PHANTOM_TOOL_CLAIM",
                    )
            if not canonical_citations(claim.text).issubset(canonical_citations("\n".join(bound_evidence_text))):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "FABRICATED_CITATION",
                )
            # R15 版本适用绊线（law_version_tripwire_check，默认关 = 行为逐字不变）：
            # 引用/数字两门都验"claim 说的东西在不在证据池"，而证据池本身按 law_as_of 做 cutoff
            # 捞取 ⇒ 分水岭前事实永远只配到现行法。故版本适用冲突必须在**这一层**单独判一次。
            # 判定真源在 limitation_calc.law_version_crosses_watershed（单一真源，此处只消费）。
            if settings.law_version_tripwire_check and limitation_calc.law_version_crosses_watershed(
                claim.text, _tripwire_fact_texts, law_as_of
            ):
                return self._result(
                    VerificationVerdict.FAIL_SAFE,
                    [claim.claim_id],
                    "LAW_VERSION_WATERSHED_MISMATCH",
                    # 带 draft/state：让失败路径落**被判定 claim 的原文**（同 OVERCONFIDENT_WORDING 口径），
                    # 否则线上只能看见 FAIL_SAFE，分不清是哪句按旧年份答了新时代的法。
                    draft=draft,
                    state=state,
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

        overconfident = sorted(claim.claim_id for claim in claims if _is_overconfident(claim.text))
        if overconfident:
            return self._result(
                VerificationVerdict.REWRITE,
                overconfident,
                "OVERCONFIDENT_WORDING",
                # 传 draft/state：让失败路径也能带出被判定 claim 的原文（见 _result 注释）。
                # 仅观测增强，不改变判定结果。
                draft=draft,
                state=state,
            )

        return self._result(
            VerificationVerdict.PASS,
            [],
            "VERIFIED",
            draft=draft,
            covered_issues_exempt=covered_issues_exempt,
            state=state,
            law_as_of=law_as_of,
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
        law_as_of: date | None = None,
    ) -> VerificationResult:
        # 2026-09-18：失败路径同样填充 claim_checks（原先仅 PASS 填 ⇒ 非 PASS 时
        # claim.text 完全丢失，OVERCONFIDENT_WORDING 之类的误伤无法事后归因，
        # 只能靠猜）。非 PASS 只填**被判定的**那些 claim，supported=False 且
        # rationale=原因码，便于日志侧定位"是哪个词、在什么上下文里命中"。
        is_pass = verdict is VerificationVerdict.PASS
        wanted = set(unsupported_claim_ids)
        return VerificationResult(
            verdict=verdict,
            unsupported_claim_ids=sorted(wanted),
            reason_code=reason_code,
            covered_issues_exempt=covered_issues_exempt,
            law_as_of=law_as_of,
            draft_digest=draft_digest(draft) if draft is not None else None,
            state_digest=_state_digest(state) if state is not None else None,
            claim_checks=(
                tuple(
                    DraftClaimCheck(
                        claim=claim.text,
                        supported=is_pass,
                        evidence_ids=claim.evidence_ids,
                        rationale="deterministic_verifier_pass" if is_pass else reason_code,
                    )
                    for claim in _claims(draft)
                    if is_pass or claim.claim_id in wanted
                )
                if draft is not None
                else ()
            ),
        )
