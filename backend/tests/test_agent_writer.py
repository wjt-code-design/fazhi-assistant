from datetime import datetime

import pytest

import agent.writer as writer_module
from agent.schemas import (
    Evidence,
    EvidenceConflict,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
    UnknownFact,
)
from agent.writer import DraftAnswer, EvidenceBoundedWriter, WriterStatus


class RecordingGenerator:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate(self, *, payload, system_prompt, feedback=None):
        self.calls.append((payload, system_prompt))
        return self.response


class PerIssueGenerator:
    """按 payload 中实际争点动态生成 claim（Ticket 2：每次渲染只看到一个争点）。

    generate 负责记录调用，respond 负责构造响应（子类只覆写 respond 即可保留调用记录）。
    """

    def __init__(self, text_by_issue=None, *, base_text="根据《民法典》第一百八十八条，诉讼时效期间为三年。"):
        self.calls = []
        self.text_by_issue = text_by_issue or {}
        self.base_text = base_text

    def generate(self, *, payload, system_prompt, feedback=None):
        self.calls.append((payload, system_prompt))
        return self.respond(payload)

    def respond(self, payload):
        issue = payload.issues[0]
        text = self.text_by_issue.get(issue.issue_id, self.base_text)
        return {
            "claims": [
                {
                    "local_id": f"local-{issue.issue_id}",
                    "issue_id": issue.issue_id,
                    "text": text,
                    "evidence_ids": [issue.evidence[0].evidence_id] if issue.evidence else [],
                    "fact_ids": [],
                    "section": "conclusion",
                }
            ],
            # missing_information 只能来自本争点 unknown_facts（逐字）
            "missing_information": list(issue.unknown_facts[:1]),
        }


def evidence(
    evidence_id: str,
    *,
    source_type: SourceType = SourceType.STATUTE,
    validity: LegalValidity = LegalValidity.EFFECTIVE,
    snippet: str = "《民法典》第一百八十八条规定诉讼时效期间为三年。",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_id=f"source-{evidence_id}",
        source_ref="《民法典》第一百八十八条",
        source_type=source_type,
        snippet=snippet,
        legal_validity=validity,
        acquired_at=datetime(2026, 8, 30),
    )


def state() -> LegalAgentState:
    return LegalAgentState(
        steps=9,
        verifier_research_returns=0,
        action_fingerprints={"secret-fingerprint"},
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="诉讼时效多久？",
                facts=[
                    Fact(
                        statement="权利受损日期为2023年8月1日",
                        source=SourceType.USER,
                        source_ref="user:answer",
                        confidence=1,
                    ),
                    Fact(
                        statement="模型推断用户已催告",
                        source=SourceType.INFERENCE,
                        source_ref="planner:thought",
                        confidence=0.2,
                    ),
                ],
                unknown_facts=[UnknownFact(statement="是否存在中止事由", why_outcome_changes="影响时效")],
            ),
            LegalIssue(issue_id="issue-b", question="违约金是否过高？"),
        ],
        observations=[
            Observation(
                issue_id="issue-a",
                statement="raw observation prose canary",
                evidence_ids=["ev-a"],
                confidence=0.9,
            ),
            Observation(
                issue_id="issue-b",
                statement="second issue",
                evidence_ids=["ev-b"],
                confidence=0.8,
            ),
        ],
        evidence=[
            evidence("ev-a"),
            evidence("ev-b", snippet="《民法典》第五百八十五条规定约定违约金。"),
            evidence("ev-unlinked", snippet="unlinked retrieval document canary"),
        ],
        conflicts=[
            EvidenceConflict(
                conflict_id="conflict-resolved",
                issue_id="issue-a",
                evidence_ids=("ev-a",),
                critical=True,
                resolved=True,
            )
        ],
    )


def response_claim(**updates):
    claim = {
        "local_id": "local-a",
        "issue_id": "issue-a",
        "text": "根据《民法典》第一百八十八条，诉讼时效期间为三年。",
        "evidence_ids": ["ev-a"],
        "fact_ids": [],
        "section": "conclusion",
    }
    claim.update(updates)
    return {"claims": [claim], "missing_information": ["是否存在中止事由"]}


def test_writer_payload_is_allowlisted_and_excludes_untrusted_canaries():
    generator = PerIssueGenerator(text_by_issue={"issue-b": "《民法典》第五百八十五条规定约定违约金。"})

    result = EvidenceBoundedWriter(generator).render(state())

    assert result.status is WriterStatus.READY
    assert result.draft is not None
    assert result.draft.claim_checks == ()
    payload, prompt = generator.calls[0]
    dumped = payload.model_dump(mode="json")
    serialized = payload.model_dump_json()
    assert set(dumped) == {"issues", "resolved_conflict_ids"}
    assert "raw observation prose canary" not in serialized
    assert "unlinked retrieval document canary" not in serialized
    assert "模型推断用户已催告" not in serialized
    for forbidden in ("history", "summary", "retrieval", "planner", "fingerprint", "budget", "counter", "tool_args"):
        assert forbidden not in serialized.lower()
    assert "secret-fingerprint" not in serialized
    assert "尽力回答" not in prompt
    assert "不得新增" in prompt


@pytest.mark.parametrize(
    "response",
    [
        "raw text",
        {"claims": [], "missing_information": [], "conclusion": "unchecked"},
        {
            "claims": [
                {
                    "local_id": "x",
                    "issue_id": "issue-a",
                    "text": "a",
                    "evidence_ids": ["ev-a"],
                    "fact_ids": [],
                    "section": "unknown",
                }
            ],
            "missing_information": [],
        },
        {
            "claims": [
                {
                    "local_id": "same",
                    "issue_id": "issue-a",
                    "text": "a",
                    "evidence_ids": ["ev-a"],
                    "fact_ids": [],
                    "section": "conclusion",
                },
                {
                    "local_id": "same",
                    "issue_id": "issue-a",
                    "text": "b",
                    "evidence_ids": ["ev-a"],
                    "fact_ids": [],
                    "section": "risk",
                },
            ],
            "missing_information": [],
        },
    ],
)
def test_writer_rejects_malformed_extra_unknown_section_and_duplicate_local_ids(response):
    result = EvidenceBoundedWriter(RecordingGenerator(response)).render(state())
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.draft is None


