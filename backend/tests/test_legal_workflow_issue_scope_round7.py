"""Prompt contracts for the overbroad live-model decomposition found in round 7.

These check instructions, not model compliance. Live samples are recorded
separately with the actual model response and source hashes.
"""

import json

from legal_workflow.runtime import _ISSUE_SYSTEM_PROMPT, LLMIssueDecomposer


def test_issue_prompt_keeps_exhaustiveness_within_the_users_actual_request():
    assert "用户实际咨询范围" in _ISSUE_SYSTEM_PROMPT
    assert "不得仅因某项事实出现就单独拆成争点" in _ISSUE_SYSTEM_PROMPT
    assert "用户实际争议的事实及其法律影响仍应分析" in _ISSUE_SYSTEM_PROMPT
    assert "只列出回答该问题必需的争点" in _ISSUE_SYSTEM_PROMPT
    assert "解释计算或起算规则不要求拿到参数的具体值" in _ISSUE_SYSTEM_PROMPT
    assert "每一项都必须各自成为一个独立争点" not in _ISSUE_SYSTEM_PROMPT


def test_issue_prompt_separates_questions_and_hypothetical_exceptions_from_facts():
    assert "不得将疑问或请求写成已确认事实" in _ISSUE_SYSTEM_PROMPT
    assert "不得仅因理论上可能存在例外" in _ISSUE_SYSTEM_PROMPT
    assert "unknown_facts" in _ISSUE_SYSTEM_PROMPT


def test_fact_repair_keeps_the_same_request_scope():
    from tests.test_legal_workflow_runtime import RecordingTransport, bootstrap

    messages = LLMIssueDecomposer(RecordingTransport())._messages(bootstrap(), repair={"uncovered": ["工资8000元"]})
    repair = json.loads(messages[-1].content)
    assert "用户实际咨询范围内遗漏的独立争点" in repair["instruction"]
    assert "不扩展仅假设的争点" in repair["instruction"]
