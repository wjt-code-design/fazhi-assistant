"""One bounded, request-scoped Legal Agent execution service."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, Protocol, cast

from request_bootstrap import RequestBootstrap
from routing_metrics import is_technical_fallback_reason
from tools.gateway import ToolGateway

from .chat_integration import (
    AgentFinalizationConflict,
    AgentOutcome,
    AgentPublicResult,
    CoverageStatus,
    persist_agent_final_once,
)
from .controller import ControllerResult
from .repository import (
    CheckpointMetadata,
    RunVersionConflict,
    compare_and_save,
    create_run,
    load_owned_run,
)
from .runtime import (
    AdapterPolicyViolation,
    IssueDecompositionError,
    IssueDecompositionUnavailable,
    LLMTransport,
    RuntimeUnavailable,
    build_agent_runtime,
)
from .schemas import AgentStatus, LegalAgentState, UncoveredIssue
from .state_machine import BudgetExceeded, transition
from .verifier import VerificationVerdict
from .writer import DraftAnswer, WriterStatus, is_effective_statute, issue_is_deficient, merge_draft_answers


class FinalizationResult(Protocol):
    answer: str | None
    reason_code: str


def _log_pre_run_failure(reason_code: str, conversation_id: int, exc: Exception) -> None:
    """run 创建前失败的唯一可观测点（003 已知限制 2 的可诊断性修复）。

    只记录 reason code 与异常摘要——不记录用户消息、模型原始输出或环境变量。
    """
    import logging

    logging.getLogger("legal.agent").warning(
        "agent_pre_run_failure",
        extra={
            "agent_pre_run_reason": reason_code,
            "agent_conversation_id": conversation_id,
            "agent_failure_detail": f"{type(exc).__name__}: {exc}"[:300],
        },
    )


Finalizer = Callable[..., FinalizationResult]
CancellationCheck = Callable[[], bool]


def _result(
    outcome: AgentOutcome,
    reason_code: str,
    *,
    run_id: str | None = None,
    conversation_id: int | None = None,
    state_version: int = 0,
    answer: str | None = None,
    prompt: str | None = None,
    issue_id: str | None = None,
    # T1（2026-09-16）：仅 completed 携带覆盖契约；其余 outcome 保持 None（模型校验强制）
    coverage_status: CoverageStatus | None = None,
    uncovered_issues: list[UncoveredIssue] | None = None,
) -> AgentPublicResult:
    return AgentPublicResult(
        outcome=outcome,
        run_id=run_id,
        conversation_id=conversation_id,
        state_version=state_version,
        answer=answer,
        prompt=prompt,
        issue_id=issue_id,
        reason_code=reason_code,
        coverage_status=coverage_status,
        uncovered_issues=uncovered_issues or [],
    )


def _failure_or_fallback(
    reason_code: str,
    *,
    run_id: str | None = None,
    conversation_id: int | None = None,
    state_version: int = 0,
) -> AgentPublicResult:
    return _result(
        "fallback" if is_technical_fallback_reason(reason_code) else "failed",
        reason_code,
        run_id=run_id,
        conversation_id=conversation_id,
        state_version=state_version,
    )


def _saved_failure_reason(db: Any, *, run_id: str, user_id: int, conversation_id: int) -> str:
    record = load_owned_run(
        db,
        run_id=run_id,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    if record is None:
        return "OWNERSHIP_FAILURE"
    return cast(str | None, record.last_error_code) or cast(str | None, record.degraded_reason) or "AGENT_FAILED"


def _coverage_issue_facts(state: LegalAgentState, draft: DraftAnswer) -> list[dict[str, Any]]:
    """逐争点的覆盖率判定事实（**只记标识与计数，不含任何文本**）。

    动机（2026-09-12 H3 C01 付费运行无法归因）：覆盖率闸门终态失败只落 `VERIFIER:FAIL_SAFE`
    与原因码，而 `verifier.py:289` 的 `not issue_claims or not has_effective_statute` 两种缺口
    ——「该争点**没有 claim**」与「有 claim 但**未绑定生效成文法**」——在归档里完全同形。
    这里把两者分开记录，使下一次失败可直接归因。

    判定复用 `writer.issue_is_deficient`（谓词单一真源）；证据视图 = `state.evidence` 全局视图，
    与 writer 侧 per-issue 视图的口径一致，不引入第二套谓词。
    """
    claims = [*draft.conclusion, *draft.issue_analysis, *draft.risks]
    evidence_by_id = {evidence.evidence_id: evidence for evidence in state.evidence}
    facts: list[dict[str, Any]] = []
    for issue in state.issues:
        issue_claims = [claim for claim in claims if claim.issue_id == issue.issue_id]
        bound = sum(
            1
            for claim in issue_claims
            if any(is_effective_statute(evidence_by_id.get(evidence_id)) for evidence_id in claim.evidence_ids)
        )
        facts.append(
            {
                "issue_id": issue.issue_id,
                "claims": len(issue_claims),
                "claims_bound_effective_statute": bound,
                "deficient": issue_is_deficient(issue.issue_id, issue_claims, evidence_by_id),
            }
        )
    return facts


_UNCOVERED_REASON_TEXT = {
    "UNSUPPORTED_CITATION": "引用的法条不在已检索到的依据范围内",
    "UNKNOWN_FACT_ID": "所需事实不在已确认事实范围内",
    "UNKNOWN_EVIDENCE_ID": "所引证据不在本争点的检索结果内",
    "CROSS_ISSUE_EVIDENCE": "引用了属于其他争点的证据",
    "CROSS_ISSUE_FACT": "引用了属于其他争点的事实",
    "UNSUPPORTED_NUMERIC_TOKEN": "使用了无来源可核对的数字",
    "NON_CANONICAL_CITATION": "法条引用格式不规范",
    "ISSUE_CLAIMS_MISSING": "该争点未能形成可核验的结论",
    "INVALID_STATUTE_EVIDENCE": "所引法条非现行有效",
}


def _with_uncovered_notice(answer: str, uncovered: Sequence[tuple[str, str]], state: LegalAgentState) -> str:
    """在终稿**显式**列出未覆盖争点及原因（争点级部分交付，2026-09-15）。

    为什么必须显式：`§4.2` 禁止"为制造通过而降低覆盖率要求"，也禁止静默降级——
    用户必须能看见"哪些争点没答、为什么"，因此说明随**答复文本**一起交付（任何客户端都可见，
    无需前端改动）。未覆盖争点在评测口径中**仍记 FAIL/REVIEW**，本函数只改变交付形态。
    """
    if not uncovered:
        return answer
    question_by_id = {issue.issue_id: getattr(issue, "question", "") for issue in state.issues}
    lines = [answer, "", "—" * 8, "", "【未能覆盖的争点】", ""]
    lines.append("以下争点因现有依据不足，本次未能给出结论（已从结论部分排除，未作推断）：")
    lines.append("")
    for index, (issue_id, reason_code) in enumerate(uncovered, start=1):
        question = question_by_id.get(issue_id) or issue_id
        reason = _UNCOVERED_REASON_TEXT.get(reason_code, reason_code)
        lines.append(f"{index}. {question}")
        lines.append(f"   原因：{reason}（{reason_code}）")
    lines.append("")
    lines.append("如需就上述争点获得结论，建议补充相应材料后重新咨询。")
    return "\n".join(lines)


def _persist_drafting_failure(
    db: Any,
    *,
    saved_record: Any,
    state: LegalAgentState,
    state_version: int,
    public_reason: str,
    stage_reason: str,
) -> AgentPublicResult:
    """保存终稿阶段失败；存储/CAS 故障优先公开报告，原业务原因仅作诊断。"""
    run_id, conversation_id = saved_record.id, saved_record.conversation_id
    result_reason = public_reason
    try:
        try:
            failed_state = transition(state, AgentStatus.FAILED)
        except BudgetExceeded:
            failed_state = state.model_copy(update={"status": AgentStatus.FAILED})
        compare_and_save(
            db,
            run=saved_record,
            expected_version=state_version,
            state=failed_state,
            status=AgentStatus.FAILED.value,
            checkpoint=CheckpointMetadata(
                decision="failure",
                reason_code=public_reason,
                result_code=stage_reason,
                last_error_code=public_reason,
            ),
        )
        state_version += 1
    except Exception as exc:
        result_reason = (
            "AGENT_FINALIZATION_CONFLICT" if isinstance(exc, RunVersionConflict) else "AGENT_STORAGE_FAILURE"
        )
        logging.getLogger("legal.agent").warning(
            "agent_failure_persistence_failed",
            extra={
                "agent_run_id": run_id,
                "agent_conversation_id": conversation_id,
                "agent_failure_detail": {
                    "reason_code": result_reason,
                    "original_reason": public_reason,
                    "stage": stage_reason,
                    "error_class": type(exc).__name__,
                },
            },
        )
    return _failure_or_fallback(
        result_reason, run_id=run_id, conversation_id=conversation_id, state_version=state_version
    )


def execute_agent_request(
    *,
    db: Any,
    user_id: int,
    settings: Any,
    bootstrap: RequestBootstrap,
    finalizer: Finalizer,
    run_id: str | None = None,
    llm: LLMTransport | None = None,
    gateway: ToolGateway | None = None,
    cancelled: CancellationCheck | None = None,
) -> AgentPublicResult:
    """Execute or resume one bounded Agent run and persist PASS before returning it."""
    try:
        runtime = build_agent_runtime(
            db=db,
            user_id=user_id,
            settings=settings,
            llm=llm,
            gateway=gateway,
        )
    except RuntimeUnavailable:
        return _failure_or_fallback("TOOL_UNAVAILABLE", conversation_id=bootstrap.conv_id)
    except Exception:
        return _failure_or_fallback("AGENT_EXECUTION_FAILURE", conversation_id=bootstrap.conv_id)

    if run_id is None:
        try:
            initial_state = runtime.build_initial_state(bootstrap)
        except AdapterPolicyViolation as exc:
            _log_pre_run_failure("PLANNER_POLICY_VIOLATION", bootstrap.conv_id, exc)
            return _failure_or_fallback("PLANNER_POLICY_VIOLATION", conversation_id=bootstrap.conv_id)
        except IssueDecompositionError as exc:
            _log_pre_run_failure("ISSUE_DECOMPOSITION_INVALID", bootstrap.conv_id, exc)
            return _failure_or_fallback("ISSUE_DECOMPOSITION_INVALID", conversation_id=bootstrap.conv_id)
        except IssueDecompositionUnavailable as exc:
            _log_pre_run_failure("PLANNER_PARSE_ERROR", bootstrap.conv_id, exc)
            return _failure_or_fallback("PLANNER_PARSE_ERROR", conversation_id=bootstrap.conv_id)
        try:
            record = create_run(
                db,
                user_id=user_id,
                conversation_id=bootstrap.conv_id,
                state=initial_state,
            )
        except (PermissionError, ValueError):
            return _failure_or_fallback("OWNERSHIP_FAILURE", conversation_id=bootstrap.conv_id)
        active_run_id = cast(str, record.id)
    else:
        active_run_id = run_id

    try:
        controller_result: ControllerResult = runtime.controller.run(active_run_id, bootstrap)
    except PermissionError:
        return _failure_or_fallback("OWNERSHIP_FAILURE", run_id=active_run_id, conversation_id=bootstrap.conv_id)
    except Exception:
        # 此处原有一句冗余的 `import logging`（模块顶部已导入）。它会把这个名字变成整个
        # 函数的**局部变量**，使任何绕过本 except 块却使用 `logging` 的路径抛
        # UnboundLocalError（2026-09-12 覆盖率诊断埋点即因此失败）。删除后行为不变。
        logging.getLogger("legal.agent").exception(
            "agent_execution_failure_diagnostic", extra={"agent_run_id": active_run_id}
        )
        return _failure_or_fallback("AGENT_EXECUTION_FAILURE", run_id=active_run_id, conversation_id=bootstrap.conv_id)

    saved_record = load_owned_run(
        db,
        run_id=active_run_id,
        user_id=user_id,
        conversation_id=bootstrap.conv_id,
    )
    if saved_record is None:
        return _failure_or_fallback("OWNERSHIP_FAILURE", run_id=active_run_id, conversation_id=bootstrap.conv_id)
    state_version = cast(int, saved_record.state_version)
    state = controller_result.state
    # Do not combine a controller snapshot with a version belonging to another writer.
    if LegalAgentState.model_validate_json(cast(str, saved_record.state_json)) != state:
        return _failure_or_fallback(
            "AGENT_FINALIZATION_CONFLICT",
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )
    if cancelled is not None and cancelled():
        return _failure_or_fallback(
            "CLIENT_DISCONNECTED",
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )

    if state.status is AgentStatus.WAITING_USER:
        if state.pending_scope_issue_ids:
            # Ticket 1：争点范围选择待决——公开专用澄清事件（issue_id="scope"）。
            # 优先于普通事实澄清分支：此时无 evaluator 澄清锚点，prompt 取持久化编号清单。
            if not controller_result.pending_question:
                return _failure_or_fallback(
                    "AGENT_STATE_INTEGRITY_FAILURE",
                    run_id=active_run_id,
                    conversation_id=bootstrap.conv_id,
                    state_version=state_version,
                )
            return _result(
                "clarification",
                "ISSUE_SCOPE_SELECTION_REQUIRED",
                run_id=active_run_id,
                conversation_id=bootstrap.conv_id,
                state_version=state_version,
                prompt=controller_result.pending_question,
                issue_id="scope",
            )
        evaluation = controller_result.evaluation
        issue_id = evaluation.issue_id if evaluation is not None else None
        if not controller_result.pending_question or evaluation is None or not issue_id:
            return _failure_or_fallback(
                "AGENT_STATE_INTEGRITY_FAILURE",
                run_id=active_run_id,
                conversation_id=bootstrap.conv_id,
                state_version=state_version,
            )
        return _result(
            "clarification",
            evaluation.reason_code,
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
            prompt=controller_result.pending_question,
            issue_id=issue_id,
        )

    if state.status is not AgentStatus.DRAFTING:
        reason_code = _saved_failure_reason(
            db,
            run_id=active_run_id,
            user_id=user_id,
            conversation_id=bootstrap.conv_id,
        )
        return _failure_or_fallback(
            reason_code,
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )

    # Ticket 2（2026-09-12）：逐争点、单次、串行 writer——service 驱动循环，
    # 每个争点前检查取消；任一争点非 READY 立即失败（后续争点不再调用），
    # 全部成功后服务端确定性合并。不进入 coverage 回喂重写。
    drafts: list[DraftAnswer] = []
    # 争点级部分交付（2026-09-15，开关默认关 ⇒ 行为逐字不变）：
    # 关时维持"首个争点非 READY 即整轮失败"；开时把失败争点记为 uncovered 并继续其余争点，
    # 最后由 verifier 对其豁免覆盖判定、终稿显式列出未覆盖争点（防静默降级）。
    # 经**函数参数** settings 读取（与既有模式一致：service 不用全局单例）；
    # getattr 兜底兼容未带该字段的注入替身（缺省 = 关 = 行为逐字不变）。
    partial = bool(getattr(settings, "agent_partial_delivery_enabled", False))
    uncovered: list[tuple[str, str]] = []
    for issue in state.issues:
        if cancelled is not None and cancelled():
            return _failure_or_fallback(
                "CLIENT_DISCONNECTED",
                run_id=active_run_id,
                conversation_id=bootstrap.conv_id,
                state_version=state_version,
            )
        issue_result = runtime.writer.render_issue(state, issue.issue_id)
        if (
            partial
            and issue_result.status is not WriterStatus.READY
            and issue_result.reason_code == "ISSUE_CLAIMS_MISSING"
        ):
            # T3（2026-09-16）：零 claim 是 writer 单次生成的**非确定性抖动**——
            # 1e9 实证同分布输入 r1 写满 5 claim、r2 漏产 2/4 争点（required 条文
            # 87 条已检索归位仍丢失确定性结论）。对 ISSUE_CLAIMS_MISSING 重试**至多一次**
            # （重采样可改变结果）；确定性校验失败（UNKNOWN_*_ID / CROSS_ISSUE_* /
            # UNSUPPORTED_* 等）同输入同校验，重试无意义，不在此列。
            # 重试仍失败 → 落入下方既有 uncovered 兜底，行为不劣于现状。
            issue_result = runtime.writer.render_issue(state, issue.issue_id)
        if issue_result.status is not WriterStatus.READY or issue_result.draft is None:
            if not partial:
                return _persist_drafting_failure(
                    db,
                    saved_record=saved_record,
                    state=state,
                    state_version=state_version,
                    public_reason=issue_result.reason_code,
                    stage_reason=f"WRITER:{issue.issue_id}:{issue_result.reason_code}",
                )
            uncovered.append((issue.issue_id, issue_result.reason_code))
            continue
        drafts.append(issue_result.draft)
    if not drafts:
        # 全部争点都失败：**不得**伪造"部分交付"（无内容可交付）→ 仍整轮失败，
        # 保留**首个**失败争点的原因码（与关闭开关时的首个失败口径一致）。
        first_issue_id, first_reason = uncovered[0]
        return _persist_drafting_failure(
            db,
            saved_record=saved_record,
            state=state,
            state_version=state_version,
            public_reason=first_reason,
            stage_reason=f"WRITER:{first_issue_id}:{first_reason}",
        )
    draft = merge_draft_answers(drafts)
    try:
        verification = runtime.verifier.verify(
            state,
            draft,
            covered_issues_exempt=frozenset(issue_id for issue_id, _ in uncovered),
        )
    except Exception:
        return _persist_drafting_failure(
            db,
            saved_record=saved_record,
            state=state,
            state_version=state_version,
            public_reason="VERIFIER_TECHNICAL_FAILURE",
            stage_reason="VERIFIER:EXCEPTION",
        )
    if verification.verdict is not VerificationVerdict.PASS:
        # Ticket 2：每个争点只接受一次有效生成，coverage 不再回喂重写——首次 verifier
        # 非 PASS（RESEARCH_MORE/REWRITE/FAIL_SAFE）即终态失败（fail-closed），不触发第二轮 writer。
        # 保留逐争点可归因诊断：DB 里只留 verdict 与原因码，两种缺口（无 claim / 有 claim
        # 未绑生效成文法）同形。这里把逐争点事实写进结构化日志；字段已在 observability 白名单登记。
        facts = _coverage_issue_facts(state, draft)
        logging.getLogger("legal.agent").warning(
            "coverage_gate_terminal_failure",
            extra={
                "verdict": verification.verdict.value,
                "agent_run_id": active_run_id,
                "agent_conversation_id": bootstrap.conv_id,
                "agent_issue_count": len(state.issues),
                "agent_coverage_gap_count": sum(1 for row in facts if row["deficient"]),
                "agent_coverage_issues": facts,
            },
        )
        return _persist_drafting_failure(
            db,
            saved_record=saved_record,
            state=state,
            state_version=state_version,
            public_reason=verification.reason_code,
            stage_reason=f"VERIFIER:{verification.verdict.value}",
        )
    if cancelled is not None and cancelled():
        return _failure_or_fallback(
            "CLIENT_DISCONNECTED",
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )
    try:
        finalized = finalizer(state, draft, verification)
    except Exception:
        return _persist_drafting_failure(
            db,
            saved_record=saved_record,
            state=state,
            state_version=state_version,
            public_reason="VERIFIER_TECHNICAL_FAILURE",
            stage_reason="FINALIZER:EXCEPTION",
        )
    if finalized.answer is None:
        reason_code = (
            "VERIFIER_TECHNICAL_FAILURE"
            if finalized.reason_code == "FINAL_GATE_TECHNICAL_FAILURE"
            else finalized.reason_code
        )
        return _persist_drafting_failure(
            db,
            saved_record=saved_record,
            state=state,
            state_version=state_version,
            public_reason=reason_code,
            stage_reason=f"FINALIZER:{finalized.reason_code}",
        )
    if cancelled is not None and cancelled():
        return _failure_or_fallback(
            "CLIENT_DISCONNECTED",
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )
    # 争点级部分交付：未覆盖争点**必须显式出现**在交付文本里（防静默降级）。
    final_answer = _with_uncovered_notice(finalized.answer, uncovered, state)

    # R1b（2026-09-14，预注册 dept-law-filter-r1）：终稿程序法串台校验。
    # 开关 agent_proc_misroute_check=False 时零行为变化、零开销（纯函数短路）。
    # 检测不到 → 正常持久化；检测到 → 仍持久化（不阻断 agent_completed），仅记红线供评测/日志判定。
    from agent.dept_guard import check_proc_misroute, domain_of_text

    _domain = domain_of_text(" ".join(i.question for i in state.issues if getattr(i, "question", None)))
    if check_proc_misroute(final_answer, _domain):
        logging.getLogger("legal.agent").warning(
            "proc_misroute_flag",
            extra={"agent_run_id": active_run_id, "agent_conversation_id": bootstrap.conv_id},
        )
    # T1（2026-09-16）：把局部 uncovered 写入 state（覆盖信息事实源 = completed 的 run.state_json）。
    # 仅部分交付时需要一次 CAS（full 路径 state 不变，行为逐字不变）：
    # persist_agent_final_once 会校验 run.state_json == 传入 state，故必须先落盘再持久化。
    uncovered_items = [UncoveredIssue(issue_id=i, reason_code=r) for i, r in uncovered]
    if uncovered:
        state = state.model_copy(update={"uncovered_issues": uncovered_items})
        compare_and_save(
            db,
            run=saved_record,
            expected_version=state_version,
            state=state,
            status=AgentStatus.DRAFTING.value,
            checkpoint=CheckpointMetadata(
                decision="state_transition",
                reason_code="PARTIAL_DELIVERY_COVERAGE_RECORDED",
            ),
        )
        state_version += 1
    try:
        persist_agent_final_once(
            db,
            user_id=user_id,
            conversation_id=bootstrap.conv_id,
            run_id=active_run_id,
            expected_version=state_version,
            state=state,
            answer=final_answer,
            verification=verification,
        )
    except AgentFinalizationConflict:
        return _failure_or_fallback(
            "AGENT_FINALIZATION_CONFLICT",
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )
    except Exception:
        return _failure_or_fallback(
            "AGENT_STORAGE_FAILURE",
            run_id=active_run_id,
            conversation_id=bootstrap.conv_id,
            state_version=state_version,
        )
    return _result(
        "completed",
        "READY",
        run_id=active_run_id,
        conversation_id=bootstrap.conv_id,
        state_version=state_version + 1,
        answer=final_answer,
        coverage_status="partial" if uncovered else "full",
        uncovered_issues=uncovered_items,
    )


__all__ = ["execute_agent_request"]
