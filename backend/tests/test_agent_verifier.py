from datetime import datetime

import pytest
from pydantic import ValidationError

from agent.schemas import (
    AgentBudgets,
    Evidence,
    EvidenceConflict,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
)
from agent.verifier import (
    DeterministicVerifier,
    VerificationResult,
    VerificationVerdict,
    draft_digest,
)
from agent.writer import (
    DraftAnswer,
    DraftClaimCheck,
    EvidenceBoundedWriter,
    derive_claim_id,
    derive_fact_id,
)


class Generator:
    def __init__(self, response):
        self.response = response

    def generate(self, *, payload, system_prompt, feedback=None):
        return self.response


class PerIssueFilterGenerator:
    """Ticket 2 适配：每次渲染只收到一个争点，响应只返回属于该争点的 claims。"""

    def __init__(self, raw):
        self.raw = raw

    def generate(self, *, payload, system_prompt, feedback=None):
        issue_id = payload.issues[0].issue_id
        claims = [claim for claim in self.raw["claims"] if claim["issue_id"] == issue_id]
        return {"claims": claims, "missing_information": self.raw["missing_information"]}


def grounded_state(*, returns=0, conflicts=()) -> LegalAgentState:
    evidence = [
        Evidence(
            evidence_id="ev-a",
            source_id="law-a",
            source_ref="《民法典》第一百八十八条",
            source_type=SourceType.STATUTE,
            snippet="《民法典》第一百八十八条规定诉讼时效期间为三年。",
            legal_validity=LegalValidity.EFFECTIVE,
            acquired_at=datetime(2026, 8, 30),
        ),
        Evidence(
            evidence_id="ev-b",
            source_id="law-b",
            source_ref="《民法典》第五百八十五条",
            source_type=SourceType.STATUTE,
            snippet="《民法典》第五百八十五条规定约定违约金。",
            legal_validity=LegalValidity.EFFECTIVE,
            acquired_at=datetime(2026, 8, 30),
        ),
    ]
    return LegalAgentState(
        budgets=AgentBudgets(max_verifier_research_returns=1),
        verifier_research_returns=returns,
        issues=[LegalIssue(issue_id="issue-a", question="诉讼时效"), LegalIssue(issue_id="issue-b", question="违约金")],
        evidence=evidence,
        observations=[
            Observation(issue_id="issue-a", statement="a", evidence_ids=["ev-a"], confidence=1),
            Observation(issue_id="issue-b", statement="b", evidence_ids=["ev-b"], confidence=1),
        ],
        conflicts=list(conflicts),
    )


def draft_for_both(state=None, *, overconfident=False, only_first=False):
    raw = {
        "claims": [
            {
                "local_id": "a",
                "issue_id": "issue-a",
                "text": (
                    "根据《民法典》第一百八十八条，一定适用三年诉讼时效。"
                    if overconfident
                    else "根据《民法典》第一百八十八条，诉讼时效期间通常为三年。"
                ),
                "evidence_ids": ["ev-a"],
                "fact_ids": [],
                "section": "conclusion",
            },
            {
                "local_id": "b",
                "issue_id": "issue-b",
                "text": "根据《民法典》第五百八十五条，约定违约金可能被调整。",
                "evidence_ids": ["ev-b"],
                "fact_ids": [],
                "section": "risk",
            },
        ],
        "missing_information": [],
    }
    writer = EvidenceBoundedWriter(PerIssueFilterGenerator(raw))
    if only_first:
        # 只起草第一个争点 → issue-b 无 claim → verifier 应判 RESEARCH_MORE
        result = writer.render_issue(state or grounded_state(), "issue-a")
    else:
        result = writer.render(state or grounded_state())
    assert result.draft is not None
    return result.draft


