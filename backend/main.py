import asyncio
import base64
import json
import logging
import os
import socket
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from threading import Event
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

# 必须在导入会读取环境变量的本地模块之前加载 .env
load_dotenv()

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import func, text
from sqlalchemy.orm import Session

import answer_cache
import chunking
import clarify
import complexity
import knowledge_service as ks
import output_normalize
import quality
import query_understand
import quota_store
import routing_metrics
from agent.chat_integration import (
    CoverageProjection,
    coverage_from_state_json,
    encode_sse_stream,
    serialize_agent_events,
)
from agent.controller import (
    _DEFAULT_RUN_LOCKS,
    RESUME_CONFLICT_DETAIL,
    RESUME_NOT_FOUND_DETAIL,
    ResumeRunConflict,
    ResumeRunNotFound,
    resume_with_user_fact,
)
from agent.gate import GATE_TECHNICAL_FAILURE, AgentGateDecision, decide_gate
from agent.schemas import LegalAgentState
from agent.service import execute_agent_request
from agent.verifier import VerificationResult, render_verified
from agent.writer import DraftAnswer
from audit import log_audit
from auth import create_token, get_current_user, hash_password, require_admin, verify_password
from curation import should_curate
from database import SessionLocal, get_db, init_db
from domain_rules import (
    CITATION_SELECTION_RULE,
    build_contract_data,
    cheating_docs,
    consumer_clause_docs,
    consumer_fraud_docs,
    is_consumer_clause_scenario,
    is_consumer_fraud_scenario,
    is_contract_review,
)
from intent import classify_intent
from llm_errors import is_transient_error
from llm_guard import LLMBusyError, llm_guard
from llm_registry import QuotaExhausted, estimate_tokens, registry
from memory import compress, load_context, needs_compress, recent_messages, rewrite_query
from models import AgentRun, AnalysisRun, AuditLog, Conversation, Feedback, Message, QaCandidate, User
from multimodal import (
    AUDIO_EXTS,
    MEDIA_DIR,
    build_vision_content,
    describe_image,
    persist_image,
    transcribe_audio,
    validate_image,
)
from observability import (
    RequestIdMiddleware,
    log_account,
    make_agent_correlation_id,
    request_id_var,
    setup_logging,
)
from prompts import (
    _EXAM_TYPE_SUFFIX,
    _EXAM_VERDICT_RULE,
    CONTRACT_CLARIFY_PROMPT,
    IMAGE_GUIDANCE,
    OUTPUT_FORMAT_RULE,
    SYSTEM_BASE,
    SYSTEM_CHEATING,
    SYSTEM_CONTRACT_FOLLOWUP,
    SYSTEM_CONTRACT_REVIEW,
    SYSTEM_STUDY,
)
from quota_utils import UtilityQuotaExhausted
from rag_chain import clean_answer, embeddings, format_docs, make_chain, stream_with_retry, vectorstore
from request_bootstrap import (
    DEFAULT_CONTRACT_STATE,
    BootstrapDependencies,
    FastPathDependencies,
    RequestBootstrap,
    bootstrap_request,
    cleanup_persisted_images,
    configure_default_image_describer,
    is_contract_exit,
    prepare_fast_path,
)
from retrieval import (
    _normalize_article,
    citation_grounding,
    citation_verify,
    exact_article_lookup,
    extract_citations,
    grounded_top_score,
    prewarm,
    retrieve,
    retrieve_exam,
    retrieve_for_test,
    scenario_supplement_docs,
    source_in_kb,
)
from schemas import (
    ChatIn,
    ConversationDetail,
    ConversationListItem,
    FeedbackIn,
    KnowledgeAddIn,
    KnowledgeTestIn,
    LlmDisableIn,
    LlmPromoteIn,
    LlmQuotaIn,
    LlmSwitchIn,
    LoginIn,
    MessageOut,
    PreviewChunkIn,
    QaDecisionIn,
    RegisterIn,
    UserUpdateIn,
)
from settings import settings

# 启动期强校验
if not settings.jwt_secret:
    raise RuntimeError("缺少 JWT_SECRET，请在 .env 中设置")
if not settings.api_key or not settings.llm_base_url:
    raise RuntimeError("缺少 LLM_API_KEY / LLM_BASE_URL，请在 backend/.env 配置")

init_db()

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


def _rate_key(request) -> str:
    """限流按真实客户端 IP（2026-08-08 公网反代穿透，手机端上线）。

    走 Cloudflare Tunnel 后默认取 request.client.host 会全部聚合成代理 IP，限流失效。
    优先级：CF-Connecting-IP（cloudflared 注入的真实 IP，不可伪造）→ X-Forwarded-For
    最右段（Caddy 追加的真实客户端 IP；攻击者伪造的中间段被忽略）→ client.host。
    """
    cf = request.headers.get("CF-Connecting-IP")
    if cf and cf.strip():
        return cf.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1]
    client = getattr(request, "client", None)
    return (client.host if client else None) or "unknown"


limiter = Limiter(key_func=_rate_key)

# 登录失败锁定（2026-08-08 公网安全）：内存级，单 worker 可靠；重启清零（2 人场景可接受）。
# username -> [失败次数, 最近失败时间戳]
_LOGIN_FAILURES: dict[str, list] = {}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCK_SECONDS = 300


async def _read_capped(file: UploadFile, max_bytes: int, detail: str) -> bytes:
    """流式读取上传文件，按实际接收字节累计，超限立即 413。

    防无界内存（原 file.read() 在校验前把整个文件物化为 bytes）：Content-Length
    可被伪造/缺失，必须按真实接收字节计数而非信任请求头。
    """
    out = bytearray()
    while True:
        chunk = await file.read(256 * 1024)
        if not chunk:
            break
        out += chunk
        if len(out) > max_bytes:
            raise HTTPException(status_code=413, detail=detail)
    return bytes(out)


