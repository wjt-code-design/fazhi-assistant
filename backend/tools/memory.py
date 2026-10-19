"""User-scoped, read-only memory adapter with an owned SQLAlchemy session."""

from __future__ import annotations

from typing import Any

from .contracts import (
    MemoryMessage,
    RetrieveMemoryInput,
    RetrieveMemoryOutput,
    ToolAuthorizationError,
    ToolContext,
)


def _session_factory() -> Any:
    from database import SessionLocal

    return SessionLocal()


def _conversation_model() -> Any:
    from models import Conversation

    return Conversation


def _load_context(db: Any, conversation: Any) -> tuple[str, list[Any]]:
    """W06-C §5.2：工具读取**同一安全投影**（已知失效助手/摘要不进模型上下文），
    形状与旧 `memory.load_context` 兼容（`(summary, [条目])`）。UI/审计仍走 `memory.load_context`。
    """
    from memory import load_model_context_bootstrap

    return load_model_context_bootstrap(db, conversation)


def _output_provenance(selected: list[Any]) -> str | None:
    """把投影里**助手/系统**条目的来源包并为输出级来源（任一未知 ⇒ None＝未知，不签空集）。

    用户消息是用户自述、无 QA 祖先，不参与合并；没有可合并的助手条目 ⇒ None（保守未知）。
    """
    provs = []
    for message in selected:
        if getattr(message, "role", "") == "user":
            continue
        prov = getattr(message, "provenance", None)
        if prov is None or not getattr(prov, "complete", False):
            return None
        provs.append(prov)
    if not provs:
        return None
    import qa_eligibility as qe

    merged = qe.build_provenance((), ancestors=tuple(provs))
    return qe.serialize_provenance(merged) if merged is not None else None


def retrieve_memory(context: ToolContext, tool_input: RetrieveMemoryInput) -> RetrieveMemoryOutput:
    db = _session_factory()
    try:
        conversation_model = _conversation_model()
        conversation = (
            db.query(conversation_model)
            .filter(
                conversation_model.id == context.conversation_id,
                conversation_model.user_id == context.user_id,
            )
            .one_or_none()
        )
        if conversation is None or conversation.user_id != context.user_id:
            raise ToolAuthorizationError("conversation is not owned by the server-context user")
        summary, raw_messages = _load_context(db, conversation)
        selected = raw_messages[-tool_input.limit :]
        messages = [
            MemoryMessage(
                message_id=getattr(message, "message_id", None) or getattr(message, "id", None),
                role=getattr(message, "role", "system"),
                content=str(getattr(message, "content", "") or ""),
                created_at=getattr(message, "created_at", None),
            )
            for message in selected
        ]
        statement = f"读取到 {len(messages)} 条会话记忆。" if messages else "未找到可用的会话记忆。"
        return RetrieveMemoryOutput(
            statement=statement,
            summary=summary or "",
            messages=messages,
            provenance=_output_provenance(selected),
        )
    finally:
        db.close()