def replace_claim_text(draft, old_claim, text):
    forged_claim = old_claim.model_copy(
        update={
            "text": text,
            "claim_id": derive_claim_id(
                old_claim.issue_id,
                text,
                old_claim.evidence_ids,
                old_claim.fact_ids,
            ),
        }
    )
    sections = {
        "conclusion": tuple(
            forged_claim if claim.claim_id == old_claim.claim_id else claim for claim in draft.conclusion
        ),
        "issue_analysis": tuple(
            forged_claim if claim.claim_id == old_claim.claim_id else claim for claim in draft.issue_analysis
        ),
        "risks": tuple(forged_claim if claim.claim_id == old_claim.claim_id else claim for claim in draft.risks),
    }
    return draft.model_copy(update=sections)


def test_verifier_requires_every_issue_and_returns_stable_claim_ids():
    state = grounded_state()
    missing = draft_for_both(state, only_first=True)
    result = DeterministicVerifier().verify(state, missing)
    assert result.verdict is VerificationVerdict.RESEARCH_MORE
    assert result.unsupported_claim_ids == []


def test_unresolved_critical_conflict_obeys_durable_one_return_budget():
    conflict = EvidenceConflict(
        conflict_id="conflict-a", issue_id="issue-a", evidence_ids=("ev-a",), critical=True, resolved=False
    )
    first_state = grounded_state(conflicts=(conflict,))
    restored_state = LegalAgentState.model_validate_json(
        grounded_state(returns=1, conflicts=(conflict,)).model_dump_json()
    )
    first = DeterministicVerifier().verify(first_state, draft_for_both(first_state))
    exhausted = DeterministicVerifier().verify(restored_state, draft_for_both(restored_state))
    assert first.verdict is VerificationVerdict.RESEARCH_MORE
    assert exhausted.verdict is VerificationVerdict.FAIL_SAFE
    assert restored_state.verifier_research_returns == 1


def test_integrity_failure_is_fail_safe_and_cannot_be_upgraded_by_reviewer():
    state = grounded_state()
    draft = draft_for_both(state)
    forged = draft.model_copy(
        update={
            "conclusion": [draft.conclusion[0].model_copy(update={"claim_id": "forged", "evidence_ids": ["missing"]})]
        }
    )
    result = DeterministicVerifier().verify(state, forged)
    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.unsupported_claim_ids == ["forged"]


def test_wording_only_overconfidence_returns_rewrite():
    result = DeterministicVerifier().verify(grounded_state(), draft_for_both(overconfident=True))
    assert result.verdict is VerificationVerdict.REWRITE
    assert result.unsupported_claim_ids


def test_only_pass_can_render():
    from agent.verifier import render_verified

    draft = draft_for_both()
    state = grounded_state()
    verification = DeterministicVerifier().verify(state, draft)
    assert render_verified(state, draft, verification)
    for verdict in ("REWRITE", "RESEARCH_MORE", "FAIL_SAFE"):
        assert (
            render_verified(
                state,
                draft,
                VerificationResult(verdict=verdict, unsupported_claim_ids=[]),
            )
            is None
        )


def test_pass_renders_six_sections_without_internal_ids():
    """任务书 §3.4：通过后渲染六段式标题；不泄漏 issue_id/fact_id/evidence_id。"""
    from agent.verifier import render_verified

    draft = draft_for_both()
    state = grounded_state()
    verification = DeterministicVerifier().verify(state, draft)
    assert verification.verdict is VerificationVerdict.PASS

    rendered = render_verified(state, draft, verification)
    assert rendered is not None
    for title in ("已确认事实", "尚不确定的事实", "核心法律争点", "法律依据", "分情形分析", "可执行建议与风险提示"):
        assert title + "：" in rendered, f"缺少六段式标题: {title}"
    # 引用以《》书名号展示，禁止方括号引文
    assert "《" in rendered
    assert "[" not in rendered
    # 内部标识不进入用户可见答案
    for private in ("issue_", "fact_", "evidence_", "state_json"):
        assert private not in rendered