class MaxContentLengthMiddleware:
    """纯 ASGI 预检：content-length 超过上限直接 413，避免超大请求体进入 spool/内存。

    用类而非 @app.middleware("http")（后者 BaseHTTPMiddleware 会缓冲流式 body，
    与 RequestIdMiddleware 同款约束）。Content-Length 可伪造，这只是第一层防御，
    真正的上限由各端点的 _read_capped 按实际字节强制。
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        cl = headers.get(b"content-length")
        if cl:
            try:
                if int(cl) > self.max_bytes:
                    resp = JSONResponse(
                        status_code=413, content={"detail": f"请求体过大（>{self.max_bytes // (1024 * 1024)}MB）"}
                    )
                    await resp(scope, receive, send)
                    return
            except (ValueError, TypeError):
                pass
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(_app):
    setup_logging(settings.log_level)
    # 预热：BM25 索引 + 源名集合（重启后首问冷启动 3s+ → 0），不阻塞事件循环。
    # 失败仅降级（首问走惰性构建），不让应用拒绝启动（code-review：chroma 损坏时原惰性路径可恢复）
    try:
        await run_in_threadpool(prewarm)
    except Exception as e:
        logging.warning("[prewarm] 预热失败，降级惰性构建（重启后首问稍慢）：%s", e)
    yield


app = FastAPI(title="AI 法律咨询小助手", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


async def _utility_quota_exhausted_handler(request: Request, exc: Exception) -> JSONResponse:
    """embedding 配额耗尽 → 409（ADR-011 阶段5 换班制）：明确报错，不静默降级/放任 429。"""
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.add_exception_handler(UtilityQuotaExhausted, _utility_quota_exhausted_handler)
# CORS 源可配置（CORS_ORIGINS 逗号分隔，backend/.env 中设置）；默认仅放行本机开发端口。
# 局域网/公网/内网穿透等部署场景的源在 .env 里追加（.env 不入库，避免部署细节进仓库）。
# 另用正则放行任意 localhost 开发端口（Next dev 端口被占用时会自动 +1，硬编码单端口会导致 "Failed to fetch"）。
_CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"https?://localhost:\d+",
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)  # 纯 ASGI，不缓冲流式 body
# 后注册者在外层：Content-Length 预检最先执行（>12MB 请求体直接 413，防 OOM）
app.add_middleware(MaxContentLengthMiddleware, max_bytes=12 * 1024 * 1024)


# ==================== 健康检查 ====================
@app.get("/api/health")
def health():
    """能力发现（阶段B 诚实停用）：前端据此隐藏未验证能力的入口，而非展示必然失败的按钮。"""
    return {
        "status": "ok",
        "capabilities": {
            "image_chat": registry.has_modality("vision"),
            "voice_transcribe": settings.feature_transcribe and registry.has_modality("voice"),
        },
    }


@app.get("/api/utility/quota")
def utility_quota_overview():
    """公开轻量预警（B 更优版，grilling）：embedding 快用完/耗尽 + rerank 整体降级状态。

    不暴露配额总量（用户端无权限），只返回预警布尔与剩余百分比，驱动前端横幅。
    """
    import quota_utils as _qu

    embed_key = _qu.embedding_model_key()
    monitoring = settings.embedding_quota_total > 0
    pct = round(_qu.utility_pct_left(embed_key) * 100) if monitoring else 100
    return {
        "embedding_warn": monitoring and pct < settings.embedding_warn_threshold * 100,
        "embedding_depleted": monitoring and _qu.utility_depleted(embed_key),
        "embedding_pct": pct,
        "embedding_model": settings.embedding_model,
        "rerank_degraded": settings.rerank_enabled and _qu.rerank_active_model() is None,
    }


@app.get("/healthz")
def healthz():
    """深度就绪检查：DB + 向量库 + 模型主机连通（不发起真实 LLM 调用，不耗 token）。"""
    checks = {"db": False, "vector": False, "llm_host": False}
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:
        pass
    finally:
        db.close()
    try:
        vectorstore._collection.count()
        checks["vector"] = True
    except Exception:
        pass
    try:
        u = urlparse(settings.llm_base_url)
        host = u.hostname
        port = u.port or (443 if u.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=3):
            checks["llm_host"] = True
    except Exception:
        pass
    ok = checks["db"] and checks["vector"]  # llm_host 为软检查（主机可达≠key 有效）
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", **checks},
    )


# ==================== 认证 ====================
@app.post("/api/auth/register")
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterIn):
    # 方案C（2026-08-08，用户要求"一个用户只能注册一个账号"）：默认关闭公开注册，仅管理员开户。
    # 前端不再引导注册，绕过前端直调本接口也 403；.env FEATURE_SELF_REGISTER=true 可重开（小团队自管）。
    if not settings.feature_self_register:
        raise HTTPException(status_code=403, detail="注册已关闭，请联系管理员创建账号")

    def _do():
        db = SessionLocal()
        try:
            # admin 用户名保留（对抗审计 v2 #4）：普通用户不得抢占，否则 seed 前被注册同名会锁死管理接口
            if body.username == settings.admin_username:
                raise HTTPException(status_code=400, detail="该用户名不可注册")
            if db.query(User).filter(User.username == body.username).first():
                raise HTTPException(status_code=400, detail="用户名已存在")
            user = User(username=body.username, password_hash=hash_password(body.password), role="user")
            db.add(user)
            db.commit()
            db.refresh(user)
            return {"token": create_token(user), "role": user.role, "username": user.username}
        finally:
            db.close()

    return await run_in_threadpool(_do)


@app.post("/api/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginIn):
    def _do():
        db = SessionLocal()
        try:
            now = time.time()
            fail = _LOGIN_FAILURES.get(body.username)
            if fail and fail[0] >= _LOGIN_MAX_ATTEMPTS and now < fail[1] + _LOGIN_LOCK_SECONDS:
                raise HTTPException(status_code=429, detail="登录失败次数过多，账号已锁定，请稍后再试")
            user = db.query(User).filter(User.username == body.username).first()
            if not user or not verify_password(body.password, user.password_hash):
                # 失败累计（2026-08-08 公网安全：爆破防护；内存级，重启清零，2 人场景可接受）
                cnt, ts = _LOGIN_FAILURES.get(body.username, (0, now))
                _LOGIN_FAILURES[body.username] = (cnt + 1, ts if cnt > 0 else now)
                raise HTTPException(status_code=401, detail="用户名或密码错误")
            if not user.is_active:
                raise HTTPException(status_code=403, detail="账号已被禁用")
            _LOGIN_FAILURES.pop(body.username, None)  # 成功清除失败记录
            return {"token": create_token(user), "role": user.role, "username": user.username}
        finally:
            db.close()

    return await run_in_threadpool(_do)


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}


# ==================== 受鉴权的媒体文件（历史图片回显） ====================
@app.get("/api/media/{filepath:path}")
def get_media(filepath: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base = os.path.dirname(MEDIA_DIR)
    full = os.path.normpath(os.path.join(base, filepath))
    # 防路径穿越：必须落在 media 目录内
    if full != os.path.normpath(MEDIA_DIR) and not full.startswith(os.path.normpath(MEDIA_DIR) + os.sep):
        raise HTTPException(status_code=400, detail="非法路径")
    # 归属校验（BOLA/IDOR，对抗审计 2026-08-07）：文件必须属于当前用户的会话消息，
    # 否则 404（与"文件不存在"同语义，不泄露存在性）。image_ref/thumb_ref 均为相对路径。
    owned = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user.id)
        .filter((Message.image_ref == filepath) | (Message.thumb_ref == filepath))
        .first()
    )
    if owned is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(full)


# ==================== 问答编排（多轮 + 多模态 + 异步压缩 + 受控沉淀） ====================
def _build_messages(pre: dict) -> list:
    intent = pre.get("intent", "legal_query")
    if intent == "study_aid":
        sys_text = SYSTEM_STUDY
    elif intent == "cheating_request":
        sys_text = SYSTEM_CHEATING
    else:
        sys_text = SYSTEM_BASE
    if pre.get("is_exam"):  # 法考题题型指令 + 判断规则：紧接 SYSTEM 主体，优先于格式规则（2026-08-05 前移）
        sys_text += _EXAM_TYPE_SUFFIX[query_understand.question_type(pre.get("user_text") or "")]
        sys_text += _EXAM_VERDICT_RULE
    sys_text += OUTPUT_FORMAT_RULE
    sys_text += CITATION_SELECTION_RULE
    if pre.get("image"):
        sys_text += IMAGE_GUIDANCE
    if pre["summary"]:
        sys_text += f"\n\n【此前对话摘要】\n{pre['summary']}"
    history = []
    for m in pre["recent"]:
        if m["role"] == "user":
            # 多轮图片上下文：历史图片用其视觉描述代替裸 [图片]，否则后续轮次看不到图里内容
            desc = m.get("image_desc") or ""
            body = m["content"] or ""
            content = f"[用户上传的图片，内容如下：{desc}]\n{body}" if desc else body
            history.append(HumanMessage(content=content))
        elif m["role"] == "assistant":
            history.append(AIMessage(content=m["content"] or ""))
    qa_note = ""
    if pre["qa_hit"]:
        qa_note = (
            f"此前已确认的问答（可优先参考）：\n问：{pre['qa_hit']['question']}\n答：{pre['qa_hit']['answer']}\n\n"
        )
    context_block = (
        f"本题相关法律条文（以下均为本题判断依据，含场景补充条文，可全部直接引用）：\n"
        f"{pre['context'] or '（无直接命中条文）'}\n\n{qa_note}"
    )
    user_text = pre["user_text"]
    if pre["image"]:
        final_text = f"{context_block}用户问题：{user_text or '请结合图片内容回答相关法律问题。'}"
        final_content = build_vision_content(final_text, pre["image"])
    else:
        final_content = f"{context_block}用户问题：{user_text}"
    return [SystemMessage(content=sys_text)] + history + [HumanMessage(content=final_content)]


def _rewrite_for_retrieval(raw_query: str, recent_ser: list, recent: list, has_options: bool) -> str:
    """检索分支的惰性改写（决策 2/3，query rewrite v3）：完整带选项法考题自带题干 → 跳过；
    有历史 → LLM 改写。意图已在调用前判定为检索分支；此处只按「有无历史 + 是否完整法考题」
    决定是否烧改写调用（grilling：自包含正则 gate 账目不成立，只保留这两个确定判据）。
    """
    if not recent_ser or has_options:
        return raw_query
    with llm_guard:  # 多轮改写是 LLM 调用，同样占并发位
        return rewrite_query(registry.get(), recent, raw_query)


# 会话级合同状态保留 main 公共符号；canonical storage 供公开 bootstrap 默认适配器共享。
_contract_convs = DEFAULT_CONTRACT_STATE.active
_contract_reviewed_convs = DEFAULT_CONTRACT_STATE.reviewed


def _describe_image_for_bootstrap(image: str, text: str) -> str:
    """Resolve the image capability here so bootstrap never selects a provider.

    阶段B（2026-09-05）：必须按模态取视觉模型。旧写法 registry.get() 会拿默认文本模型
    （LongCat 实测静默忽略图片）——能力缺失已由 chat() 的 501 门拦截，此处再遇
    QuotaExhausted 说明能力存在但配额耗尽，显式 503 而非静默降级为"无图回答"。
    """
    try:
        _, vision_llm = registry.pick("vision", "flag")
    except QuotaExhausted as qe:
        raise HTTPException(status_code=503, detail="视觉模型配额不足，请稍后重试") from qe
    with llm_guard:
        return describe_image(vision_llm, image, text)


configure_default_image_describer(_describe_image_for_bootstrap)


def _contract_messages(pre: dict, cd: dict) -> list:
    """组装合同 messages（首轮 = 完整报告；追问 = 只答追问）。

    B5（2026-08-07）根因修复：之前只构造 [System, Human(证据+请按模板输出报告)]，
    丢历史 `pre["recent"]` + 丢当前追问 `pre["user_text"]`，且 SYSTEM_CONTRACT_REVIEW
    每次强制全报告模板 → 追问时模型看不到追问、只会重新输出整份报告。
    现按「首轮 / 追问」分流：追问带历史 Q&A + 当前追问，换 SYSTEM_CONTRACT_FOLLOWUP。
    """
    evidence = []
    for b in cd["blocks"]:
        arts = "、".join(b["articles"]) or "（无命中条文，依据为检索结果）"
        tags = "、".join(b["tags"]) or "无"
        evidence.append(f"[{b['n']}. {b['label']}] 风险标签：{tags}\n{b['text']}\n（相关条文：{arts}）")
    evidence_block = "\n\n".join(evidence)

    # 追问判定用「是否已产出过完整报告」，而非「recent 有无 assistant 消息」——
    # need_clarify 信息确认反问也是 assistant 消息，会把首次真评估误判成追问、
    # 跳过完整报告模板（对抗审计 2026-08-07）
    is_followup = pre.get("conv_id") in _contract_reviewed_convs

    if is_followup:
        # 追问：带历史（模型可见已答内容）+ 当前追问，只答追问，不重出报告
        history = []
        for m in pre["recent"]:
            content = m.get("content") or ""
            if m.get("role") == "user":
                history.append(HumanMessage(content=content))
            else:
                history.append(AIMessage(content=content))
        sys_text = SYSTEM_BASE + SYSTEM_CONTRACT_FOLLOWUP
        user_content = (
            f"【合同（分条款）】\n{evidence_block}\n\n"
            f"用户追问：{pre.get('user_text') or ''}\n\n"
            "请直接针对上面的追问回答，不要重新输出完整风险评估报告。"
        )
        return [SystemMessage(content=sys_text)] + history + [HumanMessage(content=user_content)]

    # 首轮：完整评估报告
    sys_text = SYSTEM_BASE + SYSTEM_CONTRACT_REVIEW
    sys_text += f"\n（本份合同总体风险等级：{cd['level']}——判定依据：{cd['basis']}）"
    if cd.get("truncated"):
        sys_text += "\n（合同过长已截取前段，末尾请列出'未覆盖条款段'清单，建议用户分段审查）"
    user_content = f"【合同（分条款）】\n{evidence_block}\n\n请按模板输出合同风险评估报告。"
    return [SystemMessage(content=sys_text), HumanMessage(content=user_content)]


def _best_effort_log_agent_gate_failure(correlation_id: str | None = None) -> None:
    """Emit the terminal Gate failure signal without ever entering another observer."""
    extra = {
        "agent_gate_mode": "fast_path",
        "agent_gate_reason_codes": [GATE_TECHNICAL_FAILURE],
    }
    if correlation_id is not None:
        extra["agent_correlation_id"] = correlation_id
    try:
        logging.getLogger("legal.chat").exception(GATE_TECHNICAL_FAILURE, extra=extra)
    except Exception:
        # Logging is the terminal best-effort sink. Never recurse into metrics,
        # account logging, or the request coordinator from this failure path.
        pass


def _observe_agent_gate(
    correlation_id: str,
    mode: str,
    reason_codes: list[str],
    *,
    technical_failure: bool,
) -> None:
    """Best-effort, privacy-safe Gate observers; failures never alter request execution."""
    try:
        routing_metrics.record_agent_gate(
            mode,
            reason_codes,
            correlation_id,
            technical_failure=technical_failure,
        )
    except Exception:
        try:
            log_account(
                agent_correlation_id=correlation_id,
                agent_gate_mode="fast_path",
                agent_gate_reason_codes=[GATE_TECHNICAL_FAILURE],
            )
        except Exception:
            _best_effort_log_agent_gate_failure(correlation_id)
        return

    try:
        log_account(
            agent_correlation_id=correlation_id,
            agent_gate_mode=mode,
            agent_gate_reason_codes=reason_codes,
        )
    except Exception:
        if not technical_failure:
            try:
                routing_metrics.record_agent_gate(
                    "fast_path",
                    [GATE_TECHNICAL_FAILURE],
                    correlation_id,
                    technical_failure=True,
                )
            except Exception:
                pass
        _best_effort_log_agent_gate_failure(correlation_id)


def _run_agent_gate_shadow(bootstrap) -> None:
    """Predict and observe only; Task 6 never selects or starts Agent Path."""
    correlation_id = make_agent_correlation_id(conversation_id=bootstrap.conv_id)
    try:
        decision: AgentGateDecision = decide_gate(bootstrap)
    except Exception:
        _observe_agent_gate(
            correlation_id,
            "fast_path",
            [GATE_TECHNICAL_FAILURE],
            technical_failure=True,
        )
        return
    _observe_agent_gate(
        correlation_id,
        decision.mode,
        list(decision.reason_codes),
        technical_failure=False,
    )


def _bootstrap_only(
    user_id: int,
    conversation_id,
    text: str,
    image,
    client_truncated: bool = False,
    case_domain: str | None = None,
):
    """Persist one accepted user request without starting either answer path."""
    return bootstrap_request(
        user_id,
        conversation_id,
        text,
        image,
        client_truncated,
        case_domain=case_domain,
        _deps=BootstrapDependencies(
            session_factory=SessionLocal,
            load_context=load_context,
            validate_image=validate_image,
            persist_image=persist_image,
            cleanup_persisted_image=cleanup_persisted_images,
            describe_image=_describe_image_for_bootstrap,
            classify_intent=classify_intent,
            is_exam_question=query_understand._is_exam_question,
            has_exam_options=query_understand.has_exam_options,
            is_contract_review=is_contract_review,
            feature_multi_analyze=settings.feature_multi_analyze,
            contract_conversations=_contract_convs,
            contract_reviewed_conversations=_contract_reviewed_convs,
            is_contract_exit=is_contract_exit,
        ),
    )


def _prepare_fast_path_only(bootstrap: RequestBootstrap):
    """Run legacy retrieval from an already committed bootstrap exactly once."""
    return prepare_fast_path(
        bootstrap,
        _deps=FastPathDependencies(
            feature_study_retrieval=settings.feature_study_retrieval,
            is_meta_study=query_understand.is_meta_study,
            rewrite_for_retrieval=_rewrite_for_retrieval,
            scenario_supplement_docs=scenario_supplement_docs,
            retrieve_exam=retrieve_exam,
            cheating_docs=cheating_docs,
            build_contract_data=build_contract_data,
            retrieve=retrieve,
            search_qa=ks.search_qa,
            is_consumer_clause_scenario=is_consumer_clause_scenario,
            consumer_clause_docs=consumer_clause_docs,
            is_consumer_fraud_scenario=is_consumer_fraud_scenario,
            consumer_fraud_docs=consumer_fraud_docs,
            format_docs=format_docs,
        ),
    )


def _pre(user_id: int, conversation_id, text: str, image, client_truncated: bool = False):
    """Compatibility coordinator for committed bootstrap plus legacy fast retrieval."""
    bootstrap = _bootstrap_only(user_id, conversation_id, text, image, client_truncated)
    if settings.agent_shadow_enabled:
        try:
            _run_agent_gate_shadow(bootstrap)
        except Exception:
            # Correlation/observer setup is technical infrastructure too. The Fast
            # Path remains authoritative even if the best-effort observer itself fails.
            _best_effort_log_agent_gate_failure()
    return _prepare_fast_path_only(bootstrap)


def _stable_agent_request_seed(user_id: int, conversation_id: int) -> str:
    """Length-delimited request assignment material; this value is never logged."""
    request_id = request_id_var.get()
    parts = (str(user_id), str(conversation_id), request_id if request_id != "-" else "test-request")
    return "|".join(f"{len(part)}:{part}" for part in parts)


def _record_actual_agent_route(route: str, *, fallback_reason: str | None = None) -> None:
    """Best-effort observer; metric failure cannot change the selected route."""
    try:
        routing_metrics.record_agent_route(route, fallback_reason=fallback_reason)
    except Exception:
        try:
            log_account(agent_actual_route=route, agent_fallback_reason=fallback_reason)
        except Exception:
            pass


def fallback_to_fast_path(bootstrap: RequestBootstrap, reason_code: str) -> dict:
    """Prepare Fast Path only for one allowlisted technical Agent failure."""
    if not routing_metrics.is_technical_fallback_reason(reason_code):
        raise ValueError("Agent failure is not eligible for Fast Path fallback")
    prepared = _prepare_fast_path_only(bootstrap)
    prepared["agent_fallback_reason"] = reason_code
    return prepared


def _resume_bootstrap(*, conversation_id: int, answer: str, state: LegalAgentState) -> RequestBootstrap:
    """Build a non-persisting Planner snapshot after an owned clarification CAS."""
    issue_context = "；".join(issue.question for issue in state.issues)
    query = f"原法律争点：{issue_context}\n用户补充：{answer.strip()}"
    return RequestBootstrap(
        conv_id=conversation_id,
        summary="",
        recent=[],
        recent_messages=[],
        image=None,
        user_text=query,
        image_rel=None,
        thumb_rel=None,
        image_description="",
        raw_query=query,
        supplement_text=query,
        intent="legal_query",
        is_exam=False,
        has_options=False,
        contract_mode=False,
        contract_text=None,
        client_truncated=False,
        # R1-OB：resume 场景判域元信息沿用 state（首次请求时已持久化），保证多轮一致。
        case_domain=state.case_domain,
    )


def _agent_streaming_response(result) -> StreamingResponse:
    return StreamingResponse(
        encode_sse_stream(serialize_agent_events(result)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


async def _execute_agent_observing_disconnect(request: Request, **kwargs):
    """Run one bounded service call while projecting client disconnect into a stop check."""
    disconnected = Event()
    finished = asyncio.Event()

    async def watch_disconnect() -> None:
        while not finished.is_set():
            if await request.is_disconnected():
                disconnected.set()
                return
            try:
                await asyncio.wait_for(finished.wait(), timeout=0.1)
            except TimeoutError:
                continue

    watcher = asyncio.create_task(watch_disconnect())
    try:
        return await run_in_threadpool(
            execute_agent_request,
            cancelled=disconnected.is_set,
            **kwargs,
        )
    finally:
        finished.set()
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher


def _record_analysis(
    user_id: int | None,
    conv_id: int | None,
    source_type: str,
    cd: dict,
    duration_ms: int,
):
    """合同评估运行记录写库（analysis_runs，审计/评测用）。失败不阻断主流程。

    传确定性骨架 contract_data（cd）而非 8 个位置参数（code-review Standards 收敛）。
    """
    db = SessionLocal()
    try:
        article_count = len({d.metadata.get("article", "") for d in cd.get("docs", []) if d.metadata.get("article")})
        db.add(
            AnalysisRun(
                user_id=user_id,
                conversation_id=conv_id,
                source_type=source_type,
                clause_count=len(cd.get("blocks", [])),
                article_count=article_count,
                risk_level=cd.get("level", ""),
                truncated=bool(cd.get("truncated")),
                duration_ms=duration_ms,
            )
        )
        db.commit()
    except Exception as e:
        print(f"[analysis-run] {e}", flush=True)
    finally:
        db.close()


# 三分法接地量化（B3）：in_context / recall_miss / hallucination 累计，进程内。
# 供验收/复盘读值；后续可接 admin 面板。多 worker 下为分片值（单 worker 部署无此问题）。
_grounding_stats: dict = {"in_context": 0, "recall_miss": 0, "hallucination": 0}


@dataclass(frozen=True)
class AgentFinalizationResult:
    """Buffered Task 9 result; this seam performs no storage, routing or SSE."""

    answer: str | None
    reason_code: str


def finalize_verified_agent_answer(
    state: LegalAgentState,
    draft: DraftAnswer,
    verification: VerificationResult,
    *,
    citation_checker=citation_verify,
    quality_checker=quality.self_check,
    expand_law_names_fn=output_normalize.expand_law_names,
    expand_citations_fn=output_normalize.expand_citations,
    money_normalize_fn=output_normalize.money_normalize,
    strip_notes_fn=output_normalize.strip_unprovided_notes,
    source_lookup=source_in_kb,
) -> AgentFinalizationResult:
    """Run deterministic final gates on a complete buffer and reveal only PASS.

    Normalization intentionally happens after the first citation and quality
    checks, then citations are checked again because expansion can create a
    newly recognizable canonical citation.
    """

    answer = render_verified(state, draft, verification)
    if answer is None:
        return AgentFinalizationResult(answer=None, reason_code="VERIFIER_NOT_PASS")
    try:
        if citation_checker(answer):
            return AgentFinalizationResult(answer=None, reason_code="CITATION_CHECK_FAILED")
        quality_result = quality_checker(answer, True)
        if not quality_result.ok:
            return AgentFinalizationResult(
                answer=None,
                reason_code=f"QUALITY_CHECK_FAILED:{quality_result.reason}",
            )
        normalized = expand_law_names_fn(answer)
        normalized = expand_citations_fn(normalized)
        normalized = money_normalize_fn(normalized)
        normalized = strip_notes_fn(normalized, source_lookup)
        if citation_checker(normalized):
            return AgentFinalizationResult(
                answer=None,
                reason_code="POST_NORMALIZE_CITATION_CHECK_FAILED",
            )
    except Exception:
        return AgentFinalizationResult(answer=None, reason_code="FINAL_GATE_TECHNICAL_FAILURE")
    return AgentFinalizationResult(answer=normalized, reason_code="READY")


def _post(pre: dict, answer: str, curate: bool = True):
    """流式后的写库 + 受控沉淀 + 压缩（独立会话，线程池内，不阻塞用户该轮）。

    curate=False：缓存命中路径——答案当初已沉淀过，跳过避免重复候选。

    B1/B2/B3（2026-08-07）：写库前做生成层输出归一（零 LLM 零 BGE 确定性）——
    money_normalize 币种 $/¥→元；strip_unprovided_notes 删"未检索到/建议核对"矛盾句
    （带库证据：库内删、库外保）；legal_query 跑三分法接地量化漏召回/幻觉率。
    """
    db = SessionLocal()
    try:
        # 生成层输出归一（幂等，缓存命中路径重跑无害）
        # 先补"法律名+第X条"书名号（"刑法第23条"→《刑法》第23条），再展开省略书名的
        # 连续条号（"《民法典》第715条（...）、第716条"→补书名），再币种归一、矛盾句删除
        # ——让前端标色/citation_grounding 抽到完整《X》第N条。
        answer = output_normalize.expand_law_names(answer)
        answer = output_normalize.expand_citations(answer)
        answer = output_normalize.money_normalize(answer)
        answer = output_normalize.strip_unprovided_notes(answer, source_in_kb)
        if pre.get("intent") == "legal_query":
            citation_grounding(answer, pre.get("sources") or [], _grounding_stats)
        db.add(Message(conversation_id=pre["conv_id"], role="assistant", content=answer))
        conv = db.get(Conversation, pre["conv_id"])
        # 对抗审计 v2 #21：原子自增（与 _pre 同款防读-改-写竞态）
        db.execute(
            text("UPDATE conversations SET message_count = COALESCE(message_count, 0) + 1 WHERE id = :id"),
            {"id": pre["conv_id"]},
        )
        conv.message_count = (conv.message_count or 0) + 1
        conv.last_active_at = datetime.utcnow()
        if not conv.answer:
            conv.answer = (answer or "")[:2000]
        db.commit()

        # 受控沉淀：高有据 + 含引用 + 非空答 → 入待审
        # 沉淀闸（决策 7）：只收真实法律咨询——study_aid 法考题错答（多选漏答）可被采纳污染
        # qa_pairs；cheating 问答本就不该沉淀；chitchat/meta 无引用本就不沉淀。
        if curate and pre.get("intent") == "legal_query":
            grounded = grounded_top_score(pre["rewritten"])
            q = pre["user_text"] or pre["rewritten"]
            if q and should_curate(grounded, answer):
                ks.create_candidate(db, q, answer, grounded, json.dumps(pre["sources"], ensure_ascii=False))

        # 增量压缩（对抗审计 v2 #9：LLM 调用纳入 llm_guard 并发位——突发长答复时不再无界并发，
        # 且不再独占共享线程池/悬挂 SSE 连接最长 120s）
        recent = recent_messages(db, conv.id)
        if needs_compress(conv, recent):
            with llm_guard:
                compress(db, conv, registry.get())
    finally:
        db.close()


def _post_placeholder(pre: dict) -> None:
    """SSE 失败/空答的补偿：落一条 assistant 占位消息，保持 user/assistant 成对与 message_count 一致。

    _pre 已落库用户消息；若流式生成失败/空答时 _post 从未执行，会留下无答复的用户消息、
    计数永久错位（对抗审计 2026-08-07）。占位不沉淀、不压缩。
    """
    db = SessionLocal()
    try:
        db.add(Message(conversation_id=pre["conv_id"], role="assistant", content="服务暂时无响应，请稍后重试。"))
        conv = db.get(Conversation, pre["conv_id"])
        # 对抗审计 v2 #21：原子自增（与 _pre/_post 同款防竞态）
        db.execute(
            text("UPDATE conversations SET message_count = COALESCE(message_count, 0) + 1 WHERE id = :id"),
            {"id": pre["conv_id"]},
        )
        conv.message_count = (conv.message_count or 0) + 1
        conv.last_active_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def _usage_total(resp) -> int | None:
    """从 langchain 响应读 total_tokens（兼容 usage_metadata / response_metadata）。"""
    if resp is None:
        return None
    um = getattr(resp, "usage_metadata", None) or {}
    if um.get("total_tokens"):
        return int(um["total_tokens"])
    rm = getattr(resp, "response_metadata", None) or {}
    tu = rm.get("token_usage") or rm.get("usage") or {}
    t = tu.get("total_tokens") if isinstance(tu, dict) else None
    return int(t) if t else None


def _token_charge(resp, text: str) -> int:
    """真实 usage 优先，否则按文本估算。"""
    return _usage_total(resp) or estimate_tokens(text)


def _safe_pick(modality: str, tier: str, *, exclude: set[str] | None = None) -> tuple[str, Any, bool]:
    """pick 耗尽/无该档模型时回退默认模型。第三项 degraded：回退模型本身也已不可用
    （配额耗尽/低于阈值），调用方应明说降级，不静默烧耗尽模型。

    exclude（F7，2026-09-14）：本次重试中**已尝试过**的模型 key，透传给 `registry.pick` 以
    避免重复选中同一模型 —— 瞬时故障不再 `mark_depleted` 时，靠它推进到下一个模型。
    """
    try:
        key, llm = registry.pick(modality, tier, exclude=exclude)
        return key, llm, False
    except QuotaExhausted:
        dk = registry.default_key()
        return dk, registry.get(), registry.is_unavailable(dk)


# 核对/降级提示（轻量升级失败、旗舰自检失败、配额紧张共用，避免字面量重复）
# B1（2026-08-07）：去掉"建议核对条文原文"——前端曾为清这句写 stripUnprovidedHint，后端不再制造该噪音
NOTE_COMPLEX = "\n\n> 注：该问题较复杂，本回答仅供参考。"
NOTE_QUOTA = "\n\n> 注：模型配额紧张，本回答仅供参考。"

# 低置信反问计数（任务2）：conv_id → 已反问（最多一次，防死循环）。进程内状态，
# 单 worker 下有效（ADR-008 单 worker 约束）；重启清零可接受——反问上限防的是同会话循环。
_clarified: dict[int, bool] = {}


def _cutoff() -> str:
    return datetime.now().date().isoformat()


def _cacheable(pre: dict) -> bool:
    """仅安全形态可缓存：法律咨询/法考题(study_aid) + 无图 + 首轮 + 检索命中。

    study_aid 白名单由 feature_study_cache 控制（ADR-012 后法考题答案自检通过率高——
    评测 19/20 带库内引用，写闸见 _cache_write_ok，防"引在库但答非所问"入缓存）。"""
    intent = pre.get("intent")
    ok_intent = intent == "legal_query" or (settings.feature_study_cache and intent == "study_aid")
    return ok_intent and not pre.get("image") and not pre.get("recent") and bool(pre.get("sources"))


def _cache_key(pre: dict) -> str:
    ids = [f"{s.get('source', '')}|{s.get('article', '')}" for s in (pre.get("sources") or [])]
    return answer_cache.make_key(pre.get("rewritten", ""), pre.get("intent", ""), _cutoff(), ids)


def _cache_write_ok(pre: dict, answer: str) -> bool:
    """确定性缓存写闸（审查 C2）：study_aid 答案的引用必须全部命中本轮检索返回条文。

    自检（quality.self_check）只是"无实体"门禁——查引用是否在库，不保证"引对题"
    （引在库但答非所问）。法考题答案与检索条文强绑定，故写缓存前追加确定性校验：
    引用条号 ⊆ 检索 sources 的条号集合，防止"引对库内条但语义不对题"的坏答案被
    TTL 6h 缓存放大给所有同 key 用户。legal_query 维持现状（自检已覆盖）。
    """
    if pre.get("intent") != "study_aid":
        return True
    retrieved = {_normalize_article(s.get("article", "")) for s in (pre.get("sources") or []) if s.get("article")}
    if not retrieved:
        return False
    cited = {_normalize_article(a) for _, a, _ in extract_citations(answer or "")}
    return bool(cited) and cited <= retrieved


def _cache_guards(text: str) -> tuple[str, int, str, str]:
    """近重复护栏：极性/选项数/标号体系/选项内容指纹（确定性纯函数，query_understand）。

    指纹（审查 C4 修复）：同题干换选项内容必须 miss——防旧题"选B"答案错位下发。
    """
    return (
        query_understand._polarity(text),
        query_understand.option_count(text),
        query_understand._label_system(text),
        query_understand._options_fingerprint(text),
    )


def _embed_question(text: str) -> list[float] | None:
    """本地 BGE 嵌入（零成本）；失败静默返回 None（不阻塞主流程）。"""
    try:
        return embeddings.embed_query(text or "")
    except Exception:
        return None


def _similar_cache_hit(pre: dict) -> dict | None:
    """近重复命中（feature_similar_cache，grilling 定稿）：嵌入输入 + 护栏 → get_similar。

    仅当精确 key miss 时调用；护栏不一致（极性/选项数/标号体系/指纹）→ miss，安全。
    """
    try:
        emb = _embed_question(pre.get("rewritten") or "")
        if not emb:
            return None
        pol, cnt, lab, fp = _cache_guards(pre.get("rewritten") or "")
        return answer_cache.get_similar(emb, polarity=pol, option_count=cnt, label_system=lab, options_fingerprint=fp)
    except Exception:
        return None


_QA_DIRECT_RETURN_THRESHOLD = 0.92  # QA 语义直返阈值（审查护栏：低于则回落 LLM）


def _qa_direct_return(pre: dict) -> str | None:
    """QA 持久语义缓存直返（8-23 智谱免费 token 预生成语料）：高阈值 + 指纹 + 时效护栏。

    命中返回预生成解析答案（零 LLM）；任一护栏不过 → None（回落 LLM 生成）。
    - score ≥ 0.92（search_qa 余弦，接近同一问法）
    - 选项指纹护栏（审查 C4）：选项题同题干换选项内容必须 miss
    - evidence 时效校验：source|article 在库且仍有效（exact_article_lookup）
    """
    qa = pre.get("qa_hit")
    if not qa or qa.get("score", 0) < _QA_DIRECT_RETURN_THRESHOLD:
        return None
    q = pre.get("rewritten") or ""
    q_fp = query_understand._options_fingerprint(q)
    stored_fp = qa.get("fingerprint") or ""
    if q_fp and stored_fp and q_fp != stored_fp:
        return None  # 同题干换选项内容 → 直返必错（C4）
    evidence = qa.get("evidence") or ""
    if "|" in evidence:
        # 种子格式：source|article
        src, art = evidence.split("|", 1)
        try:
            if not exact_article_lookup(src, art):
                return None  # 证据条文已失效/不在库 → 不直返
        except Exception:
            return None
    elif evidence.lstrip().startswith("["):
        # 自动沉淀格式：JSON 数组 [{source, article, ...}]——逐条校验，任一条失效 → 不直返
        # （原只认 "|" 格式，自动沉淀的 JSON evidence 被静默跳过时效护栏，对抗审计 2026-08-07）
        try:
            refs = json.loads(evidence)
        except Exception:
            return None
        for r in refs:
            src = (r or {}).get("source", "")
            art = (r or {}).get("article", "")
            if src and art:
                try:
                    if not exact_article_lookup(src, art):
                        return None
                except Exception:
                    return None
    # feedback:... 等其他 evidence 无条文引用 → 跳过时效校验
    return qa.get("answer") or None


@dataclass
class _LightResult:
    """轻量路径返回结构（消除四处重复 dict 形状）。key=None 表示不计配额。"""

    answer: str
    key: str | None
    modality: str
    tier: str
    usage: int
    escalated: bool
    verdict: str


def _light_buffered(pre: dict, messages: list) -> _LightResult:
    """轻量路径：缓冲生成 → 自检 → 至多一次升级旗舰重答。同步，线程池内跑。"""
    modality = "vision" if pre.get("image") else "text"
    ctx_present = bool(pre.get("sources"))
    lkey, llm, _ = _safe_pick(modality, "light")  # 轻量回退降级由下方升级 except 兜底
    with llm_guard:  # 轻量+升级重答共占一个并发位（同一请求串行持有，突增时降级）
        return _light_buffered_locked(pre, messages, modality, ctx_present, lkey, llm)


def _light_buffered_locked(pre: dict, messages: list, modality: str, ctx_present: bool, lkey, llm) -> _LightResult:
    """轻量路径主体（已持有并发位）：缓冲生成 → 自检 → 至多一次升级旗舰重答。"""
    resp = llm.invoke(messages)
    raw = clean_answer(resp.content or "") if resp else ""
    usage = _token_charge(resp, raw)
    v = quality.self_check(raw, ctx_present)
    if v.ok:
        return _LightResult(raw, lkey, modality, "light", usage, False, "pass")
    # 升级旗舰（配额耗尽则不升级，明说降级）
    try:
        fkey, fllm = registry.pick(modality, "flag")
    except QuotaExhausted:
        return _LightResult(
            (raw + NOTE_QUOTA) if raw else "", lkey, modality, "light", usage, False, v.reason or "low_quota"
        )
    if fkey == lkey:  # 轻量即旗舰，无更强者可升
        return _LightResult((raw + NOTE_COMPLEX) if raw else "", lkey, modality, "light", usage, False, v.reason)
    fresp = fllm.invoke(messages)
    fraw = clean_answer(fresp.content or "") if fresp else ""
    fusage = _token_charge(fresp, fraw)
    fv = quality.self_check(fraw, ctx_present)
    if fv.ok:
        return _LightResult(fraw, fkey, modality, "flag", usage + fusage, True, "pass")
    return _LightResult((fraw + NOTE_COMPLEX) if fraw else "", fkey, modality, "flag", usage + fusage, True, fv.reason)


def _invoke_llm(messages, llm=None) -> str:
    """非流式兜底：流式不兼容/空答时，用给定（或默认）模型 invoke 一次拿完整答案。"""
    llm = llm or registry.get()
    with llm_guard:  # 同步兜底同样占一个并发位
        resp = llm.invoke(messages)
    return resp.content if resp else ""


@app.post("/api/chat/file")
@limiter.limit("20/minute")
async def chat_file(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """文件→文本（合同评估/普通问答输入，二期）。复用 knowledge_service 解析
    （txt/md/pdf/docx，魔数校验），零 LLM 零 BGE。前端拿文本后走现有 /api/chat 管线。
    """
    raw = await _read_capped(file, settings.upload_max_mb * 1024 * 1024, f"文件过大（>{settings.upload_max_mb}MB）")
    try:
        ext, text = ks.parse_upload_or_raise(file.filename, raw)  # 与 admin_upload 共用（code-review Standards）
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve

    def _do():
        t = text
        truncated = len(t) > settings.contract_max_chars
        if truncated:
            t = t[: settings.contract_max_chars]
        return {
            "file_name": file.filename,
            "ext": ext,
            "chars": len(t),
            "truncated": truncated,
            "text": t,
        }

    return await run_in_threadpool(_do)


@app.post("/api/chat/transcribe")
@limiter.limit("20/minute")
async def chat_transcribe(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """语音→文字（M2，Qwen livetranslate 语音模型转写，前端 PC 语音输入）。

    前端 MediaRecorder→PCM→WAV（webm/opus 不被语音模型接受，见 scripts/smoke_transcribe.py）。
    门禁实测：OpenAI 兼容 /chat/completions + input_audio(data:;base64, 前缀 + wav) + stream +
    translation_options(source/target 均 zh)。失败显式 502，让前端回退浏览器 Web Speech。
    """
    if not settings.feature_transcribe or not registry.has_modality("voice"):
        raise HTTPException(
            status_code=501,
            detail="语音转写未启用（feature_transcribe=False 或所配置模型无语音能力）",
        )
    raw = await _read_capped(file, settings.audio_max_mb * 1024 * 1024, f"音频过大（>{settings.audio_max_mb}MB）")
    fname = file.filename or ""
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if ext not in AUDIO_EXTS:
        raise HTTPException(status_code=400, detail=f"仅支持 {'/'.join(sorted(AUDIO_EXTS))} 音频")
    if len(raw) < 1024:
        raise HTTPException(status_code=400, detail="音频内容为空")
    if len(raw) > settings.audio_max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"音频过大（>{settings.audio_max_mb}MB）")
    b64 = base64.b64encode(raw).decode()

    def _do() -> dict:
        with llm_guard:  # LLM 调用，占并发位（与图片描述同级）
            key, llm = registry.pick("voice", "flag")
            text = transcribe_audio(llm, b64, ext)
            registry.deduct(key, estimate_tokens(text))
            return {"text": text}

    try:
        return await run_in_threadpool(_do)
    except QuotaExhausted as qe:
        raise HTTPException(status_code=503, detail="语音模型配额不足，请稍后重试") from qe
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).warning("transcribe failed: %s", e)
        raise HTTPException(status_code=502, detail="语音识别服务暂时不可用，请稍后重试") from e


@app.get("/api/admin/analysis-runs")
@limiter.limit("30/minute")
async def admin_analysis_runs(request: Request, limit: int = 50, admin: User = Depends(require_admin)):
    """合同评估运行记录（analysis_runs，审计用）。倒序返回最近 N 条（≤200）。"""

    def _do():
        db = SessionLocal()
        try:
            rows = db.query(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(max(1, min(limit, 200))).all()
            return [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "conversation_id": r.conversation_id,
                    "source_type": r.source_type,
                    "clause_count": r.clause_count,
                    "article_count": r.article_count,
                    "risk_level": r.risk_level,
                    "truncated": r.truncated,
                    "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()

    return await run_in_threadpool(_do)


@app.get("/api/law")
@limiter.limit("60/minute")
async def law_detail(request: Request, source: str, article: str, user: User = Depends(get_current_user)):
    """法条原文（前端法条悬浮卡 / 速查面板，P1）。复用 exact_article_lookup，未命中 404。

    B3（2026-08-07）：article 先 _normalize_article 归一（〇/零、阿拉伯/中文、之条），
    前端传原始条号文本即可命中，不再自行拼"第X条"。
    """

    def _do():
        docs = exact_article_lookup(source, _normalize_article(article))
        if not docs:
            return None
        d = docs[0]
        return {
            "source": d.metadata.get("source", source),
            "article": d.metadata.get("article", article),
            "content": d.page_content,
            "status": d.metadata.get("status", ""),
            "effective_from": d.metadata.get("effective_from", ""),
            "effective_to": d.metadata.get("effective_to", ""),
        }

    res = await run_in_threadpool(_do)
    if res is None:
        raise HTTPException(status_code=404, detail="未找到该法条")
    return res


@app.get("/api/law/search")
@limiter.limit("60/minute")
async def law_search(request: Request, q: str, user: User = Depends(get_current_user)):
    """法条搜索（速查面板）：关键词/条号 → 库内法条去重列表。"""

    def _do():
        docs = retrieve(q, k=8)
        seen, out = set(), []
        for d in docs:
            src = d.metadata.get("source", "")
            art = d.metadata.get("article", "")
            key = (src, art)
            if not art or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "source": src,
                    "article": art,
                    "preview": d.page_content[:80],
                    "content": d.page_content,
                    "status": d.metadata.get("status", ""),
                }
            )
        return out

    return await run_in_threadpool(_do)


async def _stream_with_status_preframe(gen):
    """P0 即时首帧：先发一个占位状态帧，再委托原 stream() 生成器。

    浏览器首字符从"模型 prefill + RAG 检索"的秒级等待，降到 <50ms（助手气泡+提示瞬出）；
    原 stream() 内的 _pre / RAG / 模型调用逻辑零改动，错误语义不变。前端对未知 type 帧自动忽略。
    注：本帧只改善"首个可见字符"的体感延迟；真实首内容 token 延迟（日志 first_ms）由后续 P1/P2 优化。
    """
    yield f"data: {json.dumps({'type': 'status', 'msg': '正在思考…'}, ensure_ascii=False)}\n\n"
    async for frame in gen:
        yield frame


def serialize_clarification_event(*, run_id: str, state_version: int, prompt: str, issue_id: str) -> dict[str, object]:
    """Project one public clarification event; internal evaluator data is excluded."""
    return {
        "type": "clarification",
        "run_id": run_id,
        "state_version": state_version,
        "prompt": prompt,
        "issue_id": issue_id,
    }


@app.post("/api/chat")
@limiter.limit("60/minute")
async def chat(request: Request, body: ChatIn, user: User = Depends(get_current_user)):
    text = (body.content if body.content is not None else body.question) or ""
    text = text.strip()
    image = body.image
    # 阶段B 能力门（2026-09-05）：当前注册模型无视觉能力时显式 501，禁止把图片内容块
    # 静默回退给文本模型（LongCat 实测会忽略图片并按文字作答——诚实停用优于悄悄答错）。
    if image and not registry.has_modality("vision"):
        raise HTTPException(status_code=501, detail="图片理解当前不可用：所配置模型无视觉能力")
    t0 = time.perf_counter()
    pre = None
    if body.agent_run_id is not None:
        assert body.agent_state_version is not None and body.conversation_id is not None
        if not text:
            raise HTTPException(status_code=400, detail="请输入对 Agent 追问的回答")
        if not settings.agent_enabled:
            raise HTTPException(status_code=503, detail="Agent 当前已停用，请稍后重试")
        db = SessionLocal()
        try:
            resumed = await run_in_threadpool(
                resume_with_user_fact,
                db=db,
                run_locks=_DEFAULT_RUN_LOCKS,
                run_id=str(body.agent_run_id),
                expected_version=body.agent_state_version,
                user_id=user.id,
                conversation_id=body.conversation_id,
                answer=text,
            )
            resume_bootstrap = _resume_bootstrap(
                conversation_id=body.conversation_id,
                answer=text,
                state=resumed.state,
            )
            agent_result = await _execute_agent_observing_disconnect(
                request,
                db=db,
                user_id=user.id,
                settings=settings,
                bootstrap=resume_bootstrap,
                finalizer=finalize_verified_agent_answer,
                run_id=resumed.run_id,
            )
        except ResumeRunNotFound:
            raise HTTPException(status_code=404, detail=RESUME_NOT_FOUND_DETAIL) from None
        except ResumeRunConflict:
            raise HTTPException(status_code=409, detail=RESUME_CONFLICT_DETAIL) from None
        finally:
            db.close()
        _record_actual_agent_route("agent_path")
        if agent_result.outcome != "fallback":
            return _agent_streaming_response(agent_result)
        _record_actual_agent_route("fast_path", fallback_reason=agent_result.reason_code)
        pre = await run_in_threadpool(
            fallback_to_fast_path,
            resume_bootstrap,
            agent_result.reason_code,
        )
    if not text and not image:
        raise HTTPException(status_code=400, detail="请输入问题或上传图片")
    if pre is None:
        try:
            if not settings.agent_enabled:
                pre = await run_in_threadpool(
                    _pre,
                    user.id,
                    body.conversation_id,
                    text,
                    image,
                    body.truncated,
                )
                _record_actual_agent_route("fast_path")
            else:
                bootstrap = await run_in_threadpool(
                    _bootstrap_only,
                    user.id,
                    body.conversation_id,
                    text,
                    image,
                    body.truncated,
                    body.case_domain,
                )
                correlation_id = make_agent_correlation_id(conversation_id=bootstrap.conv_id)
                try:
                    gate = decide_gate(bootstrap)
                except Exception:
                    _observe_agent_gate(
                        correlation_id,
                        "fast_path",
                        [GATE_TECHNICAL_FAILURE],
                        technical_failure=True,
                    )
                    selected = False
                else:
                    _observe_agent_gate(
                        correlation_id,
                        gate.mode,
                        list(gate.reason_codes),
                        technical_failure=False,
                    )
                    forced_manual = bool(getattr(body, "force_agent", False)) and gate.mode != "refuse"
                    selected = forced_manual or routing_metrics.should_route_agent(
                        gate,
                        settings,
                        _stable_agent_request_seed(user.id, bootstrap.conv_id),
                    )
                if selected:
                    db = SessionLocal()
                    try:
                        agent_result = await _execute_agent_observing_disconnect(
                            request,
                            db=db,
                            user_id=user.id,
                            settings=settings,
                            bootstrap=bootstrap,
                            finalizer=finalize_verified_agent_answer,
                        )
                    finally:
                        db.close()
                    _record_actual_agent_route("agent_path")
                    if agent_result.outcome != "fallback":
                        return _agent_streaming_response(agent_result)
                    _record_actual_agent_route(
                        "fast_path",
                        fallback_reason=agent_result.reason_code,
                    )
                    pre = await run_in_threadpool(
                        fallback_to_fast_path,
                        bootstrap,
                        agent_result.reason_code,
                    )
                else:
                    _record_actual_agent_route("fast_path")
                    pre = await run_in_threadpool(_prepare_fast_path_only, bootstrap)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve)) from ve
        except LLMBusyError:
            raise HTTPException(status_code=503, detail="服务繁忙，请稍后重试") from None

    assert pre is not None
    messages = _build_messages(pre)

    # ---- 多模型路由决策（feature_router 关 → 全走 legacy 流式，旧行为零变化） ----
    use_router = settings.feature_router
    modality, tier = complexity.assess(text, bool(image), pre["intent"], pre["recent"])
    if use_router:
        if tier is None:  # 图片：描述已在 _pre 完成（两级预判第一级），回答阶段走旗舰
            tier = "flag"
        elif tier == "light" and not complexity.admit_light(
            text, bool(image), pre["intent"], pre["recent"], bool(pre["sources"])
        ):
            tier = "flag"  # 轻量准入不通过 → 升旗舰
    # 仅当该 modality+tier 真有模型时才走轻量缓冲路径；否则短文本走旗舰流式（避免回退 omni 非流式的 awkward 路径）
    use_light = use_router and tier == "light" and modality == "text" and registry.has_role("text", "light")
    if pre.get("contract_data") and use_router:
        use_light = False  # 合同评估强制旗舰流式（确定性骨架的报告生成）
    # ---- 低置信反问策略（任务2，feature_router 关 → 不启用，旧行为零变化）----
    # legal_query：库外硬信号/指名来源不在库 → 诚实拒答；信息不足 → 反问；其余直接答。
    # chitchat：直接聊（_pre 已不检索）。纯规则决策，零额外嵌入（标定结论：置信度分
    # 区分不了库外，见 clarify 模块注释——不为此调 grounded_top_score）。
    strategy = "direct"
    if use_router and pre["intent"] in ("legal_query", "chitchat"):
        if pre.get("contract_data"):
            # 合同模式：信息确认闸由分支0.3 need_clarify 负责（触发但无合同全文时反问），
            # 通用 clarify 不得拦截续聊短句（"那利息24%算吗"被判信息不足会绕开合同路径，
            # 2026-08-06 验收发现，第二轮"第二条违约金"direct 而第三轮被误拦）
            strategy = "direct"
        else:
            strategy = clarify.decide(
                pre["intent"],
                text,
                bool(pre["sources"]),
                _clarified.get(pre["conv_id"], False),
            )
    cache_key = None if body.no_cache else (_cache_key(pre) if (use_router and _cacheable(pre)) else None)
    cache_hit = answer_cache.get(cache_key) if cache_key else None
    flag_key = flag_llm = None
    if use_router and not use_light:
        flag_key, flag_llm, flag_degraded = _safe_pick(modality, tier or "flag")

    async def stream():
        _posted = False  # 本轮 assistant 消息是否已落库（对抗审计 v2 #5/#8：客户端断开时 finally 兜底占位）
        try:
            if pre.get("agent_fallback_reason"):
                yield f"data: {json.dumps({'type': 'restart', 'reason_code': pre['agent_fallback_reason']}, ensure_ascii=False)}\n\n"
            # ── 分支决策总览图（零 token 优先，LLM 兜底）─────────────────────────
            #   0   → 精确/近重复缓存命中          → 零 token 直返
            #   0.2 → QA 持久语义缓存命中           → 零 token 直返
            #   0.5 → 低置信反问 / 拒答             → 确定性模板（零 LLM）
            #   0.3 → 合同骨架（分条款风险评估）     → 一次 LLM
            #   1   → 非检索分支（闲聊/作弊/元问题）→ 零检索
            #   2   → LLM 生成（轻量自检 → 升级重试 → 流式剥 think）
            # ─────────────────────────────────────────────────────────────────
            # 分支0：缓存命中（精确 key 优先，近重复兜底 feature_similar_cache）→ 零 token 直返
            hit = cache_hit
            if not hit and cache_key and settings.feature_similar_cache:
                hit = await run_in_threadpool(_similar_cache_hit, pre)
            if hit:
                ca = hit["answer"]
                _f0 = time.perf_counter()  # 缓存命中：首帧≈总耗时（瞬时，用于首帧埋点分段标注）
                yield f"data: {json.dumps({'content': ca}, ensure_ascii=False)}\n\n"
                routing_metrics.record("cache", False, "pass", "hit", checked=False)
                log_account(
                    model="cache",
                    tier="cache",
                    cache="hit",
                    first_ms=round((_f0 - t0) * 1000, 1),
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    ok=True,
                    conv_id=pre["conv_id"],
                    user_id=user.id,
                    q_len=len(text),
                )
                yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                try:
                    await run_in_threadpool(_post, pre, ca, False)
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
                return

            # 分支0.2：QA 持久语义缓存直返（8-23 智谱免费 token 预生成语料，零 LLM）
            # 高阈值 + 选项指纹 + evidence 时效三护栏；仅命中才直返，否则回落 LLM
            # 对抗审计 v2 #20：_qa_direct_return 内 Chroma .get() 同步阻塞事件循环 → 线程池
            qa_ans = None if body.no_cache else await run_in_threadpool(_qa_direct_return, pre)
            if qa_ans:
                _f0 = time.perf_counter()
                yield f"data: {json.dumps({'content': qa_ans}, ensure_ascii=False)}\n\n"
                routing_metrics.record("qa_cache", False, "pass", "hit", checked=False)
                log_account(
                    model="qa_cache",
                    tier="qa_cache",
                    cache="hit",
                    token_est=0,
                    first_ms=round((_f0 - t0) * 1000, 1),
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    ok=True,
                    conv_id=pre["conv_id"],
                    user_id=user.id,
                    q_len=len(text),
                )
                yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                try:
                    await run_in_threadpool(_post, pre, qa_ans, False)
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
                return

            # 分支0.5：低置信反问 / 诚实拒答（任务2，零 LLM：省 token、措辞稳定、拦截硬答）
            if strategy in ("clarify", "refuse"):
                msg = clarify.CLARIFY_PROMPT if strategy == "clarify" else clarify.REFUSE_PROMPT
                if strategy == "clarify":
                    _clarified[pre["conv_id"]] = True  # 会话级：最多反问一次
                _f0 = time.perf_counter()  # 反问/拒答：零 LLM，首帧≈总耗时
                yield f"data: {json.dumps({'content': msg}, ensure_ascii=False)}\n\n"
                routing_metrics.record(strategy, False, "pass", "miss", checked=False)
                log_account(
                    model="rule",
                    tier=strategy,
                    cache="miss",
                    token_est=0,
                    first_ms=round((_f0 - t0) * 1000, 1),
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    ok=True,
                    conv_id=pre["conv_id"],
                    user_id=user.id,
                    q_len=len(text),
                )
                yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                try:
                    await run_in_threadpool(_post, pre, msg)
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
                return

            # 分支0.3：合同 / 文书风险评估（确定性骨架，2026-08-06）
            if pre.get("contract_data"):
                cd = pre["contract_data"]
                if cd.get("need_clarify"):
                    # 信息确认闸：触发但无合同全文 → 零 LLM 反问要内容/范围/立场/类型
                    _f0 = time.perf_counter()
                    yield f"data: {json.dumps({'content': CONTRACT_CLARIFY_PROMPT}, ensure_ascii=False)}\n\n"
                    routing_metrics.record("contract_clarify", False, "pass", "miss", checked=False)
                    log_account(
                        model="rule",
                        tier="contract_clarify",
                        cache="miss",
                        token_est=0,
                        first_ms=round((_f0 - t0) * 1000, 1),
                        ms=round((time.perf_counter() - t0) * 1000, 1),
                        ok=True,
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        q_len=len(text),
                    )
                    yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    try:
                        await run_in_threadpool(_post, pre, CONTRACT_CLARIFY_PROMPT, False)
                        _posted = True
                    except Exception as e:
                        print(f"[chat-post] {e}", flush=True)
                    return
                cm = _contract_messages(pre, cd)
                _f0 = None
                # SSE 分析进度（二期）：报告生成前回放确定性骨架已完成的步骤——真实数据，非虚假进度条
                _hit_arts = sorted(
                    {d.metadata.get("article", "") for d in cd.get("docs", []) if d.metadata.get("article")}
                )
                _steps = [
                    {"label": "解析合同", "detail": f"识别 {len(cd['blocks'])} 个条款"},
                    {"label": "匹配法条", "detail": f"定位 {len(_hit_arts)} 条法条依据"},
                    {"label": "风险初判", "detail": f"总体风险等级：{cd['level']}"},
                ]
                yield f"data: {json.dumps({'type': 'step', 'steps': _steps}, ensure_ascii=False)}\n\n"
                chunks = []
                # 重试队列 + 失败记账（对抗审计 2026-08-07）：合同分支原为固定回退
                # registry.variant(True) + on_model_failure 空实现 + 零扣减——后备模型从不记账
                _ccur = {"key": flag_key}
                _rstart = False  # 重试零重答：清空半截并通知前端（对抗审计 2026-08-07）
                _ctried: set[str] = set()  # F7：已尝试过的模型 key（瞬时故障不标记时靠它推进）

                def _cmake_chain(_i, _disabled):
                    if use_router:
                        if _i == 0 and _ccur["key"]:
                            return make_chain(flag_llm)
                        key, llm, _ = _safe_pick(modality, tier or "flag", exclude=_ctried)
                        _ccur["key"] = key
                        return make_chain(llm)
                    return make_chain(registry.get() if _i == 0 else registry.variant(True))

                def _cfail(_e):
                    nonlocal _rstart
                    if use_router and _ccur["key"]:
                        # F7（2026-09-14）：瞬时故障（429/5xx/连接抖动）**不再标记耗尽** —— 该模型其实
                        # 仍可用（同 1k 修复口径）；改由 _ctried 排除已试过的 key 来推进到下一个模型
                        # （否则 pick 会再选回同一模型 → 死循环）。
                        _ctried.add(_ccur["key"])
                        if not is_transient_error(_e):
                            registry.mark_depleted(_ccur["key"], "model_failure")
                    _rstart = True

                async for piece in stream_with_retry(
                    _cmake_chain,
                    cm,
                    [(False, 0.0), (True, 0.5), (False, 0.5)],
                    on_model_failure=_cfail if use_router else None,
                ):
                    if _rstart:
                        _rstart = False
                        chunks = []
                        _f0 = None
                        yield f"data: {json.dumps({'type': 'restart'}, ensure_ascii=False)}\n\n"
                    if _f0 is None:
                        _f0 = time.perf_counter()
                    chunks.append(piece)
                    yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"
                answer = "".join(chunks)
                if answer:
                    _contract_reviewed_convs.add(pre["conv_id"])  # 完整报告已产出：之后续聊才算追问
                    # 合同分支补配额记账（原零扣减，后备模型用量从不计入）
                    if use_router and _ccur["key"]:
                        est = estimate_tokens(answer) + estimate_tokens(
                            pre.get("context", "") + pre.get("user_text", "")
                        )
                        # 对抗审计 v2 #20：SQLite 扣减同步阻塞事件循环 → 线程池
                        await run_in_threadpool(
                            registry.deduct, _ccur["key"], est * registry.thinking_mult(_ccur["key"])
                        )
                    bad = citation_verify(answer)
                    if cache_key:
                        # 继承回答缓存（code-review #5：重复贴同一合同零重烧）
                        answer_cache.put(cache_key, answer, pre["sources"], model="contract_review")
                    if bad:
                        note = "\n\n> 注：报告引用 " + "、".join(bad) + " 未在知识库中检索到，建议核对。"
                        answer += note
                        yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"
                routing_metrics.record("contract_review", False, "pass", "miss", checked=False)
                log_account(
                    model="contract_review",
                    tier="contract_review",
                    cache="miss",
                    first_ms=round((_f0 or 0.0) * 1000, 1),
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    ok=True,
                    conv_id=pre["conv_id"],
                    user_id=user.id,
                    q_len=len(text),
                )
                yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                # analysis_runs 审计记录（二期）：失败不阻断主流程
                try:
                    await run_in_threadpool(
                        _record_analysis,
                        user.id,
                        pre["conv_id"],
                        "image" if pre.get("image") else "text",
                        cd,
                        int((time.perf_counter() - t0) * 1000),
                    )
                except Exception as e:
                    print(f"[analysis-run] {e}", flush=True)
                try:
                    await run_in_threadpool(_post, pre, answer, False)
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
                return

            # 分支1：轻量缓冲 + 自检 + 至多一次升级旗舰
            if use_light:
                res = await run_in_threadpool(_light_buffered, pre, messages)
                answer = res.answer
                if answer:
                    _f0 = time.perf_counter()  # 轻量缓冲：非流式整答返回，首帧=完成时刻
                    yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'error': '服务暂时无响应，请稍后重试'}, ensure_ascii=False)}\n\n"
                if cache_key and res.verdict == "pass":
                    answer_cache.put(cache_key, answer, pre["sources"])
                if res.key:
                    # 对抗审计 v2 #20：SQLite 扣减同步阻塞事件循环 → 线程池
                    await run_in_threadpool(registry.deduct, res.key, res.usage)
                routing_metrics.record(res.tier, res.escalated, res.verdict, "miss", checked=True)
                log_account(
                    model=registry.model_of(res.key),
                    tier=res.tier,
                    escalated=res.escalated,
                    verdict=res.verdict,
                    cache="miss",
                    token_est=res.usage,
                    first_ms=round((_f0 - t0) * 1000, 1) if answer else None,
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    ok=bool(answer),
                    conv_id=pre["conv_id"],
                    user_id=user.id,
                    q_len=len(text),
                )
                yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                if answer:
                    try:
                        await run_in_threadpool(_post, pre, answer)
                        _posted = True
                    except Exception as e:
                        print(f"[chat-post] {e}", flush=True)
                return

            # 分支2：旗舰 / legacy 流式（空答重试 + 配额耗尽自动换模型 块2.2）
            current = {"key": flag_key}
            _restart_pending = False  # 重试将零重答：清空已发半截，防拼接（对抗审计 2026-08-07）
            _tried: set[str] = set()  # F7：已尝试过的模型 key（瞬时故障不标记时靠它推进）

            def make_chain_fn(_i, disabled):
                # 首次用已 pick 的模型；重试（空答/配额耗尽 mark_depleted 后）重新 pick →
                # 自动落到下一个可用后备模型
                if use_router:
                    if _i == 0 and current["key"]:
                        key = current["key"]
                        llm = registry.variant_of(key, disabled) if disabled else flag_llm
                    else:
                        key, llm, _ = _safe_pick(modality, tier or "flag", exclude=_tried)
                        current["key"] = key
                        if disabled:
                            llm = registry.variant_of(key, disabled)
                    return make_chain(llm)
                llm = registry.get() if _i == 0 else registry.variant(disabled)
                return make_chain(llm)

            def _on_model_failure(_e):
                # 失败后切换模型（明细：配额耗尽/模型名错 → mark_depleted；瞬时故障 → 只排除不标记，
                # F7 2026-09-14：瞬时（429/5xx/连接抖动）标记会把仍可用的模型永久禁用，
                # 同 1k 修复口径；靠 _tried 排除已试过的 key 推进，避免 pick 选回同一模型 → 死循环）
                nonlocal _restart_pending
                if use_router and current["key"]:
                    _tried.add(current["key"])
                    if not is_transient_error(_e):
                        registry.mark_depleted(current["key"], "model_failure")
                _restart_pending = True  # 下一 config 将从零重答：前端需清空半截

            chunks = []
            _f0 = None
            async for piece in stream_with_retry(
                make_chain_fn,
                messages,
                [(False, 0.0), (True, 0.5), (False, 0.5)],
                on_model_failure=_on_model_failure,
            ):
                if _restart_pending:
                    # 上一个模型失败、即将从零重答：先清空已发半截并通知前端（防拼接乱码）
                    _restart_pending = False
                    chunks = []
                    _f0 = None
                    yield f"data: {json.dumps({'type': 'restart'}, ensure_ascii=False)}\n\n"
                if _f0 is None:
                    _f0 = time.perf_counter()  # 真流式：首个 token 时刻（首帧埋点）
                chunks.append(piece)
                yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"
            answer = "".join(chunks)
            if not answer:
                try:
                    fb = await run_in_threadpool(_invoke_llm, messages, flag_llm)
                    answer = clean_answer(fb)
                    if answer:
                        if _f0 is None:
                            _f0 = time.perf_counter()
                        yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"
                except Exception:
                    answer = ""
            else:
                answer = clean_answer(answer)
            # 多选完整性症状（决策 8）：多选题型 + 回答只声明 1 个正确项 → 疑似漏答。
            # 流式已发出，只能追加确定性核对注（不静默）+ 拦缓存（防错答传播）。纯函数零成本。
            multi_bad = bool(answer) and quality.multi_incomplete(pre.get("user_text") or "", answer)
            if answer:
                bad_cites = citation_verify(answer)
                if bad_cites:
                    # B1：中性措辞，不再"建议核对原文"（该句曾是前端 stripUnprovidedHint 要删的噪音）
                    note = "\n\n> 注：回答中引用的 " + "、".join(bad_cites) + " 未收录于本知识库。"
                    answer += note
                    yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"
                    log_account(
                        kind="citation_anomaly",
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        detail=";".join(bad_cites)[:300],
                    )
                if multi_bad:
                    note = "\n\n> ⚠️ 本题可能为多选题，上述回答似乎只给出了一个正确选项，请核对是否遗漏。"
                    answer += note
                    yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"
                    log_account(
                        kind="multi_incomplete",
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        detail=f"len={len(pre.get('user_text') or '')}",
                    )
            if not answer:
                yield f"data: {json.dumps({'error': '服务暂时无响应，请稍后重试'}, ensure_ascii=False)}\n\n"
                # 空答补偿：用户消息已落库，落一条占位 assistant 消息保持成对（对抗审计 2026-08-07）
                try:
                    await run_in_threadpool(_post_placeholder, pre)
                    _posted = True
                except Exception as e:
                    print(f"[chat-placeholder] {e}", flush=True)
            # S3+S6：旗舰流式路径也跑自检 + 写缓存（让缓存/自检对 text 生效，不只轻量分支）。
            # 自检 PASS 才写缓存；FAIL 则旗舰无更强模型可升，追加核对注（S6 兜底扩展到旗舰）。
            verdict_flag = "pass" if answer else "empty"
            if use_router and answer and pre["intent"] != "chitchat":  # 闲聊豁免质检（无检索语境）
                sv = quality.self_check(answer, bool(pre["sources"]))
                if sv.ok:
                    # 写缓存三闸（审查 C2/C3）：非降级（降级答案不入缓存，防缓存用户
                    # 看不到免责注）+ 确定性写闸（study_aid 引用 ⊆ 检索条文）
                    # + 多选漏答不入缓存（决策 8：防错答传播给近重复题）
                    if cache_key and not flag_degraded and _cache_write_ok(pre, answer) and not multi_bad:
                        emb = await run_in_threadpool(_embed_question, pre.get("rewritten") or "")
                        pol, cnt, lab, fp = _cache_guards(pre.get("rewritten") or "")
                        answer_cache.put(
                            cache_key,
                            answer,
                            pre["sources"],
                            embedding=emb,
                            polarity=pol,
                            option_count=cnt,
                            label_system=lab,
                            options_fingerprint=fp,
                            model=registry.model_of(flag_key) if use_router else "",
                        )
                else:
                    verdict_flag = sv.reason
                    # 法考题(study_aid)自检 FAIL 只不写缓存，不加"较复杂"注（解析型回答
                    # 常引格式条文/库外表达，注语义违和且误导；审查 I3）
                    if pre["intent"] != "study_aid":
                        answer += NOTE_COMPLEX
                        yield f"data: {json.dumps({'content': NOTE_COMPLEX}, ensure_ascii=False)}\n\n"
            # S2：回退模型本身已不可用 → 明说降级，不静默烧耗尽模型（闲聊豁免：降级注不适合闲聊语境）
            if use_router and flag_degraded and answer and pre["intent"] != "chitchat":
                verdict_flag = "low_quota"
                answer += NOTE_QUOTA
                yield f"data: {json.dumps({'content': NOTE_QUOTA}, ensure_ascii=False)}\n\n"
            # 流式无真实 usage → 按输出 + 主要输入估算扣减（补输入，避免长期低估）。
            # thinking 模型 reasoning_content 不计入估算 → ×thinking_mult 近似（审查 K1）
            # failover 后按真正回答的模型扣减（current["key"] 由 make_chain_fn 在重试时
            # _safe_pick 更新），而非最初 flag_key——否则后备模型用量从不记账、
            # 看门狗 mark_depleted 的 key 与实际扣减 key 错位（对抗审计 2026-08-07）
            if use_router and current["key"] and answer:
                est = estimate_tokens(answer) + estimate_tokens(pre.get("context", "") + pre.get("user_text", ""))
                # 对抗审计 v2 #20：SQLite 扣减同步阻塞事件循环 → 线程池
                await run_in_threadpool(registry.deduct, current["key"], est * registry.thinking_mult(current["key"]))
            routing_metrics.record(
                (tier or "flag") if use_router else "legacy",
                False,
                verdict_flag,
                "miss",
                checked=bool(use_router and answer),
            )
            log_account(
                model=(
                    registry.model_of(current["key"]) if use_router and current["key"] else registry.config()["model"]
                ),
                tier=(tier or "flag") if use_router else "legacy",
                cache="miss",
                token_est=estimate_tokens(answer) if answer else 0,
                first_ms=round((_f0 - t0) * 1000, 1) if _f0 else None,
                ms=round((time.perf_counter() - t0) * 1000, 1),
                ok=bool(answer),
                conv_id=pre["conv_id"],
                user_id=user.id,
                q_len=len(text),
            )
            yield f"data: {json.dumps({'conversation_id': pre['conv_id'], 'sources': pre['sources']}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            if answer:
                try:
                    await run_in_threadpool(_post, pre, answer)
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
        except LLMBusyError:
            # 并发门控降级：不占日志噪音（每次 surge 都刷不可取），仅下发繁忙提示
            yield f"data: {json.dumps({'error': '服务繁忙，请稍后重试'}, ensure_ascii=False)}\n\n"
            # 补偿：_post 未执行（try 中途抛错）→ 占位 assistant 消息保持成对（对抗审计 2026-08-07）
            try:
                await run_in_threadpool(_post_placeholder, pre)
                _posted = True
            except Exception as e:
                print(f"[chat-placeholder] {e}", flush=True)
        except Exception as e:
            # 详情只进日志：str(e) 可能含内部 model id / 供应商错误体 / 服务器路径，不得下发普通用户
            print(f"[chat-stream] {type(e).__name__}: {e}", flush=True)
            yield f"data: {json.dumps({'error': '服务暂时无响应，请稍后重试'}, ensure_ascii=False)}\n\n"
            # 补偿：_post 未执行 → 占位 assistant 消息保持成对（对抗审计 2026-08-07）
            try:
                await run_in_threadpool(_post_placeholder, pre)
                _posted = True
            except Exception as e:
                print(f"[chat-placeholder] {e}", flush=True)
        finally:
            # 对抗审计 v2 #5/#8：客户端断开（GeneratorExit 不属 Exception）或未走任何落库分支时，
            # 生成器在此被 close → 独立后台任务派占位 assistant，保持 user/assistant 成对与计数平衡。
            # 不 await/yield（GeneratorExit 下不可再产出数据帧）；失败静默，下次会话自然成对。
            if not _posted:
                try:
                    import asyncio

                    asyncio.get_running_loop().run_in_executor(None, _post_placeholder, pre)
                except Exception:
                    pass

    # 反缓冲响应头：SSE 经 Cloudflare Tunnel / Nginx 等代理中转时，若上游未显式声明，
    # 代理会攒批到连接关闭才一次性下发（手机端表现为“一次性输出”）。以下头禁用代理缓冲、
    # 禁止 CDN 改写，确保逐帧流式。
    return StreamingResponse(
        _stream_with_status_preframe(stream()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


# ==================== 会话 CRUD ====================
@app.post("/api/conversations")
def create_conversation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = Conversation(user_id=user.id, title="", summary="", message_count=0)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id}


@app.get("/api/conversations", response_model=list[ConversationListItem])
def my_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(func.coalesce(Conversation.last_active_at, Conversation.created_at).desc())
        .limit(50)
        .all()
    )
    out = []
    for c in convs:
        first_user = (
            db.query(Message)
            .filter(Message.conversation_id == c.id, Message.role == "user")
            .order_by(Message.created_at.asc())
            .first()
        )
        has_image = (
            db.query(Message.id).filter(Message.conversation_id == c.id, Message.image_ref.isnot(None)).first()
            is not None
        )
        preview = (c.question or (first_user.content if first_user else "") or c.title or "新对话")[:60]
        out.append(
            ConversationListItem(
                id=c.id,
                title=c.title or preview,
                preview=preview,
                message_count=c.message_count or 0,
                has_image=has_image,
                last_active_at=c.last_active_at,
                created_at=c.created_at,
            )
        )
    return out


@app.get("/api/conversations/{conv_id}", response_model=ConversationDetail)
def get_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc()).all()
    # T1（2026-09-16）覆盖投影：批量读取本页消息关联的 run（禁止逐消息 N+1）。
    # - Agent assistant 消息（有关联 run）→ run.state_json 的结构化覆盖（full/partial）；
    # - 旧消息 / 无关联（agent_run_id 为 NULL）→ unknown，不得推断 full；
    # - 用户消息 → None（覆盖不适用）。
    coverage_by_run: dict[str, tuple[CoverageProjection, list[dict[str, str]]]] = {}
    run_ids = [m.agent_run_id for m in msgs if m.agent_run_id]
    if run_ids:
        for run in db.query(AgentRun).filter(AgentRun.id.in_(run_ids)).all():
            coverage_by_run[str(run.id)] = coverage_from_state_json(run.state_json)  # str(): 运行时为 str，仅类型收窄
    message_outs = []
    for m in msgs:
        coverage = coverage_by_run.get(str(m.agent_run_id)) if m.agent_run_id else None
        if m.role == "assistant":
            coverage_status, uncovered = coverage if coverage is not None else ("unknown", [])
        else:
            coverage_status, uncovered = None, []
        message_outs.append(
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                image_ref=m.image_ref,
                thumb_ref=m.thumb_ref,
                created_at=m.created_at,
                coverage_status=coverage_status,
                uncovered_issues=uncovered,
            )
        )
    return ConversationDetail(
        id=conv.id,
        title=conv.title or "",
        summary=conv.summary or "",
        messages=message_outs,
    )


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(
    conv_id: int, title: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    conv.title = (title or "")[:200]
    db.commit()
    return {"id": conv.id, "title": conv.title}


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(conv)
    db.commit()
    return {"deleted": conv_id}


# ==================== 管理员：统计 ====================
@app.get("/api/admin/stats")
def admin_stats(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return {
        "user_count": db.query(User).count(),
        "conversation_count": db.query(Conversation).count(),
        "knowledge_count": ks.count_docs(),
        "knowledge_expired": ks.count_docs(status="已废止"),
        "llm_model": registry.config()["model"],
        "qa_pending": db.query(QaCandidate).filter(QaCandidate.status == "pending").count(),
    }


# ==================== 管理员：用户管理 ====================
@app.get("/api/admin/users")
def admin_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@app.post("/api/admin/users")
def admin_create_user(body: RegisterIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """管理员开户（方案C 2026-08-08）：创建普通用户账号，替代公开注册。

    一人一账号由管理员发放账号天然保证（每个真实用户由 admin 创建一个账号）。
    用户名不可占用 admin 保留名（与 register 同款防抢占）。
    """
    if body.username == settings.admin_username:
        raise HTTPException(status_code=400, detail="该用户名不可创建（管理员保留名）")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password), role="user")
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(_admin.id, "user.create", target=user.id, detail=body.username)
    return {"id": user.id, "username": user.username, "role": user.role}


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: int, body: UserUpdateIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    log_audit(_admin.id, "user.toggle", target=user_id, detail=f"is_active={body.is_active}")
    return {"id": user.id, "username": user.username, "is_active": user.is_active}


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """删除账号（硬删）：级联会话/消息；Feedback/AnalysisRun 无级联需显式清理。
    防自删（admin 不能删自己）；audit_logs 保留（审计轨迹不删）。"""
    if user_id == _admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员账号")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    # Feedback / AnalysisRun 有 user_id FK 但无级联（orphan 行）→ 显式清理
    db.query(Feedback).filter(Feedback.user_id == user_id).delete(synchronize_session=False)
    db.query(AnalysisRun).filter(AnalysisRun.user_id == user_id).delete(synchronize_session=False)
    username = user.username
    db.delete(user)  # conversations → messages 级联
    db.commit()
    log_audit(_admin.id, "user.delete", target=user_id, detail=username)
    return {"ok": True, "id": user_id, "username": username}


# ==================== 管理员：对话审查 ====================
@app.get("/api/admin/conversations")
def admin_conversations(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    # 分页钳制（对抗审计 2026-08-07）：limit 负数被 SQLite 当作"不限"全表导出，offset 负数触发 500
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    rows = (
        db.query(Conversation, User.username)
        .join(User, Conversation.user_id == User.id)
        .order_by(Conversation.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": c.id,
            "username": uname,
            "question": c.question,
            "answer": c.answer,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c, uname in rows
    ]


# ==================== 管理员：知识库 ====================
@app.get("/api/admin/knowledge")
def admin_knowledge(limit: int = 50, offset: int = 0, source: str = None, _admin: User = Depends(require_admin)):
    return ks.list_docs(limit=limit, offset=offset, source=source)


@app.post("/api/admin/knowledge")
def admin_add_knowledge(body: KnowledgeAddIn, admin: User = Depends(require_admin)):
    extra = {
        "effective_from": body.effective_from,
        "effective_to": body.effective_to,
        "status": body.status or "现行",
        "version_id": body.version_id,
        "promulgated_at": body.promulgated_at,
        "source_url": body.source_url,
        "source_document_sha256": body.source_document_sha256,
        "supersedes_version_id": body.supersedes_version_id,
        "reviewed_at": body.reviewed_at,
    }
    n = ks.add_text(body.content, source=body.title, article=body.article, origin="manual", extra_meta=extra)
    log_audit(admin.id, "knowledge.add", target=f"{body.title} {body.article}".strip(), detail=f"chunks={n}")
    return {"added_chunks": n}


@app.delete("/api/admin/knowledge/{doc_id}")
def admin_delete_knowledge(doc_id: str, _admin: User = Depends(require_admin)):
    ks.delete_doc(doc_id)
    log_audit(_admin.id, "knowledge.delete", target=doc_id)
    return {"deleted": doc_id}


@app.post("/api/admin/knowledge/upload")
@limiter.limit("10/minute")
async def admin_upload(request: Request, file: UploadFile = File(...), admin: User = Depends(require_admin)):
    raw = await _read_capped(file, settings.upload_max_mb * 1024 * 1024, f"文件过大（>{settings.upload_max_mb}MB）")
    try:
        _ext, text = ks.parse_upload_or_raise(file.filename, raw)  # 与 chat_file 共用（code-review Standards）
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve

    def _do():
        fh = ks.file_hash(raw)
        source = os.path.splitext(file.filename)[0]
        # 版本递增（阶段6）：同 hash 重传时 version+1，审计语义正确
        try:
            prev = vectorstore._collection.get(where={"file_hash": fh}, include=["metadatas"])["metadatas"]
            version = max((int(m.get("version") or 0) for m in prev), default=0) + 1
        except Exception:
            version = 1
        extra = {
            "filename": file.filename,
            "uploaded_by": admin.username,
            "uploaded_at": datetime.utcnow().isoformat(),
            "version": version,
            "status": "现行",
        }
        n = ks.add_text(text, source=source, origin="upload", extra_meta=extra, file_hash_value=fh)
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), source)
        preview = retrieve_for_test(first_line[:200], k=3)
        return {"filename": file.filename, "added_chunks": n, "preview": preview}

    res = await run_in_threadpool(_do)
    log_audit(admin.id, "knowledge.upload", target=res["filename"], detail=f"chunks={res['added_chunks']}")
    return res


@app.post("/api/admin/knowledge/preview-chunk")
@limiter.limit("20/minute")
async def admin_preview_chunk(request: Request, body: PreviewChunkIn, _admin: User = Depends(require_admin)):
    """切分预览（阶段6）：结构化切分不写库，供管理员核对条号边界。纯函数零耗时。"""
    chunks = chunking.split_law_document(body.text)
    structured = any(c.meta.get("article") for c in chunks)
    return {
        "mode": "structured" if structured else "fallback",
        "count": len(chunks),
        "chunks": [
            {
                "article": c.meta.get("article", ""),
                "chapter": c.meta.get("chapter", ""),
                "chars": len(c.page_content),
                "content": c.page_content[:200],
            }
            for c in chunks
        ],
    }


@app.post("/api/admin/knowledge/test")
@limiter.limit("30/minute")
async def admin_knowledge_test(request: Request, body: KnowledgeTestIn, _admin: User = Depends(require_admin)):
    return await run_in_threadpool(retrieve_for_test, body.query, 5)


# ==================== 管理员：受控沉淀 ====================
@app.get("/api/admin/qa/candidates")
def admin_qa_candidates(status: str = None, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return ks.list_candidates(db, status=status)


@app.post("/api/admin/qa/{cand_id}/decision")
def admin_qa_decision(
    cand_id: int, body: QaDecisionIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
):
    r = ks.decide_candidate(db, cand_id, body.decision)
    if not r:
        raise HTTPException(status_code=404, detail="候选不存在")
    log_audit(_admin.id, f"qa.{body.decision}", target=cand_id)
    return {"id": r.id, "status": r.status}


# ==================== 管理员：模型在线切换 ====================
@app.post("/api/admin/llm")
@limiter.limit("10/minute")
async def admin_llm_switch(request: Request, body: LlmSwitchIn, _admin: User = Depends(require_admin)):
    if not body.model:
        raise HTTPException(status_code=400, detail="请提供 model")
    cfg = registry.reload(model=body.model)
    log_audit(_admin.id, "llm.switch", target=body.model)
    return cfg


@app.post("/api/admin/llm-promote")
@limiter.limit("10/minute")
def admin_llm_promote(request: Request, body: LlmPromoteIn, _admin: User = Depends(require_admin)):
    """把某模型提为所在 (modality, tier) 自动路由链首（运行时生效，重启回落 .env）。"""
    try:
        new_priority = registry.promote(body.key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log_audit(_admin.id, "llm.promote", target=body.key)
    return {"key": body.key, "priority": new_priority}


@app.post("/api/admin/llm-disable")
@limiter.limit("10/minute")
def admin_llm_disable(request: Request, body: LlmDisableIn, _admin: User = Depends(require_admin)):
    """禁用/启用某模型参与自动路由（运行时生效，重启回落 .env；不影响显式指定场景）。"""
    try:
        registry.set_disabled(body.key, body.disabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log_audit(_admin.id, "llm.disable" if body.disabled else "llm.enable", target=body.key)
    return {"key": body.key, "admin_disabled": body.disabled}


@app.get("/api/admin/llm-status")
def admin_llm_status(_admin: User = Depends(require_admin)):
    """模型配额 + 路由运行态指标（仅管理员；普通用户接口不返回模型信息）。

    前端只展示当前活跃模型与切换原因，不渲染估算配额数字（用户决策：估算时效性太低）。
    """
    return {
        "feature_router": settings.feature_router,
        "models": registry.status(),
        "utility_quota": registry.utility_quota_status(),  # embedding/rerank 配额（ADR-011 阶段E）
        "metrics": routing_metrics.snapshot(),
    }


@app.post("/api/admin/llm-quota")
@limiter.limit("10/minute")
async def admin_llm_quota(request: Request, body: LlmQuotaIn, _admin: User = Depends(require_admin)):
    """配额校准（块 3）：按控制台真实剩余值回写该模型已用量，看门狗对齐真实值。

    用户决策：后台不展示估算配额数字（时效性太低，控制台为准），但"用完即切"的看门狗
    依赖 remaining——本端点让管理员从控制台读实际值后校准。
    - LLM key（text_* / vision_*）→ registry.calibrate（改 initial_used）
    - 工具模型名（rerank 队列 / embedding 模型名）→ quota_store.set_used
      （runtime_used = total - remaining - initial，共享 initial 下按模型记）
    """
    import quota_utils as qu

    # 工具模型：rerank 队列或当前 embedding 模型
    if body.key in qu.rerank_model_list() or body.key == qu.embedding_model_key():
        total = qu.utility_quota_total_for(body.key)
        initial = qu._quota_initial(body.key)
        used_target = max(0, total - body.remaining - initial)
        quota_store.set_used(body.key, used_target)
        log_audit(_admin.id, "quota.calibrate", target=body.key, detail=f"remaining={body.remaining}")
        return {"key": body.key, "quota_left": qu.utility_pct_left(body.key) * total, "used": used_target}
    try:
        res = registry.calibrate(body.key, body.remaining)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"未知模型 key: {body.key}") from None
    log_audit(_admin.id, "llm.quota_calibrate", target=body.key, detail=f"remaining={body.remaining}")
    return res


# ==================== 管理员：操作审计 ====================
@app.get("/api/admin/audit")
def admin_audit(limit: int = 100, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = (
        db.query(AuditLog, User.username)
        .outerjoin(User, AuditLog.admin_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return [
        {
            "id": a.id,
            "admin": uname or "-",
            "action": a.action,
            "target": a.target,
            "detail": a.detail,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a, uname in rows
    ]


# ==================== 用户反馈（点赞/踩/纠错） ====================
@app.post("/api/feedback")
@limiter.limit("20/minute")
def post_feedback(
    request: Request, body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    # 归属校验：conversation_id 必须属于当前用户（防伪造他人会话反馈、灌爆待审队列，对抗审计 2026-08-07）
    if body.conversation_id is not None:
        conv = db.get(Conversation, body.conversation_id)
        if conv is None or conv.user_id != user.id:
            raise HTTPException(status_code=404, detail="会话不存在")
    fb = Feedback(
        user_id=user.id,
        conversation_id=body.conversation_id,
        question=body.question,
        answer=body.answer,
        rating=body.rating,
        correction=body.correction or "",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    # 负反馈或带纠错 → 进受控沉淀待审，供管理员采纳"修正后的答案"（点赞不自动入库，避免污染）
    if body.rating == "down" or (body.correction and body.correction.strip()):
        # 去重：同一问题同一来源（feedback:down/up）已有待审候选则不再入队，防刷队列
        dup = (
            db.query(QaCandidate)
            .filter(
                QaCandidate.question == body.question,
                QaCandidate.status == "pending",
                QaCandidate.evidence == f"feedback:{body.rating}",
            )
            .first()
        )
        if dup is None:
            propose = (body.correction or "").strip() or body.answer
            ks.create_candidate(db, body.question, propose, 0.0, f"feedback:{body.rating}")
    return {"id": fb.id}


@app.get("/api/admin/feedback")
def admin_feedback(limit: int = 100, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": f.id,
            "user_id": f.user_id,
            "conversation_id": f.conversation_id,
            "question": f.question,
            "answer": f.answer,
            "rating": f.rating,
            "correction": f.correction,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
    ]
