"""Real ASGI routes and isolated storage, with deterministic LLM/retrieval boundaries.

This verifies routing and persistence, not real model quality or production retrieval.
The shared conftest isolates the application, quota and Chroma databases before import.
"""

from __future__ import annotations

import json
from functools import partial
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from legal_workflow.gate import AgentGateDecision
from legal_workflow.schemas import LegalAgentState
from models import AgentRun, AgentStep, Conversation, Message, User
from tools.gateway import ToolGateway


class _LoanTransport:
    def __init__(self):
        self.stages = []

    def invoke(self, messages):
        system = messages[0].content
        if "争点分解器" in system:
            self.stages.append("decompose")
            payload = {
                "issues": [
                    {
                        "question": "借款是否应返还？",
                        "facts": [{"quote": "借款本金为10000元"}],
                        "unknown_facts": [
                            {"statement": "是否约定还款期限？", "why_outcome_changes": "影响返还请求的期限。"}
                        ],
                    }
                ]
            }
        elif "Planner" in system:
            self.stages.append("plan")
            payload = {"kind": "finish_research", "summary": "交由确定性评估。"}
        else:
            self.stages.append("write")
            issue = json.loads(messages[1].content)["issues"][0]
            payload = {
                "claims": [
                    {
                        "local_id": "repayment",
                        "issue_id": issue["issue_id"],
                        "text": "依据《民法典》第675条，借款人应当按照约定的期限返还借款。",
                        "evidence_ids": [issue["evidence"][0]["evidence_id"]],
                        "fact_ids": [],
                        "section": "conclusion",
                    }
                ],
                "missing_information": [],
            }
        return SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))


@pytest.fixture
def route_store(db, monkeypatch):
    import database
    import main
    from auth import get_current_user

    sessions = database.SessionLocal
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(main.settings, "agent_enabled", True)
    monkeypatch.setattr(main.settings, "agent_traffic_percent", 100)
    monkeypatch.setattr(main.settings, "agent_partial_delivery_enabled", False)
    monkeypatch.setattr(main.settings, "agent_writer_corrective_retry_enabled", False)
    monkeypatch.setattr(main, "classify_intent", lambda _text: "legal_query")
    monkeypatch.setattr(
        main,
        "decide_gate",
        lambda _bootstrap: AgentGateDecision(mode="agent_path", complexity="complex", reason_codes=("MULTI_STAGE",)),
    )
    monkeypatch.setattr(
        main, "_prepare_fast_path_only", lambda _bootstrap: pytest.fail("completed Agent must not enter Fast Path")
    )
    users = [User(username=name, password_hash="test") for name in ("route-owner", "route-other")]
    db.add_all(users)
    db.commit()
    conversation = Conversation(user_id=users[0].id, title="", summary="", message_count=0)
    db.add(conversation)
    db.commit()
    store = SimpleNamespace(
        sessions=sessions,
        user_id=users[0].id,
        other_id=users[1].id,
        conversation_id=conversation.id,
    )
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=store.user_id)
    try:
        yield store
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def route_runtime(monkeypatch):
    import main
    from legal_workflow.service import execute_agent_request

    transport = _LoanTransport()

    def retrieve(_context, args):
        return {
            "kind": "retrieve_laws",
            "statement": "取得借款返还期限规则。",
            "evidence": [
                {
                    "source_id": "civil-code-675",
                    "source": "民法典",
                    "article": "第675条",
                    "snippet": "借款人应当按照约定的期限返还借款。",
                    "legal_validity": "effective",
                }
            ],
            "retrieval": {"query": args.query, "requested_k": args.k, "returned_count": 1},
        }

    gateway = ToolGateway(wrapper_overrides={"retrieve_laws": retrieve})
    monkeypatch.setattr(main, "execute_agent_request", partial(execute_agent_request, llm=transport, gateway=gateway))
    actual_finalizer = main.finalize_verified_agent_answer
    # Only the isolated evidence lookup is replaced. The Writer, verifier,
    # normalization, final storage and public SSE projection remain real.
    monkeypatch.setattr(
        main,
        "finalize_verified_agent_answer",
        partial(
            actual_finalizer,
            citation_checker=lambda answer: [] if "《民法典》第675条" in answer else ["missing test citation"],
            quality_checker=lambda answer, has_context: SimpleNamespace(ok=bool(answer) and has_context),
            source_lookup=lambda source: source == "民法典",
        ),
    )
    return transport


def _events(response):
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.endswith("data: [DONE]\n\n")
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]


