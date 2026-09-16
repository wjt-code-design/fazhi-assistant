import json
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent.repository import (
    CheckpointMetadata,
    RunVersionConflict,
    compare_and_save,
    create_run,
    load_owned_run,
)
from agent.schemas import AgentStatus, Evidence, LegalAgentState, LegalValidity, SourceType
from models import AgentEvidence, AgentRun, AgentStep, Conversation, User


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Self-contained migrated SQLite boundary; this file runs with --noconftest."""
    import database
    import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'agent-repository.db'}")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(migrations, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    migrations.run_migrations()
    migrations.run_migrations()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def owner(db):
    user = User(username="agent-owner", password_hash="test")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def other(db):
    user = User(username="agent-other", password_hash="test")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def conversation(db, owner):
    record = Conversation(user_id=owner.id, question="", answer="")
    db.add(record)
    db.commit()
    return record


def bootstrap_state():
    return LegalAgentState(status=AgentStatus.BOOTSTRAPPING)


def planning_state():
    return LegalAgentState(status=AgentStatus.PLANNING, steps=1)


def test_other_user_cannot_load_agent_run(db, owner, other, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())

    assert load_owned_run(db, run_id=run.id, user_id=other.id, conversation_id=conversation.id) is None


def test_other_conversation_cannot_load_agent_run(db, owner, conversation):
    another_conversation = Conversation(user_id=owner.id, question="", answer="")
    db.add(another_conversation)
    db.commit()
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())

    assert load_owned_run(db, run_id=run.id, user_id=owner.id, conversation_id=another_conversation.id) is None


def test_cannot_create_run_for_another_users_conversation(db, owner, other, conversation):
    with pytest.raises(ValueError, match="does not belong"):
        create_run(db, user_id=other.id, conversation_id=conversation.id, state=bootstrap_state())

    assert db.query(AgentRun).count() == 0
    assert db.query(User).count() == 2


def test_stale_state_version_cannot_overwrite_newer_run(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())

    saved = compare_and_save(db, run=run, expected_version=0, state=planning_state(), status="planning")

    assert saved.state_version == 1
    assert saved.status == "planning"
    with pytest.raises(RunVersionConflict):
        compare_and_save(db, run=run, expected_version=0, state=planning_state(), status="planning")


def test_compare_and_save_rejects_status_that_conflicts_with_state(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())

    with pytest.raises(ValueError, match="must match"):
        compare_and_save(db, run=run, expected_version=0, state=planning_state(), status="failed")

    persisted_run = db.get(type(run), run.id)
    assert persisted_run.state_version == 0
    assert persisted_run.status == AgentStatus.BOOTSTRAPPING.value
    assert db.query(AgentStep).filter_by(agent_run_id=run.id).count() == 0


def test_state_change_writes_step_in_same_commit(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())
    compare_and_save(db, run=run, expected_version=0, state=planning_state(), status="planning")

    steps = db.query(AgentStep).filter_by(agent_run_id=run.id).all()
    assert len(steps) == 1
    assert steps[0].state_version == 1
    assert steps[0].status == "planning"


def test_create_run_persists_serialized_state_and_defaults(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())

    assert run.state_version == 0
    assert run.status == AgentStatus.BOOTSTRAPPING.value
    assert '"status":"bootstrapping"' in run.state_json
    assert run.law_as_of == date.today()


def canonical_evidence() -> Evidence:
    return Evidence(
        evidence_id="evidence-internal-1",
        source_id="chunk-external-7",
        source_ref="中华人民共和国民法典#第一条",
        source_type=SourceType.STATUTE,
        snippet="为了保护民事主体的合法权益。",
        legal_validity=LegalValidity.EFFECTIVE,
        acquired_at=datetime(2026, 8, 30, 8, 0),
    )


def test_checkpoint_metadata_and_materialized_evidence_commit_atomically(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())
    item = canonical_evidence()
    state = planning_state().model_copy(update={"evidence": [item]})

    saved = compare_and_save(
        db,
        run=run,
        expected_version=0,
        state=state,
        status="planning",
        checkpoint=CheckpointMetadata(
            decision="tool_result",
            reason_code="TOOL_SUCCEEDED",
            issue_id="issue-a",
            tool_name="retrieve_laws",
            fingerprint="sha256-fingerprint",
            duration_ms=12,
            result_code="SUCCEEDED",
        ),
        new_evidence_by_issue={"issue-a": [item]},
    )

    step = db.query(AgentStep).filter_by(agent_run_id=run.id).one()
    audit = db.query(AgentEvidence).filter_by(agent_run_id=run.id).one()
    assert saved.state_version == 1
    assert LegalAgentState.model_validate_json(saved.state_json) == state
    assert step.decision == "tool_result"
    assert step.reason_code == "TOOL_SUCCEEDED"
    assert step.normalized_input == "sha256-fingerprint"
    assert step.result_summary == "SUCCEEDED"
    assert step.duration_ms == 12
    assert saved.degraded_reason is None
    assert saved.last_error_code is None
    assert json.loads(audit.provenance) == {
        "evidence_id": "evidence-internal-1",
        "source_ref": "中华人民共和国民法典#第一条",
    }
    assert audit.source_identifier == "chunk-external-7"
    assert audit.snippet == item.snippet


def test_commit_failure_rolls_back_run_step_and_evidence_together(db, owner, conversation, monkeypatch):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())
    original_commit = db.commit

    def fail_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    item = canonical_evidence()
    with pytest.raises(RuntimeError, match="simulated commit failure"):
        compare_and_save(
            db,
            run=run,
            expected_version=0,
            state=planning_state().model_copy(update={"evidence": [item]}),
            status="planning",
            checkpoint=CheckpointMetadata(decision="tool_result"),
            new_evidence_by_issue={"issue-a": [item]},
        )

    monkeypatch.setattr(db, "commit", original_commit)
    db.expire_all()
    persisted = db.get(AgentRun, run.id)
    assert persisted.state_version == 0
    assert persisted.status == AgentStatus.BOOTSTRAPPING.value
    assert db.query(AgentStep).filter_by(agent_run_id=run.id).count() == 0
    assert db.query(AgentEvidence).filter_by(agent_run_id=run.id).count() == 0


def test_checkpoint_persists_explicit_degraded_and_pending_run_fields(db, owner, conversation):
    run = create_run(db, user_id=owner.id, conversation_id=conversation.id, state=bootstrap_state())
    waiting = LegalAgentState(status=AgentStatus.WAITING_USER, steps=1)

    saved = compare_and_save(
        db,
        run=run,
        expected_version=0,
        state=waiting,
        status="waiting_user",
        checkpoint=CheckpointMetadata(
            decision="clarification",
            reason_code="OUTCOME_CHANGING_FACT_UNKNOWN",
            pending_question="是否约定履行期限",
        ),
    )
    assert saved.pending_question == "是否约定履行期限"
    assert saved.degraded_reason is None
    assert saved.last_error_code is None

    failed = LegalAgentState(status=AgentStatus.FAILED, steps=2)
    saved = compare_and_save(
        db,
        run=saved,
        expected_version=1,
        state=failed,
        status="failed",
        checkpoint=CheckpointMetadata(
            decision="failure",
            reason_code="TOOL_TIMEOUT",
            result_code="TOOL_TIMEOUT",
            degraded_reason="TOOL_TIMEOUT",
            last_error_code="TOOL_TIMEOUT",
        ),
    )
    assert saved.pending_question is None
    assert saved.degraded_reason == "TOOL_TIMEOUT"
    assert saved.last_error_code == "TOOL_TIMEOUT"
