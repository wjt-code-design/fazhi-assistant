"""T-A3 两把尺子测试：numeric_matching_v2（settings 开关，默认关）。

正向（复核人 3 反例，T-A0 实证场景重构）：
  E02 口语形态（5万块→5万元）、E03 口语形态（8万开工款→8万元）、
  E01 跨争点事实数字（20万挂另一争点）+ 条文数字（三年 from 188条 snippet）
反向（数字幻觉对抗）：池外新数字（12万 无任何来源）开关开仍拦
开关关：同场景旧行为逐字不变（仍拒）
"""

from datetime import datetime

import pytest

from agent.schemas import (
    AgentBudgets,
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
    UnknownFact,
)
from agent.writer import EvidenceBoundedWriter, numeric_tokens, unsupported_numeric_tokens
from settings import settings


class PerIssueGenerator:
    def __init__(self, claims):
        self.claims = claims

    def generate(self, *, payload, system_prompt):
        issue_id = payload.issues[0].issue_id
        return {"claims": [c for c in self.claims if c["issue_id"] == issue_id], "missing_information": []}


def ev(eid, ref, snip):
    return Evidence(
        evidence_id=eid,
        source_id=f"src-{eid}",
        source_ref=ref,
        source_type=SourceType.STATUTE,
        snippet=snip,
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 9, 17),
    )


def make_state(*, question, facts, evidence_specs, unknown_facts=()):
    return LegalAgentState(
        budgets=AgentBudgets(max_verifier_research_returns=1),
        verifier_research_returns=0,
        issues=[
            LegalIssue(
                issue_id="issue-x",
                question=question,
                facts=[Fact(statement=f, source=SourceType.USER, source_ref="user", confidence=1.0) for f in facts],
                unknown_facts=[UnknownFact(statement=u, why_outcome_changes="影响结论") for u in unknown_facts],
            )
        ],
        evidence=[ev(*e) for e in evidence_specs],
        observations=[
            Observation(issue_id="issue-x", statement="obs", evidence_ids=[e[0] for e in evidence_specs], confidence=1)
        ],
        conflicts=[],
    )


def render(state, claims):
    return EvidenceBoundedWriter(PerIssueGenerator(claims)).render_issue(state, "issue-x")


def one_claim(eid, text):
    return [
        {
            "local_id": "c1",
            "issue_id": "issue-x",
            "text": text,
            "evidence_ids": [eid],
            "fact_ids": [],
            "section": "conclusion",
        }
    ]


def two_issue_state(*, issue_x_question, issue_x_facts, issue_y_facts, evidence_specs):
    state = make_state(question=issue_x_question, facts=issue_x_facts, evidence_specs=evidence_specs)
    extra = LegalIssue(
        issue_id="issue-y",
        question="债权金额与合同关系如何认定？",
        facts=[Fact(statement=f, source=SourceType.USER, source_ref="user", confidence=1.0) for f in issue_y_facts],
    )
    object.__setattr__(state, "issues", [*state.issues, extra])
    return state


# ---------- 正向：复核人 3 反例（开关开 → 通过） ----------