def test_writer_fails_explicitly_when_all_claims_dropped_for_zero_evidence():
    """Ticket 2 决策 4：READY 但该争点没有任何被接受 claim（全部因 evidence_ids 空被丢弃）→ 显式失败。

    dropped 明细只进入摘要日志（claims_dropped==1，见下方 (b) 分支测试）；失败 WriterResult
    不携带部分 ledger（draft=None）。
    """
    result = EvidenceBoundedWriter(RecordingGenerator(response_claim(evidence_ids=[], text="一定胜诉"))).render(state())
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "ISSUE_CLAIMS_MISSING"
    assert result.draft is None
    assert result.dropped_claim_ids == ()
    assert "rendered_text" not in type(result).model_fields
    assert not hasattr(writer_module, "render_draft_text")


# ---------------- writer 侧可归因诊断（2026-09-12 归因轮） ----------------
# 动机：真实 C01 终态 4/4 争点 claims=0，而归档无法区分
# (a) 模型压根没产出 claim 与 (b) 产出后因 evidence_ids 为空被 writer.py 静默丢弃；
# 且真实失败是循环内 `_fail("NON_CANONICAL_CITATION")`，归档只留 stage 字符串，
# 不知是哪条 claim / 哪个争点触发。以下断言锁住这三件事的可区分性。
def _writer_summaries(caplog):
    return [r for r in caplog.records if getattr(r, "agent_writer_summary", None) is not None]


def test_writer_summary_distinguishes_zero_claims_from_dropped(caplog):
    """(a) 分支：模型没产出任何 claim → 单争点渲染即显式 ISSUE_CLAIMS_MISSING。

    Ticket 2：逐争点串行渲染——每次调用只看到一个争点，per_issue 摘要只含该争点；
    第一个争点失败即停，后续争点不被调用。
    """
    import logging as _logging

    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        result = EvidenceBoundedWriter(RecordingGenerator({"claims": [], "missing_information": []})).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "ISSUE_CLAIMS_MISSING"
    recs = _writer_summaries(caplog)
    assert recs, "writer 必须留下 agent_writer_summary 诊断，否则 claims=0 不可归因"
    summary = recs[-1].agent_writer_summary
    assert summary["reason"] == "ISSUE_CLAIMS_MISSING"
    assert summary["claims_proposed"] == 0
    assert summary["claims_accepted"] == 0
    assert summary["claims_dropped"] == 0
    # 单争点 payload：摘要只含本争点
    assert {row["issue_id"] for row in summary["per_issue"]} == {"issue-a"}
    assert all(row["proposed"] == 0 for row in summary["per_issue"])


def test_writer_summary_shows_dropped_claim_for_missing_evidence(caplog):
    """(b) 分支：产出了 claim，但因 evidence_ids 为空被丢弃 → ISSUE_CLAIMS_MISSING 且可区分。"""
    import logging as _logging

    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        result = EvidenceBoundedWriter(RecordingGenerator(response_claim(evidence_ids=[], text="一定胜诉"))).render(
            state()
        )

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "ISSUE_CLAIMS_MISSING"
    summary = _writer_summaries(caplog)[-1].agent_writer_summary
    assert summary["claims_proposed"] == 1
    assert summary["claims_accepted"] == 0
    assert summary["claims_dropped"] == 1
    dropped_row = [row for row in summary["per_issue"] if row["issue_id"] == "issue-a"][0]
    assert dropped_row == {"issue_id": "issue-a", "proposed": 1, "accepted": 0, "dropped": 1}


def test_writer_summary_reports_failing_reason_and_issue(caplog):
    """writer `_fail` 必须带出**失败原因 + 出问题的争点**（循环内 _fail 也要有）。"""
    import logging as _logging

    # 未加书名号的引用 → has_noncanonical_citation 命中 → 循环内 _fail
    response = response_claim(text="依据民法典第五百八十五条，违约金过高可以调整。")
    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        result = EvidenceBoundedWriter(RecordingGenerator(response)).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "NON_CANONICAL_CITATION"
    summary = _writer_summaries(caplog)[-1].agent_writer_summary
    assert summary["reason"] == "NON_CANONICAL_CITATION"
    assert summary["failing_issue_id"] == "issue-a"
    assert summary["claims_proposed"] == 1


def test_writer_summary_field_is_registered_in_log_whitelist():
    """白名单回归：字段未登记会被 JSON formatter 静默丢弃（同 V2-T8 教训）。"""
    from observability import _ACCOUNT_FIELDS

    assert "agent_writer_summary" in _ACCOUNT_FIELDS


# ---------------- 数字校验违规的分桶归因（2026-09-12 grilling 对齐后） ----------------
# 动机：`UNSUPPORTED_NUMERIC_TOKEN` 整篇作废，但可能是三种根因，改法互不通用：
#   ② 漏绑 —— 数字在本争点其它来源里，模型只是没引   → 改 payload/提示词
#   ③ 跨争点 —— 数字属于别的争点，模型**无权**引用   → 改 planner/争点-事实绑定（超出本轮）
#   ① 编造 —— 哪里都查不到                            → 改提示词
# 对齐决定：日志只记**分桶计数**，不记任何数值/文本（隐私面为零）。
# 注：对齐时列的「出现在该 claim 自己绑定来源里」一桶在定义上恒为 0
# （unsupported = text − bound，属集合差），因此不记这个伪桶，改记 `unsupported_total`。
def _numeric_violation(caplog):
    summary = _writer_summaries(caplog)[-1].agent_writer_summary
    return summary["numeric_violation"]


