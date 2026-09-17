"""阶段A 仪器化复现 #2：decompose/decide/generate 全部旁路记录原始输出形状。"""
import json
import sys
import time

sys.path.insert(0, "/app")

QUERY = "2020年借款约定2021年还，至今未还，2026年还能起诉吗？"
records = []


def _shape(text: str) -> dict:
    t = text.strip()
    return {
        "len": len(t),
        "head": t[:300],
        "tail": t[-200:],
        "starts_json": t.startswith("{"),
        "has_fence": t.startswith("```") or "\n```" in t,
    }


def wrap(cls, method, tag):
    orig = getattr(cls, method)

    def instrumented(self, *args, **kwargs):
        t0 = time.perf_counter()
        try:
            out = orig(self, *args, **kwargs)
        except Exception as exc:
            records.append(
                {"tag": tag, "ok": False, "ms": round((time.perf_counter() - t0) * 1000), "exc": type(exc).__name__}
            )
            raise
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
        records.append(
            {"tag": tag, "ok": True, "ms": round((time.perf_counter() - t0) * 1000), **_shape(text)}
        )
        return out

    setattr(cls, method, instrumented)


def main() -> None:
    from request_bootstrap import RequestBootstrap
    from agent.runtime import LLMDraftGenerator, LLMIssueDecomposer, LLMPlannerAdapter
    from agent.service import execute_agent_request
    from database import SessionLocal
    from models import Conversation
    from main import finalize_verified_agent_answer

    wrap(LLMIssueDecomposer, "decompose", "decompose")
    wrap(LLMPlannerAdapter, "decide", "planner_decide")
    wrap(LLMDraftGenerator, "generate", "draft_generate")

    db = SessionLocal()
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
    from settings import settings

    t0 = time.perf_counter()
    result = execute_agent_request(
        db=db,
        user_id=1,
        settings=settings,
        bootstrap=bootstrap,
        finalizer=finalize_verified_agent_answer,
    )
    print("OUTCOME:", result.outcome)
    print("REASON_CODE:", result.reason_code)
    print("ANSWER_CHARS:", len(result.answer) if result.answer else 0)
    print("TOTAL_MS:", round((time.perf_counter() - t0) * 1000))
    print("CALLS:")
    for r in records:
        print(json.dumps(r, ensure_ascii=False)[:900])


if __name__ == "__main__":
    main()
