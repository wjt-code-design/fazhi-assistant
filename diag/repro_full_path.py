"""阶段A 仪器化复现：走完整生产 execute_agent_request 路径（隔离容器内）。

对分解器调用做旁路记录（原始输出形状/耗时），结果只打印 outcome/reason_code
与数据库行数，不打印正文与密钥。目标：判别 07:34 失败是确定性还是间歇性，
并拿到违约输出的真实形状。
"""
import json
import sys
import time

sys.path.insert(0, "/app")

QUERY = "2020年借款约定2021年还，至今未还，2026年还能起诉吗？"

records = []


def main() -> None:
    from request_bootstrap import RequestBootstrap
    from agent.runtime import LLMIssueDecomposer
    from agent.service import execute_agent_request

    bootstrap = RequestBootstrap(
        conv_id=0,  # 由下方真实创建的会话回填
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
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )

    from database import SessionLocal
    from models import Conversation, User

    db = SessionLocal()
    user = db.query(User).filter_by(id=1).one_or_none()
    assert user is not None, "isolated synthetic user missing"
    conv = Conversation(user_id=1, question=QUERY, message_count=1)
    db.add(conv)
    db.commit()
    bootstrap = RequestBootstrap(
        conv_id=conv.id,
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
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
    )

    # 旁路仪器：包装 decomposer.decompose，记录每次调用的输出形状与耗时
    import agent.runtime as runtime_mod

    orig_decompose = LLMIssueDecomposer.decompose

    def instrumented_decompose(self, bs):
        t0 = time.perf_counter()
        try:
            raw = orig_decompose(self, bs)
        except Exception as exc:
            records.append(
                {
                    "phase": "decompose",
                    "ok": False,
                    "ms": round((time.perf_counter() - t0) * 1000),
                    "exc": type(exc).__name__,
                }
            )
            raise
        records.append(
            {
                "phase": "decompose",
                "ok": True,
                "ms": round((time.perf_counter() - t0) * 1000),
                "raw_type": type(raw).__name__,
                "raw": raw if isinstance(raw, dict) else repr(raw)[:500],
            }
        )
        return raw

    LLMIssueDecomposer.decompose = instrumented_decompose  # type: ignore[method-assign]

    from main import finalize_verified_agent_answer

    t0 = time.perf_counter()
    result = execute_agent_request(
        db=db,
        user_id=1,
        settings=_settings_like(),
        bootstrap=bootstrap,
        finalizer=finalize_verified_agent_answer,
    )
    total_ms = round((time.perf_counter() - t0) * 1000)

    print("OUTCOME:", result.outcome)
    print("REASON_CODE:", result.reason_code)
    print("RUN_ID:", result.run_id)
    print("STATE_VERSION:", result.state_version)
    print("ANSWER_CHARS:", len(result.answer) if result.answer else 0)
    print("TOTAL_MS:", total_ms)
    print("LLM_CALLS:", json.dumps(records, ensure_ascii=False, default=str)[:4000])

    from models import AgentRun, AgentStep, Message

    print(
        "DB_ROWS runs=%d steps=%d assistant_msgs=%d"
        % (
            db.query(AgentRun).filter_by(conversation_id=conv.id).count(),
            db.query(AgentStep).count(),
            db.query(Message).filter_by(conversation_id=conv.id, role="assistant").count(),
        )
    )

    if records and not records[-1].get("ok", True):
        print("LAST_CALL_FAILED_WITH:", records[-1]["exc"])


def _settings_like():
    from settings import settings

    return settings


if __name__ == "__main__":
    main()