def test_numeric_violation_bucket_own_issue(caplog):
    """② 漏绑：数字在本争点其它事实里，claim 没引对应 fact_id。"""
    import logging as _logging

    response = response_claim(text="权利受损日期为2023年8月1日，故应适用相应时效。")
    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        result = EvidenceBoundedWriter(RecordingGenerator(response)).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"
    buckets = _numeric_violation(caplog)
    assert buckets["issue_id"] == "issue-a"
    assert buckets["in_own_issue_other_sources"] >= 1
    assert buckets["unsupported_total"] == (
        buckets["in_own_issue_other_sources"]
        + buckets["in_other_issues"]
        + buckets["from_unknown_facts"]
        + buckets["nowhere"]
    )


def test_numeric_violation_bucket_other_issues(caplog):
    """跨争点数字在单争点 payload 下不可见（Ticket 2）→ 归入 nowhere 桶并显式失败。

    旧多争点 payload 时代该数字可归因 `in_other_issues`；逐争点渲染后模型根本看不到
    别的争点的数字，故统一按"不可引用"处理（nowhere）。跨争点标识引用仍由
    CROSS_ISSUE_EVIDENCE / CROSS_ISSUE_FACT 基于 state 全集拦截。
    """
    import logging as _logging

    generator = PerIssueGenerator(text_by_issue={"issue-b": "权利受损日期为2023年8月1日，故应适用相应时效。"})
    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        EvidenceBoundedWriter(generator).render_issue(state(), "issue-b")

    buckets = _numeric_violation(caplog)
    assert buckets["issue_id"] == "issue-b"
    assert buckets["nowhere"] >= 1


def test_numeric_violation_bucket_nowhere(caplog):
    """① 编造：数字在可引用来源与未决事实里都查不到。"""
    import logging as _logging

    response = response_claim(text="劳动者已在本单位工作四年，故应支付四个月工资。")
    with caplog.at_level(_logging.INFO, logger="legal.agent"):
        result = EvidenceBoundedWriter(RecordingGenerator(response)).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    buckets = _numeric_violation(caplog)
    assert buckets["nowhere"] >= 1
    assert buckets["in_own_issue_other_sources"] == 0


@pytest.mark.parametrize(
    ("updates", "mutate", "reason"),
    [
        ({"evidence_ids": ["missing"]}, None, "UNKNOWN_EVIDENCE_ID"),
        ({"evidence_ids": ["ev-b"]}, None, "CROSS_ISSUE_EVIDENCE"),
        (
            {"evidence_ids": ["ev-a"]},
            lambda s: s.model_copy(
                update={"evidence": [evidence("ev-a", validity=LegalValidity.SUPERSEDED), *s.evidence[1:]]}
            ),
            "INVALID_STATUTE_EVIDENCE",
        ),
        ({"fact_ids": ["missing"]}, None, "UNKNOWN_FACT_ID"),
    ],
)
def test_writer_fails_safe_for_unknown_cross_issue_or_invalid_sources(updates, mutate, reason):
    current = state()
    if mutate:
        current = mutate(current)
    result = EvidenceBoundedWriter(RecordingGenerator(response_claim(**updates))).render(current)
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == reason
    assert result.draft is None


def test_writer_derives_fact_and_claim_ids_and_accepts_bound_number():
    capture = RecordingGenerator({"claims": [], "missing_information": []})
    EvidenceBoundedWriter(capture).render_issue(state(), "issue-a")
    fact_id = capture.calls[0][0].issues[0].facts[0].fact_id
    raw = response_claim(text="权利受损日期为2023年8月1日，依据《民法典》第一百八十八条处理。", fact_ids=[fact_id])
    first = EvidenceBoundedWriter(RecordingGenerator(raw)).render_issue(state(), "issue-a")
    second = EvidenceBoundedWriter(RecordingGenerator(raw)).render_issue(state(), "issue-a")
    assert first.status is WriterStatus.READY
    assert first.draft is not None and second.draft is not None
    claim = first.draft.conclusion[0]
    assert claim.claim_id
    assert claim.fact_ids == (fact_id,)
    assert claim.claim_id == second.draft.conclusion[0].claim_id


@pytest.mark.parametrize("text", ["金额为5000元。", "比例为30%。", "日期为2025年1月1日。", "期限为六个月。"])
def test_writer_fails_safe_for_unsupported_numbers_dates_amounts_and_durations(text):
    result = EvidenceBoundedWriter(RecordingGenerator(response_claim(text=text))).render(state())
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"


def test_writer_rejects_invented_missing_information():
    raw = response_claim()
    raw["missing_information"] = ["模型新增的待补信息"]
    result = EvidenceBoundedWriter(RecordingGenerator(raw)).render(state())
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNKNOWN_MISSING_INFORMATION"


