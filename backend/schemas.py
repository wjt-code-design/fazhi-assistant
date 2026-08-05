import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    model_config = ConfigDict(from_attributes=True)


class UserUpdateIn(BaseModel):
    is_active: bool | None = None


# ===== 问答（多轮 + 多模态，向后兼容旧 question 字段） =====
class ChatIn(BaseModel):
    question: str | None = Field(default=None, max_length=2000)  # 旧客户端兼容
    content: str | None = Field(default=None, max_length=12000)  # 文本（优先；合同上限，之上截取注明）
    conversation_id: int | None = None  # 续聊；空=新建
    image: str | None = Field(default=None, description="data URL 或 http URL；base64 不写库")
    no_cache: bool = False  # 绕过 QA/答案缓存直返（评测脚本用，测真实 LLM）
    truncated: bool = False  # 客户端已截断（文件上传超长）：穿透给合同评估/analysis_runs（截到恰 12000 时服务端判不出）


# ===== 会话 / 消息 =====
class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    image_ref: str | None = None
    thumb_ref: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListItem(BaseModel):
    id: int
    title: str
    preview: str
    message_count: int
    has_image: bool
    last_active_at: datetime | None = None
    created_at: datetime


class ConversationDetail(BaseModel):
    id: int
    title: str
    summary: str
    messages: list[MessageOut]


# ===== 统计 =====
class StatsOut(BaseModel):
    user_count: int
    conversation_count: int
    knowledge_count: int
    llm_model: str
    qa_pending: int = 0


# ===== 对话审查（旧） =====
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
    # 时效字段（阶段5）：日期必须为 YYYY-MM-DD 或空，保证字典序比较可靠
    effective_from: str | None = None
    effective_to: str | None = None
    status: str | None = None

    @field_validator("effective_from", "effective_to")
    @classmethod
    def _date_or_empty(cls, v: str | None) -> str | None:
        if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        return v


class KnowledgeTestIn(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


class PreviewChunkIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=200_000)


# ===== 受控沉淀 =====
class QaCandidateOut(BaseModel):
    id: int
    question: str
    answer: str
    grounded_score: float
    evidence: str
    status: str
    created_at: datetime | None = None


class QaDecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")


# ===== 模型在线切换 =====
class LlmSwitchIn(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=64)


class LlmQuotaIn(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    remaining: int = Field(ge=0)  # 控制台真实剩余 token（管理员读数校准）


class FeedbackIn(BaseModel):
    conversation_id: int | None = None
    question: str = Field(..., min_length=1, max_length=4000)
    answer: str = Field(..., min_length=1, max_length=8000)
    rating: str = Field(..., pattern="^(up|down)$")
    correction: str | None = Field(default=None, max_length=8000)


class FeedbackOut(BaseModel):
    id: int
    user_id: int | None = None
    conversation_id: int | None = None
    question: str
    answer: str
    rating: str
    correction: str
    created_at: datetime | None = None