def test_pass_is_bound_to_the_exact_immutable_draft():
    from agent.verifier import render_verified

    state = grounded_state()
    draft = draft_for_both(state)
    verification = DeterministicVerifier().verify(state, draft)
    forged_claim = draft.conclusion[0].model_copy(update={"text": "模型伪造事实，金额为999999元。"})
    forged = draft.model_copy(update={"conclusion": (forged_claim,)})

    assert verification.verdict is VerificationVerdict.PASS
    assert verification.claim_checks
    assert all(check.supported for check in verification.claim_checks)
    assert render_verified(state, forged, verification) is None
    with pytest.raises((AttributeError, TypeError)):
        draft.conclusion.append(forged_claim)
    with pytest.raises(ValidationError):
        VerificationResult(verdict="PASS", unsupported_claim_ids=[])

    forged_check = DraftClaimCheck(
        claim=forged_claim.text,
        supported=True,
        evidence_ids=forged_claim.evidence_ids,
        rationale="forged",
    )
    forged_pass = VerificationResult(
        verdict="PASS",
        draft_digest=draft_digest(forged),
        state_digest="caller-forged-state-digest",
        claim_checks=(forged_check,),
    )
    assert render_verified(state, forged, forged_pass) is None


def test_buffered_finalization_order_short_circuits_and_rechecks_after_normalize():
    import main

    draft = draft_for_both()
    verification = DeterministicVerifier().verify(grounded_state(), draft)
    calls = []
    citation_results = iter([[], []])

    def citations(text):
        calls.append("citation")
        return next(citation_results)

    class Quality:
        ok = True
        reason = ""

    result = main.finalize_verified_agent_answer(
        grounded_state(),
        draft,
        verification,
        citation_checker=citations,
        quality_checker=lambda text, context_present: calls.append("quality") or Quality(),
        expand_law_names_fn=lambda text: calls.append("expand_law_names") or text,
        expand_citations_fn=lambda text: calls.append("expand_citations") or text,
        money_normalize_fn=lambda text: calls.append("money") or text,
        strip_notes_fn=lambda text, source_lookup: calls.append("strip_notes") or text,
        source_lookup=lambda source: True,
    )
    assert result.answer
    assert calls == ["citation", "quality", "expand_law_names", "expand_citations", "money", "strip_notes", "citation"]


def test_finalization_never_normalizes_after_citation_or_quality_failure():
    import main

    draft = draft_for_both()
    verification = DeterministicVerifier().verify(grounded_state(), draft)
    normalized = []
    result = main.finalize_verified_agent_answer(
        grounded_state(),
        draft,
        verification,
        citation_checker=lambda text: ["bad"],
        quality_checker=lambda text, context_present: (_ for _ in ()).throw(AssertionError("quality called")),
        expand_law_names_fn=lambda text: normalized.append(text) or text,
    )
    assert result.answer is None
    assert normalized == []

    class BadQuality:
        ok = False
        reason = "bad"

    result = main.finalize_verified_agent_answer(
        grounded_state(),
        draft,
        verification,
        citation_checker=lambda text: [],
        quality_checker=lambda text, context_present: BadQuality(),
        expand_law_names_fn=lambda text: normalized.append(text) or text,
    )
    assert result.answer is None
    assert normalized == []


@pytest.mark.parametrize("resolved", [False, True])
def test_verifier_fails_safe_before_retry_for_dangling_conflicts(resolved):
    conflict = EvidenceConflict(
        conflict_id="dangling",
        issue_id="missing-issue",
        evidence_ids=("missing-evidence",),
        critical=True,
        resolved=resolved,
    )
    current = grounded_state(conflicts=(conflict,))

    result = DeterministicVerifier().verify(current, draft_for_both())

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "STATE_INTEGRITY_FAILURE"


def test_verifier_rejects_empty_issue_state():
    result = DeterministicVerifier().verify(LegalAgentState(), DraftAnswer())

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "STATE_INTEGRITY_FAILURE"


