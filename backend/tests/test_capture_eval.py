"""Phase C 采集适配器的确定性映射单测（离线，零 HTTP 零容器）。

期望独立来源：引用规范化结果按《民法典》第675条等手算样例核对；
覆盖率语义依据 docs/capability-matrix 与 eval_agent.RUBRIC 的文字定义。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from scripts.capture_eval import (
    _case_laws_for_sentence,
    _extract_citations,
    _match_case_issues,
    _split_sentences,
    answer_chars,
    deidentify,
    is_agent_routed,
    parse_sse,
)


def test_extract_citations_normalises_law_and_article():
    text = "依据《中华人民共和国民法典》第675条与《民法典》第一百八十八条之规定。"
    got = _extract_citations(text)
    assert "民法典:675" in got
    assert "民法典:188" in got


def test_extract_citations_bracket_form():
    """2026-09-07：010 实证 agent 输出 '[民法典 第六百八十条]' 方括号合法引用。"""
    text = "根据[民法典 第六百八十条]禁止高利放贷；[刑法 第二百六十四条]盗窃罪。"
    got = _extract_citations(text)
    assert "民法典:680" in got
    assert "刑法:264" in got
    assert "民法典:第六百八十条" in got


def test_extract_citations_bracket_no_space_form():
    text = "根据[民法典第六百八十条]与[中华人民共和国刑法第二百六十四条]。"
    got = _extract_citations(text)
    assert "民法典:680" in got
    assert "刑法:264" in got


def test_case_law_mapping_bracket_form():
    sentence = "根据[民法典 第六百八十条]，禁止高利放贷，利率不得违反国家规定。"
    assert _case_laws_for_sentence(sentence, ["民法典:680", "民法典:577"]) == ["民法典:680"]


def test_split_sentences_keeps_actual_answer_units():
    text = "结论：可以起诉。\n\n依据《民法典》第675条；诉讼时效为三年。"
    got = _split_sentences(text)
    assert got[0] == "结论：可以起诉。"
    assert any("诉讼时效为三年" in s for s in got)


def test_case_law_mapping_requires_case_expected_law():
    sentence = "根据《民法典》第675条，借款应返还。"
    assert _case_laws_for_sentence(sentence, ["民法典:675", "民法典:188"]) == ["民法典:675"]
    # 答案里实际引用了题集未预期的法 → 不映射（诚实留空）
    assert _case_laws_for_sentence("根据《刑法》第266条。", ["民法典:675"]) == []


def test_issue_matching_is_deterministic_containment():
    assert _match_case_issues(["诉讼时效", "借款合同"], ["……诉讼时效……已经届满", ""]) == ["诉讼时效"]
    assert _match_case_issues(["劳动合同"], ["今天天气不错"]) == []


def test_parse_sse_counts_both_event_shapes():
    raw = (
        'data: {"type": "status", "msg": "x"}\n\n'
        'data: {"content": "红色"}\n\n'
        'data: {"type": "token", "content": "abc"}\n\n'
        "data: [DONE]\n\n"
    )
    events = parse_sse(raw)
    assert answer_chars(events) == 5  # "红色"(2) + "abc"(3)
    assert is_agent_routed(events) is False
    assert is_agent_routed([{"type": "agent_status", "status": "completed"}]) is True


def test_deidentify_strips_routing_ids():
    events = [
        {"type": "final", "run_id": "abc", "conversation_id": 7, "state_version": 3},
        {"type": "clarification", "run_id": "abc", "conversation_id": 7, "prompt": "问题"},
    ]
    clean = deidentify(events)
    assert all("run_id" not in e and "conversation_id" not in e for e in clean)
    assert clean[1]["prompt"] == "问题"


def _protocol_payload(tmp_path, case_ids=None):
    return {
        "schema_version": "legal-agent-capture-protocol/v1",
        "protocol_id": "test-protocol-1",
        "case_set_sha256": "a" * 64,
        "modes": ["existing_rag", "agent"],
        "controls": {
            "timeout_seconds": 90,
            "total_timeout_seconds": 3600,
            "max_retries": 1,
            "concurrency": 1,
            "cache_policy": "disabled",
            "network_policy": "frozen-knowledge-only",
            "max_output_tokens": 4096,
            "max_tool_calls": 8,
            "retain_failure_rows": True,
        },
    }


def test_capture_rejects_non_20_case_set_and_existing_output(tmp_path, monkeypatch):
    import scripts.capture_eval as ce

    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps([{"id": "only-one", "query": "q"}]), encoding="utf-8")
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(_protocol_payload(tmp_path, ["only-one"])), encoding="utf-8")
    out = tmp_path / "answers.json"
    out.write_text("{}", encoding="utf-8")  # 已存在 → 必须拒绝（只新增不覆盖）

    rc = ce.capture(
        ce.parse_args(
            [
                "--base-url",
                "http://127.0.0.1:1",
                "--mode",
                "existing_rag",
                "--cases",
                str(cases_path),
                "--protocol",
                str(protocol_path),
                "--execution-id",
                "test-exec-1",
                "--trace-dir",
                str(tmp_path / "traces"),
                "--out",
                str(out),
            ]
        )
    )
    assert rc == 2

    out.unlink()
    # 题集 SHA 与 protocol.case_set_sha256 不一致且未显式 dry-run 放行 → 拒绝
    rc = ce.capture(
        ce.parse_args(
            [
                "--base-url",
                "http://127.0.0.1:1",
                "--mode",
                "existing_rag",
                "--cases",
                str(cases_path),
                "--protocol",
                str(protocol_path),
                "--execution-id",
                "test-exec-1",
                "--trace-dir",
                str(tmp_path / "traces"),
                "--out",
                str(out),
            ]
        )
    )
    assert rc == 2
    cases_path.write_text(json.dumps([{"id": f"c{i}", "query": "q"} for i in range(21)]), encoding="utf-8")
    rc = ce.capture(
        ce.parse_args(
            [
                "--base-url",
                "http://127.0.0.1:1",
                "--mode",
                "existing_rag",
                "--cases",
                str(cases_path),
                "--protocol",
                str(protocol_path),
                "--execution-id",
                "test-exec-1",
                "--trace-dir",
                str(tmp_path / "traces"),
                "--out",
                str(out),
            ]
        )
    )
    assert rc == 2