def test_writer_accepts_missing_information_with_whitespace_or_width_variance():
    """2a'（2026-09-15）：missing_information 与 unknown_facts 的比对必须**归一化**。

    修复前：writer.py:691 逐字比对 → LLM 仅改空白/全角半角/标点形态即
    UNKNOWN_MISSING_INFORMATION fail-closed 拒答（基线库实测占失败 run 3/14）。
    归一化**不放宽来源要求**（仍须来自本争点 unknown_facts）——与同函数内
    claim 文本已用的 `_normalize_text` 保持一致。

    ⚠️ 测试设计要点：render **逐争点**循环，必须用 PerIssueGenerator 让每个争点
    回答**自己的** unknown_facts 变体——若用固定 raw，issue-b（空 unknown_facts）
    会因跨争点泄漏被正确拒绝（那测的是另一个东西）。
    """
    st = state()
    variant_by_issue = {
        issue.issue_id: [" " + u.statement.replace(" ", "\u3000") + " " for u in issue.unknown_facts[:1]]
        for issue in st.issues
    }

    class VariantGen(PerIssueGenerator):
        def respond(self, payload):
            issue = payload.issues[0]
            result = super().respond(payload)
            # 用归一化等价的形态变体替换（仅当本争点确有 unknown_facts）
            result["missing_information"] = variant_by_issue.get(issue.issue_id, [])
            return result

    # 用单争点接口：只渲染 issue-a（issue-b 的 base_text 数字在 ev-b 不可溯源，
    # 会触发与本验证目标无关的 UNSUPPORTED_NUMERIC_TOKEN——那是另一条防线的职责）
    result = EvidenceBoundedWriter(VariantGen()).render_issue(st, "issue-a")
    assert result.status is WriterStatus.READY, (result.status, result.reason_code)
    # 落库的是 canonical 原文（非变体）——下游 verifier 逐字检查天然通过
    assert result.draft.missing_information == ("是否存在中止事由",)


def test_writer_rejects_citation_not_present_in_claim_bound_evidence():
    result = EvidenceBoundedWriter(
        RecordingGenerator(
            response_claim(
                text="根据《民法典》第五百八十五条，诉讼时效期间为三年。",
                evidence_ids=["ev-a"],
            )
        )
    ).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_CITATION"


@pytest.mark.parametrize(
    "text",
    [
        "根据民法典第五百八十五条，诉讼时效期间为三年。",
    ],
)
def test_writer_rejects_noncanonical_citation_before_normalization(text):
    result = EvidenceBoundedWriter(
        RecordingGenerator(
            response_claim(
                text=text,
                evidence_ids=["ev-a"],
            )
        )
    ).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "NON_CANONICAL_CITATION"


def test_writer_expands_continuation_and_verifies_each_article():
    """A 项（2026-09-15）：续引展开后**逐条核验**——第二条未绑定仍被拒。

    原先该文本判 NON_CANONICAL_CITATION（形式问题）；A 项改为展开核验后，
    188 已绑、585 未绑 → 判 UNSUPPORTED_CITATION（**核验强度不变，只是归因更准**）。
    """
    result = EvidenceBoundedWriter(
        RecordingGenerator(
            response_claim(
                text="根据《民法典》第一百八十八条、第五百八十五条，诉讼时效期间为三年。",
                evidence_ids=["ev-a"],
            )
        )
    ).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_CITATION"


def test_writer_does_not_accept_user_fact_as_statute_citation_authority():
    current = state()
    issue_a = current.issues[0].model_copy(
        update={
            "facts": [
                *current.issues[0].facts,
                Fact(
                    statement="用户称《民法典》第五百八十五条适用",
                    source=SourceType.USER,
                    source_ref="user:answer",
                    confidence=1,
                ),
            ]
        }
    )
    current = current.model_copy(update={"issues": [issue_a, current.issues[1]]})
    capture = RecordingGenerator({"claims": [], "missing_information": []})
    EvidenceBoundedWriter(capture).render_issue(current, "issue-a")
    user_fact_id = capture.calls[0][0].issues[0].facts[-1].fact_id

    result = EvidenceBoundedWriter(
        RecordingGenerator(
            response_claim(
                text="根据《民法典》第五百八十五条，诉讼时效期间为三年。",
                fact_ids=[user_fact_id],
            )
        )
    ).render_issue(current, "issue-a")

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_CITATION"


@pytest.mark.parametrize(
    ("source_text", "claim_text"),
    [
        ("证据仅记载赔偿金额为30元。", "违约比例为30%。"),
        ("证据仅记载赔偿金额为2025元。", "履行期限为2025年。"),
        ("证据仅记载违约比例为3%。", "履行期限为3个月。"),
    ],
)
def test_writer_rejects_same_value_with_fabricated_numeric_kind_or_unit(source_text, claim_text):
    current = state().model_copy(
        update={
            "evidence": [
                evidence("ev-a", snippet=source_text),
                *state().evidence[1:],
            ]
        }
    )

    result = EvidenceBoundedWriter(RecordingGenerator(response_claim(text=claim_text))).render(current)

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "UNSUPPORTED_NUMERIC_TOKEN"


def test_writer_accepts_evidence_linked_to_multiple_issues():
    """共享证据可被两个争点分别引用（逐争点渲染：每个争点各一次有效生成）。"""
    current = state()
    current = current.model_copy(
        update={
            "observations": [
                *current.observations,
                Observation(
                    issue_id="issue-b",
                    statement="shared statute",
                    evidence_ids=["ev-a"],
                    confidence=0.9,
                ),
            ]
        }
    )
    generator = PerIssueGenerator(text_by_issue={"issue-b": "《民法典》第一百八十八条也适用于该争点。"})

    result = EvidenceBoundedWriter(generator).render(current)

    assert result.status is WriterStatus.READY
    assert result.draft is not None
    assert [claim.issue_id for claim in result.draft.conclusion] == ["issue-a", "issue-b"]
    assert result.draft.conclusion[1].evidence_ids == ("ev-a",)


@pytest.mark.parametrize("resolved", [False, True])
def test_writer_fails_safe_for_dangling_conflict_references(resolved):
    current = state().model_copy(
        update={
            "conflicts": [
                EvidenceConflict(
                    conflict_id="dangling",
                    issue_id="missing-issue",
                    evidence_ids=("missing-evidence",),
                    critical=True,
                    resolved=resolved,
                )
            ]
        }
    )

    result = EvidenceBoundedWriter(RecordingGenerator(response_claim())).render(current)

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "STATE_INTEGRITY_FAILURE"


