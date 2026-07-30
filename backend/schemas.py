from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ===== 认证 =====
class RegisterIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    # bcrypt 对超 72 字节密码会静默截断，这里限制 8-64 位
    password: str = Field(..., min_length=8, max_length=64)


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    token: str
    role: str
    username: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdateIn(BaseModel):
    is_active: Optional[bool] = None


# ===== 统计 =====
class StatsOut(BaseModel):
    user_count: int
    conversation_count: int
    knowledge_count: int


# ===== 对话审查 =====
class ConversationOut(BaseModel):
    id: int
    username: str
    question: str
    answer: str
    created_at: datetime


# ===== 知识库 =====
class KnowledgeAddIn(BaseModel):
    title: str = Field(..., min_length=1)
    article: str = ""
    content: str = Field(..., min_length=1)
