"""Task 8: explicit, owned and versioned WAITING_USER resume contract."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent.repository import create_run
from agent.schemas import (
    AgentStatus,
    Fact,
    LegalAgentState,
    LegalIssue,
    SourceType,
    UnknownFact,
)
from models import AgentRun, AgentStep, Base, Conversation, Message, User
from schemas import ChatIn

NOT_FOUND_DETAIL = "未找到可恢复的 Agent 任务"
CONFLICT_DETAIL = "Agent 任务已变化，无法恢复"
# D-10（2026-10-11）409 分档文案。这里**逐字硬编码**而不是从被测源码 import：
# 期望值必须独立于实现，否则文案改错时测试会跟着一起改绿。
ADVANCED_DETAIL = "这条任务已经处理过了，请回到对话查看最新结果。"
ANSWER_INVALID_DETAIL = "这个回答和当前的问题对不上，请重新回答一次。"
STEP_BUDGET_DETAIL = "这次任务可用的处理步骤已经用完了，请重新发起一次咨询。"
UNRECOVERABLE_DETAIL = "这条任务接不上了，请重新发起一次咨询。"
QUESTION = "是否约定履行期限"


@pytest.fixture
def store(tmp_path, monkeypatch):
    import database
    import main

    engine = create_engine(
        f"sqlite:///{tmp_path / 'agent-resume.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    Base.metadata.create_all(engine)
    try:
        yield engine, sessions
    finally:
        engine.dispose()


@pytest.fixture
def records(store):
    _engine, sessions = store
    db = sessions()
    owner = User(username="resume-owner", password_hash="test")
    other = User(username="resume-other", password_hash="test")
    db.add_all([owner, other])
    db.commit()
    conversation = Conversation(user_id=owner.id, question="", answer="")
    other_conversation = Conversation(user_id=owner.id, question="", answer="")
    db.add_all([conversation, other_conversation])
    db.commit()
    run = _waiting_run(db, owner.id, conversation.id)
    result = {
        "owner": SimpleNamespace(id=owner.id),
        "other": SimpleNamespace(id=other.id),
        "conversation": SimpleNamespace(id=conversation.id),
        "other_conversation": SimpleNamespace(id=other_conversation.id),
        "run_id": run.id,
    }
    db.close()
    return result


def _waiting_state(*, pending: str = QUESTION) -> LegalAgentState:
    return LegalAgentState(
        status=AgentStatus.WAITING_USER,
        steps=3,
        tool_calls=2,
        replans=1,
        clarifications=1,
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="请求权是否成立",
                facts=[
                    Fact(
                        statement="双方签署借款合同",
                        source=SourceType.DOCUMENT,
                        source_ref="document:contract-1",
                        confidence=1.0,
                    )
                ],
                unknown_facts=[
                    UnknownFact(statement=pending, why_outcome_changes="影响诉讼时效起算"),
                    UnknownFact(statement="是否约定违约金", why_outcome_changes="影响责任范围"),
                ],
            ),
            LegalIssue(
                issue_id="issue-b",
                question="是否存在担保责任",
                unknown_facts=[UnknownFact(statement="保证方式是什么", why_outcome_changes="影响责任范围")],
            ),
        ],
    )


def _waiting_run(db, user_id: int, conversation_id: int, *, pending: str = QUESTION) -> AgentRun:
    run = create_run(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
        state=_waiting_state(),
    )
    run.pending_question = pending
    db.commit()
    db.refresh(run)
    return run


def _service():
    from agent.controller import _DEFAULT_RUN_LOCKS, resume_with_user_fact

    return resume_with_user_fact, _DEFAULT_RUN_LOCKS


def _load_snapshot(sessions, run_id: str):
    db = sessions()
    try:
        run = db.get(AgentRun, run_id)
        assert run is not None
        return (
            run.status,
            run.state_version,
            run.pending_question,
            LegalAgentState.model_validate_json(run.state_json),
            db.query(AgentStep).filter_by(agent_run_id=run_id).count(),
        )
    finally:
        db.close()


def test_chat_in_resume_fields_are_uuid_versioned_and_all_or_none():
    ordinary = ChatIn(content="普通追问", conversation_id=1)
    assert ordinary.agent_run_id is None
    assert ordinary.agent_state_version is None

    with pytest.raises(ValidationError):
        ChatIn(content="回答", conversation_id=1, agent_run_id="not-a-uuid", agent_state_version=0)
    with pytest.raises(ValidationError):
        ChatIn(content="回答", conversation_id=1, agent_run_id="d53a02e0-4b80-4f16-8ad2-dcd877ddbfbc")
    with pytest.raises(ValidationError):
        ChatIn(
            content="回答",
            agent_run_id="d53a02e0-4b80-4f16-8ad2-dcd877ddbfbc",
            agent_state_version=0,
        )
    with pytest.raises(ValidationError):
        ChatIn(
            content="回答",
            conversation_id=1,
            agent_run_id="d53a02e0-4b80-4f16-8ad2-dcd877ddbfbc",
            agent_state_version=-1,
        )


def test_legal_resume_updates_exact_issue_once_and_preserves_other_state(store, records):
    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        result = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer=" 约定于2023年1月还款 ",
        )
    finally:
        db.close()

    assert result.run_id == records["run_id"]
    assert result.issue_id == "issue-a"
    assert result.old_state_version == 0
    assert result.new_state_version == 1
    assert result.state.status is AgentStatus.PLANNING
    # DB-15（审查报告 B-47）：`WAITING_USER→PLANNING` 是"接受用户自己回答"的记账边，**不计步**
    # ⇒ 用户回答不再消耗步数（改前此处是 3→4，且当 4 恰好等于 max_steps 时整个 run 永久 409）。
    # 步数预算的语义由此明确为"模型/工具推进次数"，防循环上界仍在（工具/重规划/澄清边照旧计步，
    # 见 `tests/test_agent_budget_terminal_edges.py::test_charging_edges_are_untouched`）。
    assert result.state.steps == 3
    assert result.state.tool_calls == 2
    assert result.state.replans == 1
    assert result.state.clarifications == 1
    issue_a, issue_b = result.state.issues
    assert issue_a.facts[-1].model_dump(mode="json") == {
        "statement": "约定于2023年1月还款",
        "source": "user",
        "source_ref": f"agent_run:{records['run_id']}:clarification:v0",
        "confidence": 1.0,
    }
    assert [item.statement for item in issue_a.unknown_facts] == ["是否约定违约金"]
    assert [item.statement for item in issue_b.unknown_facts] == ["保证方式是什么"]
    status, version, pending, saved, step_count = _load_snapshot(sessions, records["run_id"])
    assert (status, version, pending, step_count) == ("planning", 1, None, 1)
    assert saved == result.state
    db = sessions()
    try:
        step = db.query(AgentStep).filter_by(agent_run_id=records["run_id"]).one()
        assert (step.decision, step.reason_code, step.issue_id) == (
            "user_fact",
            "USER_CLARIFICATION_RECORDED",
            "issue-a",
        )
        audit_text = "|".join(
            str(value)
            for value in (
                step.decision,
                step.reason_code,
                step.issue_id,
                step.normalized_input,
                step.result_summary,
            )
        )
        assert "约定于2023年1月还款" not in audit_text
        assert "影响诉讼时效起算" not in audit_text
    finally:
        db.close()


def test_resume_rejects_empty_answer_as_conflict_without_mutation(store, records):
    """对抗审查 fx4（2026-09-13）：空输入按非法回答拒绝（ResumeRunConflict/409），
    不再抛 ValueError→500；状态/版本/检查点均不变。"""
    from agent.controller import ResumeRunConflict

    _engine, sessions = store
    resume, locks = _service()
    before = _load_snapshot(sessions, records["run_id"])
    db = sessions()
    try:
        with pytest.raises(ResumeRunConflict):
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=0,
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer="   ",
            )
    finally:
        db.close()
    assert _load_snapshot(sessions, records["run_id"]) == before


@pytest.mark.parametrize("foreign", ["user", "conversation"])
def test_resume_not_found_is_non_enumerating_and_does_not_mutate(store, records, foreign):
    from agent.controller import ResumeRunNotFound

    _engine, sessions = store
    resume, locks = _service()
    before = _load_snapshot(sessions, records["run_id"])
    db = sessions()
    try:
        with pytest.raises(ResumeRunNotFound, match=NOT_FOUND_DETAIL):
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=0,
                user_id=(records["other"].id if foreign == "user" else records["owner"].id),
                conversation_id=(
                    records["other_conversation"].id if foreign == "conversation" else records["conversation"].id
                ),
                answer="回答",
            )
    finally:
        db.close()
    assert _load_snapshot(sessions, records["run_id"]) == before


@pytest.mark.parametrize("case", ["stale", "non_waiting", "inconsistent_pending", "duplicate"])
def test_resume_conflicts_are_stable_and_do_not_duplicate(store, records, case):
    from agent.controller import ResumeRunConflict

    _engine, sessions = store
    resume, locks = _service()
    if case == "non_waiting":
        db = sessions()
        run = db.get(AgentRun, records["run_id"])
        state = LegalAgentState.model_validate_json(run.state_json).model_copy(update={"status": AgentStatus.PLANNING})
        run.status = AgentStatus.PLANNING.value
        run.state_json = state.model_dump_json()
        run.pending_question = None
        db.commit()
        db.close()
    elif case == "inconsistent_pending":
        db = sessions()
        run = db.get(AgentRun, records["run_id"])
        run.pending_question = "另一个问题"
        db.commit()
        db.close()
    elif case == "duplicate":
        db = sessions()
        resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="第一次回答",
        )
        db.close()

    before = _load_snapshot(sessions, records["run_id"])
    db = sessions()
    # 四例里只有 pending 锚点对不上是"服务端接不上"，其余三例都是"这条任务已被推进"。
    expected_detail = UNRECOVERABLE_DETAIL if case == "inconsistent_pending" else ADVANCED_DETAIL
    try:
        with pytest.raises(ResumeRunConflict) as excinfo:
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=(99 if case == "stale" else 0),
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer="重复回答",
            )
        assert str(excinfo.value) == expected_detail != CONFLICT_DETAIL
    finally:
        db.close()
    after = _load_snapshot(sessions, records["run_id"])
    assert after == before
    facts = [fact.statement for issue in after[3].issues for fact in issue.facts]
    assert facts.count("重复回答") == 0


def test_commit_failure_rolls_back_run_state_pending_and_step(store, records, monkeypatch):
    _engine, sessions = store
    resume, locks = _service()
    before = _load_snapshot(sessions, records["run_id"])
    db = sessions()
    monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failed")))
    try:
        with pytest.raises(RuntimeError, match="commit failed"):
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=0,
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer="回答",
            )
    finally:
        db.close()
    assert _load_snapshot(sessions, records["run_id"]) == before


def test_two_independent_sessions_allow_only_one_database_cas(store, records, monkeypatch):
    import agent.controller as controller

    _engine, sessions = store
    barrier = Barrier(2)
    original = controller.compare_and_save

    def synchronized_compare_and_save(*args, **kwargs):
        barrier.wait(timeout=5)
        return original(*args, **kwargs)

    monkeypatch.setattr(controller, "compare_and_save", synchronized_compare_and_save)

    def attempt(answer: str):
        db = sessions()
        try:
            return controller.resume_with_user_fact(
                db=db,
                run_locks=controller.InMemoryRunLockRegistry(),
                run_id=records["run_id"],
                expected_version=0,
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer=answer,
            )
        except controller.ResumeRunConflict:
            return None
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["并发回答A", "并发回答B"]))
    assert sum(result is not None for result in results) == 1
    snapshot = _load_snapshot(sessions, records["run_id"])
    assert snapshot[1] == 1
    assert snapshot[4] == 1
    answers = [fact.statement for issue in snapshot[3].issues for fact in issue.facts if fact.source is SourceType.USER]
    assert len(answers) == 1


def test_clarification_projection_has_exact_keys_and_no_internal_rationale():
    from main import serialize_clarification_event

    event = serialize_clarification_event(
        run_id="d53a02e0-4b80-4f16-8ad2-dcd877ddbfbc",
        state_version=6,
        prompt=QUESTION,
        issue_id="issue-a",
    )
    assert set(event) == {"type", "run_id", "state_version", "prompt", "issue_id"}
    assert event == {
        "type": "clarification",
        "run_id": "d53a02e0-4b80-4f16-8ad2-dcd877ddbfbc",
        "state_version": 6,
        "prompt": QUESTION,
        "issue_id": "issue-a",
    }
    serialized = json.dumps(event, ensure_ascii=False)
    for private in ("why_outcome_changes", "影响诉讼时效起算", "state_json", "tool_args"):
        assert private not in serialized


def _client(store, monkeypatch, user):
    from fastapi.testclient import TestClient

    import main
    from auth import get_current_user

    main.app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(main, "_pre", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_pre called")))
    return TestClient(main.app, raise_server_exceptions=False)


def test_http_resume_kill_switch_rejects_before_any_state_change(store, records, monkeypatch):
    import main

    monkeypatch.setattr(main.settings, "agent_enabled", False)
    monkeypatch.setattr(
        main,
        "resume_with_user_fact",
        lambda **kwargs: pytest.fail("kill switch must reject before resume CAS"),
    )
    _engine, sessions = store
    client = _client(store, monkeypatch, records["owner"])
    try:
        response = client.post(
            "/api/chat",
            json={
                "content": "约定于2023年1月还款",
                "conversation_id": records["conversation"].id,
                "agent_run_id": records["run_id"],
                "agent_state_version": 0,
            },
        )
    finally:
        client.close()
        import main

        main.app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "Agent 当前已停用，请稍后重试"}
    assert "data:" not in response.text
    assert _load_snapshot(sessions, records["run_id"])[1] == 0
    db = sessions()
    try:
        assert db.query(Message).count() == 0
        assert db.query(Conversation).count() == 2
    finally:
        db.close()


@pytest.mark.parametrize(
    ("payload_update", "status", "detail"),
    [
        ({"content": "   "}, 400, "请输入对 Agent 追问的回答"),
        # 图片门禁（阶段B 501）优先于 resume 的 content 空校验——与 main.py 能力门顺序一致
        ({"image": "data:image/png;base64,eA==", "content": None}, 501, "图片理解当前不可用：所配置模型无视觉能力"),
        ({"agent_run_id": "7d408f72-1dfb-4d30-89b1-1f9c303455d4"}, 404, NOT_FOUND_DETAIL),
        # 版本不符 ⇒ state_stale ⇒ D-10 分档里的"已处理过"那一句
        ({"agent_state_version": 8}, 409, ADVANCED_DETAIL),
    ],
)
def test_http_resume_failures_bypass_pre_and_emit_no_sse(store, records, monkeypatch, payload_update, status, detail):
    import main

    monkeypatch.setattr(main.settings, "agent_enabled", True)
    # T5（2026-09-09）固定"视觉能力不可用"前置：registry 单例构建时机依赖 import 顺序
    # （rollout 等模块在 main.load_dotenv 之前 import settings 单例 → llm_models_json 为空
    # → 回退 DEFAULT_ROLES 含 vision → has_modality 漂移为 True），本测试不依赖该漂移，
    # 显式固定为 False 以锁定本契约：图片门禁 501 优先于 resume 的 content 空校验 400。
    monkeypatch.setattr(main, "registry", SimpleNamespace(has_modality=lambda modality: False))
    client = _client(store, monkeypatch, records["owner"])
    payload = {
        "content": "回答",
        "conversation_id": records["conversation"].id,
        "agent_run_id": records["run_id"],
        "agent_state_version": 0,
    }
    payload.update(payload_update)
    try:
        response = client.post("/api/chat", json=payload)
    finally:
        client.close()
        import main

        main.app.dependency_overrides.clear()
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "data:" not in response.text


def test_ordinary_followup_without_run_id_does_not_query_or_guess_waiting_run(store, records, monkeypatch):
    import main

    called = []

    def ordinary_pre(*args, **kwargs):
        called.append(args)
        raise ValueError("ordinary-path-sentinel")

    monkeypatch.setattr(main, "_pre", ordinary_pre)
    client = _client(store, monkeypatch, records["owner"])
    monkeypatch.setattr(main, "_pre", ordinary_pre)
    try:
        response = client.post(
            "/api/chat",
            json={"content": "普通追问", "conversation_id": records["conversation"].id},
        )
    finally:
        client.close()
        main.app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json() == {"detail": "ordinary-path-sentinel"}
    assert len(called) == 1


def test_resume_explicit_unknown_is_acknowledged_not_conflict(store, records):
    """Gate 4：用户显式表示无法提供该事实 → 不放行 409（防绕过仍对胡答生效），acknowledge 后转 PLANNING。"""

    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        result = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="我没有这方面的信息。",
        )
    finally:
        db.close()
    assert result.new_state_version == 1
    assert result.state.status is AgentStatus.PLANNING
    issue_a = result.state.issues[0]
    # 被确认未知的事实从 unknown_facts 移除，且不把"不知道"写入已确认事实
    assert len(issue_a.unknown_facts) == 1
    assert all("没有" not in str(f.statement) for f in issue_a.facts)


def test_resume_uses_pending_anchor_even_when_evaluator_prefers_another_issue(store, records):
    """Gate 4：多轮澄清时 pending_question 与实际评估首选漂移——按 pending 锚点恢复，杜绝 409 假冲突。"""
    from models import AgentRun

    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        run = db.get(AgentRun, records["run_id"])
        run.pending_question = "保证方式是什么"  # issue-b 的项；评估器对 state 的首选缺失可能是 issue-a
        db.commit()
        result = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="保证方式约定为连带责任保证",
        )
    finally:
        db.close()
    assert result.issue_id == "issue-b"
    assert result.state.status is AgentStatus.PLANNING
    issue_b = next(i for i in result.state.issues if i.issue_id == "issue-b")
    assert issue_b.facts[-1].statement == "保证方式约定为连带责任保证"


def test_resume_unknown_pending_anchor_still_conflicts(store, records):
    """Gate 4 失败路径：pending 锚点不存在且评估器无法校验通过 → 仍 409（防绕过不削弱）。"""
    from agent.controller import ResumeRunConflict

    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        run = db.get(AgentRun, records["run_id"])
        run.pending_question = "一个在状态中不存在的待澄清项"
        db.commit()
    finally:
        db.close()
    with pytest.raises(ResumeRunConflict):
        resume(
            db=sessions(),
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="保证方式约定为连带责任保证",
        )


def test_resume_twice_advances_version_chain(store, records):
    """Gate 4：多轮澄清的第二次 resume 走版本链续接（v0→v1→v2），不把用户第二轮回答误判为冲突。

    真实链路：第一次 resume 写入 checkpoint 后由 planner 生成第二轮澄清 checkpoint（WAITING_USER），
    第二次 resume 携带新版本继续推进——此场景曾被 settings.agent_max_steps=8 的 steps 预算耗尽误杀。
    """
    from agent.repository import CheckpointMetadata, compare_and_save

    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        first = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="约定于2023年1月还款",
        )
        assert first.new_state_version == 1

        # 模拟 planner 生成的第二轮澄清 checkpoint（WAITING_USER，pending 指向剩下的未知事实）
        run = db.get(AgentRun, first.run_id)
        second_state = first.state.model_copy(deep=True)
        second_state.status = AgentStatus.WAITING_USER
        second_state.clarifications = 2
        pending = [u.statement for iss in second_state.issues for u in iss.unknown_facts][0]
        run = compare_and_save(
            db,
            run=run,
            expected_version=first.new_state_version,
            state=second_state,
            status=AgentStatus.WAITING_USER.value,
            checkpoint=CheckpointMetadata(
                decision="planner",
                reason_code="CLARIFY",
                issue_id="issue-a",
                pending_question=pending,
            ),
        )
        assert run.state_version == 2

        second = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=run.state_version,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="没有约定违约金",
        )
        assert second.new_state_version == 3
        assert second.issue_id == "issue-a"
        assert second.state.status is AgentStatus.PLANNING
        issue_a = second.state.issues[0]
        assert issue_a.facts[-1].statement == "没有约定违约金"
        assert issue_a.unknown_facts == []
    finally:
        db.close()


def test_resume_at_exact_step_cap_succeeds_and_still_rejects_stale_version(store, records):
    """DB-15（审查报告 B-47）：steps 打满时用户的回答**不再被 409 拒收**——恢复边不计步。

    本测试原先钉的是反面语义（"steps 预算耗尽时第二次 resume 必须仍 409，budget 防护不被
    多轮会话绕过"），docstring 自己写明：`settings.agent_max_steps` 默认 8 时两轮澄清把
    steps 顶到 cap ⇒ 第三次转换抛 `BudgetExceeded` ⇒ 409，而当时的"修复"是把默认预算 8→16
    （后又 16→20）。**边界本身没动**：真数据 47 只 waiting_user run 里有 16 只 steps==cap，
    它们带着"Agent 任务已变化，无法恢复"这句**假话**永久卡死（任务没变，是预算没了）。

    本轮把 `WAITING_USER→PLANNING` 归入 `state_machine.FREE_STEP_EDGES`（该边不发起任何
    模型/工具调用；无限追问由 `max_clarifications` 单独封顶，见
    `tests/test_agent_budget_terminal_edges.py::test_clarification_budget_still_bounds_resume_loop`）。
    同一条 run 仍必须因**真正的**版本冲突被拒 ⇒ 防绕过的那半防线一口没拆。
    """
    from agent.controller import ResumeRunConflict
    from agent.schemas import AgentBudgets

    _engine, sessions = store
    resume, locks = _service()

    tight_state = LegalAgentState(
        status=AgentStatus.WAITING_USER,
        steps=8,
        tool_calls=2,
        replans=0,
        clarifications=1,
        budgets=AgentBudgets(
            max_steps=8,
            max_tool_calls=10,
            max_replans=3,
            max_clarifications=2,
            max_duplicate_attempts_per_issue=2,
            max_verifier_research_returns=1,
        ),
        issues=[
            LegalIssue(
                issue_id="issue-a",
                question="请求权是否成立",
                unknown_facts=[UnknownFact(statement=QUESTION, why_outcome_changes="影响诉讼时效起算")],
            )
        ],
    )
    db = sessions()
    try:
        run = db.get(AgentRun, records["run_id"])
        run.state_json = tight_state.model_dump_json()
        run.state_version = 7
        run.pending_question = QUESTION
        db.commit()
    finally:
        db.close()

    # ① 改前红、改后必须绿：steps 恰满 cap 的回答要能收下，且状态推进到 PLANNING
    db = sessions()
    try:
        first = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=7,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="约定于2023年1月还款",
        )
        assert first.new_state_version == 8, "CAS 正常推进应 +1 个 state_version"
        assert first.state.status is AgentStatus.PLANNING
        assert first.state.steps == 8, "恢复边免计费 ⇒ steps 仍停在 cap，不被顶到 9"
        assert first.state.issues[0].facts[-1].statement == "约定于2023年1月还款"
    finally:
        db.close()

    # ② 真·版本冲突仍必须 409（防我把"预算绕过"的防线一并拆掉），且成因可归因
    db = sessions()
    try:
        with pytest.raises(ResumeRunConflict) as exc:
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=7,  # 旧版本重放
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer="再答一次",
            )
        assert exc.value.reason_code == "state_stale"
    finally:
        db.close()

    # ③ 空回答仍按非法回答拒（fx4 语义不变），但成因码与"任务已变化"那一类分得开
    db = sessions()
    try:
        with pytest.raises(ResumeRunConflict) as exc:
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=8,
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer="   ",
            )
        assert exc.value.reason_code == "answer_invalid"
    finally:
        db.close()


# ==================== 恢复分支的法律基准日（AUTH-2 续） ====================
# `law_as_of` 随 run 建立即固定（`create_run` 落库、工具 cutoff 消费）。恢复请求此前算了
# 客户端日期却既不校验也不下传 —— 那是"静默接受后丢弃"。本组测试锁三件事：
#   1. 客户端改日期 → CAS 之前明确拒绝（不是 409 泛化文案，也不是收下不用）；
#   2. `resume_with_user_fact` 回传 run 的基准日；
#   3. Agent 技术性失败降级到快车道时，取数按 run 的基准日，而不是悄悄改用现行法。

RESUME_LAW_AS_OF_DETAIL = "Agent 追问回答沿用该任务建立时的法律基准日，不能中途更改"


def test_resume_rejects_conflicting_law_as_of_before_any_state_change(store, records):
    from agent.controller import ResumeLawAsOfConflict

    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        with pytest.raises(ResumeLawAsOfConflict):
            resume(
                db=db,
                run_locks=locks,
                run_id=records["run_id"],
                expected_version=0,
                user_id=records["owner"].id,
                conversation_id=records["conversation"].id,
                answer="约定于2023年1月还款",
                expected_law_as_of=date(2019, 1, 1),
            )
    finally:
        db.close()
    assert _load_snapshot(sessions, records["run_id"])[1] == 0  # 版本号未动 = 没发生 CAS


def test_resume_accepts_matching_date_and_reports_run_law_as_of(store, records):
    _engine, sessions = store
    resume, locks = _service()
    db = sessions()
    try:
        result = resume(
            db=db,
            run_locks=locks,
            run_id=records["run_id"],
            expected_version=0,
            user_id=records["owner"].id,
            conversation_id=records["conversation"].id,
            answer="约定于2023年1月还款",
            expected_law_as_of=date.today(),
        )
    finally:
        db.close()

    assert result.law_as_of == date.today()


def test_http_resume_reports_conflicting_law_as_of_as_409(store, records, monkeypatch):
    import main

    _engine, sessions = store
    monkeypatch.setattr(main.settings, "agent_enabled", True)
    monkeypatch.setattr(main.settings, "allow_client_law_as_of", True)
    client = _client(store, monkeypatch, records["owner"])
    payload = {
        "content": "约定于2023年1月还款",
        "conversation_id": records["conversation"].id,
        "agent_run_id": records["run_id"],
        "agent_state_version": 0,
        "law_as_of": "2019-01-01",
    }
    try:
        response = client.post("/api/chat", json=payload)
    finally:
        client.close()
        main.app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": RESUME_LAW_AS_OF_DETAIL}
    assert "data:" not in response.text
    assert _load_snapshot(sessions, records["run_id"])[1] == 0


def test_resume_law_as_of_maps_run_date_onto_fast_path_cutoff():
    """run 落当日 ⇒ 视同"未指定历史"（快车道退回原行为）；run 是历史日 ⇒ 降级也按该日取数。"""
    from main import _resume_law_as_of

    assert _resume_law_as_of(date.today()) is None
    assert _resume_law_as_of(date(2019, 1, 1)) == date(2019, 1, 1)


def test_agent_fallback_on_resume_feeds_run_date_into_fast_path(store, records, monkeypatch):
    """端到端接线：恢复 → Agent 技术性失败 → 快车道路由必须带上 run 的基准日。

    末段用 599 哨兵中断，避免把整条答案生成链路卷进本用例；判据只看被捕获的 bootstrap。
    """
    from fastapi import HTTPException

    import main

    monkeypatch.setattr(main.settings, "agent_enabled", True)
    monkeypatch.setattr(main.settings, "allow_client_law_as_of", True)
    run_date = date(2019, 1, 1)
    captured: dict = {}

    def fake_resume(**kwargs):
        return SimpleNamespace(
            run_id=kwargs["run_id"],
            issue_id="issue-a",
            old_state_version=0,
            new_state_version=1,
            state=_waiting_state(),
            law_as_of=run_date,
        )

    async def fake_execute(request, **kwargs):
        return SimpleNamespace(outcome="fallback", reason_code="TOOL_TIMEOUT")

    def fake_fallback(bootstrap, reason_code):
        captured["bootstrap"] = bootstrap
        raise HTTPException(status_code=599, detail="stop-after-capture")

    monkeypatch.setattr(main, "resume_with_user_fact", fake_resume)
    monkeypatch.setattr(main, "_execute_agent_observing_disconnect", fake_execute)
    monkeypatch.setattr(main, "fallback_to_fast_path", fake_fallback)
    client = _client(store, monkeypatch, records["owner"])
    payload = {
        "content": "约定于2023年1月还款",
        "conversation_id": records["conversation"].id,
        "agent_run_id": records["run_id"],
        "agent_state_version": 0,
    }
    try:
        response = client.post("/api/chat", json=payload)
    finally:
        client.close()
        main.app.dependency_overrides.clear()

    assert response.status_code == 599
    bootstrap = captured["bootstrap"]
    assert bootstrap.law_as_of == run_date


def _resume_reason_codes_in_source() -> set[str]:
    """AST 现读 controller.py 里所有字面量成因码，含 `__init__` 的默认值。

    不用手写清单：新增一个抛点（带新成因码）必须**自动**进这道门，
    否则 D-10 的分档会在下一个成因码上悄悄退回笼统文案。
    """
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "agent" / "controller.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if name == "ResumeRunConflict" and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    codes.add(first.value)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "__init__"
            and any(getattr(a, "arg", "") == "reason_code" for a in node.args.args)
        ):
            for default in node.args.defaults:
                if isinstance(default, ast.Constant) and isinstance(default.value, str):
                    codes.add(default.value)
    return codes


def test_every_resume_reason_code_has_a_copy_bucket():
    """每个成因码都必须落到一档；漏登记 = 该 409 又对用户说笼统假话。"""
    from agent.controller import RESUME_CONFLICT_DETAILS

    codes = _resume_reason_codes_in_source()
    unmapped = sorted(codes - set(RESUME_CONFLICT_DETAILS))
    assert codes, "AST 没扫到任何成因码——仪器失效了，不是代码干净"
    assert not unmapped, f"以下成因码没有对应文案，会回落到笼统那句：{unmapped}"


def test_unregistered_reason_code_falls_back_to_the_generic_copy():
    """回落只给旧那句笼统文案，绝不抛错——分档不能把 409 变成 500。"""
    from agent.controller import resume_conflict_detail

    assert resume_conflict_detail("a_code_nobody_registered") == CONFLICT_DETAIL
    assert resume_conflict_detail("") == CONFLICT_DETAIL


def test_copy_buckets_are_distinct_and_leak_no_internal_jargon():
    """四档必须是四个不同的下一步动作，且不带内部状态机名/版本号。"""
    from agent.controller import RESUME_CONFLICT_DETAILS

    texts = {ADVANCED_DETAIL, ANSWER_INVALID_DETAIL, STEP_BUDGET_DETAIL, UNRECOVERABLE_DETAIL}
    assert len(texts) == 4, "四档文案有重复，等于没拆开"
    assert set(RESUME_CONFLICT_DETAILS.values()) == texts
    for text in texts:
        for jargon in ("state_stale", "cas_conflict", "WAITING_USER", "run_id", "version", "Agent"):
            assert jargon not in text, f"文案泄漏了内部标识：{jargon}"