def test_writer_rejects_unlinked_evidence_and_cross_issue_fact():
    current = state()
    unlinked = current.model_copy(
        update={
            "observations": [
                *[item for item in current.observations if item.issue_id != "issue-a"],
                Observation(
                    issue_id="issue-a",
                    statement="tool failed",
                    evidence_ids=["ev-a"],
                    tool_name="retrieve_laws",
                    status="failed",
                    error_code="TOOL_TIMEOUT",
                ),
            ]
        }
    )
    result = EvidenceBoundedWriter(RecordingGenerator(response_claim(evidence_ids=["ev-a"]))).render(unlinked)
    assert result.status is WriterStatus.FAIL_SAFE

    capture = RecordingGenerator({"claims": [], "missing_information": []})
    EvidenceBoundedWriter(capture).render_issue(current, "issue-a")
    issue_a_fact_id = capture.calls[0][0].issues[0].facts[0].fact_id
    result = EvidenceBoundedWriter(
        RecordingGenerator(
            {
                "claims": [
                    {
                        "local_id": "steal-fact",
                        "issue_id": "issue-b",
                        "text": "《民法典》第五百八十五条规定约定违约金。",
                        "evidence_ids": ["ev-b"],
                        "fact_ids": [issue_a_fact_id],
                        "section": "conclusion",
                    }
                ],
                "missing_information": [],
            }
        )
    ).render_issue(current, "issue-b")
    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "CROSS_ISSUE_FACT"


def test_writer_payload_orders_effective_statute_evidence_first():
    """V2-W4: payload 证据确定性重排序——生效成文法优先（一行可回退）。

    原按 evidence_id（内容哈希）排序使有效法条证据随机沉底，模型倾向只绑前部
    证据（run-11 C02 实证：金标法条在表中但 draft 未绑定）。排序只影响模型输入
    分布，不影响任何校验与 claim_id/state_digest 的正确性。
    """
    mixed = LegalAgentState(
        issues=[LegalIssue(issue_id="issue-a", question="加班费如何计算？")],
        observations=[
            Observation(
                issue_id="issue-a",
                statement="检索加班费依据",
                evidence_ids=["ev-aaa", "ev-mmm", "ev-zzz"],
                confidence=0.9,
            )
        ],
        evidence=[
            evidence("ev-aaa", source_type=SourceType.CASE, snippet="指导案例：某加班费劳动争议案。"),
            evidence("ev-mmm", validity=LegalValidity.SUPERSEDED, snippet="已废止条例相关文本。"),
            evidence("ev-zzz", snippet="《劳动法》第四十四条：休息日加班支付百分之二百工资报酬。"),
        ],
    )

    payload = writer_module.build_writer_payload(mixed)

    # 生效成文法证据排最前；其余按 (source_ref, evidence_id) 稳定排序
    assert [item.evidence_id for item in payload.issues[0].evidence] == ["ev-zzz", "ev-aaa", "ev-mmm"]


# ---------------- Ticket 2（2026-09-12）：逐争点、单次、串行 writer（DoD） ----------------


def test_serial_render_shows_each_issue_exactly_once_in_state_order():
    """两个争点的 generator 每次只看到一个 issue，调用顺序与 state 一致，payload 不泄漏他争点证据。"""
    generator = PerIssueGenerator(text_by_issue={"issue-b": "《民法典》第五百八十五条规定约定违约金。"})
    result = EvidenceBoundedWriter(generator).render(state())

    assert result.status is WriterStatus.READY
    assert [payload.issues[0].issue_id for payload, _ in generator.calls] == ["issue-a", "issue-b"]
    assert all(len(payload.issues) == 1 for payload, _ in generator.calls)
    first_payload = generator.calls[0][0]
    assert [item.evidence_id for item in first_payload.issues[0].evidence] == ["ev-a"]
    serialized = first_payload.model_dump_json()
    assert "ev-b" not in serialized
    assert "违约金" not in serialized  # issue-b 的问题文本不得进入 issue-a 的 payload


def test_serial_render_stops_at_first_failure_with_exactly_n_calls():
    """第 N 个争点失败后调用次数恰为 N，后续争点不调用。"""

    class FailOnSecondIssue(PerIssueGenerator):
        def respond(self, payload):
            if payload.issues[0].issue_id == "issue-b":
                return {"claims": [], "missing_information": []}  # 零 claim → ISSUE_CLAIMS_MISSING
            return super().respond(payload)

    generator = FailOnSecondIssue()
    result = EvidenceBoundedWriter(generator).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "ISSUE_CLAIMS_MISSING"
    assert result.draft is None
    assert [payload.issues[0].issue_id for payload, _ in generator.calls] == ["issue-a", "issue-b"]


def test_second_issue_referencing_first_issue_evidence_fails_deterministically():
    """第二个争点故意引用第一个争点的证据 ID → CROSS_ISSUE_EVIDENCE 确定性失败，无终稿。"""

    class StealEvidenceGenerator(PerIssueGenerator):
        def respond(self, payload):
            issue = payload.issues[0]
            if issue.issue_id == "issue-b":
                return {
                    "claims": [
                        {
                            "local_id": "steal",
                            "issue_id": "issue-b",
                            "text": "《民法典》第一百八十八条规定诉讼时效期间为三年。",
                            "evidence_ids": ["ev-a"],  # 属于 issue-a 的证据
                            "fact_ids": [],
                            "section": "conclusion",
                        }
                    ],
                    "missing_information": [],
                }
            return super().respond(payload)

    result = EvidenceBoundedWriter(StealEvidenceGenerator()).render(state())

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "CROSS_ISSUE_EVIDENCE"
    assert result.draft is None