def test_e02_colloquial_amount_passes(monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(
        question="用户与朋友之间5万元借贷关系是否成立？",
        facts=["朋友借我5万块", "他认账但一直拖着不还。"],
        evidence_specs=[
            ("ev-1", "《民法典》第六百六十七条", "《民法典》第六百六十七条 借款合同是借款人向贷款人借款的合同。")
        ],
    )
    result = render(state, one_claim("ev-1", "根据《民法典》第六百六十七条，双方之间5万元借贷关系成立。"))
    assert result.status.name == "READY", f"reason={result.reason_code}"


def test_e03_colloquial_amount_passes(monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(
        question="用户是否有权要求装修公司返还已支付的8万元开工款及利息？",
        facts=["装修公司收了8万开工款", "签了固定总价15万合同。"],
        evidence_specs=[
            ("ev-1", "《民法典》第五百六十二条", "《民法典》第五百六十二条 当事人协商一致，可以解除合同。")
        ],
    )
    result = render(state, one_claim("ev-1", "根据《民法典》第五百六十二条，用户有权解除并要求返还8万元开工款。"))
    assert result.status.name == "READY", f"reason={result.reason_code}"


def test_e01_cross_issue_fact_and_statute_number_pass(monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = two_issue_state(
        issue_x_question="该笔货款债权是否已超过诉讼时效？",
        issue_x_facts=["已经两年多了。"],
        issue_y_facts=["一家公司欠我们货款20万。"],
        evidence_specs=[
            (
                "ev-188",
                "《民法典》第一百八十八条",
                "《民法典》第一百八十八条 向人民法院请求保护民事权利的诉讼时效期间为三年。",
            ),
        ],
    )
    result = render(
        state,
        one_claim("ev-188", "根据《民法典》第一百八十八条，该20万元货款债权的三年诉讼时效尚未届满。"),
    )
    assert result.status.name == "READY", f"reason={result.reason_code}"


def test_unknown_fact_number_allowlisted(monkeypatch):
    """T-A0 机理3：未决事实数字（脱敏前原值）也应放行。"""
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(
        question="装修公司是否应返还开工款？",
        facts=["装修公司停工了。"],
        unknown_facts=["该笔8万元开工款是否已经过双方结算确认"],
        evidence_specs=[
            ("ev-1", "《民法典》第五百六十二条", "《民法典》第五百六十二条 当事人协商一致，可以解除合同。")
        ],
    )
    result = render(state, one_claim("ev-1", "该8万元开工款的性质尚需确认。"))
    assert result.status.name == "READY", f"reason={result.reason_code}"


# ---------- 反向：数字幻觉对抗（开关开仍拦） ----------


@pytest.mark.parametrize(
    "text",
    [
        "根据《民法典》第五百六十二条，装修公司应当赔偿12万元损失。",  # 池外新数字
        "根据《民法典》第五百六十二条，应返还3万5000元开工款。",  # 白名单数字的变体放大
    ],
)
def test_hallucinated_numbers_still_blocked(text, monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(
        question="用户是否有权要求装修公司返还已支付的8万元开工款及利息？",
        facts=["装修公司收了8万开工款。"],
        evidence_specs=[
            ("ev-1", "《民法典》第五百六十二条", "《民法典》第五百六十二条 当事人协商一致，可以解除合同。")
        ],
    )
    result = render(state, one_claim("ev-1", text))
    assert result.status.name == "FAIL_SAFE"
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"


# ---------- T-A3(b)：受控计算（受理费）放行与验算 ----------

FEE_EVIDENCE = [
    (
        "ev-121",
        "《民事诉讼法》第一百二十一条",
        "《民事诉讼法》第一百二十一条 当事人进行民事诉讼，应当按照规定交纳案件受理费。",
    ),
]


def test_controlled_fee_amount_passes(monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(
        question="起诉要求偿还5万元借款需要承担多少案件受理费？",
        facts=["朋友借我5万元", "我想起诉。"],
        evidence_specs=FEE_EVIDENCE,
    )
    text = "根据《民事诉讼法》第一百二十一条，案件受理费为1050元（简易程序减半为525元）。"
    result = render(state, one_claim("ev-121", text))
    assert result.status.name == "READY", f"reason={result.reason_code}"


def test_uncontrolled_fee_amount_still_blocked(monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(
        question="起诉要求偿还5万元借款需要承担多少案件受理费？",
        facts=["朋友借我5万元", "我想起诉。"],
        evidence_specs=FEE_EVIDENCE,
    )
    result = render(state, one_claim("ev-121", "根据《民事诉讼法》第一百二十一条，案件受理费为2000元。"))
    assert result.status.name == "FAIL_SAFE"
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"


# ---------- 开关关：旧行为逐字不变 ----------


def test_switch_off_keeps_old_behavior(monkeypatch):
    monkeypatch.setattr(settings, "numeric_matching_v2", False)
    state = make_state(
        question="用户与朋友之间5万元借贷关系是否成立？",
        facts=["朋友借我5万块", "他认账但一直拖着不还。"],
        evidence_specs=[
            ("ev-1", "《民法典》第六百六十七条", "《民法典》第六百六十七条 借款合同是借款人向贷款人借款的合同。")
        ],
    )
    result = render(state, one_claim("ev-1", "根据《民法典》第六百六十七条，双方之间5万元借贷关系成立。"))
    assert result.status.name == "FAIL_SAFE"
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"


# ---------- token 层单元断言 ----------


def test_loose_amount_token_equivalence():
    assert numeric_tokens("借我5万块", loose_amounts=True) == numeric_tokens("借我5万元", loose_amounts=True)
    assert numeric_tokens("收了8万开工款", loose_amounts=True) == numeric_tokens("返还8万元", loose_amounts=True)
    # 默认（关）：旧行为——口语形态退化为裸数字
    assert numeric_tokens("借我5万块") == {"number:5"}
    assert "amount:5:万" not in numeric_tokens("借我5万块")
    # 反向护栏：unsupported 判定
    assert unsupported_numeric_tokens("借我5万元", "朋友借我5万块", loose_amounts=True) == set()
    assert unsupported_numeric_tokens("借我5万元", "朋友借我5万块") == {"amount:5:万"}
