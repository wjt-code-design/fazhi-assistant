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
    from memory import load_context

    return load_context(db, conversation)


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
                message_id=getattr(message, "id", None),
                role=getattr(message, "role", "system"),
                content=str(getattr(message, "content", "") or ""),
                created_at=getattr(message, "created_at", None),
            )
            for message in selected
        ]
        statement = f"读取到 {len(messages)} 条会话记忆。" if messages else "未找到可用的会话记忆。"
        return RetrieveMemoryOutput(statement=statement, summary=summary or "", messages=messages)
    finally:
        db.close()