def test_verifier_accepts_shared_evidence_for_each_linked_issue():
    current = grounded_state()
    current = current.model_copy(
        update={
            "observations": [
                *current.observations,
                Observation(
                    issue_id="issue-b",
                    statement="shared",
                    evidence_ids=["ev-a"],
                    confidence=1,
                ),
            ]
        }
    )
    raw = {
        "claims": [
            {
                "local_id": "a",
                "issue_id": "issue-a",
                "text": "《民法典》第一百八十八条规定诉讼时效。",
                "evidence_ids": ["ev-a"],
                "fact_ids": [],
                "section": "conclusion",
            },
            {
                "local_id": "b",
                "issue_id": "issue-b",
                "text": "《民法典》第一百八十八条也适用于该争点。",
                "evidence_ids": ["ev-a"],
                "fact_ids": [],
                "section": "risk",
            },
        ],
        "missing_information": [],
    }
    writer_result = EvidenceBoundedWriter(PerIssueFilterGenerator(raw)).render(current)
    assert writer_result.draft is not None

    result = DeterministicVerifier().verify(current, writer_result.draft)

    assert result.verdict is VerificationVerdict.PASS


def test_verifier_independently_rejects_fabricated_citation():
    current = grounded_state()
    draft = draft_for_both(current)
    forged = replace_claim_text(
        draft,
        draft.conclusion[0],
        "根据《民法典》第五百八十五条，诉讼时效期间通常为三年。",
    )

    result = DeterministicVerifier().verify(current, forged)

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "FABRICATED_CITATION"


@pytest.mark.parametrize(
    "text",
    [
        "根据民法典第五百八十五条，诉讼时效期间通常为三年。",
    ],
)
def test_verifier_rejects_noncanonical_citation_before_normalization(text):
    current = grounded_state()
    draft = draft_for_both(current)
    forged = replace_claim_text(
        draft,
        draft.conclusion[0],
        text,
    )

    result = DeterministicVerifier().verify(current, forged)

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "NON_CANONICAL_CITATION"


def test_verify_exempt_skips_uncovered_issue_coverage():
    """争点级部分交付（2026-09-15）：exempt 争点**跳过**"须有绑生效成文法 claim"判定。

    only_first 草稿缺 issue-b 的 claim ⇒ 默认判定 EVIDENCE_COVERAGE_DEFICIENT（非 PASS）；
    传入 covered_issues_exempt={issue-b} ⇒ 不再因此 deficient → PASS（其余判定不变）。
    边界：豁免只影响 service 是否因此失败；该争点在**评测口径**中仍记 FAIL/REVIEW。
    """
    current = grounded_state()
    draft = draft_for_both(current, only_first=True)

    default = DeterministicVerifier().verify(current, draft)
    assert default.verdict is not VerificationVerdict.PASS
    assert default.reason_code == "EVIDENCE_COVERAGE_DEFICIENT"

    exempted = DeterministicVerifier().verify(current, draft, covered_issues_exempt=frozenset({"issue-b"}))
    assert exempted.verdict is VerificationVerdict.PASS


def test_render_draft_text_lists_only_cited_statutes():
    """§4.3「法条墙」修复（2026-09-16）：法律依据只列 claim **实际引用**的条文。

    1e7 r3 端到端实测：渲染遍历整个 `state.evidence`（检索池）⇒ 16 条依据混入
    《行政强制法》等串台条目（§4.3 明文禁止"将整个检索池展示成相关法律"）。
    修复后：按 draft 各 section claim 绑定的 evidence 取、按《法名》+条号去重；
    未被任何 claim 引用的池内条目**不得出现**。
    """
    from agent.verifier import _render_draft_text

    current = grounded_state()
    pool_only = Evidence(
        evidence_id="ev-pool",
        source_id="law-pool",
        source_ref="《行政强制法》第三十六条",
        source_type=SourceType.STATUTE,
        snippet="《行政强制法》第三十六条规定……",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 30),
    )
    state_with_pool = current.model_copy(update={"evidence": (*current.evidence, pool_only)})

    full_text = _render_draft_text(state_with_pool, draft_for_both(state_with_pool))
    assert "- 《行政强制法》第三十六条" not in full_text  # 池内未被引用 ⇒ 不得出现
    assert "- 《民法典》第一百八十八条" in full_text  # 被 issue-a claim 引用 ⇒ 应列
    assert "- 《民法典》第五百八十五条" in full_text  # 被 issue-b claim 引用 ⇒ 应列

    first_text = _render_draft_text(state_with_pool, draft_for_both(state_with_pool, only_first=True))
    assert "- 《民法典》第一百八十八条" in first_text
    assert "- 《民法典》第五百八十五条" not in first_text  # only_first 未引用 ⇒ 不得出现


