"""多轮上下文 + 增量滚动压缩 + 条件查询改写。

- 上下文窗口 = summary + 最近 RECENT_K 条原文。
- 压缩触发：message_count > TURN_THRESHOLD 或 (summary+recent) 字符 > CHAR_THRESHOLD。
- 压缩为增量：用 summary_upto 指针，只把"刚滑出窗口的旧消息"合并进摘要，不重复劳动。
- 旧消息不删除（保留历史/审计），窗口仅靠 summary+recent 表达。
- 查询改写仅在"有历史"时做；单轮跳过，省一次调用。
"""
from typing import List, Tuple

from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage

from models import Conversation, Message

RECENT_K = 6
TURN_THRESHOLD = 12
CHAR_THRESHOLD = 6000
SUMMARY_MAX = 400


def _msg_text(m: Message) -> str:
    role = "用户" if m.role == "user" else ("助手" if m.role == "assistant" else "系统")
    return f"{role}：{m.content or ''}"


def recent_messages(db: Session, conversation_id: int) -> List[Message]:
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(RECENT_K)
        .all()
    )
    return list(reversed(rows))  # 转为时间正序


def char_count(summary: str, recent: List[Message]) -> int:
    return len(summary or "") + sum(len(m.content or "") for m in recent)


def load_context(db: Session, conv: Conversation) -> Tuple[str, List[Message]]:
    return (conv.summary or ""), recent_messages(db, conv.id)


def needs_compress(conv: Conversation, recent: List[Message]) -> bool:
    if (conv.message_count or 0) <= TURN_THRESHOLD:
        return False
    return char_count(conv.summary, recent) > CHAR_THRESHOLD or (conv.message_count or 0) > TURN_THRESHOLD


def _gap_messages(db: Session, conv: Conversation) -> List[Message]:
    """尚未被摘要覆盖、且已滑出最近窗口的消息（时间正序）。"""
    window_start = max(0, (conv.message_count or 0) - RECENT_K)
    upto = conv.summary_upto or 0
    if upto >= window_start:
        return []
    # 取第 upto..window_start 条（按时间正序，用 offset/limit）
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .offset(upto)
        .limit(window_start - upto)
        .all()
    )


def _extend_summary(llm, existing: str, batch: List[Message]) -> str:
    batch_text = "\n".join(_msg_text(m) for m in batch)
    sys = (
        "你是法律对话摘要器。把'新对话'增量合并进'已有摘要'，保留：涉及的法律主题、"
        "已引用的条文、已给出的结论、用户尚未解决的问题；丢弃寒暄与冗余。"
        f"输出更新后的完整摘要，不超过{SUMMARY_MAX}字，不要加前缀解释。"
    )
    user = f"已有摘要：\n{existing or '（无）'}\n\n新对话：\n{batch_text}"
    try:
        resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=user)])
        new = (resp.content or "").strip()
        return new[:SUMMARY_MAX] if new else (existing or "")
    except Exception:
        return existing or ""


def compress(db: Session, conv: Conversation, llm) -> bool:
    """增量压缩；返回是否实际更新了摘要。同步函数，调用方放线程池。"""
    batch = _gap_messages(db, conv)
    if not batch:
        return False
    new_summary = _extend_summary(llm, conv.summary or "", batch)
    conv.summary = new_summary
    conv.summary_upto = max(0, (conv.message_count or 0) - RECENT_K)
    db.commit()
    return True


def rewrite_query(llm, recent: List[Message], current: str) -> str:
    """有历史时把含指代/省略的最新提问改写为独立检索句；无历史或失败则原样返回。"""
    cur = (current or "").strip()
    if not recent or not cur:
        return cur
    hist = "\n".join(_msg_text(m) for m in recent[-4:])
    sys = (
        "根据对话历史，把用户最新这句可能含指代或省略的提问，改写为一句独立、完整、"
        "适合检索法律条文的提问。只输出改写后的提问本身，不要解释、不要加引号。"
    )
    user = f"历史：\n{hist}\n\n最新提问：{cur}"
    try:
        resp = llm.invoke([SystemMessage(content=sys), HumanMessage(content=user)])
        rw = (resp.content or "").strip().strip('"').strip()
        return rw or cur
    except Exception:
        return cur