def test_render_issue_unknown_issue_id_fails_integrity():
    result = EvidenceBoundedWriter(PerIssueGenerator()).render_issue(state(), "issue-zz")

    assert result.status is WriterStatus.FAIL_SAFE
    assert result.reason_code == "STATE_INTEGRITY_FAILURE"


def test_five_issues_produce_five_generations_and_merged_draft_passes_verifier():
    """五个争点成功时恰好得到五次有效生成，合并后 verifier PASS。"""
    from agent.verifier import DeterministicVerifier, VerificationVerdict

    issues = [LegalIssue(issue_id=f"issue-{index}", question=f"争点{index}的认定") for index in range(1, 6)]
    observations = [
        Observation(
            issue_id=issue.issue_id,
            statement=f"已取得争点{issue.issue_id}依据",
            evidence_ids=[f"ev-{issue.issue_id}"],
            confidence=0.9,
        )
        for issue in issues
    ]
    evidence_list = [
        evidence(
            f"ev-{issue.issue_id}",
            snippet="《民法典》第一百八十八条规定诉讼时效期间为三年。",
        )
        for issue in issues
    ]
    merged_state = LegalAgentState(
        steps=9,
        issues=issues,
        observations=observations,
        evidence=evidence_list,
    )
    generator = PerIssueGenerator()  # 每个 payload 只有一个 issue，claim 绑其自身证据
    result = EvidenceBoundedWriter(generator).render(merged_state)

    assert result.status is WriterStatus.READY
    assert len(generator.calls) == 5
    assert [payload.issues[0].issue_id for payload, _ in generator.calls] == [issue.issue_id for issue in issues]
    assert result.draft is not None
    assert [claim.issue_id for claim in result.draft.conclusion] == [issue.issue_id for issue in issues]
    verification = DeterministicVerifier().verify(merged_state, result.draft)
    assert verification.verdict is VerificationVerdict.PASS


def test_merge_draft_answers_preserves_order_and_dedups_missing_information():
    """合并保持各 section 争点原顺序；missing_information 稳定去重；claim_checks 恒空（由 verifier 生成）。"""
    from agent.writer import DraftClaim, derive_claim_id, merge_draft_answers

    def claim(issue_id: str, text: str, section: str) -> DraftClaim:
        return DraftClaim(
            claim_id=derive_claim_id(issue_id, text, ["ev-x"], []),
            issue_id=issue_id,
            text=text,
            evidence_ids=("ev-x",),
            fact_ids=(),
            section=section,  # type: ignore[arg-type]
        )

    first = DraftAnswer(
        conclusion=(claim("issue-a", "甲争点结论。", "conclusion"),),
        issue_analysis=(claim("issue-a", "甲争点分析。", "issue_analysis"),),
        risks=(claim("issue-a", "甲争点风险。", "risk"),),
        missing_information=("待补信息一", "待补信息二"),
    )
    second = DraftAnswer(
        conclusion=(claim("issue-b", "乙争点结论。", "conclusion"),),
        missing_information=("待补信息二", "待补信息三"),
    )

    merged = merge_draft_answers([first, second])

    assert [item.text for item in merged.conclusion] == ["甲争点结论。", "乙争点结论。"]
    assert [item.text for item in merged.issue_analysis] == ["甲争点分析。"]
    assert [item.text for item in merged.risks] == ["甲争点风险。"]
    assert merged.missing_information == ("待补信息一", "待补信息二", "待补信息三")
    assert merged.claim_checks == ()


# ==================== 2026-09-15 观测改进：引用失败的**形态类别** ====================


def test_noncanonical_citation_reduces_to_unbracketed_form():
    """N1（2026-09-15 代码审查）：NON_CANONICAL_CITATION 目前**只有**「法名缺书名号」一类。

    `has_noncanonical_citation` 的定义即 `_UNBRACKETED_CITATION_RE` 命中，故 writer 里
    该失败的形态类别是**固定值** `unbracketed_law_name`（原独立分类函数为恒返回同值的
    常量包装，已删除）。本测试钉住这个**不变量**：一旦引入第二类非规范形态，
    这里会立刻失败，提醒恢复独立分类函数（否则观测字段失真）。
    """
    from agent.writer import _UNBRACKETED_CITATION_RE, has_noncanonical_citation

    for text in ("民法典第五百八十五条", "根据《民法典》第一百八十八条", "《民法典》第一百八十八条"):
        assert has_noncanonical_citation(text) is (_UNBRACKETED_CITATION_RE.search(text) is not None)


# ==================== 2026-09-15 代码审查 B：未决事实脱敏 ====================


@pytest.mark.parametrize(
    "statement",
    [
        # 真实语料里 from_unknown_facts 违规的来源（C01，1e3 轮实测）
        "公司是否提前三十日书面通知或额外支付一个月工资作为代通知金",
        "用户的入职时间及解除前十二个月的平均工资数额",
        # 其他类型数字（日期/金额/百分比）——通用性
        "是否在2026年3月1日前支付5000元赔偿金（占比30%）",
        "拖欠工资共计12000.50元，逾期365日",
        # 无数字：必须原样不变（避免过度脱敏）
        "绩效考核制度是否经过民主程序制定并已向劳动者公示或告知",
    ],
)
def test_desensitize_unknown_fact_removes_every_numeric_token(statement: str) -> None:
    """B 的**确定性验收断言**：脱敏后与原文本的 numeric token **交集必须为空**。

    这是"模型无从复述未决事实数字"的充要条件（口径与 `numeric_tokens` 完全一致——
    writer 的 numeric 校验用的就是它）。
    """
    from agent.writer import desensitize_unknown_fact, numeric_tokens

    out = desensitize_unknown_fact(statement)
    assert numeric_tokens(out) & numeric_tokens(statement) == set(), f"{statement!r} -> {out!r}"
    # 二次脱敏幂等（不会反复改写）
    assert desensitize_unknown_fact(out) == out
    # 无数字文本必须原样保留（不过度脱敏）
    if not numeric_tokens(statement):
        assert out == statement
    # 跨模块契约（2026-09-16）：脱敏输出**不得**含 verifier 的违禁词——
    # 初版替换词"一定期限/一定比例"里的"一定"命中 _OVERCONFIDENT_MARKERS ⇒
    # 模型忠实复述脱敏文本反而触发 OVERCONFIDENT_WORDING（1e6/1e8 实测的回归）。
    from agent.verifier import _OVERCONFIDENT_MARKERS

    hits = [m for m in _OVERCONFIDENT_MARKERS if m in out]
    assert not hits, f"{statement!r} -> {out!r} 含违禁词 {hits}"