def test_render_draft_text_excludes_bound_but_uncited_statutes():
    """T2（2026-09-16）：法律依据 = 正文引用 ∩ claim 绑定证据——**绑定但正文未引用的不展示**。

    1e9 报告观察：两份终稿分别 8/13、4/5 条冗余（绑定证据被整批列入法律依据，
    但 claim 正文只引用其中少数）。修复后：claim 引用即绑定的交集才进入法律依据。
    数据契约（handoff §4.4/4.5）：claim 可在内部绑定更多证据用于审计，
    但未在正文引用的条文不进入用户可见法律依据区。
    """
    from agent.verifier import _render_draft_text

    current = grounded_state()
    # issue-a 的 claim 绑定 ev-a（正文引用）+ ev-extra（绑定但正文不引用）
    extra = Evidence(
        evidence_id="ev-extra",
        source_id="law-extra",
        source_ref="《劳动法》第七十七条",
        source_type=SourceType.STATUTE,
        snippet="《劳动法》第七十七条规定劳动争议处理办法。",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 30),
    )
    state_with_extra = current.model_copy(update={"evidence": (*current.evidence, extra)})

    base = draft_for_both(state_with_extra)
    issue_a_claim = base.conclusion[0]
    expanded = issue_a_claim.model_copy(update={"evidence_ids": (*issue_a_claim.evidence_ids, "ev-extra")})
    draft = base.model_copy(
        update={"conclusion": (expanded, *base.conclusion[1:])},
    )
    # claim_id 含 evidence_ids 派生 ⇒ 扩绑后必须重算，否则 verifier 拒绝；
    # 本测试只测渲染纯函数，直接用扩绑 draft 调 _render_draft_text（不经 verifier）。
    text = _render_draft_text(state_with_extra, draft)

    assert "- 《民法典》第一百八十八条" in text  # 引用且绑定 ⇒ 显示
    assert "- 《劳动法》第七十七条" not in text  # 绑定但未引用 ⇒ **不显示**（B1）


def test_render_draft_text_legal_basis_order_and_dedup():
    """T2：法律依据顺序 = claim 顺序 × 正文首次引用顺序；同条文跨 claim 只显示一次（B2）。"""
    from agent.verifier import _render_draft_text

    current = grounded_state()
    extra = Evidence(
        evidence_id="ev-extra",
        source_id="law-extra",
        source_ref="《劳动法》第七十七条",
        source_type=SourceType.STATUTE,
        snippet="《劳动法》第七十七条规定劳动争议处理办法。",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 30),
    )
    state = current.model_copy(update={"evidence": (*current.evidence, extra)})

    base = draft_for_both(state)
    # claim-a 正文先引 77 后引 188（与绑定顺序 ev-a, ev-extra 相反）→ 显示按正文首次引用顺序
    claim_a = base.conclusion[0]
    text_a = "根据《劳动法》第七十七条与《民法典》第一百八十八条，主张权利。"
    expanded_a = claim_a.model_copy(update={"text": text_a, "evidence_ids": ("ev-a", "ev-extra")})
    # claim-b 改为引用与 claim-a 相同的 188（跨 claim 去重）+ 自身 585
    claim_b = base.risks[0]
    text_b = "根据《民法典》第一百八十八条与第五百八十五条，注意时效与违约金调整。"
    expanded_b = claim_b.model_copy(update={"text": text_b, "evidence_ids": ("ev-a", "ev-b")})
    draft = base.model_copy(update={"conclusion": (expanded_a,), "risks": (expanded_b,)})

    text = _render_draft_text(state, draft)
    basis = text.split("法律依据：\n", 1)[1].split("\n\n", 1)[0]
    assert basis.splitlines() == [
        "- 《劳动法》第七十七条",  # 正文首次引用顺序：77 先于 188
        "- 《民法典》第一百八十八条",
        "- 《民法典》第五百八十五条",  # claim-b 新增；188 跨 claim 去重不重复
    ]


