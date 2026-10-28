"""方案 B（离线支持审查器）的契约测试：一红一绿 + 证据封闭 + 失败状态可区分。

判据来源：docs/reviews/2026-10-23-round67-q1-support-gap-review.md §5 方案 B。
本文件的"红"不是比断言更弱：它要求**缺口句必须被判 supported=false** 且 span 定位到原文；
"绿"要求**逐字引条文的正常句不得被误杀**。若两条任一退化，本模块在评测里就失去意义。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from legal_workflow.schemas import (
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
    UnknownFact,
)
from legal_workflow.writer import DraftAnswer, DraftClaim, derive_claim_id, derive_fact_id
from scripts.support_review import (
    AggregateStatus,
    JudgeOutputUnparseable,
    ReviewRequest,
    ReviewVerdict,
    SupportReviewInputError,
    SupportReviewResult,
    SupportReviewStatus,
    aggregate_rounds,
    build_requests,
    review,
)

ISSUE_A = "issue-a"
ISSUE_B = "issue-b"
EV_82 = "ev-82"
EV_OTHER = "ev-other"
_EMPLOYMENT_FACT = Fact(
    statement="劳动者自2026年1月1日起在该公司工作。",
    source=SourceType.USER,
    source_ref="用户陈述",
    confidence=1.0,
)
FACT_ID = derive_fact_id(ISSUE_A, _EMPLOYMENT_FACT)
_BACKEND = Path(__file__).resolve().parents[1]


def _state() -> LegalAgentState:
    return LegalAgentState(
        issues=[
            LegalIssue(
                issue_id=ISSUE_A,
                question="未签书面劳动合同的二倍工资如何计算？",
                facts=[_EMPLOYMENT_FACT],
                unknown_facts=[
                    UnknownFact(
                        statement="月工资标准尚未确定。",
                        why_outcome_changes="工资标准决定二倍工资的计算基数。",
                    )
                ],
            ),
            LegalIssue(issue_id=ISSUE_B, question="诉讼时效是否届满？"),
        ],
        evidence=[
            Evidence(
                evidence_id=EV_82,
                source_id="law-labor-contract",
                source_ref="《劳动合同法》第八十二条",
                source_type=SourceType.STATUTE,
                snippet=(
                    "用人单位自用工之日起超过一个月不满一年未与劳动者订立书面劳动合同的，"
                    "应当向劳动者每月支付二倍的工资。"
                ),
                legal_validity=LegalValidity.EFFECTIVE,
                acquired_at=datetime(2026, 10, 20),
            ),
            Evidence(
                evidence_id=EV_OTHER,
                source_id="law-civil",
                source_ref="《民法典》第一百八十八条",
                source_type=SourceType.STATUTE,
                snippet="向人民法院请求保护民事权利的诉讼时效期间为三年。",
                legal_validity=LegalValidity.EFFECTIVE,
                acquired_at=datetime(2026, 10, 20),
            ),
        ],
        observations=[
            Observation(issue_id=ISSUE_A, statement="a", evidence_ids=[EV_82], confidence=1.0),
            Observation(issue_id=ISSUE_B, statement="b", evidence_ids=[EV_OTHER], confidence=1.0),
        ],
    )


GROUNDED = (
    "根据《劳动合同法》第八十二条，用人单位自用工之日起超过一个月不满一年未与劳动者"
    "订立书面劳动合同的，应当向劳动者每月支付二倍的工资。"
)
GAP = "根据《劳动合同法》第八十二条，劳动者申请仲裁的时效期间为一年，从知道权利被侵害之日起计算。"


def _draft(text: str, *, evidence_ids: tuple[str, ...] = (EV_82,), fact_ids: tuple[str, ...] = ()) -> DraftAnswer:
    claims = (
        DraftClaim(
            claim_id=derive_claim_id(ISSUE_A, text, evidence_ids, fact_ids),
            issue_id=ISSUE_A,
            text=text,
            evidence_ids=evidence_ids,
            fact_ids=fact_ids,
            section="conclusion",
        ),
    )
    return DraftAnswer(conclusion=claims)


class FakeJudge:
    """确定性替身：按 claim 原文关键词返回预置 verdict，或抛异常。"""

    def __init__(self, *, payload: object | None = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.requests: list[ReviewRequest] = []

    def judge(self, *, request: ReviewRequest, system_prompt: str) -> object:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.payload


def _verdict(claim_id: str, *, supported: bool, spans: tuple[str, ...] = (), rationale: str = "ok") -> dict:
    return {
        "claim_id": claim_id,
        "supported": supported,
        "unsupported_spans": list(spans),
        "rationale": rationale,
    }


def _single_request(state: LegalAgentState | None = None, draft: DraftAnswer | None = None) -> ReviewRequest:
    requests = build_requests(state or _state(), draft or _draft(GROUNDED))
    assert len(requests) == 1
    return requests[0]


def test_green_grounded_claim_is_supported() -> None:
    """绿：逐字引条文 + 事实适用的正常句必须 PASS。"""
    request = _single_request()
    result = review((request,), FakeJudge(payload=_verdict(request.claim_id, supported=True)))

    assert result.status is SupportReviewStatus.REVIEWED
    assert result.reviews[0].supported is True
    assert result.reviews[0].unsupported_spans == ()
    assert result.attempts == 1


def test_red_gap_claim_is_unsupported_with_verbatim_span() -> None:
    """红：仲裁时效一年属于绑定条文中没有的规则，必须 supported=false 且 span 回到原文。"""
    request = _single_request(draft=_draft(GAP))
    span = "劳动者申请仲裁的时效期间为一年"
    result = review((request,), FakeJudge(payload=_verdict(request.claim_id, supported=False, spans=(span,))))

    assert result.status is SupportReviewStatus.REVIEWED
    assert result.reviews[0].supported is False
    assert result.reviews[0].unsupported_spans == (span,)
    assert span in request.claim_text


def test_forged_span_is_rejected_not_trusted() -> None:
    """伪造锚：span 不在 claim 原文里 ⇒ 模型自证无效，判输出契约违约。"""
    request = _single_request()
    result = review(
        (request,),
        FakeJudge(payload=_verdict(request.claim_id, supported=False, spans=("绑定条文没有规定时效",))),
    )

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_SPAN_NOT_VERBATIM"
    assert result.reviews == ()


def test_short_span_is_rejected() -> None:
    """过短 span 无法定位（<4 字）⇒ 不得当作有效定位，且与"改写"分开归因。"""
    request = _single_request()
    result = review((request,), FakeJudge(payload=_verdict(request.claim_id, supported=False, spans=("时效",))))

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_SPAN_TOO_SHORT"


def test_supported_true_with_spans_is_contract_violation() -> None:
    """supported=true 与 unsupported_spans 非空互相矛盾 ⇒ 不得择一采信。"""
    request = _single_request()
    result = review(
        (request,),
        FakeJudge(payload=_verdict(request.claim_id, supported=True, spans=("二倍的工资",))),
    )

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_SPANS_WITH_SUPPORTED_TRUE"


def test_unsupported_without_spans_is_contract_violation() -> None:
    """supported=false 却不给定位片段 ⇒ 无法审计，不得静默接受。"""
    request = _single_request()
    result = review((request,), FakeJudge(payload=_verdict(request.claim_id, supported=False)))

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_SPANS_MISSING"


def test_judge_claim_id_mismatch_is_contract_violation() -> None:
    """模型回错 claim_id（串题/串争点）⇒ 输出不可用。"""
    request = _single_request()
    result = review((request,), FakeJudge(payload=_verdict("claim_other", supported=True)))

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_OUTPUT_CONTRACT_VIOLATION"


def test_supported_must_be_boolean() -> None:
    """supported 为字符串 "true" 时不得被真值化。"""
    request = _single_request()
    result = review(
        (request,),
        FakeJudge(
            payload={"claim_id": request.claim_id, "supported": "true", "unsupported_spans": [], "rationale": "ok"}
        ),
    )

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_OUTPUT_CONTRACT_VIOLATION"


def test_judge_exception_is_failure_not_unsupported() -> None:
    """模型异常必须记为 JUDGE_FAILURE，绝不能兜底成 supported=false（防假绿）。"""
    request = _single_request()
    result = review((request,), FakeJudge(error=RuntimeError("boom")))

    assert result.status is SupportReviewStatus.JUDGE_FAILURE
    assert result.reason_code == "JUDGE_FAILURE:RuntimeError"
    assert result.reviews == ()


class ScriptedJudge:
    """按调用序号回放预置结果；元素是异常就抛出，否则作为原始输出返回。"""

    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls = 0

    def judge(self, *, request: ReviewRequest, system_prompt: str) -> object:
        self.calls += 1
        item = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item


@pytest.mark.parametrize(
    "error",
    [TimeoutError("msg-a"), ConnectionError("msg-b"), PermissionError("msg-c")],
)
def test_judge_failure_reason_names_exception_type(error: Exception) -> None:
    """归因：不同异常类型给出可区分的 reason_code（只含类名，不含异常文本）。"""
    request = _single_request()
    result = review((request,), FakeJudge(error=error))

    assert result.status is SupportReviewStatus.JUDGE_FAILURE
    assert result.reason_code == f"JUDGE_FAILURE:{type(error).__name__}"
    assert "msg-" not in result.reason_code
    assert result.attempts == 1


def test_unparseable_output_is_retried_once_then_succeeds() -> None:
    """格式抖动可重试一次：第一次无可解析 JSON，第二次合契约 ⇒ REVIEWED。"""
    request = _single_request()
    judge = ScriptedJudge(
        JudgeOutputUnparseable("no JSON object in judge output"),
        _verdict(request.claim_id, supported=True),
    )
    result = review((request,), judge)

    assert result.status is SupportReviewStatus.REVIEWED
    assert result.reviews[0].supported is True
    assert judge.calls == 2
    assert result.attempts == 2


def test_non_object_output_is_retried_once_then_succeeds() -> None:
    """非 dict 同样属于"没按格式回"，重试一次；第二次合契约即通过。"""
    request = _single_request()
    judge = ScriptedJudge("not a dict", _verdict(request.claim_id, supported=False, spans=("二倍的工资",)))
    result = review((request,), judge)

    assert result.status is SupportReviewStatus.REVIEWED
    assert result.reviews[0].supported is False
    assert judge.calls == 2


def test_unparseable_output_after_retry_stays_invalid() -> None:
    """重试一次仍不可解析 ⇒ INVALID（不是 false、也不是 true），attempts 记 2。"""
    request = _single_request()
    judge = ScriptedJudge("no json here", "still no json")
    result = review((request,), judge)

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_OUTPUT_NOT_OBJECT"
    assert result.attempts == 2
    assert result.reviews == ()
    assert judge.calls == 2


def test_contract_violation_is_not_retried() -> None:
    """契约违约（span 非逐字）不重试：内容已给出、只是不可信，重试不改变判断。"""
    request = _single_request()
    judge = ScriptedJudge(_verdict(request.claim_id, supported=False, spans=("绑定条文没有规定时效",)))
    result = review((request,), judge)

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_SPAN_NOT_VERBATIM"
    assert result.attempts == 1
    assert judge.calls == 1


def test_llm_judge_reports_unparseable_output_as_retryable_error() -> None:
    """LLMSupportJudge 对"没有 JSON 对象"的回复必须抛可重试错误，而不是调用层异常。"""
    from scripts.support_review import LLMSupportJudge

    class _Response:
        content = "抱歉，我无法按格式输出。"

    class _LLM:
        def invoke(self, messages):  # noqa: ANN001
            return _Response()

    request = _single_request()
    with pytest.raises(JudgeOutputUnparseable):
        LLMSupportJudge(_LLM()).judge(request=request, system_prompt="x")


def test_llm_judge_extracts_embedded_json_object() -> None:
    """回复里混了额外文字时，只取花括号内 JSON（原有容错行为不得回退）。"""
    from scripts.support_review import LLMSupportJudge

    request = _single_request()
    body = (
        f'判断如下：{{"claim_id":"{request.claim_id}","supported":false,'
        '"unsupported_spans":["劳动者申请仲裁的时效期间为一年"],"rationale":"条文无此规则"}'
    )

    class _Response:
        content = body

    class _LLM:
        def invoke(self, messages):  # noqa: ANN001
            return _Response()

    parsed = LLMSupportJudge(_LLM()).judge(request=request, system_prompt="x")

    assert parsed["claim_id"] == request.claim_id
    assert parsed["supported"] is False


def test_request_is_evidence_closed() -> None:
    """证据封闭：请求只含该 claim 绑定证据/事实/该争点未决事实，不含其他争点证据。"""
    request = _single_request(draft=_draft(GROUNDED, fact_ids=(FACT_ID,)))

    assert [item.evidence_id for item in request.evidence] == [EV_82]
    assert request.facts == ("劳动者自2026年1月1日起在该公司工作。",)
    assert request.unknown_facts == ("月工资标准尚未确定。",)
    serialized = request.model_dump_json()
    assert EV_OTHER not in serialized
    assert "诉讼时效" not in serialized


def test_unbound_evidence_is_input_error() -> None:
    """绑定其他争点的证据 ⇒ 输入前提不成立，不是审查结论。"""
    draft = _draft(GROUNDED, evidence_ids=(EV_OTHER,))
    with pytest.raises(SupportReviewInputError) as exc:
        build_requests(_state(), draft)

    assert exc.value.reason_code == "EVIDENCE_NOT_BOUND"


def test_unbound_fact_is_input_error() -> None:
    """绑定不存在的 fact_id ⇒ 输入前提不成立。"""
    draft = _draft(GROUNDED, fact_ids=("fact-missing",))
    with pytest.raises(SupportReviewInputError) as exc:
        build_requests(_state(), draft)

    assert exc.value.reason_code == "FACT_NOT_BOUND"


def test_claim_id_mismatch_is_input_error() -> None:
    """claim_id 与服务端重算值不一致 ⇒ 输入被篡改，拒绝审查。"""
    text = GROUNDED
    forged = DraftClaim(
        claim_id="claim_forged",
        issue_id=ISSUE_A,
        text=text,
        evidence_ids=(EV_82,),
        fact_ids=(),
        section="conclusion",
    )
    with pytest.raises(SupportReviewInputError) as exc:
        build_requests(_state(), DraftAnswer(conclusion=(forged,)))

    assert exc.value.reason_code == "CLAIM_ID_MISMATCH"


def test_unknown_issue_is_input_error() -> None:
    """claim 指向不存在的争点 ⇒ 输入前提不成立。"""
    text = GROUNDED
    forged = DraftClaim(
        claim_id=derive_claim_id("issue-missing", text, (EV_82,), ()),
        issue_id="issue-missing",
        text=text,
        evidence_ids=(EV_82,),
        fact_ids=(),
        section="conclusion",
    )
    with pytest.raises(SupportReviewInputError) as exc:
        build_requests(_state(), DraftAnswer(conclusion=(forged,)))

    assert exc.value.reason_code == "UNKNOWN_ISSUE_ID"


def test_review_stops_at_first_invalid_output() -> None:
    """多条 claim 中一条输出违约 ⇒ 整体 INVALID，已通过的逐 claim 记录保留供审计。"""
    state = _state()
    first = _draft(GROUNDED)
    second = _draft(GAP)
    draft = DraftAnswer(conclusion=(*first.conclusion, *second.conclusion))
    requests = build_requests(state, draft)
    assert len(requests) == 2

    class SequenceJudge:
        def __init__(self) -> None:
            self.calls = 0

        def judge(self, *, request: ReviewRequest, system_prompt: str) -> object:
            self.calls += 1
            if self.calls == 1:
                return _verdict(request.claim_id, supported=True)
            return _verdict(request.claim_id, supported=False, spans=("不存在于原文的定位",))

    result = review(requests, SequenceJudge())

    assert result.status is SupportReviewStatus.INVALID_JUDGE_OUTPUT
    assert result.reason_code == "JUDGE_SPAN_NOT_VERBATIM"
    assert len(result.reviews) == 1
    assert result.reviews[0].supported is True


@pytest.mark.parametrize("relative", ["legal_workflow/service.py", "legal_workflow/runtime.py", "main.py"])
def test_module_is_not_wired_into_online_path(relative: str) -> None:
    """离线约束：线上路径不得出现 support_review（B 只进评测，不接阻断）。"""
    source = (_BACKEND / relative).read_text(encoding="utf-8")

    assert "support_review" not in source


def _round(claim_id: str, *verdicts: ReviewVerdict | None) -> SupportReviewResult:
    return SupportReviewResult(
        status=SupportReviewStatus.REVIEWED
        if all(v is not None for v in verdicts)
        else SupportReviewStatus.JUDGE_FAILURE,
        reason_code="test",
        reviews=tuple(v for v in verdicts if v is not None),
    )


def _vote(claim_id: str, supported: bool, *spans: str) -> ReviewVerdict:
    return ReviewVerdict(claim_id=claim_id, supported=supported, unsupported_spans=spans, rationale="ok")


def test_aggregate_two_false_of_three_is_unsupported() -> None:
    """红：3 轮里 2 轮 false ⇒ UNSUPPORTED（一次翻转不足以洗白）。"""
    request = _single_request()
    rounds = [
        _round(request.claim_id, _vote(request.claim_id, False, "时效期间为一年")),
        _round(request.claim_id, _vote(request.claim_id, True)),
        _round(request.claim_id, _vote(request.claim_id, False, "时效期间为一年")),
    ]
    result = aggregate_rounds((request,), rounds, required_false=2)[0]

    assert result.status is AggregateStatus.UNSUPPORTED
    assert result.unsupported_votes == 2
    assert result.support_votes == 1
    assert result.failed_votes == 0
    assert result.unsupported_spans == ("时效期间为一年",)  # 去重


def test_aggregate_two_true_of_three_is_supported() -> None:
    """绿：3 轮里 2 轮 true ⇒ SUPPORTED（一次误判 false 不足以拦正常答案）。"""
    request = _single_request()
    rounds = [
        _round(request.claim_id, _vote(request.claim_id, True)),
        _round(request.claim_id, _vote(request.claim_id, False, "二倍的工资")),
        _round(request.claim_id, _vote(request.claim_id, True)),
    ]
    result = aggregate_rounds((request,), rounds, required_false=2)[0]

    assert result.status is AggregateStatus.SUPPORTED
    assert result.support_votes == 2
    assert result.unsupported_spans == ("二倍的工资",)


def test_aggregate_failures_are_insufficient_not_true() -> None:
    """失败票既不算 false 也不算 true：1 false + 2 未判 ⇒ INSUFFICIENT。"""
    request = _single_request()
    rounds = [
        _round(request.claim_id, _vote(request.claim_id, False, "时效期间为一年")),
        _round(request.claim_id, None),
        _round(request.claim_id, None),
    ]
    result = aggregate_rounds((request,), rounds, required_false=2)[0]

    assert result.status is AggregateStatus.INSUFFICIENT_EVIDENCE
    assert result.failed_votes == 2


def test_aggregate_all_failures_is_insufficient() -> None:
    """全部失败 ⇒ INSUFFICIENT，不得因为"没有 false 票"而算 true。"""
    request = _single_request()
    rounds = [_round(request.claim_id, None) for _ in range(3)]
    result = aggregate_rounds((request,), rounds, required_false=2)[0]

    assert result.status is AggregateStatus.INSUFFICIENT_EVIDENCE
    assert result.support_votes == 0
    assert result.failed_votes == 3


@pytest.mark.parametrize("required_false", [0, 4])
def test_aggregate_rejects_out_of_range_threshold(required_false: int) -> None:
    request = _single_request()
    rounds = [_round(request.claim_id, _vote(request.claim_id, False, "时效期间为一年")) for _ in range(3)]
    with pytest.raises(ValueError):
        aggregate_rounds((request,), rounds, required_false=required_false)


def test_aggregate_rejects_unknown_claim_id() -> None:
    request = _single_request()
    rounds = [_round("claim_other", _vote("claim_other", False, "时效期间为一年"))]
    with pytest.raises(ValueError):
        aggregate_rounds((request,), rounds, required_false=1)
