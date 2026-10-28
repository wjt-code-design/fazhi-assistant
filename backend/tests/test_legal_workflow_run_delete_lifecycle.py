"""V5-01（2026-10-21 第 5 轮只读审查）：删除会话/账号必须清掉所属 AgentRun。

修前：Conversation / User 都没有指向 AgentRun 的级联，删除后 run 仍在；
SQLite 数字主键会被复用（max+1），新会话拿到同一 id 后，
`load_owned_run(run_id, user_id, conversation_id)` 会把旧 run 重新认领。

判据（独立于实现）：
1. 删除会话后，该会话的 run 及 steps / evidence / claim_checks 一条不剩；
2. 新建会话复用同一数字 id 时，旧 run_id 加载结果为 None；
3. 删除账号后，该用户的 run 同样不剩。
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from legal_workflow.repository import load_owned_run
from models import AgentClaimCheck, AgentEvidence, AgentRun, AgentStep, Conversation, Message, User


def _make_run(db, *, user_id: int, conversation_id: int) -> AgentRun:
    run = AgentRun(
        id=str(uuid.uuid4()),
        user_id=user_id,
        conversation_id=conversation_id,
        status="waiting_user",
        state_version=0,
        law_as_of=date.today(),
        state_json='{"status":"waiting_user"}',
    )
    db.add(run)
    db.flush()
    db.add(AgentStep(agent_run_id=run.id, state_version=0, status="waiting_user"))
    db.add(
        AgentEvidence(
            agent_run_id=run.id,
            source_type="statute",
            source_identifier="民法典",
            provenance="test",
        )
    )
    db.add(
        AgentClaimCheck(
            agent_run_id=run.id,
            claim="test claim",
            supported=True,
        )
    )
    db.commit()
    return run


def _agent_counts(db) -> dict[str, int]:
    return {
        "runs": db.query(AgentRun).count(),
        "steps": db.query(AgentStep).count(),
        "evidence": db.query(AgentEvidence).count(),
        "claims": db.query(AgentClaimCheck).count(),
    }


def test_delete_conversation_removes_agent_run_and_children(db):
    import main

    user = User(username="v501-user", password_hash="x", role="user")
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id, title="旧案件")
    db.add(conv)
    db.commit()

    run = _make_run(db, user_id=user.id, conversation_id=conv.id)
    old_run_id = run.id
    old_conv_id = conv.id
    db.add(Message(conversation_id=conv.id, role="user", content="旧问题", agent_run_id=old_run_id))
    db.commit()

    assert _agent_counts(db) == {"runs": 1, "steps": 1, "evidence": 1, "claims": 1}

    main.delete_conversation(conv.id, user, db)

    assert db.query(Conversation).count() == 0
    assert db.query(Message).count() == 0
    assert _agent_counts(db) == {"runs": 0, "steps": 0, "evidence": 0, "claims": 0}

    # SQLite 复用被删掉的最高编号：新会话拿到同一 id
    new_conv = Conversation(user_id=user.id, title="新案件")
    db.add(new_conv)
    db.commit()
    assert new_conv.id == old_conv_id
    assert load_owned_run(db, run_id=old_run_id, user_id=user.id, conversation_id=new_conv.id) is None


def test_admin_delete_user_removes_agent_runs(db):
    import main

    admin = User(username="v501-admin", password_hash="x", role="admin")
    victim = User(username="v501-victim", password_hash="x", role="user")
    db.add_all([admin, victim])
    db.flush()
    conv = Conversation(user_id=victim.id, title="案件")
    db.add(conv)
    db.commit()
    _make_run(db, user_id=victim.id, conversation_id=conv.id)

    assert db.query(AgentRun).count() == 1

    main.admin_delete_user(victim.id, db, admin)

    assert db.query(User).filter(User.id == victim.id).count() == 0
    assert _agent_counts(db) == {"runs": 0, "steps": 0, "evidence": 0, "claims": 0}


def test_load_owned_run_rejects_pre_fix_orphan_after_id_reuse(db):
    """升级前遗留的孤儿 run（旧删除逻辑没清）也不能被同号新会话认领。

    这里故意绕开新删除逻辑、直接用 `db.delete(conv)` 复刻修复前的数据库状态。
    """
    user = User(username="v501-orphan", password_hash="x", role="user")
    db.add(user)
    db.flush()
    conv = Conversation(user_id=user.id, title="旧会话")
    db.add(conv)
    db.commit()
    run = _make_run(db, user_id=user.id, conversation_id=conv.id)
    old_conv_id = conv.id

    # 复刻修复前路径：只删会话，留下 run
    db.delete(conv)
    db.commit()
    assert db.query(AgentRun).count() == 1

    new_conv = Conversation(user_id=user.id, title="新会话")
    db.add(new_conv)
    db.commit()
    assert new_conv.id == old_conv_id

    assert load_owned_run(db, run_id=run.id, user_id=user.id, conversation_id=new_conv.id) is None


def test_delete_conversation_keeps_other_conversations_runs(db):
    """只删目标会话：别的会话的 run 必须原样保留（防修成全局清空）。"""
    import main

    user = User(username="v501-multi", password_hash="x", role="user")
    db.add(user)
    db.flush()
    keep = Conversation(user_id=user.id, title="保留")
    drop = Conversation(user_id=user.id, title="删除")
    db.add_all([keep, drop])
    db.commit()

    kept_run = _make_run(db, user_id=user.id, conversation_id=keep.id)
    _make_run(db, user_id=user.id, conversation_id=drop.id)

    main.delete_conversation(drop.id, user, db)

    assert db.query(AgentRun).count() == 1
    assert db.query(AgentRun).one().id == kept_run.id
    assert load_owned_run(db, run_id=kept_run.id, user_id=user.id, conversation_id=keep.id) is not None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