def test_render_draft_text_legal_basis_no_self_match():
    """T2 必须测试（handoff 行 241）：法律依据文本本身不会造成自匹配。

    实现只消费 claim.text（结构保证）；本测试锁行为——把完整渲染文本（含法律依据区自身
    的《法名》条目）当作新 claim 的正文再渲染，法律依据集合**不变**：
    未绑定条目不因"出现在渲染文本里"而被吸收（若实现从整篇答案提取引文，此处会漏）。
    """
    from agent.verifier import _render_draft_text

    current = grounded_state()
    pool_only = Evidence(
        evidence_id="ev-pool",
        source_id="law-pool",
        source_ref="《行政强制法》第三十六条",
        source_type=SourceType.STATUTE,
        snippet="《行政强制法》第三十六条规定……",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 30),
    )
    state = current.model_copy(update={"evidence": (*current.evidence, pool_only)})

    first = _render_draft_text(state, draft_for_both(state))
    # 把第一篇完整渲染（含法律依据区自身条目）当作 claim 正文再渲染。
    # 直接构造 draft（不经 writer 校验）——writer 会正确拒绝引用未绑定条文的 claim，
    # 而本测试只锁渲染纯函数的自匹配行为。
    base = draft_for_both(state)
    self_ref_claim = base.conclusion[0].model_copy(
        update={"text": first, "claim_id": derive_claim_id("issue-a", first, ("ev-a",), ())}
    )
    draft = base.model_copy(update={"conclusion": (self_ref_claim,)})
    second = _render_draft_text(state, draft)

    def _basis(text: str) -> list[str]:
        return [ln for ln in text.split("法律依据：\n", 1)[1].split("\n\n", 1)[0].splitlines() if ln.startswith("- ")]

    # 法律依据集合不变：池内未绑定/未引用条目（《行政强制法》）不因自文本而混入
    assert _basis(second) == _basis(first)
    assert all("行政强制法" not in ln for ln in _basis(second))


def test_render_unknown_facts_use_state_text_not_payload_desensitized():
    """渲染层「尚不确定的事实」来自 **state 原文**（非 payload 脱敏文本）——非缺陷，钉住口径。

    B 项脱敏只作用于 writer payload（模型输入）；用户侧渲染 state.unknown_facts 原文
    （含"十二个月"等具体表述）⇒ 信息量更高，且**天然补偿**脱敏的"待确认项模糊化"代价。
    该段不经数字校验**是有意设计**：它是待确认问题清单，不是 claim，不构成"unknown 当既成事实"。
    """
    from agent.schemas import UnknownFact
    from agent.verifier import _render_draft_text

    current = grounded_state()
    state_with_unknown = current.model_copy(
        update={
            "issues": tuple(
                issue.model_copy(
                    update={
                        "unknown_facts": [
                            UnknownFact(
                                statement="解除前十二个月的平均工资数额。",
                                why_outcome_changes="直接影响赔偿金的计算基数。",
                            )
                        ]
                    }
                )
                for issue in current.issues
            )
        }
    )
    text = _render_draft_text(state_with_unknown, draft_for_both(current))
    assert "解除前十二个月的平均工资数额" in text  # state 原文（未脱敏）面向用户
    assert "一定期限" not in text  # payload 脱敏文本不得泄入渲染