def _start(client, store):
    events = _events(
        client.post(
            "/api/chat",
            json={"content": "借款本金为10000元，可以要求返还吗？", "conversation_id": store.conversation_id},
        )
    )
    assert events[0] == {"type": "agent_status", "status": "processing"}
    assert events[-1]["type"] == "clarification"
    steps = [event for event in events if event["type"] == "step"]
    assert steps, "Agent 路径必须推送真实 step 事件"
    for event in steps:
        step = event["steps"][0]
        assert step["label"] and step["detail"]
    clarification = events[-1]
    assert clarification["prompt"] == "是否约定还款期限？"
    return {
        "content": "约定于2023年1月还款",
        "conversation_id": store.conversation_id,
        "agent_run_id": clarification["run_id"],
        "agent_state_version": clarification["state_version"],
    }


def test_real_route_resume_stores_one_verified_answer_and_rejects_replay(route_store, route_runtime):
    import main

    with TestClient(main.app) as client:
        payload = _start(client, route_store)
        with route_store.sessions() as db:
            record = db.get(AgentRun, payload["agent_run_id"])
            assert record.status == "waiting_user"
            assert db.query(Message).filter_by(role="user").count() == 1
            assert db.query(Message).filter_by(role="assistant").count() == 0

        events = _events(client.post("/api/chat", json=payload))
        types = [event["type"] for event in events]
        assert types[0] == "agent_status"
        assert "step" in types
        assert types[-3:] == ["verification", "token", "final"]
        assert events[0]["status"] == "processing"
        assert any(event.get("status") == "completed" for event in events)
        verification = next(event for event in events if event["type"] == "verification")
        assert verification["verdict"] == "PASS"
        assert events[-1]["run_id"] == payload["agent_run_id"]
        assert events[-1]["state_version"] > payload["agent_state_version"]
        stages = list(route_runtime.stages)

        replay = client.post("/api/chat", json=payload)
        assert replay.status_code == 409
        assert "data:" not in replay.text
        assert route_runtime.stages == stages

    with route_store.sessions() as db:
        run = db.query(AgentRun).one()
        assert run.status == "completed"
        state = LegalAgentState.model_validate_json(run.state_json)
        assert "约定于2023年1月还款" in [fact.statement for fact in state.issues[0].facts]
        assert db.query(AgentStep).filter_by(decision="finalize").count() == 1
        assert db.query(Message).filter_by(role="user").count() == 1
        answers = db.query(Message).filter_by(role="assistant").all()
        assert [answer.content for answer in answers] == [events[-2]["content"]]
        assert db.get(Conversation, route_store.conversation_id).message_count == 2


def test_real_route_foreign_resume_rejects_before_execution_and_state_write(route_store, route_runtime):
    import main
    from auth import get_current_user

    with TestClient(main.app) as client:
        payload = _start(client, route_store)
        stages = list(route_runtime.stages)
        with route_store.sessions() as db:
            before = db.get(AgentRun, payload["agent_run_id"])
            snapshot = before.state_json, before.state_version, db.query(AgentStep).count()
        main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=route_store.other_id)
        response = client.post("/api/chat", json=payload)

    assert response.status_code == 404
    assert response.json() == {"detail": "未找到可恢复的 Agent 任务"}
    assert "data:" not in response.text
    assert route_runtime.stages == stages
    with route_store.sessions() as db:
        after = db.get(AgentRun, payload["agent_run_id"])
        assert (after.state_json, after.state_version, db.query(AgentStep).count()) == snapshot
        assert db.query(Message).filter_by(role="assistant").count() == 0


def test_real_route_failed_worker_emits_safe_sse_error_and_releases_turn(route_store, monkeypatch):
    import main

    locks = []
    actual_acquire = main._acquire_chat_turn

    async def capture_lock(*args):
        lock = await actual_acquire(*args)
        locks.append(lock)
        return lock

    def fail_worker(**kwargs):
        raise RuntimeError("private provider detail must not escape")

    monkeypatch.setattr(main, "_acquire_chat_turn", capture_lock)
    monkeypatch.setattr(main, "execute_agent_request", fail_worker)
    with TestClient(main.app) as client:
        events = _events(
            client.post(
                "/api/chat",
                json={"content": "借款本金为10000元，可以要求返还吗？", "conversation_id": route_store.conversation_id},
            )
        )
    assert events == [
        {"type": "agent_status", "status": "processing"},
        {"type": "error", "message": "服务暂时无响应，请稍后重试。"},
    ]
    assert len(locks) == 1 and not locks[0].locked()
    with route_store.sessions() as db:
        assert db.query(Message).filter_by(role="assistant").count() == 0
