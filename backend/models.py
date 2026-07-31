from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # user / admin
    role = Column(String(16), default="user", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # 旧字段保留：新多轮流程里存"首轮/预览"，兼容旧列表接口
    question = Column(Text, default="")
    answer = Column(Text, default="")
    # 多轮 + 压缩
    title = Column(String(200), default="")
    summary = Column(Text, default="")  # 增量滚动摘要
    message_count = Column(Integer, default=0)
    summary_upto = Column(Integer, default=0)  # 增量压缩指针：已被摘要覆盖的最旧消息条数
    last_active_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True
    )
    # user / assistant / system
    role = Column(String(16), nullable=False)
    content = Column(Text, default="")
    image_ref = Column(String(500), nullable=True)  # 存盘相对路径（相对 backend/）
    thumb_ref = Column(String(500), nullable=True)
    token_est = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class QaCandidate(Base):
    """受控沉淀待审：高有据问答先入此表，管理员采纳后才写入 qa_pairs 向量集合。"""

    __tablename__ = "qa_candidates"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    grounded_score = Column(Float, default=0.0)  # 命中分（top1 相似度等）
    evidence = Column(Text, default="")  # 命中来源（JSON 串）
    # pending / approved / rejected
    status = Column(String(16), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """管理员操作审计日志（best-effort 记录，独立会话写入）。"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # e.g. llm.switch / knowledge.upload / qa.approve / user.toggle
    target = Column(String(255), default="")
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    """用户对某条 AI 回答的反馈（点赞/踩 + 可选纠错），用于沉淀与评测。"""

    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, index=True)
    question = Column(Text, default="")  # 被评价的用户问题快照
    answer = Column(Text, default="")  # 被评价的 AI 回答快照
    rating = Column(String(8), nullable=False)  # up / down
    correction = Column(Text, default="")  # 用户纠错/期望答案（可选）
    created_at = Column(DateTime, default=datetime.utcnow)