def test_writer_unknown_facts_gate_controls_desensitization() -> None:
    """B：开关收口在 `writer_unknown_facts`——关时**逐字不变**，开时才脱敏。

    只动 `unknown_facts`；`facts`/`evidence` 不在此函数内，故不会被脱敏
    （已确认事实允许引用，不得脱敏——这条由函数边界保证）。
    """
    from types import SimpleNamespace

    from agent.writer import writer_unknown_facts

    issue = SimpleNamespace(
        unknown_facts=[
            SimpleNamespace(statement="公司是否提前三十日书面通知？"),
            SimpleNamespace(statement="是否有客观、量化的考核记录？"),
        ]
    )
    off = writer_unknown_facts(issue, desensitize=False)
    on = writer_unknown_facts(issue, desensitize=True)

    assert off == ("公司是否提前三十日书面通知？", "是否有客观、量化的考核记录？")  # 关：逐字不变
    assert "三十日" not in on[0]  # 开：数字消失
    assert on[1] == off[1]  # 无数字项不受影响


def test_build_writer_payload_honours_desensitize_setting(monkeypatch) -> None:
    """B：`build_writer_payload` 必须按 settings 开关决定是否脱敏（默认关）。

    用真实 fixture state；若该 state 的未知事实不含数字，则两臂相同也算通过
    （重点是**开关被真正读取**，不是特例行为）。
    """
    from agent.writer import build_writer_payload
    from settings import settings

    monkeypatch.setattr(settings, "agent_writer_desensitize_unknown_facts", False, raising=False)
    off = build_writer_payload(state())
    monkeypatch.setattr(settings, "agent_writer_desensitize_unknown_facts", True, raising=False)
    on = build_writer_payload(state())

    assert len(off.issues) == len(on.issues)
    for a, b in zip(off.issues, on.issues, strict=True):
        assert a.facts == b.facts  # facts 永不脱敏
        assert a.evidence == b.evidence  # evidence 永不脱敏
        assert len(a.unknown_facts) == len(b.unknown_facts)


def test_continuation_form_is_expanded_not_rejected():
    """A 项（2026-09-15）：「《民法典》第577条、第578条」展开为**两条独立引用**，不再判非规范。

    依据：12 次采样量化中 citation 失败 2/2 全为 continuation_form——原实现
    （`has_noncanonical_citation` 直接拒绝 + `canonical_citations` 只提取首条）
    使续引的第二条**既被拒又无法被核验**，属解析能力不足造成的误杀。
    """
    from agent.writer import canonical_citations, has_noncanonical_citation

    text = "《民法典》第五百七十七条、第五百七十八条"
    assert has_noncanonical_citation(text) is False
    assert canonical_citations(text) == {("民法典", "577", ""), ("民法典", "578", "")}


def test_continuation_expansion_preserves_verification_strength():
    """展开后第二条**照样独立核验**：只绑 577 时引用「577、578」仍判 unsupported（强度不变）。"""
    from agent.writer import canonical_citations

    cited = canonical_citations("《民法典》第五百七十七条、第五百七十八条")
    bound = canonical_citations("《民法典》第五百七十七条")
    assert cited - bound == {("民法典", "578", "")}


def test_canonical_citations_in_order_keeps_first_mention_order():
    """T2（2026-09-16）：顺序提取视图——同一解析器（复用 canonical_citations 的模式集），
    只是把集合变成"按正文首次出现顺序去重"的列表（法律依据渲染的顺序真源）。"""
    from agent.writer import canonical_citations, canonical_citations_in_order

    text = "根据《民法典》第五百七十八条与《劳动法》第七十七条，另依《民法典》第五百七十七条。"
    ordered = canonical_citations_in_order(text)
    assert ordered == [
        ("民法典", "578", ""),
        ("劳动法", "77", ""),
        ("民法典", "577", ""),
    ]
    # 与集合视图一致（同一解析能力，不另写第二套 parser）
    assert set(ordered) == canonical_citations(text)
    # 重复引用去重，保留首次位置
    assert canonical_citations_in_order("依《民法典》第五百七十七条，再引《民法典》第五百七十七条。") == [
        ("民法典", "577", "")
    ]


