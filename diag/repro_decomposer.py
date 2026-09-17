"""阶段A 最小复现：在隔离预检容器内直接调用 Agent 争点分解器。

只针对冻结题跑一次分解调用，打印脱敏的响应形状与确切的异常类型/消息，
不打印 token、密钥、环境变量。用于定位 agent_status,failed 的根因层。
"""
import json
import sys

sys.path.insert(0, "/app")

QUERY = "2020年借款约定2021年还，至今未还，2026年还能起诉吗？"


def main() -> None:
    from request_bootstrap import RequestBootstrap
    from agent.runtime import (
        AdapterPolicyViolation,
        IssueDecompositionError,
        IssueDecompositionUnavailable,
        LLMIssueDecomposer,
        build_initial_agent_state,
    )
    from agent.schemas import AgentBudgets
    from llm_registry import registry

    bootstrap = RequestBootstrap(
        conv_id=2,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=QUERY,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=QUERY,
        supplement_text="",
        intent="legal",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )

    transport = registry.get()
    print("TRANSPORT_MODEL:", getattr(transport, "model_name_or_path", None) or getattr(transport, "model", None))

    decomposer = LLMIssueDecomposer(transport)

    # 第 1 步：单独观察分解器原始输出（合成测试题，非用户数据；只打印结构与引文）
    try:
        raw = decomposer.decompose(bootstrap)
    except IssueDecompositionUnavailable as exc:
        print("STEP1_DECOMPOSE_UNAVAILABLE:", exc)
        return
    except Exception as exc:  # noqa: BLE001 - 诊断脚本需要看到一切
        print("STEP1_UNEXPECTED_EXCEPTION:", type(exc).__name__, "|", str(exc)[:400])
        return

    print("STEP1_RAW_TYPE:", type(raw).__name__)
    try:
        print("STEP1_RAW_JSON:", json.dumps(raw, ensure_ascii=False)[:3000])
    except TypeError:
        print("STEP1_RAW_NOT_JSON_SERIALIZABLE:", repr(raw)[:1000])

    # 第 2 步：走完整的 build_initial_agent_state 校验链
    try:
        state = build_initial_agent_state(bootstrap, decomposer=decomposer, budgets=AgentBudgets())
    except AdapterPolicyViolation as exc:
        print("STEP2_ADAPTER_POLICY_VIOLATION:", str(exc)[:300])
        return
    except IssueDecompositionError as exc:
        print("STEP2_ISSUE_DECOMPOSITION_ERROR:", str(exc)[:300])
        return
    except IssueDecompositionUnavailable:
        print("STEP2_DECOMPOSITION_UNAVAILABLE")
        return
    except Exception as exc:  # noqa: BLE001
        print("STEP2_UNEXPECTED_EXCEPTION:", type(exc).__name__, "|", str(exc)[:400])
        return

    print("STEP2_STATE_OK issues=%d" % len(state.issues))
    for issue in state.issues:
        print(
            "ISSUE %s facts=%d unknowns=%d q=%s"
            % (issue.issue_id[:20], len(issue.facts), len(issue.unknown_facts), issue.question[:60])
        )


if __name__ == "__main__":
    main()