def test_verifier_expands_continuation_and_verifies_each_article():
    """A 项（2026-09-15）：续引展开后**逐条核验**——第二条未绑定 → FABRICATED_CITATION。

    原先该文本判 NON_CANONICAL_CITATION（形式问题）；A 项改为展开核验后，
    已绑的首条通过、未绑的续引条被判伪造（**核验强度不变，归因更准**）。
    """
    current = grounded_state()
    draft = draft_for_both(current)
    forged = replace_claim_text(
        draft,
        draft.conclusion[0],
        "根据《民法典》第一百八十八条、第五百八十五条，诉讼时效期间通常为三年。",
    )

    result = DeterministicVerifier().verify(current, forged)

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "FABRICATED_CITATION"


def test_verifier_does_not_accept_user_fact_as_statute_citation_authority():
    current = grounded_state()
    user_fact = Fact(
        statement="用户称《民法典》第五百八十五条适用",
        source=SourceType.USER,
        source_ref="user:answer",
        confidence=1,
    )
    issue_a = current.issues[0].model_copy(update={"facts": [user_fact]})
    current = current.model_copy(update={"issues": [issue_a, current.issues[1]]})
    fact_id = derive_fact_id("issue-a", user_fact)
    draft = draft_for_both(current)
    old_claim = draft.conclusion[0].model_copy(update={"fact_ids": (fact_id,)})
    forged = replace_claim_text(
        draft,
        old_claim,
        "根据《民法典》第五百八十五条，诉讼时效期间通常为三年。",
    )

    result = DeterministicVerifier().verify(current, forged)

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "FABRICATED_CITATION"


def test_verifier_independently_rejects_numeric_unit_swap():
    current = grounded_state()
    evidence_with_amount = current.evidence[0].model_copy(
        update={"source_ref": "用户材料", "snippet": "证据仅记载赔偿金额为30元。"}
    )
    current = current.model_copy(update={"evidence": [evidence_with_amount, current.evidence[1]]})
    raw = {
        "claims": [
            {
                "local_id": "a",
                "issue_id": "issue-a",
                "text": "赔偿金额为30元。",
                "evidence_ids": ["ev-a"],
                "fact_ids": [],
                "section": "conclusion",
            },
            {
                "local_id": "b",
                "issue_id": "issue-b",
                "text": "《民法典》第五百八十五条规定约定违约金。",
                "evidence_ids": ["ev-b"],
                "fact_ids": [],
                "section": "risk",
            },
        ],
        "missing_information": [],
    }
    writer_result = EvidenceBoundedWriter(PerIssueFilterGenerator(raw)).render(current)
    assert writer_result.draft is not None
    forged = replace_claim_text(
        writer_result.draft,
        writer_result.draft.conclusion[0],
        "违约比例为30%。",
    )

    result = DeterministicVerifier().verify(current, forged)

    assert result.verdict is VerificationVerdict.FAIL_SAFE
    assert result.reason_code == "FABRICATED_NUMERIC_TOKEN"


def test_post_normalize_citation_failure_and_non_pass_short_circuit():
    import main

    draft = draft_for_both()
    verification = DeterministicVerifier().verify(grounded_state(), draft)

    class Quality:
        ok = True
        reason = ""

    citations = iter([[], ["new citation"]])
    result = main.finalize_verified_agent_answer(
        grounded_state(),
        draft,
        verification,
        citation_checker=lambda text: next(citations),
        quality_checker=lambda text, context_present: Quality(),
        expand_law_names_fn=lambda text: text,
        expand_citations_fn=lambda text: text,
        money_normalize_fn=lambda text: text,
        strip_notes_fn=lambda text, source_lookup: text,
    )
    assert result.answer is None
    assert result.reason_code == "POST_NORMALIZE_CITATION_CHECK_FAILED"

    not_pass = VerificationResult(verdict="REWRITE", unsupported_claim_ids=())
    result = main.finalize_verified_agent_answer(
        grounded_state(),
        draft,
        not_pass,
        citation_checker=lambda text: (_ for _ in ()).throw(AssertionError("citation checker called")),
        quality_checker=lambda text, context_present: (_ for _ in ()).throw(AssertionError("quality checker called")),
    )
    assert result.answer is None
    assert result.reason_code == "VERIFIER_NOT_PASS"
