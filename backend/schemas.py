import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    StrictBool,
    field_validator,
    model_validator,
)


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
    force_agent: bool = (
        False  # 手动深入分析显式入口（任务书 §3.6/Gate 6）：用户显式触发进 Agent，不豁免 policy refuse；非自动静默切换
    )
    agent_run_id: UUID | None = None
    agent_state_version: NonNegativeInt | None = None
    # R1-OB（2026-09-16 预注册 docs/preregistration-dept-guard-r1-optionB-20260916.md）：
    # 评测/灰度通道案例域码（tier-1 判域直判源）。生产客户端不传 → None（恒不触发）。
    # 非法值拒绝（422 契约）；合法值 = agent/r1ob.VALID_CASE_DOMAINS。
    case_domain: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_case_domain(self) -> "ChatIn":
        if self.case_domain is not None:
            from agent.r1ob import VALID_CASE_DOMAINS

            if self.case_domain not in VALID_CASE_DOMAINS:
                raise ValueError(f"case_domain must be one of {sorted(VALID_CASE_DOMAINS)}, got {self.case_domain!r}")
        return self

    @model_validator(mode="after")
    def validate_agent_resume_identity(self) -> "ChatIn":
        resume_fields = (
            self.agent_run_id is not None,
            self.agent_state_version is not None,
            self.conversation_id is not None,
        )
        if any(resume_fields[:2]) and not all(resume_fields):
            raise ValueError("agent_run_id, agent_state_version and conversation_id are required together")
        return self


# ===== 会话 / 消息 =====
class UncoveredIssueOut(BaseModel):
    """T1（2026-09-16）：未覆盖争点的公开投影（仅标识与原因码，无内部文本）。"""

    issue_id: str
    reason_code: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    image_ref: str | None = None
    thumb_ref: str | None = None
    created_at: datetime
    # T1（2026-09-16）覆盖投影：full/partial（Agent 消息且 run 有结构化覆盖）、
    # unknown（旧 assistant 消息或 run 缺结构化信息——不得推断 full）、
    # None（用户消息，覆盖不适用）。
    coverage_status: Literal["full", "partial", "unknown"] | None = None
    uncovered_issues: list[UncoveredIssueOut] = Field(default_factory=list)

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
    version_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    promulgated_at: str | None = None
    source_url: str | None = Field(default=None, pattern=r"^https://[^\s]+$")
    source_document_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    supersedes_version_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    reviewed_at: str | None = None

    @field_validator("promulgated_at", "effective_from", "effective_to", "reviewed_at")
    @classmethod
    def _date_or_empty(cls, v: str | None) -> str | None:
        if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        return v

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str | None) -> str | None:
        if v and v not in {"现行", "已修改", "已废止", "即将施行", "未生效"}:
            raise ValueError("status 必须为现行/已修改/已废止/即将施行/未生效")
        return v

    @model_validator(mode="after")
    def _valid_version_period(self):
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to 不能早于 effective_from")
        if self.version_id and self.supersedes_version_id == self.version_id:
            raise ValueError("supersedes_version_id 不能等于 version_id")
        return self


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


class LlmPromoteIn(BaseModel):
    """把某模型提为链首（`POST /api/admin/llm-promote`）。

    2026-09-15 代码审查（S2）：原端点用裸 `body: dict` 绕过校验，与同文件
    `LlmSwitchIn`/`LlmQuotaIn` 的 Pydantic 惯例相悖 → 改为显式 schema（key 长度上限 64）。
    """

    key: str = Field(min_length=1, max_length=64)


class LlmDisableIn(BaseModel):
    """禁用/启用某模型参与自动路由（`POST /api/admin/llm-disable`）。

    2026-09-15 代码审查（S1/S2）两处修正：
    - `disabled` 用 **StrictBool**：原实现 `bool(body.get("disabled", True))` 会把字符串
      `"false"`/`"0"` 判为 True（Python `bool("false") is True`）→ **误禁用**；StrictBool
      只接受真正的布尔值，字符串会被 422 拒绝。
    - `disabled` **必填**（无默认）：原实现默认 True，只传 `{"key": ...}` 就会静默禁用。
    """

    key: str = Field(min_length=1, max_length=64)
    disabled: StrictBool


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
