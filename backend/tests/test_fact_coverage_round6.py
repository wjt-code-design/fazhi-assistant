"""Fact coverage must retain quantities and negation, not just matching keywords."""

import json

import pytest

from legal_workflow.runtime import _IssueEnvelope, _uncovered_fact_clauses


def proposal(*quotes):
    return _IssueEnvelope.model_validate(
        json.loads(
            json.dumps(
                {
                    "issues": [
                        {"question": "能否主张责任？", "facts": [{"quote": q} for q in quotes], "unknown_facts": []}
                    ]
                }
            )
        )
    )


def test_keywords_do_not_cover_salary_tenure_or_negation():
    text = "我每月工资8000元，工作已经满三年，公司没有签订劳动合同。"
    assert _uncovered_fact_clauses(text, proposal("工资", "工作", "合同")) == [
        "我每月工资8000元",
        "工作已经满三年",
        "公司没有签订劳动合同",
    ]


def test_complete_clauses_are_covered():
    text = "工资8000元，公司没有签订劳动合同。"
    assert _uncovered_fact_clauses(text, proposal("工资8000元", "公司没有签订劳动合同")) == []


def test_numeric_punctuation_is_not_a_fact_boundary():
    from legal_workflow.runtime import _fact_clauses

    assert _fact_clauses("我每月工资8,000.50元，公司没有签合同。") == ["我每月工资8,000.50元", "公司没有签合同"]


def test_blank_quote_cannot_expand_into_all_user_facts():
    from legal_workflow.runtime import IssueDecompositionError, LLMIssueDecomposer, build_initial_agent_state
    from tests.test_legal_workflow_runtime import RecordingTransport, bootstrap

    raw = proposal("   ").model_dump_json()
    with pytest.raises(IssueDecompositionError, match="blank"):
        build_initial_agent_state(
            bootstrap("月工资8000元，公司未签合同"),
            decomposer=LLMIssueDecomposer(RecordingTransport(raw), fact_repair=False),
        )


def test_failed_model_repair_keeps_complete_trusted_facts_in_writer():
    from legal_workflow.runtime import LLMIssueDecomposer, build_initial_agent_state
    from legal_workflow.writer import build_writer_payload
    from tests.test_legal_workflow_runtime import RecordingTransport, bootstrap

    text = "我每月工资8000元，工作已经满三年，公司没有签订劳动合同。"
    raw = proposal("工资", "工作", "合同").model_dump_json()
    transport = RecordingTransport(raw, raw)
    state = build_initial_agent_state(bootstrap(text), decomposer=LLMIssueDecomposer(transport))
    assert len(transport.calls) == 2
    facts = build_writer_payload(state).issues[0].facts
    assert [fact.statement for fact in facts] == ["我每月工资8000元", "工作已经满三年", "公司没有签订劳动合同"]


@pytest.mark.parametrize("question", ["我是否变成一般保证", "谁指挥", "何时到期", "能拿回多少", "工具由谁提供"])
def test_verbatim_question_is_not_promoted_to_confirmed_fact(question):
    from legal_workflow.runtime import LLMIssueDecomposer, build_initial_agent_state
    from tests.test_legal_workflow_runtime import RecordingTransport, bootstrap

    text = f"双方签了保证合同，{question}？"
    raw = proposal("双方签了保证合同", question).model_dump_json()
    state = build_initial_agent_state(
        bootstrap(text), decomposer=LLMIssueDecomposer(RecordingTransport(raw), fact_repair=False)
    )
    assert [fact.statement for fact in state.issues[0].facts] == ["双方签了保证合同"]
    assert state.user_question == text


def _state_for(text, *quotes):
    from legal_workflow.runtime import LLMIssueDecomposer, build_initial_agent_state
    from tests.test_legal_workflow_runtime import RecordingTransport, bootstrap

    raw = proposal(*quotes).model_dump_json()
    return build_initial_agent_state(
        bootstrap(text), decomposer=LLMIssueDecomposer(RecordingTransport(raw), fact_repair=False)
    )


def test_mixed_quote_keeps_only_its_declarative_clause():
    """2026-10-23 二次复核反例：整条混合引用不能把问句写进确认事实。"""
    state = _state_for("双方签了保证合同，我是否变成一般保证？", "双方签了保证合同，我是否变成一般保证")
    assert [fact.statement for fact in state.issues[0].facts] == ["双方签了保证合同"]


def test_short_fragment_of_an_interrogative_clause_is_not_promoted():
    """反例二：quote='工具' 本身无问号，但来源分句是疑问句，不得回退成事实。"""
    state = _state_for("双方签了保证合同，工具由谁提供？", "工具")
    assert [fact.statement for fact in state.issues[0].facts] == []


def test_short_fragment_of_a_declarative_clause_still_expands():
    """绿色对照：同一短片段落在陈述分句里时，仍扩展为完整陈述，不扩大过滤。"""
    state = _state_for("双方签了保证合同，工具由我提供。", "工具")
    assert [fact.statement for fact in state.issues[0].facts] == ["工具由我提供"]
