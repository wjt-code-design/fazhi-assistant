"""004 writer 层 live 探针：容器内用真实 LongCat 传输渲染一个服务端构造的 DRAFTING 状态。

目的：验证真实模型在补全后的 AGENT_WRITER_SYSTEM 下能否产出通过严格校验的 claims 草稿
（阶段 B 收口项）。状态由服务端代码构造（borrow 既有测试 fixture 语义），模型只做起草。
只打印状态码/reason/claim 数/答案片段，不打印密钥与环境。
"""
import sys

sys.path.insert(0, "/app")

from datetime import date

from agent.runtime import build_agent_runtime
from agent.schemas import (
    AgentBudgets,
    AgentStatus,
    Evidence,
    Fact,
    LegalAgentState,
    LegalIssue,
    LegalValidity,
    Observation,
    SourceType,
)
from agent.writer import WriterStatus


def main() -> None:
    from database import SessionLocal  # noqa: F401  (确保 models 注册)
    from settings import settings

    fact_text = "借款本金为10000元，约定2021年12月31日前归还"
    fact = Fact(statement=fact_text, source=SourceType.USER, source_ref="request:probe:user", confidence=1.0)
    issue = LegalIssue(issue_id="issue_probe_a", question="借款是否应返还", facts=[fact])
    evidence = Evidence(
        evidence_id="evidence_probe_1",
        source_id="statute:probe:675",
        source_ref="《中华人民共和国民法典》第675条",
        source_type=SourceType.STATUTE,
        snippet="借款人应当按照约定的期限返还借款。……第六百七十五条 逾期返还的，应当支付逾期利息。",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=date(2026, 8, 1),
    )
    from tools.contracts import RetrieveLawsOutput

    tool_output = RetrieveLawsOutput(
        statement="借款人应当按照约定的期限返还借款（检索命中民法典第675条）",
        evidence=[],
    )
    state = LegalAgentState(
        status=AgentStatus.DRAFTING,
        budgets=AgentBudgets(),
        issues=[issue],
        evidence=[evidence],
        observations=[
            Observation(
                issue_id="issue_probe_a",
                tool_name="retrieve_laws",
                status="succeeded",
                statement="已取得借款返还规则",
                evidence_ids=["evidence_probe_1"],
                output=tool_output,
            )
        ],
    )

    runtime = build_agent_runtime(db=None, user_id=1, settings=settings)
    result = runtime.writer.render(state)
    print("WRITER_STATUS:", result.status.value)
    print("REASON:", result.reason_code)
    print("DROPPED:", len(result.dropped_claim_ids))
    if result.draft is not None:
        d = result.draft
        print("CLAIMS: conclusion=%d issue_analysis=%d risks=%d" % (len(d.conclusion), len(d.issue_analysis), len(d.risks)))
        print("MISSING:", len(d.missing_information))
        for c in (d.conclusion + d.issue_analysis)[:3]:
            print("CLAIM_TEXT:", c.text[:120])
    verdict = result.status is WriterStatus.READY and result.draft is not None
    print("WRITER-LIVE:", "PASS" if verdict else "FAIL")
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
