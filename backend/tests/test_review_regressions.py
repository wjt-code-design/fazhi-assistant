"""独立锚点：2026-09-18 合并审查报告的回归反例。"""

from datetime import date
from decimal import Decimal

import pytest

from agent.fee_calc import case_acceptance_fee, largest_amount_yuan
from agent.limitation_calc import calc_limitation
from agent.phantom_check import NO_EXECUTION, phantom_action_categories


@pytest.mark.parametrize(
    "amount,normal",
    [
        (2000000, 22800),
        (5000000, 46800),
        (10000000, 81800),
        (20000000, 141800),
        (30000000, 191800),
        (999000, 13790),
        (1001000, 13809),
        (1999000, 22791),
        (2001000, 22808),
        (4999000, 46792),
        (5001000, 46807),
        (9999000, 81793),
        (10001000, 81806),
        (19999000, 141794),
        (20001000, 141805),
    ],
)
def test_complete_fee_brackets(amount, normal):
    # 独立手算：50 + 90000*.025 + 100000*.02 + 300000*.015 + ...
    assert case_acceptance_fee(Decimal(amount)) == {"normal": normal, "simplified": normal // 2}


@pytest.mark.parametrize("text", ["借款50000元", "借款5万块", "借款五万元", "借款５万元"])
def test_oral_amount(text):
    assert largest_amount_yuan([text]) == Decimal(50000)


def test_labor_interruption():
    result = calc_limitation(
        "labor_arbitration", fact_date=date(2025, 1, 1), interruption_dates=[date(2025, 10, 1)], as_of=date(2026, 2, 1)
    )
    assert result["expiry_date"] == date(2026, 10, 1)
    assert result["expired_as_of"] is False


def test_general_provisions_period():
    result = calc_limitation("civil", fact_date=date(2019, 1, 1), as_of=date(2021, 7, 1))
    assert result["expiry_date"] == date(2022, 1, 1)
    assert result["expired_as_of"] is False


@pytest.mark.parametrize(
    "text", ["我无法读取您的历史会话。", "没有调取您的历史会话。", "请提供此前的咨询记录。", "我未读取此前的咨询记录。"]
)
def test_denied_memory_access(text):
    assert phantom_action_categories(text, execution=NO_EXECUTION, clarifications=0) == []


@pytest.mark.parametrize(
    "text",
    [
        "历史会话显示您已还款。",
        "我已调取您的历史会话。",
        "无法读取附件，但历史会话显示已经还款。",
        "根据您的历史会话，借款已还清。",
    ],
)
def test_asserted_memory_access(text):
    assert phantom_action_categories(text, execution=NO_EXECUTION, clarifications=0) == ["memory"]


@pytest.mark.parametrize("amount", ["5万块", "五万元", "50000元"])
def test_oral_fee_writer_and_verifier(amount, monkeypatch):
    from agent.verifier import DeterministicVerifier
    from settings import settings
    from tests.test_numeric_matching_v2 import FEE_EVIDENCE, make_state, one_claim, render

    monkeypatch.setattr(settings, "numeric_matching_v2", True)
    state = make_state(question="起诉费用多少？", facts=[f"朋友借我{amount}。"], evidence_specs=FEE_EVIDENCE)
    result = render(state, one_claim("ev-121", "根据《民事诉讼法》第一百二十一条，受理费1050元，简易程序525元。"))
    assert result.status.name == "READY", result.reason_code
    assert DeterministicVerifier().verify(state, result.draft).verdict.name == "PASS"


def test_fact_conflict_writer_and_verifier():
    from agent.verifier import DeterministicVerifier, render_verified
    from agent.writer import derive_fact_id
    from tests.test_agent_verifier import replace_claim_text
    from tests.test_numeric_matching_v2 import make_state, one_claim, render

    state = make_state(
        question="借款是否应返还？",
        facts=["借款尚未清偿。"],
        evidence_specs=[("ev-1", "《民法典》第六百七十五条", "借款人应当按照约定的期限返还借款。")],
    )
    good = "根据《民法典》第六百七十五条，该借款尚未清偿。"
    bad = "根据《民法典》第六百七十五条，该借款已经全部清偿。"
    claims = one_claim("ev-1", good)
    claims[0]["fact_ids"] = [derive_fact_id("issue-x", state.issues[0].facts[0])]
    draft = render(state, claims).draft
    assert draft is not None
    assert DeterministicVerifier().verify(state, draft).verdict.name == "PASS"
    claims[0]["text"] = bad
    assert render(state, claims).reason_code == "FACT_CONTRADICTION"
    forged = replace_claim_text(draft, draft.conclusion[0], bad)
    verdict = DeterministicVerifier().verify(state, forged)
    assert verdict.reason_code == "FACT_CONTRADICTION"
    assert render_verified(state, forged, verdict) is None


@pytest.mark.parametrize(
    "text",
    [
        "如果借款已经全部清偿，则不需还款。",
        "另一笔借款已经全部清偿。",
        "借款是否已经全部清偿？",
        "借款已部分偿还。",
        "用户说：‘借款已经全部清偿’。",
    ],
)
def test_fact_rule_does_not_decide_ambiguous_cases(text):
    from agent.fact_consistency import settlement_conflicts

    assert not settlement_conflicts(text, ["借款尚未清偿。"])


def test_snippet_citation_is_rendered():
    from agent.verifier import DeterministicVerifier, render_verified
    from tests.test_numeric_matching_v2 import make_state, one_claim, render

    state = make_state(
        question="适用规则？",
        facts=[],
        evidence_specs=[("ev-1", "《民法典》第六百七十五条", "另据《民法典》第五百七十七条，应承担违约责任。")],
    )
    result = render(state, one_claim("ev-1", "根据《民法典》第五百七十七条，应承担违约责任。"))
    assert result.status.name == "READY", result.reason_code
    verdict = DeterministicVerifier().verify(state, result.draft)
    text = render_verified(state, result.draft, verdict)
    assert text is not None
    basis = text.split("法律依据：", 1)[1].split("分情形分析：", 1)[0]
    assert "《民法典》第577条" in basis
    assert "675" not in basis and "六百七十五" not in basis


def test_verifier_rejects_fact_conflict_without_writer_guard():
    """独立测第二道防线，避免 writer 的先行失败掩盖 verifier 缺陷。"""
    from agent.verifier import DeterministicVerifier, render_verified
    from tests.test_agent_verifier import replace_claim_text
    from tests.test_numeric_matching_v2 import make_state, one_claim, render

    state = make_state(question="借款是否应返还？", facts=["借款尚未清偿。"], evidence_specs=[
        ("ev-1", "《民法典》第六百七十五条", "借款人应当按照约定的期限返还借款。")])
    draft = render(state, one_claim("ev-1", "根据《民法典》第六百七十五条，该借款尚未清偿。")).draft
    assert draft is not None
    forged = replace_claim_text(draft, draft.conclusion[0], "根据《民法典》第六百七十五条，该借款已经全部清偿。")
    verdict = DeterministicVerifier().verify(state, forged)
    assert verdict.reason_code == "FACT_CONTRADICTION"
    assert render_verified(state, forged, verdict) is None


@pytest.mark.parametrize("article", ["第675条", "第６７５条", "第六百七十五条"])
def test_lookup_normalizes_at_shared_boundary(article, monkeypatch):
    from types import SimpleNamespace

    import retrieval

    class Collection:
        def get(self, *, where, include):
            assert where["$and"][1] == {"article": "第六百七十五条"}
            return {"ids": ["law"], "documents": ["条文"], "metadatas": [{"status": "现行有效"}]}

    monkeypatch.setattr(retrieval, "vectorstore", SimpleNamespace(_collection=Collection()))
    assert retrieval.exact_article_lookup("民法典", article)


@pytest.mark.parametrize(
    "start,interruptions,expected",
    [
        (date(2014, 1, 1), [], date(2016, 1, 1)),
        (date(2016, 1, 1), [], date(2019, 1, 1)),
        (date(2014, 1, 1), [date(2015, 9, 1)], date(2017, 9, 1)),
        (date(2014, 1, 1), [date(2015, 11, 1), date(2018, 5, 1)], date(2021, 5, 1)),
    ],
)
def test_civil_transition_does_not_revive_expired_period(start, interruptions, expected):
    assert calc_limitation("civil", fact_date=start, interruption_dates=interruptions)["expiry_date"] == expected


def test_labor_ignores_outside_and_future_interruptions():
    result = calc_limitation(
        "labor_arbitration",
        fact_date=date(2025, 1, 1),
        interruption_dates=[date(2024, 1, 1), date(2026, 2, 1), date(2027, 1, 1)],
        as_of=date(2026, 3, 1),
    )
    assert result["expiry_date"] == date(2026, 1, 1)