def test_continuation_digits_are_not_numeric_tokens():
    """续引条号属**引用跨度**，不得被当作可溯源数字（否则误报 UNSUPPORTED_NUMERIC_TOKEN）。

    依据：`numeric_tokens` 对引用跨度整体占位；A 项把续引纳入该占位集合，
    与首条口径一致（否则同一引用会因位置不同得到不同数字判定）。
    """
    from agent.writer import numeric_tokens, unsupported_numeric_tokens

    text = "《民法典》第五百七十七条、第五百七十八条"
    assert numeric_tokens(text) == numeric_tokens("《民法典》第五百七十七条")
    assert unsupported_numeric_tokens(text, "《民法典》第五百七十七条") == set()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 1 条（基线）
        ("《民法典》第五百七十七条", {("民法典", "577", "")}),
        # 2 连（修复前即可通过，作为回归锚点）
        ("《民法典》第五百七十七条、第五百七十八条", {("民法典", "577", ""), ("民法典", "578", "")}),
        # 3 连 —— 🔴 B1：修复前只提取前 2 条
        (
            "《民法典》第五百七十七条、第五百七十八条、第五百七十九条",
            {("民法典", "577", ""), ("民法典", "578", ""), ("民法典", "579", "")},
        ),
        # 4 连
        (
            "《民法典》第五百七十七条、第五百七十八条、第五百七十九条、第五百八十条",
            {("民法典", "577", ""), ("民法典", "578", ""), ("民法典", "579", ""), ("民法典", "580", "")},
        ),
        # 「和 / 及」分隔的 3 连（同族形态）
        (
            "《民法典》第五百七十七条和第五百七十八条及第五百七十九条",
            {("民法典", "577", ""), ("民法典", "578", ""), ("民法典", "579", "")},
        ),
        # 括号夹注后**继续续引**
        (
            "《民法典》第五百七十七条（违约责任）、第五百七十八条、第五百七十九条",
            {("民法典", "577", ""), ("民法典", "578", ""), ("民法典", "579", "")},
        ),
        # 混法名：链式条号归属**前一个**法名，另一法名另起链
        (
            "《民法典》第五百七十七条、第五百七十八条，《劳动合同法》第八十七条、第八十八条、第八十九条",
            {
                ("民法典", "577", ""),
                ("民法典", "578", ""),
                ("劳动合同法", "87", ""),
                ("劳动合同法", "88", ""),
                ("劳动合同法", "89", ""),
            },
        ),
    ],
)
def test_canonical_citations_expands_arbitrary_chain_length(text: str, expected: set) -> None:
    """任意长度的续引链都必须**逐条提取**（B1，2026-09-15 代码审查发现）。

    修复前行为（实测）：3 连及以上只提取前 2 条 ——
    `_CONTINUATION_CITATION_RE` 仅匹配「《法》A条 sep B条」**一对**，
    且 `finditer` 不重叠 → 第 3 条起因无《》前缀而落空。
    危害双向：① 编造的第 3 条**既不进核验集也不判非规范**（引用防线盲区）；
    ② 真实的第 3 条被判 UNSUPPORTED_CITATION / FABRICATED_CITATION。

    可达性证据（独立正则扫 116 个历史 DB / 1034 行文本）：链长 ≥3 出现 **16 次**。
    """
    from agent.writer import canonical_citations

    assert canonical_citations(text) == expected


def test_citation_unsupported_shape_distinguishes_three_roots():
    """漏绑 / 跨争点 / 池外编造——三类根因修法完全不同（prompt vs planner vs 防幻觉）。

    用显式 payload 构造三种情形（state() 的 issue-a 只有 1 条证据，无法构造"漏绑"）。
    """
    from agent.schemas import LegalValidity, SourceType
    from agent.writer import WriterEvidence, WriterIssue, WriterPayload, citation_unsupported_shape

    def ev(eid, ref):
        return WriterEvidence(
            evidence_id=eid,
            source_ref=ref,
            source_type=SourceType.STATUTE,
            snippet=f"{ref}之条文。",
            legal_validity=LegalValidity.EFFECTIVE,
        )

    issue_a = WriterIssue(
        issue_id="issue-a",
        question="甲争点？",
        evidence=(ev("e1", "民法典#第一百八十八条"), ev("e2", "民法典#第五百八十五条")),
    )
    issue_b = WriterIssue(issue_id="issue-b", question="乙争点？", evidence=(ev("e3", "劳动合同法#第四十条"),))
    payload = WriterPayload(issues=(issue_a, issue_b), resolved_conflict_ids=())
    bound = "《民法典》第一百八十八条"  # 只绑了 e1

    # e2 在本争点证据池内但未绑定 → 模型漏绑（改 prompt/绑定可解）
    assert (
        citation_unsupported_shape("《民法典》第五百八十五条", bound, payload, "issue-a") == "cited_in_pool_not_bound"
    )
    # e3 属**别的争点** → 无权引用（改 planner/争点-证据绑定才可解）
    assert citation_unsupported_shape("《劳动合同法》第四十条", bound, payload, "issue-a") == "cited_from_other_issue"
    # 池内哪里都查不到 → 编造/凭常识引用（防幻觉重点）
    assert citation_unsupported_shape("《刑法》第九十九条", bound, payload, "issue-a") == "cited_not_retrieved"
    # 无缺失 → 不该被判为 unsupported
    assert citation_unsupported_shape("《民法典》第一百八十八条", bound, payload, "issue-a") == "unclassified"


def test_writer_summary_carries_citation_shape_and_no_text():
    """形态类别必须落进 agent_writer_summary.citation_violation，且**不含任何法条文本**。

    依据：2026-09-15 观测改进——原先只知道 reason_code，无法区分根因；
    但观测纪律要求「不含草稿文本」，故只记类别名。
    """
    import json as _json
    import logging as _logging

    records: list[_logging.LogRecord] = []

    class _Cap(_logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = _logging.getLogger("legal.agent")
    handler = _Cap(level=_logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(_logging.DEBUG)
    try:
        raw = response_claim(text="根据民法典第一百八十八条，诉讼时效期间为三年。", evidence_ids=["ev-a"])
        EvidenceBoundedWriter(RecordingGenerator(raw)).render_issue(state(), "issue-a")
    finally:
        logger.removeHandler(handler)

    summaries = [r.agent_writer_summary for r in records if hasattr(r, "agent_writer_summary")]
    assert summaries, "writer 摘要未落日志"
    assert any(s["citation_violation"] == "unbracketed_law_name" for s in summaries), summaries
    dumped = _json.dumps(summaries, ensure_ascii=False)
    assert "《" not in dumped and "民法典" not in dumped
