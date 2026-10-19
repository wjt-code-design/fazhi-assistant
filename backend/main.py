import asyncio
import base64
import json
import logging
import os
import socket
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, replace
from datetime import date, datetime
from threading import Event
from typing import Any
from urllib.parse import urlparse
from weakref import WeakValueDictionary

from dotenv import load_dotenv

# 必须在导入会读取环境变量的本地模块之前加载 .env
load_dotenv()

from anyio import CancelScope
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import func, text
from sqlalchemy.engine import Row
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
from agent import limitation_calc  # S5：快车道只**消费**版本判定真源，不在本文件重写规则
from agent.chat_integration import (
    CoverageProjection,
    coverage_from_state_json,
    encode_sse_stream,
    serialize_agent_events,
)
from agent.controller import (
    _DEFAULT_RUN_LOCKS,
    RESUME_LAW_AS_OF_DETAIL,
    RESUME_NOT_FOUND_DETAIL,
    ResumeLawAsOfConflict,
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
    canon_source,
    cheating_docs,
    consumer_clause_docs,
    consumer_fraud_docs,
    contract_trigger_reason,
    is_consumer_clause_scenario,
    is_consumer_fraud_scenario,
    is_contract_review,
)
from intent import classify_intent
from llm_errors import is_request_shape_rejection, is_transient_error, status_of
from llm_guard import LLMBusyError, llm_guard
from llm_registry import QuotaExhausted, estimate_tokens, registry
from memory import compress, load_model_context_bootstrap, needs_compress, recent_messages, rewrite_query
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
    CONTRACT_INTENT_CONFIRM_PROMPT,
    IMAGE_GUIDANCE,
    OUTPUT_FORMAT_RULE,
    SYSTEM_BASE,
    SYSTEM_CHEATING,
    SYSTEM_CONTRACT_FOLLOWUP,
    SYSTEM_CONTRACT_REVIEW,
    SYSTEM_STUDY,
)
from qa_eligibility import capture_dependency, evaluate_revocation_state, log_read_denial, validate_dependencies
from quota_utils import UtilityQuotaExhausted
from rag_chain import ClosingStream, clean_answer, embeddings, format_docs, make_chain, stream_with_retry, vectorstore
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
    _source_key,
    citation_grounding,
    citation_verify,
    exact_article_lookup,
    extract_citations,
    grounded_top_score,
    prewarm,
    qa_citations_in_kb,
    retrieve,
    retrieve_exam,
    retrieve_for_test,
    scenario_supplement_docs,
    source_in_kb,
)
from retrieval_core import qa_provenance_verifiable, time_validity_state
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
    try:
        # 预热：BM25 索引 + 源名集合（重启后首问冷启动 3s+ → 0），不阻塞事件循环。
        # 失败仅降级（首问走惰性构建），不让应用拒绝启动（code-review：chroma 损坏时原惰性路径可恢复）
        try:
            await run_in_threadpool(prewarm)
        except Exception as e:
            logging.warning("[prewarm] 预热失败，降级惰性构建（重启后首问稍慢）：%s", e)
        yield
    finally:
        # 应用级收尾：事件循环仍在运行时由 registry 关闭其拥有的 SDK 连接池（幂等）；
        # 业务异常先完成收尾再原样上抛，不吞异常。
        await registry.aclose()


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
    """能力发现（阶段B 诚实停用）：前端据此隐藏未验证能力的入口，而非展示必然失败的按钮。

    R2-F3（复核第二轮）：一台**一条可用模型都没有**的机器过去也回 `status="ok"`——`_load` 会开心地把
    `_entries` 留成空 dict，只逐条落 warning，聚合面上读不出任何异常。探针/运维据此继续放量，
    而服务实际上一问就 503。现在把两个计数带出来，0 条就报 `degraded`。
    刻意**不**改成「0 entry 就 raise」：那正是 W7-B1 刚修掉的「坏配置打死启动」坏形状，
    两格方向相反（判据：tests/test_llm_registry_boot_impl.py::test_r2_zero_usable_entries_does_not_raise_at_construction）。
    HTTP 状态仍 200：这条是**状态读数**不是就绪门（就绪门在 `/healthz`），改成 5xx 会让
    `manage.py` 与 OPS 的 `curl -sf` 探活把「降级」读成「进程没起来」。
    """
    entry_count = registry.entry_count()
    return {
        "status": "ok" if entry_count else "degraded",
        "llm_entry_count": entry_count,
        "llm_entry_rejected": registry.skipped_count(),
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


def _law_version_scope_note(pre: dict) -> str:
    """显式历史基准日的模型可见标注（空串 = 未指定，不标注）。

    全仓一份措辞：普通问答与合同两条 messages 组装路径共用。各抄一份会漂移，
    而模型看到「哪一版法」的提示必须两处同义（同 NOTE_MULTI_INCOMPLETE 的复用理由）。
    """
    as_of = pre.get("law_as_of")
    return f"（法律版本基准日：{as_of.isoformat()}）" if as_of else ""


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
    hit = pre["qa_hit"]
    # W06-IMPL：注入出口自带状态判据（评测探针会直接构造 pre 绕过产生处）——撤回/隔离/未知来源/读不到状态
    # 都不给它递进模型上下文。来源可校验与引用在库两条判定仍在产生处做一次，此处只咨询状态轴、不重复扫库。
    if hit and evaluate_revocation_state(hit).allow:
        qa_note = f"此前已确认的问答（可优先参考）：\n问：{hit['question']}\n答：{hit['answer']}\n\n"
    date_scope = _law_version_scope_note(pre)
    context_block = (
        f"本题相关法律条文{date_scope}（以下均为本题判断依据，含场景补充条文，可全部直接引用）：\n"
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


# 票 W07（C04＝甲）：识图失败对外的说法。甲的用户可见腿**只覆盖这一支**（调用抛异常 ⇒ 本轮不作答）；
# 「模型正常返回但内容为空」那一支仍继续作答、对用户没有声明，本轮按票 §3 V-B3 的第二选项落成
# 可观测降级计数（见 `_note_empty_image_description`）。
# `/api/chat` **这条路由上** 502 只有这一个出处（另一处 502 住在 `/api/chat/transcribe` 那条语音路由上，
# 不同语义）——所以前端除了「本轮带图」还要认那只结构化信号（响应头，或逐字相符的 detail），
# 免得反代合成的裸 502 被标成「图片识别失败」（票 W7-FIX B5）。
# ——判据见 tests/test_image_failure_impl.py::test_502_on_the_chat_route_has_exactly_one_source
IMAGE_DESCRIBE_FAILED_DETAIL = "图片识别失败，本轮未作答；请稍后重试，或改用文字描述案情。"
IMAGE_FAILURE_HEADER = "X-Image-Failure"
IMAGE_FAILURE_HEADER_VALUE = "describe"


def _note_empty_image_description(bootstrap: RequestBootstrap) -> None:
    """W7-B3：把 `RequestBootstrap.image_failure` 从**只写字段**变成有读者的降级读数。

    改前全树（除测试）只有 `request_bootstrap` 自己写它，没有任何读者 ⇒ 「失败可见」这句话
    在「空内容」那一腿上并不成立。这一腿的出口形状（继续拿原图作答、描述为空）不该被伪造成
    用户可见的注记帧（新增一帧要动 gate-exit 登记表，不在本票面内），所以落**管理台可读的降级计数**：
    `kind`/`degraded` 是既有登记字段，`image_desc_empty_degraded` 本轮登记（未登记会被 formatter 丢掉）。
    读数只在「本轮确实带图且确实拿到空描述」时出现，正常轮与 502 轮都不出现（判据见
    tests/test_image_failure_impl.py::test_empty_content_leg_has_a_reader_and_counts_as_degraded）。
    """
    if bootstrap.image_failure != "content_empty":
        return
    log_account(
        kind="image_desc_empty_degraded",
        degraded=True,
        image_desc_empty_degraded=True,
        conv_id=bootstrap.conv_id,
    )


def _describe_image_for_bootstrap(image: str, text: str) -> str:
    """Resolve the image capability here so bootstrap never selects a provider.

    阶段B（2026-09-05）：必须按模态取视觉模型。旧写法 registry.get() 会拿默认文本模型
    （LongCat 实测静默忽略图片）——能力缺失已由 chat() 的 501 门拦截，此处再遇
    QuotaExhausted 说明能力存在但配额耗尽，显式 503 而非静默降级为"无图回答"。

    票 W07（C04＝甲）：`describe_image` 不再吞异常之后，**调用失败**在这一层变成明确 HTTP 502
    （本轮不产出"看起来读了图"的答案）；而**模型返回空内容**不是失败——它原样回空串，
    由 request_bootstrap 落 `image_content_empty` 并在契约上留失败位（读数只在 bootstrap 那一处落）。
    两个出口的归因键分开；本层只把**失败**那一支变成用户看得见的状态码＋结构化信号头。
    """
    try:
        _, vision_llm = registry.pick("vision", "flag")
    except QuotaExhausted as qe:
        raise HTTPException(status_code=503, detail="视觉模型配额不足，请稍后重试") from qe
    with llm_guard:
        try:
            return describe_image(vision_llm, image, text)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=IMAGE_DESCRIBE_FAILED_DETAIL,
                headers={IMAGE_FAILURE_HEADER: IMAGE_FAILURE_HEADER_VALUE},
            ) from exc


configure_default_image_describer(_describe_image_for_bootstrap)


def _contract_intent_confirm_frames():
    """E19（口径③⑥，2026-10-13）：与案情叙述同形的输入先确认审查意图，零 LLM。

    独立成生成器只为让"锚点"与"直接吐 json.dumps({'content': …}) 的那行 yield"落在同一行且不超行宽
    —— exit 扫描器是 AST 级的，要求锚点与内容表达式同行（见 gate_exit_registry 的 scan_content_yields）。
    """
    yield f"data: {json.dumps({'content': CONTRACT_INTENT_CONFIRM_PROMPT}, ensure_ascii=False)}\n\n"  # gate-exit: E19


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
    scope_note = _law_version_scope_note(pre)

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
        # 2026-09-17 合同链补审：两规则自述「所有意图统一」（prompts.py / domain_rules.py:318），
        # 主链组装处（main.py Fast Path）均拼，唯合同链漏拼——补齐对齐既定意图，非新设计。
        sys_text += OUTPUT_FORMAT_RULE
        sys_text += CITATION_SELECTION_RULE
        user_content = (
            f"【合同（分条款）】{scope_note}\n{evidence_block}\n\n"
            f"用户追问：{pre.get('user_text') or ''}\n\n"
            "请直接针对上面的追问回答，不要重新输出完整风险评估报告。"
        )
        return [SystemMessage(content=sys_text)] + history + [HumanMessage(content=user_content)]

    # 首轮：完整评估报告
    sys_text = SYSTEM_BASE + SYSTEM_CONTRACT_REVIEW
    sys_text += OUTPUT_FORMAT_RULE
    sys_text += CITATION_SELECTION_RULE
    sys_text += f"\n（本份合同总体风险等级：{cd['level']}——判定依据：{cd['basis']}）"
    if cd.get("truncated"):
        sys_text += "\n（合同过长已截取前段，末尾请列出'未覆盖条款段'清单，建议用户分段审查）"
    user_content = f"【合同（分条款）】{scope_note}\n{evidence_block}\n\n请按模板输出合同风险评估报告。"
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
    law_as_of: date | None = None,
):
    """Persist one accepted user request without starting either answer path."""
    bootstrap = bootstrap_request(
        user_id,
        conversation_id,
        text,
        image,
        client_truncated,
        case_domain=case_domain,
        law_as_of=law_as_of,
        _deps=BootstrapDependencies(
            session_factory=SessionLocal,
            # W06-C §5.2：生产快车道的历史序列化消费**同一安全投影**（已知失效/未知来源不进模型输入；
            # 原文/UI 仍走 `memory.load_context`）。改前这里绑的是旧的原文接口 ⇒ 投影没真正接线。
            load_context=load_model_context_bootstrap,
            validate_image=validate_image,
            persist_image=persist_image,
            cleanup_persisted_image=cleanup_persisted_images,
            describe_image=_describe_image_for_bootstrap,
            classify_intent=classify_intent,
            is_exam_question=query_understand._is_exam_question,
            has_exam_options=query_understand.has_exam_options,
            is_contract_review=is_contract_review,
            contract_trigger_reason=contract_trigger_reason,
            feature_multi_analyze=settings.feature_multi_analyze,
            contract_conversations=_contract_convs,
            contract_reviewed_conversations=_contract_reviewed_convs,
            is_contract_exit=is_contract_exit,
        ),
    )
    if bootstrap.law_as_of is not None:
        log_account(
            kind="historical_law_query",
            user_id=user_id,
            conv_id=bootstrap.conv_id,
            law_as_of=bootstrap.law_as_of.isoformat(),
        )
    _note_empty_image_description(bootstrap)
    return bootstrap


def _prepare_fast_path_only(bootstrap: RequestBootstrap, turn: dict | None = None):
    """Run legacy retrieval from an already committed bootstrap exactly once."""
    try:
        prepared = prepare_fast_path(
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
                # 票 C21-A：生产快车道同样走**有界资格选择**适配器（原先这里绑 raw `ks.search_qa`，
                # 会让新适配器在生产路径上成为死代码）。raw `search_qa` 的 k=1 语义本身未改，仅换接线点。
                search_qa=ks.search_eligible_qa,
                is_consumer_clause_scenario=is_consumer_clause_scenario,
                consumer_clause_docs=consumer_clause_docs,
                is_consumer_fraud_scenario=is_consumer_fraud_scenario,
                consumer_fraud_docs=consumer_fraud_docs,
                format_docs=format_docs,
            ),
        )
        if turn is not None:
            prepared.update(turn)
        return prepared
    except Exception:
        # bootstrap 已提交 user，而响应尚未构造；先完成该轮再把原异常交给入口。
        _post_placeholder(turn if turn is not None else {"conv_id": bootstrap.conv_id})
        raise


def _pre(
    user_id: int,
    conversation_id,
    text: str,
    image,
    client_truncated: bool = False,
    law_as_of: date | None = None,
):
    """Compatibility coordinator for committed bootstrap plus legacy fast retrieval."""
    bootstrap = _bootstrap_only(user_id, conversation_id, text, image, client_truncated, law_as_of=law_as_of)
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


def fallback_to_fast_path(bootstrap: RequestBootstrap, reason_code: str, turn: dict | None = None) -> dict:
    """Prepare Fast Path only for one allowlisted technical Agent failure."""
    if not routing_metrics.is_technical_fallback_reason(reason_code):
        raise ValueError("Agent failure is not eligible for Fast Path fallback")
    prepared = _prepare_fast_path_only(bootstrap) if turn is None else _prepare_fast_path_only(bootstrap, turn)
    prepared["agent_fallback_reason"] = reason_code
    return prepared


def _resume_law_as_of(run_law_as_of: date) -> date | None:
    """恢复分支的基准日取舍：基准日随 run 建立即固定，本次请求带来的不同日期在 CAS 前就被拒。

    run 落**当日** ⇒ 返回 None（按"未指定历史"处理）。这是个**有损代理**：`AgentRun.law_as_of`
    非空（`create_run` 一律 `or date.today()`），分不清"用户选了今天"和"用户没选"。唯一偏差：
    首请求显式传今天会退出直返/共享缓存/沉淀，而恢复分支技术性降级回来时不会。取这个代理是为
    不动生产默认路径（否则每个"走 Agent 再技术性降级"的请求都白丢一次缓存命中）。要彻底消偏差
    得给 run 加"日期是否被显式选择"的标记 —— 那是 schema 改动，不在本轮授权内。
    """
    return None if run_law_as_of == date.today() else run_law_as_of


def _resume_bootstrap(
    *,
    conversation_id: int,
    answer: str,
    state: LegalAgentState,
    law_as_of: date | None,
) -> RequestBootstrap:
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
        # 基准日同理沿用 run（首次请求时已落库）：技术性失败降级到快车道时不得改用现行法。
        law_as_of=law_as_of,
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


async def _join_owned_task(task: asyncio.Task):
    """Finish owned work despite repeated task cancellation; retain its result."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
        except Exception:
            break
    return task.result()


async def _execute_agent_observing_disconnect(
    request: Request,
    *,
    resume: dict | None = None,
    initial: dict | None = None,
    fast_path_pre: dict | None = None,
    **kwargs,
):
    """Own acceptance, execution and Fast Path handoff as one preparation task.

    Rejected resume has no compensation. Once accepted, worker and Session must
    outlive cancellation; clarification remains fact-only. A normal Fast Path
    handoff carries the same storage guard to response cleanup.
    """
    disconnected = Event()
    finished = asyncio.Event()
    pre: dict = {}

    def snapshot_turn() -> dict:
        with SessionLocal() as db:
            conv_id = resume["conversation_id"] if resume is not None else kwargs["bootstrap"].conv_id
            conv = db.get(Conversation, conv_id)
            if conv is None or conv.user_id != kwargs["user_id"]:
                raise RuntimeError("Agent turn conversation ownership changed")
            boundary = db.query(func.max(Message.id)).filter(Message.conversation_id == conv_id).scalar() or 0
            return {"conv_id": conv_id, "agent_user_id": kwargs["user_id"], "agent_turn_after": boundary}

    async def compensate(pre: dict) -> None:
        try:
            await run_in_threadpool(_post_placeholder, pre, "stopped" if disconnected.is_set() else "no_response")
        except Exception as exc:
            # Do not report a safe close when the only result write failed.
            print(f"[agent-turn-compensate] failed: {type(exc).__name__}", flush=True)
            logging.getLogger("legal.agent").error(
                "agent_turn_compensation_failed: %s",
                type(exc).__name__,
                extra={"conv_id": pre.get("conv_id"), "user_id": kwargs["user_id"]},
            )
            raise

    async def run_and_record():
        # Acceptance is inside the owned task: cancellation must not abandon a
        # CAS/bootstrap thread after commit but before its return is delivered.
        resumed = None
        if resume is not None:
            resumed = await run_in_threadpool(resume_with_user_fact, db=kwargs["db"], **resume)
        elif initial is not None:
            kwargs["bootstrap"] = await run_in_threadpool(
                _bootstrap_only,
                kwargs["user_id"],
                initial["conversation_id"],
                initial["text"],
                initial["image"],
                initial["truncated"],
                initial["case_domain"],
                initial["law_as_of"],
            )
        pre.update(await run_in_threadpool(snapshot_turn))
        try:
            if resumed is not None:
                kwargs["bootstrap"] = _resume_bootstrap(
                    conversation_id=resume["conversation_id"],
                    answer=resume["answer"],
                    state=resumed.state,
                    law_as_of=_resume_law_as_of(resumed.law_as_of),
                )
                kwargs["run_id"] = resumed.run_id
            if initial is not None:
                bootstrap = kwargs["bootstrap"]
                correlation_id = make_agent_correlation_id(conversation_id=bootstrap.conv_id)
                try:
                    gate = decide_gate(bootstrap)
                except Exception:
                    _observe_agent_gate(correlation_id, "fast_path", [GATE_TECHNICAL_FAILURE], technical_failure=True)
                    selected = False
                else:
                    _observe_agent_gate(correlation_id, gate.mode, list(gate.reason_codes), technical_failure=False)
                    selected = (initial["force_agent"] and gate.mode != "refuse") or routing_metrics.should_route_agent(
                        gate, settings, _stable_agent_request_seed(kwargs["user_id"], bootstrap.conv_id)
                    )
                if not selected:
                    if disconnected.is_set():
                        await compensate(pre)
                        raise asyncio.CancelledError
                    prepared = await run_in_threadpool(_prepare_fast_path_only, bootstrap, pre)
                    pre.update(prepared)
                    if disconnected.is_set():
                        await compensate(pre)
                        raise asyncio.CancelledError
                    assert fast_path_pre is not None
                    fast_path_pre.update(pre)
                    _record_actual_agent_route("fast_path")
                    return None
            result = await run_in_threadpool(execute_agent_request, cancelled=disconnected.is_set, **kwargs)
            _record_actual_agent_route("agent_path")
            if result.outcome == "fallback":
                await run_in_threadpool(kwargs["db"].rollback)
                if disconnected.is_set():
                    await compensate(pre)
                    raise asyncio.CancelledError
                if fast_path_pre is not None:
                    prepared = await run_in_threadpool(
                        fallback_to_fast_path, kwargs["bootstrap"], result.reason_code, pre
                    )
                    pre.update(prepared)
                    if disconnected.is_set():
                        await compensate(pre)
                        raise asyncio.CancelledError
                    fast_path_pre.update(pre)
                    _record_actual_agent_route("fast_path", fallback_reason=result.reason_code)
        except Exception:
            # Release failed/unfinished SQL before a fresh session writes the result.
            await run_in_threadpool(kwargs["db"].rollback)
            await compensate(pre)
            raise
        if result.outcome == "failed":
            await run_in_threadpool(kwargs["db"].rollback)
            await compensate(pre)
        return result

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
    worker = asyncio.create_task(run_and_record())
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        disconnected.set()
        # A sync worker cannot be cancelled safely. Join it before the caller
        # closes its Session or releases the conversation lock. Shield AnyIO
        # level cancellation and tolerate repeated asyncio task.cancel().
        with CancelScope(shield=True):
            try:
                result = await _join_owned_task(worker)
                # Cancellation may win exactly as the worker returns fallback;
                # then the caller never transfers storage to the Fast Path.
                if pre and (result is None or result.outcome == "fallback"):
                    await _join_owned_task(asyncio.create_task(compensate(pre)))
            except Exception as exc:
                print(f"[agent-turn-cancel-cleanup] failed: {type(exc).__name__}", flush=True)
        raise
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


def _post(pre: dict, answer: str, curate: bool = True, *, qa_dependencies=...):
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
        conv = db.get(Conversation, pre["conv_id"])
        # W06-C §5.1：为这条回答签发**真实来源包**（历史/摘要投影来源 ∪ 本次 QA 依赖）；任一未知祖先
        # ⇒ None（列 NULL＝旧来源未知）。模块名在函数内 import：`_post` 会被 AST 接缝提取执行，
        # 顶层依赖不得依赖模块全局名是否在场。与消息**同事务**落盘，正文/来源不落半截。
        import qa_eligibility as _qe
        from memory import load_model_context as _load_model_context

        _hit = pre.get("qa_hit")
        if qa_dependencies is ...:
            # 未显式给出 ⇒ 从 pre 现算（既有出口：QA 直返/合同/澄清等本次确实用了 pre.qa_hit 的分支）。
            if _hit is not None:
                _dep = _qe.capture_dependency(_hit)
                _own = (_dep,) if _dep is not None else None
            else:
                _own = ()
        else:
            # L8：调用方给的是**这次生成实际使用的输入依赖**（O 失效重建后的 `ldeps`、缓存回放的原依赖）——
            # 直接采信，**不再从未清理的 pre 现算**；否则会把本次并未使用、甚至已撤回的 QA 误签进来源包。
            _own = qa_dependencies
        _ctx = _load_model_context(db, conv)
        _prov_text = None
        if _own is not None and not _ctx.unknown_history:
            _ancestors = [m.provenance for m in _ctx.recent if m.reusable and m.provenance is not None]
            if _ctx.summary_usable and _ctx.summary_provenance is not None and (_ctx.summary or ""):
                _ancestors.append(_ctx.summary_provenance)
            _prov = _qe.build_provenance(_own, ancestors=tuple(_ancestors))
            _prov_text = _qe.serialize_provenance(_prov) if _prov is not None else None
        db.add(
            Message(
                conversation_id=pre["conv_id"],
                role="assistant",
                content=answer,
                qa_provenance=_prov_text,
            )
        )
        # 对抗审计 v2 #21：原子自增（与 _pre 同款防读-改-写竞态）
        db.execute(
            text("UPDATE conversations SET message_count = COALESCE(message_count, 0) + 1 WHERE id = :id"),
            {"id": pre["conv_id"]},
        )
        conv.last_active_at = datetime.utcnow()
        if not conv.answer:
            conv.answer = (answer or "")[:2000]
        db.commit()
        pre["assistant_committed"] = True

        # 受控沉淀：高有据 + 含引用 + 非空答 → 入待审
        # 沉淀闸（决策 7）：只收真实法律咨询——study_aid 法考题错答（多选漏答）可被采纳污染
        # qa_pairs；cheating 问答本就不该沉淀；chitchat/meta 无引用本就不沉淀。
        # 历史基准日的答案同样不收：它引的是该日有效、当日可能已废止的版本，而一条 qa_pairs 记录只带
        # 一个 `law_as_of_basis`（= 答案**产出那天**的当日口径，见 `knowledge_service.add_qa_pair`），
        # 没有版本轴 ⇒ 收下它就等于把旧版答案标成"今日之法"，现行查询会直返它。
        if curate and pre.get("intent") == "legal_query" and not pre.get("law_as_of"):
            grounded = grounded_top_score(pre["rewritten"])
            q = pre["user_text"] or pre["rewritten"]
            if q and should_curate(grounded, answer):
                # W06-C §5.1/§5.3：派生 QA 继承这条回答的真实来源包（防新 candidate id 洗白撤回）。
                # 调用形状保持既有 5 参（既有接缝替身按此签名打桩）；来源包在其**返回的候选行**上补写。
                _cand = ks.create_candidate(db, q, answer, grounded, json.dumps(pre["sources"], ensure_ascii=False))
                if _cand is not None and _prov_text is not None and getattr(_cand, "qa_provenance", None) is None:
                    # L11：派生签发处做**循环/自引用**拒绝（超限已在 build_provenance 归 None）；
                    # 自引用（来源包指向候选自身）时不写来源包，防借新 id 洗白撤回。
                    _prov_obj = _qe.parse_provenance(_prov_text)
                    if not _qe.has_self_reference(_prov_obj, _cand.id):
                        _cand.qa_provenance = _prov_text
                        db.commit()

        # 增量压缩（对抗审计 v2 #9：LLM 调用纳入 llm_guard 并发位——突发长答复时不再无界并发，
        # 且不再独占共享线程池/悬挂 SSE 连接最长 120s）
        recent = recent_messages(db, conv.id)
        if needs_compress(conv, recent):
            with llm_guard:
                compress(db, conv, registry.get())
    finally:
        db.close()


def _post_placeholder(pre: dict, reason: str = "no_response") -> None:
    """SSE 失败/空答的补偿：落一条 assistant 占位消息，保持 user/assistant 成对与 message_count 一致。

    _pre 已落库用户消息；若流式生成失败/空答时 _post 从未执行，会留下无答复的用户消息、
    计数永久错位（对抗审计 2026-08-07）。占位不沉淀、不压缩。

    `reason`（D-23，2026-10-11）决定这条历史消息怎么说：`stopped` = 连接在产出答案前就断了
    （用户停止 / 切换会话 / 断网），`no_response` = 服务端这一轮没给出内容。两者混成一句
    "服务暂时无响应"，等于把用户自己的操作写成平台故障，而这条记录会留在历史里被反复读到。
    """
    if pre.get("assistant_committed"):
        return
    content = _PLACEHOLDER_STOPPED if reason == "stopped" else _PLACEHOLDER_NO_RESPONSE
    db = SessionLocal()
    try:
        conv = db.get(Conversation, pre["conv_id"])
        if "agent_turn_after" in pre:
            # The cursor is captured by the accepted, serialized request, not
            # inferred from the last user message or a reusable run_id.
            if conv is None or conv.user_id != pre.get("agent_user_id"):
                raise RuntimeError("Agent compensation conversation ownership changed")
            later_roles: list[Row[tuple[str]]] = (
                db.query(Message.role)
                .filter(Message.conversation_id == pre["conv_id"], Message.id > pre["agent_turn_after"])
                .all()
            )
            if any(role == "assistant" for (role,) in later_roles):
                pre["assistant_committed"] = True
                return
            if any(role == "user" for (role,) in later_roles):
                raise RuntimeError("Agent compensation lost its turn ownership")
        db.add(Message(conversation_id=pre["conv_id"], role="assistant", content=content))
        # 对抗审计 v2 #21：原子自增（与 _pre/_post 同款防竞态）
        db.execute(
            text("UPDATE conversations SET message_count = COALESCE(message_count, 0) + 1 WHERE id = :id"),
            {"id": pre["conv_id"]},
        )
        conv.last_active_at = datetime.utcnow()
        db.commit()
        pre["assistant_committed"] = True
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
        # DB-17 补（2026-10-09 复核轮 B 路）：这条路绕过 `pick` 的冷却过滤，所以降级判定必须
        # 把"该模型正在 4xx 冷却"也算进去——否则整池冷却时每个请求都会再烧一次刚被打回的
        # 默认模型，且不标降级（冷却就只剩"少选它"没有"别打它"）。配额语义仍不参与。
        return dk, registry.get(), registry.is_unavailable(dk) or registry.is_rejected(dk)


# 核对/降级提示（轻量升级失败、旗舰自检失败、配额紧张共用，避免字面量重复）
# B1（2026-08-07）：去掉"建议核对条文原文"——前端曾为清这句写 stripUnprovidedHint，后端不再制造该噪音
# 空答兜底文案（4 处 SSE error 帧共用：轻量空答/合同空答/旗舰空答/R15 分支；Standards 轴：Duplicated Code）
_ERROR_NO_RESPONSE = "服务暂时无响应，请稍后重试"
# D-23（Owner 2026-10-11 裁「改」）：占位消息此前只有一句"服务暂时无响应"，连**用户自己按下的停止**
# 也被写成平台故障——当场前端显示"已停止生成"，刷新/换设备看历史却读成"服务不可用"。
# 故障文案复用上面那条（不抄第二份字面量，两处只允许句号不同）。
_PLACEHOLDER_NO_RESPONSE = _ERROR_NO_RESPONSE + "。"
_PLACEHOLDER_STOPPED = "本次回答已停止，未生成完整内容。"

NOTE_COMPLEX = "\n\n> 注：该问题较复杂，本回答仅供参考。"
NOTE_QUOTA = "\n\n> 注：模型配额紧张，本回答仅供参考。"
# S5（2026-09-19）快车道版本绊线命中时的明说降级注记（同 NOTE_* 惯用法，不静默替换答案）。
NOTE_LAW_VERSION = "\n\n> 注：本回答所适用的法律版本与所述事实的发生时间可能不一致，本回答仅供参考。"
# 多选漏答症状注记（决策 8）。**全仓只此一份措辞**：流式出口（登记表 E11）与轻量缓冲出口
# （票 J 新增，登记表 E16）共用它 —— 两处各抄一份字面量会让"同一症状两句话"漂移，
# 而它们本该是同一条告警（票 J §J-2：「复用流式那份纯函数，不许重写规则」同理）。
NOTE_MULTI_INCOMPLETE = "\n\n> ⚠️ 本题可能为多选题，上述回答似乎只给出了一个正确选项，请核对是否遗漏。"
# S0-c（2026-09-26）：显式历史基准日 + 证据时效未核验 ⇒ 明说，不静默。
# 措辞避开 `quality._HONEST_REFUSE_MARKS` 与 `VAGUE_PHRASES` 的字面（注记会进 `self_check` 的输入，
# 撞上前者会把"无据硬答"洗成诚实拒答，撞上后者会把正常答复判成含糊）。
NOTE_TIME_UNVERIFIED = (
    "\n\n> 注：本回答引用的条文缺少可核验的时效信息（生效日、废止日），"
    "在所问的历史基准日是否有效未经核验，本回答仅供参考。"
)


def _time_unverified_hit(pre: dict) -> bool:
    """S0-c 注记判据，**全仓唯一一份**。两个条件缺一不可：

    ① 本次答案用了**显式历史基准日** ⇒ 只认 `pre["law_as_of"]`。该键由
    `request_bootstrap.prepare_fast_path` 在 `bootstrap.law_as_of is not None` 时才写入
    （未指定 ⇒ 键不存在），它就是"这一答问的是过去的法"的单一源头；各出口不许再各自
    从 body 重算（`_exit_law_as_of` 已为此立过一次前科）。
    ⚠️ 别拿 `cutoff` 当这个条件：检索层 `cutoff = cutoff or date.today().isoformat()` 让它
    永远非空 ⇒ "带 cutoff 才注记"是空判据。
    ② 本轮检索证据里有 `time_validity_state == "unknown"` 的块 —— 即"没资格断言它那天有效"。
    """
    if not pre.get("law_as_of"):
        return False
    return any(time_validity_state(s) == "unknown" for s in pre.get("sources") or ())


# 低置信反问计数（任务2）：conv_id → 已反问（最多一次，防死循环）。进程内状态，
# 单 worker 下有效（ADR-008 单 worker 约束）；重启清零可接受——反问上限防的是同会话循环。
_clarified: dict[int, bool] = {}


def _cutoff() -> str:
    return datetime.now().date().isoformat()


def _cacheable(pre: dict) -> bool:
    """仅安全形态可缓存：法律咨询/法考题(study_aid) + 无图 + 首轮 + 检索命中。

    study_aid 白名单由 feature_study_cache 控制；显式历史日期不进共享答案缓存。"""
    intent = pre.get("intent")
    ok_intent = intent == "legal_query" or (settings.feature_study_cache and intent == "study_aid")
    return (
        ok_intent
        and not pre.get("law_as_of")
        and not pre.get("image")
        and not pre.get("recent")
        and bool(pre.get("sources"))
    )


def _cache_scope(pre: dict, cutoff: str | None = None) -> answer_cache.CacheScope:
    ids = [
        json.dumps(
            [s.get(field) or "" for field in ("source", "article", "effective_from", "effective_to", "status")],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for s in (pre.get("sources") or [])
    ]
    return answer_cache.make_scope(pre.get("intent", ""), cutoff or _cutoff(), ids)


def _cache_key(pre: dict, cutoff: str | None = None) -> str:
    intent, day, ids = _cache_scope(pre, cutoff)
    return answer_cache.make_key(pre.get("rewritten", ""), intent, day, list(ids))


def _cache_write_ok(pre: dict, answer: str) -> bool:
    """确定性缓存写闸（审查 C2）：study_aid 答案的引用必须全部命中本轮检索返回条文。

    自检（quality.self_check）只是"无实体"门禁——查引用是否在库，不保证"引对题"
    （引在库但答非所问）。法考题答案与检索条文强绑定，故写缓存前追加确定性校验：
    引用（法名、条号）⊆ 检索 sources 的对应集合，防止跨法同条号的坏答案被
    TTL 6h 缓存放大给所有同 key 用户。legal_query 维持现状（自检已覆盖）。
    """
    if pre.get("intent") != "study_aid":
        return True
    retrieved = {
        (_source_key(canon_source(s["source"])), _normalize_article(s["article"]))
        for s in (pre.get("sources") or [])
        if s.get("source") and s.get("article")
    }
    if not retrieved:
        return False
    cited = {
        (_source_key(canon_source(source)), _normalize_article(a)) for source, a, _ in extract_citations(answer or "")
    }
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


def _similar_cache_hit(pre: dict, scope: answer_cache.CacheScope | None = None) -> dict | None:
    """近重复命中（feature_similar_cache，grilling 定稿）：嵌入输入 + 护栏 → get_similar。

    仅当精确 key miss 时调用；护栏不一致（极性/选项数/标号体系/指纹）→ miss，安全。
    """
    try:
        emb = _embed_question(pre.get("rewritten") or "")
        if not emb:
            return None
        pol, cnt, lab, fp = _cache_guards(pre.get("rewritten") or "")
        return answer_cache.get_similar(
            emb,
            polarity=pol,
            option_count=cnt,
            label_system=lab,
            options_fingerprint=fp,
            scope=scope if scope is not None else _cache_scope(pre),
        )
    except Exception:
        return None


# ==================== W06-B：不可变 QA 依赖的缓存 / 阶段守（§4.1、§4.2） ====================
# ⚠️ `pre` 的键集被既有契约用例钉死（`test_request_bootstrap.py::test_prepare_fast_path_returns_exact_legacy_keys`）
# ⇒ 依赖快照**不塞进 `pre`**，而由下面这个**唯一签发点**从 `pre` 现有的 `qa_hit`/`summary`/`recent` 现算。


def _input_qa_dependencies(pre: dict):
    """为这一份实际生成输入**签发**不可变 QA 依赖快照（三态）——全仓唯一签发点。

    - 非空 tuple＝实际使用了 QA 且取到可靠 SQL 身份；
    - `None`＝使用了 QA 但身份不可靠（无链/不一致/读不动），或存在**未追踪**的 summary/assistant 历史
      （第三阶段完成前不许签已知空）；
    - 空 tuple＝整份输入已确认没有使用 QA（仅当无未追踪历史时才可签）。

    `put` 默认 `None` 只是防漏接线的兜底，不构成签名：任何写点都必须显式传这里的返回值。
    """
    hit = pre.get("qa_hit")
    if hit is not None:
        dep = capture_dependency(hit)
        return (dep,) if dep is not None else None
    if pre.get("summary") or any((m or {}).get("role") == "assistant" for m in (pre.get("recent") or [])):
        return None
    return ()


def _drop_tracked_qa(pre: dict) -> dict:
    """丢弃被追踪的 QA 输入（撤回/失效后重建用）：不再复用它，也不复用旧状态槽。"""
    out = dict(pre)
    out["qa_hit"] = None
    return out


async def _deps_allow(deps) -> bool:
    """把依赖复核投进线程池（fast-path 业务代码不得在主线程直接读同步 SQL）。"""
    return bool((await run_in_threadpool(validate_dependencies, deps)).allow)


async def _cache_read_deps_ok(hit) -> bool:
    """缓存命中后的依赖复核（§4.1）：精确与相似命中共用，开**新 SQL 会话**。

    旧条目没有 `qa_dependencies` 字段、或依赖未知(None) ⇒ 不放行（B06）；已知空/有效非空 ⇒ 放行。
    """
    deps = hit.get("qa_dependencies", None) if isinstance(hit, dict) else None
    return await _deps_allow(deps)


async def _cache_write_deps_ok(deps) -> bool:
    """写缓存前的依赖复核（§4.1 的 W 阶段）：依赖未知(None，含无可靠身份的 QA) ⇒ 不写；
    已知空(`()`)或有效非空 ⇒ 写。B08：无 SQL 身份的 QA 派生答案不进缓存。"""
    if deps is None:
        return False
    return await _deps_allow(deps)


async def _generation_input_invalid(deps) -> bool:
    """O 阶段（§4.2）：实际生成输入的 QA 依赖是否已失效（fresh SQL 核验）。

    已知空 `()`／无 QA(None) 不在此判失效（无链 QA 的直接读取资格另判）；仅**非空**依赖被复核。
    """
    if not deps:
        return False
    return not await _deps_allow(deps)


async def _p_recheck(pre: dict) -> dict:
    """P 阶段（§4.2）：构造生成输入前 **fresh** 复核选中 QA（清槽新读）。失效 ⇒ 丢弃该 QA。"""
    hit = pre.get("qa_hit")
    if hit is None:
        return pre
    verdict = await run_in_threadpool(evaluate_revocation_state, hit, fresh=True)
    return pre if verdict.allow else _drop_tracked_qa(pre)


async def _recheck_before_model(pre: dict, messages: list, deps):
    """实际发起模型调用前再确认依赖仍有效（B12）：失效 ⇒ 丢 QA 并**重建** messages（不是只清 pre）。"""
    updated = await _p_recheck(pre)
    if updated is pre:
        return pre, messages, deps
    msgs = await run_in_threadpool(_build_messages, updated)
    return updated, msgs, await run_in_threadpool(_input_qa_dependencies, updated)


_QA_DIRECT_RETURN_THRESHOLD = 0.92  # QA 语义直返阈值（审查护栏：低于则回落 LLM）
# 民法典分水岭：**不另立日期**，直接别名到 `limitation_calc` 的那一个（全仓唯一真源）。
# 票 I 的 I-2(a) 靠它判"请求的基准日与语料基准日是否分处分水岭两侧"。
_CIVIL_WATERSHED = limitation_calc.CIVIL_CODE_EFFECTIVE


def _qa_direct_return(pre: dict, law_as_of: date | None = None) -> str | None:
    """QA 持久语义缓存直返（8-23 智谱免费 token 预生成语料）：高阈值 + 指纹 + 时效护栏。

    命中返回预生成解析答案（零 LLM）；任一护栏不过 → None（回落 LLM 生成）。
    - score ≥ 0.92（search_qa 余弦，接近同一问法）
    - 选项指纹护栏（审查 C4）：选项题同题干换选项内容必须 miss
    - evidence 时效校验：source|article 在库且仍有效（判据本体 `retrieval.qa_citations_in_kb`）
    - **版本适用护栏（票 I 的 I-2(a)，2026-09-20）**：这份语料是 2026 年生成的
      （`scripts/gen_qa_corpus.py` docstring：「智谱免费 token …（8-23 到期前消耗）」⇒ 生成日 ≤ 2026-08-23），
      其答案反映的是**民法典时代**的法。若本次请求的 `law_as_of` 落在分水岭之前，直返就是
      **用后法答前事** ⇒ 必须 miss 回落 LLM。判据复用 `limitation_calc.CIVIL_CODE_EFFECTIVE`
      （**不另立第二个分水岭**）。

    ⚠️ 三条既有护栏**一个字没动**（票面 I-4 明令），本节是按 I-2 要求新增的**第四**条。

    **第五道（第四轮核对 §10 第 2 条，2026-09-24 由 Owner 裁决收紧）**：`retrieval_core.qa_provenance_verifiable`
    ⇒ `evidence` 给不出可校验条文引用、或 `law_as_of_basis` 不是有效 YYYY-MM-DD 日期的记录**一律不直返**。这一道**取代**了原先
    "语料没有该字段⇒不拦（保持旧行为）"的口径：分水岭守卫缺输入时不再放行，而是在源头就被拒。
    同一个判据也挂在产生处（`request_bootstrap.prepare_fast_path`），所以 `_build_messages` 那条
    "此前已确认的问答"注入通道一起被关——第 8 节②只闭了本函数，漏的就是那一条。
    本函数**自带**这道判据（而不是只靠产生处）：有既有评测探针直接构造 `pre` 调它量直返率
    （`dispatch-output/i1-e2-hitrate-20260920/probe_b_direct_return_rate.py`），那条路径绕过产生处。
    """
    qa = pre.get("qa_hit")
    if not qa or qa.get("score", 0) < _QA_DIRECT_RETURN_THRESHOLD:
        return None
    # 票 W06-FIX F3/V2：本出口这三道语料门按**合成判据的排序**跑（状态轴→来源→引用），
    # 与产生处（`request_bootstrap.prepare_fast_path` 调 `qa_eligibility.qa_read_eligible`）逐字同序 ⇒
    # 同一条记录在产生处与出口回**同一个 reason**（判据：
    # `tests/test_qa_read_eligibility.py::test_producer_and_direct_return_exit_report_the_same_reason`）。
    # 改前这里是 来源→状态→分水岭→指纹→引用：一条既被撤回、来源又是 unknown 的记录，
    # 出口报 `provenance`、产生处报 `state`，两条读数对不上同一件事（F3 说的"排序还不一样"）。
    # 状态轴判据本体仍在 `qa_eligibility`（拒绝留痕也在它内部，本出口不重复落键）；
    # 来源/引用两道沿用 `retrieval_core`／`retrieval` 的那**一个对象**（不内联循环，
    # `tests/test_qa_citation_gate_symmetry.py::test_no_exit_keeps_its_own_copy_of_the_lookup_loop`）。
    if not evaluate_revocation_state(qa).allow:
        return None  # W06-IMPL：撤回/隔离/未知来源/读不到状态 ⇒ 停服务（状态轴唯一真源 qa_eligibility）
    if not qa_provenance_verifiable(qa):
        log_read_denial(qa, "provenance")
        return None  # 来源校验不了 ⇒ 本出口不放行（与产生处同一判据，直连调用路径也挡得住）
    if law_as_of is not None:
        basis = date.fromisoformat(qa["law_as_of_basis"])  # 有效日期由共享来源判据保证
        if (basis >= _CIVIL_WATERSHED) != (law_as_of >= _CIVIL_WATERSHED):
            return None  # 版本适用跨分水岭 → 直返必错（票 I 的 I-2(a)）
    q = pre.get("rewritten") or ""
    q_fp = query_understand._options_fingerprint(q)
    stored_fp = qa.get("fingerprint") or ""
    if q_fp and stored_fp and q_fp != stored_fp:
        return None  # 同题干换选项内容 → 直返必错（C4）
    # 时效护栏：逐条校验引用的条文今天是否仍在库。判据本体在 `retrieval.qa_citations_in_kb`，
    # 与产生处（`request_bootstrap.prepare_fast_path`）调的是**同一个函数**（票 W1，2026-09-25 裁决
    # "对称收口"）——此前这一步只写在本函数里，于是另一条出路（`_build_messages` 的
    # "此前已确认的问答"注入）从未做过时效判定。本出口仍自带这道判据的理由见上面第五道。
    if not qa_citations_in_kb(qa):
        log_read_denial(qa, "citation")
        return None  # 证据条文已失效/不在库/查不动 → 不直返
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
    # S5 快车道版本绊线：命中=True 时答案已追加 NOTE_LAW_VERSION，且**不得**进缓存（见调用点）。
    # 刻意不复用 verdict 承载该信号 —— verdict 是自检归因（pass/vague/low_quota/…），覆盖它就会
    # 丢掉"为什么降级"的那一半信息，两条降级原因得能同时出现在一张日志里。
    law_version_hit: bool = False
    # 票 J：**独立的降级信号**，与 verdict 分开（同 S5 那条字段注释立下的规矩）。语义严格对齐流式的
    # `flag_degraded`（= "本来该用的模型不可用，这条答复是在降级下产出的"），**只有**
    # `_light_buffered_locked` 里 `except QuotaExhausted` 那一支为 True（升级旗舰时配额耗尽 ⇒ 退回
    # 轻量产物 + NOTE_QUOTA）。刻意**不含**"轻量即旗舰、无更强者可升"那一支：那是能力上限，不是降级；
    # 也不含自检 FAIL —— 那是 verdict 的归因域。两条必须能同时出现在一张日志里（见调用点的 log_account）。
    degraded: bool = False


def _fast_path_fact_texts(pre: dict) -> list[str]:
    """快车道的"事实文本"集 = **用户自述**（本轮问句 + 改写 + 历史里的用户消息）。

    与 agent 路径 `verifier._fact_texts`（= issue.facts + unknown_facts）同语义：都是"本案事实"，
    不是"检索到的法条"。⚠️ 刻意不含 `pre["context"]` / `pre["sources"]` —— 那里面的日期属于证据池
    （且旧法条文本必然带分水岭前的年份），当事实用会让每条引用都点亮判定，是纯假阳性。
    """
    texts = [pre.get("user_text") or "", pre.get("rewritten") or ""]
    texts += [
        m.get("content") or "" for m in (pre.get("recent") or []) if isinstance(m, dict) and m.get("role") == "user"
    ]
    return [t for t in texts if t]


def _client_law_as_of(body) -> date | None:
    """公开历史查询；部署关闭时明确拒绝，避免静默改用当日法律。"""
    if body.law_as_of is not None and not settings.allow_client_law_as_of:
        raise HTTPException(status_code=503, detail="历史查询当前不可用")
    return body.law_as_of


def _client_case_domain(body) -> str | None:
    """客户端传入的 `case_domain`，经评测通道闸过滤。

    定位：该值决定 R1-OB 判域（劳/民/商…），是**评测/灰度输入**，不是普通用户的偏好。
    `settings.allow_client_case_domain=False`（默认）⇒ 返回 None ⇒ 消费方落默认，
    行为与"客户端没传"完全一致（前端从不传该字段，生产默认路径零变化）。

    ⚠️ 本闸的消费点当前**只在 agent 启用分支内**（`if not settings.agent_enabled:` 之后）⇒
    本文件无端点级用例（harness 没有 agent 路由）；已有回归守卫保证"闸外不得存在直读"
    （`tests/test_client_case_domain_gate.py`）。
    """
    if not settings.allow_client_case_domain:
        return None
    return body.case_domain


def _fast_path_law_as_of(body) -> date:
    """快车道版本绊线基准日；检索 cutoff 已在 bootstrap 准备阶段接入。"""
    return _client_law_as_of(body) or date.today()


def _exit_law_as_of(pre: dict, body) -> date:
    """出口（QA 直返 / 轻量缓冲 / 版本绊线）的生效基准日：以**本次取数所用**的日期为准。

    各出口原先各自 `_fast_path_law_as_of(body)` 重算。正常请求上两者同值，所以看不出问题；
    但 Agent 恢复分支技术性降级时基准日在 run 上、body 里没有 ⇒ 重算得**今日**，而
    `pre["law_as_of"]` 是 run 的历史日，于是版本绊线拿现行法去判历史证据、日志也把
    `law_as_of` 记成今日。故出口只认 `pre`，`pre` 没有才回落到 body 口径。
    """
    from_body = _fast_path_law_as_of(body)  # 无条件算：让 spy 型用例仍能观测 body 口径
    return pre.get("law_as_of") or from_body


# 版本绊线门的出口标签。**为什么做成参数**：S5 时期这道门只有一个消费者，日志里那句
# "（缓冲轻量出口）"是写死的；票 C 把同一道门接到旗舰流式出口上 ⇒ 再有第二个消费者，
# 写死就是把流式的命中记成轻量的命中（假归因）。默认值一律不给：漏传直接 TypeError，
# 不给"静默记错出口"留路。
EXIT_LIGHT = "缓冲轻量出口"
EXIT_STREAM = "旗舰流式出口"


def _law_version_gate(
    answer: str, fact_texts: list[str], law_as_of: date | None, *, exit_label: str
) -> tuple[str, bool]:
    """法律版本绊线门：进出都是**答案文本**，返回 `(交付文本, 是否命中)`。

    判定规则**只**在 `limitation_calc`（单一真源，票 C §5-1）。入参形态在票 C 改过一次：
    S5 收的是 `_LightResult`，而旗舰流式出口在收口点只有 `answer` 字符串（没有配额 key、
    档位、自检 verdict 可填）⇒ 按票 C §5-2「签名不合用就改签名、别开第二份门函数」改成收文本，
    两个出口各自把 `(answer, hit)` 装回自己的返回形状（判定/注记/日志仍只此一份）。

    开关关 ⇒ 原样返回 `(answer, False)`（行为逐字不变）。开关开而拿不到 `law_as_of` ⇒
    fail-closed 按命中处理，口径照抄 agent 路径 `verifier.py:296-297`：开关开而基准日缺失 =
    接线丢失 = 判定不可信，**不等于**可以放行（静默放行正是这道门要防的失败模式）。
    """
    if not settings.fast_path_law_version_check:
        return answer, False
    if law_as_of is None:
        reason = "LAW_TRIPWIRE_NOT_WIRED"
    elif limitation_calc.law_version_crosses_watershed(answer, fact_texts, law_as_of):
        reason = "LAW_VERSION_WATERSHED_MISMATCH"
    else:
        return answer, False
    # 落被判定原文 + 基准日：否则线上只知道"拦了"，不知道按哪版法拦了哪句（5afc8d0 的可归因教训）。
    logging.getLogger("legal.chat").warning(
        "快车道版本绊线命中（%s）：%s",
        exit_label,
        reason,
        extra={
            "fast_path_law_version_hit": True,
            "fast_path_law_version_reason": reason,
            "fast_path_law_version_detail": answer[:200],
            "law_as_of": law_as_of.isoformat() if law_as_of else None,
        },
    )
    # 空答不追加注记：两个出口都靠"空答 ⇒ error 帧"兜底（缓冲出口见调用方的 `else`，流式出口见
    # `if not answer:`），给它加字会把"没答上来"伪装成"答了但仅供参考"。
    return ((answer + NOTE_LAW_VERSION) if answer else ""), True


async def _ainvoke_cancel_safe(llm, messages):
    """Own one model task so repeated ASGI cancellation cannot interrupt SDK cleanup."""
    task = asyncio.create_task(llm.ainvoke(messages))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # AnyIO uses level cancellation; gather inside LangChain would otherwise
        # forward repeated task.cancel() calls into the HTTP transport's teardown.
        with CancelScope(shield=True):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                print(f"[llm-cancel-cleanup] failed: {type(exc).__name__}", flush=True)
        raise


async def _light_buffered(pre: dict, messages: list, law_as_of: date | None = None) -> _LightResult:
    """轻量路径：可取消缓冲生成 → 自检 → 至多一次升级旗舰重答。"""
    modality = "vision" if pre.get("image") else "text"
    ctx_present = bool(pre.get("sources"))
    lkey, llm, _ = _safe_pick(modality, "light")  # 轻量回退降级由下方升级 except 兜底
    async with llm_guard:  # 轻量+升级重答共占一个并发位，取消归还同一计数源
        return await _light_buffered_locked(pre, messages, modality, ctx_present, lkey, llm, law_as_of)


async def _light_buffered_locked(
    pre: dict, messages: list, modality: str, ctx_present: bool, lkey, llm, law_as_of: date | None = None
) -> _LightResult:
    """轻量路径主体（已持有并发位）：缓冲生成 → 自检 → 至多一次升级旗舰重答。"""
    # 开关关 ⇒ 不做无谓的事实扫描（同 verifier.py:338 的省法）。
    fact_texts = _fast_path_fact_texts(pre) if settings.fast_path_law_version_check else []

    def _with_gate(res: _LightResult) -> _LightResult:
        """五个 return 点共用的**装配**：过门，再把 `(answer, hit)` 装回返回结构。

        判定、注记、日志全在 `_law_version_gate` 一处（票 C §5-2：只此一份门）；本闭包只是
        把票 C 改过的门签名接回 S5 的 `_LightResult` 形状，五个 return 点的构造一字未动。
        """
        answer, hit = _law_version_gate(res.answer, fact_texts, law_as_of, exit_label=EXIT_LIGHT)
        return replace(res, answer=answer, law_version_hit=hit)

    resp = await _ainvoke_cancel_safe(llm, messages)
    raw = clean_answer(resp.content or "") if resp else ""
    usage = _token_charge(resp, raw)
    v = quality.self_check(raw, ctx_present)
    if v.ok:
        return _with_gate(_LightResult(raw, lkey, modality, "light", usage, False, "pass"))
    # 升级旗舰（配额耗尽则不升级，明说降级）
    try:
        fkey, fllm = registry.pick(modality, "flag")
    except QuotaExhausted:
        # 票 J：这是轻量路径**唯一**的降级点 ⇒ 独立信号在这里点亮（不是靠 verdict 里那个
        # "low_quota" 字符串表达的：verdict 还同时承载自检归因，两个信号必须能分开读）。
        return _with_gate(
            _LightResult(
                (raw + NOTE_QUOTA) if raw else "",
                lkey,
                modality,
                "light",
                usage,
                False,
                v.reason or "low_quota",
                degraded=True,
            )
        )
    if fkey == lkey:  # 轻量即旗舰，无更强者可升
        return _with_gate(
            _LightResult((raw + NOTE_COMPLEX) if raw else "", lkey, modality, "light", usage, False, v.reason)
        )
    fresp = await _ainvoke_cancel_safe(fllm, messages)
    fraw = clean_answer(fresp.content or "") if fresp else ""
    fusage = _token_charge(fresp, fraw)
    fv = quality.self_check(fraw, ctx_present)
    if fv.ok:
        return _with_gate(_LightResult(fraw, fkey, modality, "flag", usage + fusage, True, "pass"))
    return _with_gate(
        _LightResult((fraw + NOTE_COMPLEX) if fraw else "", fkey, modality, "flag", usage + fusage, True, fv.reason)
    )


async def _invoke_llm(messages, llm=None) -> str:
    """非流式兜底：可取消地用给定（或默认）模型拿完整答案。"""
    llm = llm or registry.get()
    async with llm_guard:
        resp = await _ainvoke_cancel_safe(llm, messages)
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
            # 票 W07 §1 ④：transport 由 entry 单一真源给出（`transport_of` 读的是 ModelEntry 那一位），
            # 分派只发生在 multimodal.transcribe_audio 一处；现役语音条目缺省 chat ⇒ 行为逐字不变。
            text = transcribe_audio(llm, b64, ext, transport=registry.transport_of(key))
            registry.deduct(key, estimate_tokens(text))
            return {"text": text}

    try:
        return await run_in_threadpool(_do)
    except QuotaExhausted as qe:
        raise HTTPException(status_code=503, detail="语音模型配额不足，请稍后重试") from qe
    except HTTPException:
        raise
    except Exception as e:
        # 票 W7-FIX B9：只记**异常类名**，不把 SDK 异常正文写进 msg——`_JsonFormatter` 无条件输出 `msg`，
        # 而上游异常文本可能回显请求内容（这条腿没有真 key 可测 ⇒ 「上游是否回显」标 NOT TESTABLE，
        # 见 dispatch/w07-fix-ticket.md；这里做的是「即便回显也不落日志」的那一半，可静态钉）。
        logging.getLogger("legal.chat").warning("transcribe failed", extra={"llm_error_class": type(e).__name__})
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
async def law_detail(
    request: Request,
    source: str,
    article: str,
    run_id: str | None = None,
    user: User = Depends(get_current_user),
):
    """法条原文（前端法条悬浮卡 / 速查面板，P1）。复用 exact_article_lookup，未命中 404。

    B3（2026-08-07）：article 先 _normalize_article 归一（〇/零、阿拉伯/中文、之条），
    前端传原始条号文本即可命中，不再自行拼"第X条"。
    """

    def _do():
        if run_id is not None:
            from agent.schemas import LegalAgentState
            from agent.writer import canonical_citations

            # 同时核验 run 与会话归属；有 run 的卡片绝不回退为“当前版本”。
            with SessionLocal() as db:
                run = (
                    db.query(AgentRun)
                    .join(Conversation, AgentRun.conversation_id == Conversation.id)
                    .filter(AgentRun.id == run_id, AgentRun.user_id == user.id, Conversation.user_id == user.id)
                    .one_or_none()
                )
                if run is None:
                    return None
                try:
                    state = LegalAgentState.model_validate_json(run.state_json)
                except ValueError:
                    return None
                requested = canonical_citations(f"《{source}》{_normalize_article(article)}")
                if not requested:
                    return None
                matched = [
                    ev for ev in state.evidence if requested <= canonical_citations(ev.source_ref + "\n" + ev.snippet)
                ]
                if not matched:
                    return None
                return {
                    "source": source,
                    "article": _normalize_article(article),
                    "content": "\n\n".join(dict.fromkeys(ev.snippet for ev in matched)),
                    "is_snapshot": True,
                    "law_as_of": run.law_as_of.isoformat(),
                    "status": "答复证据快照（非完整条文）",
                }
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


class _ChatStreamingResponse(StreamingResponse):
    """请求返回前关闭聊天 body，包括断开发生在阻塞的 send() 中。

    `on_response_close` 只在 response/route 所有权边界上运行一次：断开若卡在
    `http.response.start` 的 send 里，body 生成器从未进入，`aclose()` 不会执行它的
    finally —— 那一段补偿只能由本响应负责，否则会留下没有答复的用户消息。
    """

    def __init__(self, *args, on_response_close=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_response_close = on_response_close

    async def __call__(self, scope, receive, send):
        try:
            async with ClosingStream(self.body_iterator):
                await super().__call__(scope, receive, send)
        finally:
            if self._on_response_close is not None:
                with CancelScope(shield=True):
                    await self._on_response_close()


async def _stream_with_status_preframe(gen):
    """显式托管原 stream；即时 status 由它在 try/finally 内发送，断开仍留失败占位。"""
    async with ClosingStream(gen) as stream:
        async for frame in stream:
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


_CHAT_TURN_WAIT_SECONDS = 180.0  # 与前端既有无帧超时预算一致，排队不永久悬挂。
# ponytail: 进程内串行边界，仅支持现有单 worker；多 worker 需持久化的轮次所有权。
_chat_turn_locks: WeakValueDictionary[tuple[int, int], asyncio.Lock] = WeakValueDictionary()


def _resolve_chat_conversation(
    user: User, conversation_id: int | None, *, create_if_missing: bool = True
) -> tuple[int, datetime | None]:
    """确定本人会话身份；聊天保留失效编号新建语义，删除只读确认。"""
    with SessionLocal() as db:
        conv = db.get(Conversation, conversation_id) if conversation_id else None
        if conv is None or conv.user_id != user.id:
            if not create_if_missing:
                raise HTTPException(status_code=404, detail="会话不存在")
            conversation_id = create_conversation(user, db)["id"]
            conv = db.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        return conv.id, conv.created_at


def _require_chat_conversation(user_id: int, conversation_id: int, created_at: datetime | None) -> None:
    """排队后核对同一会话；删除及 SQLite 编号复用均不得静默换到新会话。"""
    with SessionLocal() as db:
        conv = db.get(Conversation, conversation_id)
        if conv is None or conv.user_id != user_id or conv.created_at != created_at:
            raise HTTPException(status_code=404, detail="会话不存在")


async def _acquire_chat_turn(request: Request, user_id: int, conversation_id: int) -> asyncio.Lock:
    lock = _chat_turn_locks.setdefault((user_id, conversation_id), asyncio.Lock())
    deadline = time.monotonic() + _CHAT_TURN_WAIT_SECONDS
    while True:
        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="请求已取消")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(status_code=503, detail="上一轮请求仍在处理，请稍后重试")
        try:
            # 直接等待，不创建 acquire 子任务：wait_for 在授予/父取消同拍时可能吞取消。
            async with asyncio.timeout(min(0.1, remaining)):
                await lock.acquire()
        except TimeoutError:
            continue
        try:
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail="请求已取消")
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise asyncio.CancelledError
            return lock
        except BaseException:
            lock.release()
            raise


@app.post("/api/chat", name="chat")
@limiter.limit("60/minute")
async def _serialized_chat(request: Request, body: ChatIn, user: User = Depends(get_current_user)):
    """同会话从 bootstrap 前持有到响应持久化结束；不同会话保持并行。"""
    lock = None
    response = None
    # Populated only on an Agent preparation -> Fast Path handoff. Terminal
    # Agent outcomes keep storage responsibility inside the preparation task.
    agent_turn: dict = {}
    try:
        if body.agent_run_id is None:
            _client_law_as_of(body)  # 拒绝门须在新会话提交前执行。
            text = ((body.content if body.content is not None else body.question) or "").strip()
            if (not text and not body.image) or (body.image and not registry.has_modality("vision")):
                return await chat(request, body, user)  # 原入口负责拒绝，无需先创建空会话。
            if body.image:
                try:
                    await run_in_threadpool(validate_image, body.image)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
            conv_id, created_at = await run_in_threadpool(_resolve_chat_conversation, user, body.conversation_id)
            body = body.model_copy(update={"conversation_id": conv_id})
        if body.conversation_id is not None:
            lock = await _acquire_chat_turn(request, user.id, body.conversation_id)
            if body.agent_run_id is None:
                await run_in_threadpool(_require_chat_conversation, user.id, body.conversation_id, created_at)
        response = await chat(request, body, user, accepted_agent_turn=agent_turn)
        if isinstance(response, _ChatStreamingResponse):
            owned_lock = lock
            cleanup = response._on_response_close

            async def finish_turn():
                try:
                    await cleanup()
                finally:
                    owned_lock.release()

            response._on_response_close = finish_turn
            lock = None  # 响应接管；不能在路由返回时释放。
        return response
    except BaseException as exc:
        if isinstance(response, _ChatStreamingResponse):
            with CancelScope(shield=True):
                await _join_owned_task(asyncio.create_task(response._on_response_close()))
        elif "agent_turn_after" in agent_turn:
            # Preparation is done but no response owns cleanup yet. Keep this
            # write inside the conversation lock, including repeated cancellation.
            with CancelScope(shield=True):
                cleanup_task = asyncio.create_task(
                    run_in_threadpool(
                        _post_placeholder,
                        agent_turn,
                        "stopped" if isinstance(exc, asyncio.CancelledError) else "no_response",
                    )
                )
                try:
                    await _join_owned_task(cleanup_task)
                except Exception as cleanup_exc:
                    logging.getLogger("legal.agent").error(
                        "agent_response_compensation_failed: %s",
                        type(cleanup_exc).__name__,
                        extra={"conv_id": agent_turn["conv_id"], "user_id": user.id},
                    )
        raise
    finally:
        if lock is not None:
            lock.release()


async def chat(
    request: Request,
    body: ChatIn,
    user: User = Depends(get_current_user),
    *,
    accepted_agent_turn: dict | None = None,
):
    # 在取证前捕获代次与日期；失效前启动的请求可以完成，但不得重新污染共享缓存。
    cache_generation = answer_cache.generation()
    cache_cutoff = _cutoff()
    client_law_as_of = _client_law_as_of(body)
    text = (body.content if body.content is not None else body.question) or ""
    text = text.strip()
    image = body.image
    # 阶段B 能力门（2026-09-05）：当前注册模型无视觉能力时显式 501，禁止把图片内容块
    # 静默回退给文本模型（LongCat 实测会忽略图片并按文字作答——诚实停用优于悄悄答错）。
    if image and not registry.has_modality("vision"):
        raise HTTPException(status_code=501, detail="图片理解当前不可用：所配置模型无视觉能力")
    t0 = time.perf_counter()
    pre: dict | None = None
    if body.agent_run_id is not None:
        assert body.agent_state_version is not None and body.conversation_id is not None
        if not text:
            raise HTTPException(status_code=400, detail="请输入对 Agent 追问的回答")
        if not settings.agent_enabled:
            raise HTTPException(status_code=503, detail="Agent 当前已停用，请稍后重试")
        db = SessionLocal()
        try:
            pre = accepted_agent_turn if accepted_agent_turn is not None else {}
            agent_result = await _execute_agent_observing_disconnect(
                request,
                resume={
                    "run_locks": _DEFAULT_RUN_LOCKS,
                    "run_id": str(body.agent_run_id),
                    "expected_version": body.agent_state_version,
                    "user_id": user.id,
                    "conversation_id": body.conversation_id,
                    "answer": text,
                    "expected_law_as_of": client_law_as_of,
                },
                fast_path_pre=pre,
                db=db,
                user_id=user.id,
                settings=settings,
                finalizer=finalize_verified_agent_answer,
            )
        except ResumeRunNotFound:
            raise HTTPException(status_code=404, detail=RESUME_NOT_FOUND_DETAIL) from None
        except ResumeLawAsOfConflict:
            raise HTTPException(status_code=409, detail=RESUME_LAW_AS_OF_DETAIL) from None
        except ResumeRunConflict as _resume_exc:
            # DB-15（2026-10-09，审查报告 B-47）：同一句 409 文案背后原本是几类完全不同的成因
            # （版本冲突 / 持久状态读不出 / 用户这次的输入不合式 / 步数预算打满）。
            # 成因进结构化日志字段 `agent_resume_reason`（已登记进 observability 白名单，
            # 否则会被 JSON formatter 静默丢弃）；D-10（2026-10-11）起对外文案按成因分档，
            # 由 `ResumeRunConflict.detail` 给出——不在这里再拼一遍，避免两处漂移。
            logging.getLogger("legal.agent").warning(
                "agent_resume_conflict",
                extra={
                    "agent_resume_reason": _resume_exc.reason_code,
                    "agent_run_id": str(body.agent_run_id),
                    "user_id": user.id,
                    "conv_id": body.conversation_id,
                },
            )
            raise HTTPException(status_code=409, detail=_resume_exc.detail) from None
        finally:
            db.close()
        if agent_result.outcome != "fallback":
            return _agent_streaming_response(agent_result)
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
                    client_law_as_of,
                )
                _record_actual_agent_route("fast_path")
            else:
                db = SessionLocal()
                pre = accepted_agent_turn if accepted_agent_turn is not None else {}
                try:
                    agent_result = await _execute_agent_observing_disconnect(
                        request,
                        initial={
                            "conversation_id": body.conversation_id,
                            "text": text,
                            "image": image,
                            "truncated": body.truncated,
                            "case_domain": _client_case_domain(body),
                            "law_as_of": client_law_as_of,
                            "force_agent": bool(getattr(body, "force_agent", False)),
                        },
                        fast_path_pre=pre,
                        db=db,
                        user_id=user.id,
                        settings=settings,
                        finalizer=finalize_verified_agent_answer,
                    )
                finally:
                    db.close()
                if agent_result is not None and agent_result.outcome != "fallback":
                    return _agent_streaming_response(agent_result)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve)) from ve
        except LLMBusyError:
            raise HTTPException(status_code=503, detail="服务繁忙，请稍后重试") from None

    assert pre is not None
    # W06-IMPL：注入出口自带状态判据（评测探针会绕过产生处直接构造 `pre`）。
    # 票 W06-FIX F9/V8：候选状态读取由 `qa_eligibility.load_read_state_for` 在**一次请求内复用**
    # （`search_qa` 返回的 `QaHit` 带一条状态槽）⇒ 产生处＋本出口＋直返出口三个判定点合开**一条** session
    # （改前是这里一条＋直返那里一条，共两条）。判据是计数替身，见
    # `tests/test_qa_read_eligibility.py::test_one_sql_state_session_per_qa_bearing_request`。
    # 放线程池，绝不在事件循环里做同步 SQLite 读（对抗审计 v2 #20 同一约束）。
    # W06-B P 阶段（§4.2）：构造生成输入前 **fresh** 复核选中 QA；失效 ⇒ 丢 QA（messages 尚未构造）。
    # 注意：`_p_recheck` 只对 `pre["qa_hit"]` 那条 QA 做状态轴 fresh 读；探针直构的 `pre` 无此键亦然。
    pre = await _p_recheck(pre)
    messages = await run_in_threadpool(_build_messages, pre)
    # W06-B §4.1：为这份实际生成输入**签发**不可变 QA 依赖快照（唯一签发点，投线程池）。
    head_deps = await run_in_threadpool(_input_qa_dependencies, pre)

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
    cache_key = None if body.no_cache else (_cache_key(pre, cache_cutoff) if (use_router and _cacheable(pre)) else None)
    cache_scope = _cache_scope(pre, cache_cutoff) if cache_key else None
    cache_hit = answer_cache.get(cache_key) if cache_key else None
    flag_key = flag_llm = None
    if use_router and not use_light:
        flag_key, flag_llm, flag_degraded = _safe_pick(modality, tier or "flag")

    # 请求局部的所有权标记：正文生成器**是否真的进入过**。用可变对象而非 `nonlocal`
    # 赋值，`stream()` 里的下标写入不需要声明，既有按 AST 提取 `stream` 的测试门也不受影响。
    stream_state = {"entered": False}

    async def stream():
        stream_state["entered"] = True
        # W06-B：本流内**可变视角**（撤回失效后重建 messages 用；不改闭包外那个 `pre`，
        # 免得触发 `stream` 对 `pre` 的赋值语义变化）。`ldeps` 是这份生成输入的依赖快照。
        lpre = pre
        ldeps = head_deps
        lmsgs = messages  # 本流内可变视角的 messages（重建时覆盖，不改闭包外的 `messages`）
        _posted = False  # 本轮 assistant 消息是否已落库（对抗审计 v2 #5/#8：客户端断开时 finally 兜底占位）
        # D-23：兜底占位要区分"连接被打断"与"这一轮服务端没给出内容"。
        # 判据必须是**真实断开信号**，不能是"有没有走到 try 结尾"——正文里有 5 处 `return` 是
        # 走完正常分支后主动退出的（轻量/合同/chitchat 等），用"没走到结尾"反推会把它们全判成取消。
        # 独立复核 B（2026-10-11）就是这么打中我这版实现的：轻量分支空答走 `:2415` 的 return，
        # 会被错写成"已停止"，而同样的空答在旗舰分支写的是"不响应"——同一症状两句话。
        _client_gone = False
        try:
            yield f"data: {json.dumps({'type': 'status', 'msg': '正在思考…'}, ensure_ascii=False)}\n\n"
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
                hit = await run_in_threadpool(_similar_cache_hit, pre, cache_scope)
            # W06-B（§4.1/§4.2）：命中后、首次 content 前，用**新 SQL 会话**复核缓存自身依赖。
            # 旧条目无该字段 / 依赖未知(None) / 已撤回·隔离·变版·变内容 ⇒ miss——不能因 TTL 没到而放行，
            # 也不因当前 `pre.qa_hit=None` 而清空旧答案自身依赖（B09）。
            if hit and not await _cache_read_deps_ok(hit):
                hit = None
            if hit:
                ca = hit["answer"]
                _f0 = time.perf_counter()  # 缓存命中：首帧≈总耗时（瞬时，用于首帧埋点分段标注）
                yield f"data: {json.dumps({'content': ca}, ensure_ascii=False)}\n\n"  # gate-exit: E1
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
                    # W06-C H05：缓存回放把该条目冻结的依赖显式传给 _post，写出的新 assistant 继承之。
                    # 用零参 lambda 承载关键字，避免给既有的 run_in_threadpool 接缝替身（`async def(fn,*args)`）
                    # 增加关键字参数面。
                    await run_in_threadpool(lambda: _post(pre, ca, False, qa_dependencies=hit.get("qa_dependencies")))
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
                return

            # 分支0.2：QA 持久语义缓存直返（8-23 智谱免费 token 预生成语料，零 LLM）
            # 高阈值 + 选项指纹 + evidence 时效三护栏；仅命中才直返，否则回落 LLM
            # 对抗审计 v2 #20：_qa_direct_return 内 Chroma .get() 同步阻塞事件循环 → 线程池
            qa_ans = (
                None if body.no_cache else await run_in_threadpool(_qa_direct_return, pre, _exit_law_as_of(pre, body))
            )
            # W06-B O（§4.2）：QA 直返在首个 content 前用 fresh 状态轴复核（status/restart 都不算正文已开始）。
            # 无链 QA（capture 拿不到身份）不在本守范围内——其直接读取资格仍由既有门判（B08）。
            if qa_ans and pre.get("qa_hit") is not None:
                fresh_state = await run_in_threadpool(evaluate_revocation_state, pre["qa_hit"], fresh=True)
                if not fresh_state.allow:
                    qa_ans = None
            if qa_ans:
                _f0 = time.perf_counter()
                yield f"data: {json.dumps({'content': qa_ans}, ensure_ascii=False)}\n\n"  # gate-exit: E2
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
                yield f"data: {json.dumps({'content': msg}, ensure_ascii=False)}\n\n"  # gate-exit: E3
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
                if cd.get("confirm_intent"):
                    # 口径③⑥（2026-10-13）：与案情叙述同形的输入先确认审查意图，不静默切换。
                    # 零 LLM 反问；用户下一轮回“审合同/分析案情”即定路。会话级只问一次（request_bootstrap 记账）。
                    _f0 = time.perf_counter()
                    for _frame in _contract_intent_confirm_frames():
                        yield _frame
                    routing_metrics.record("contract_intent_confirm", False, "pass", "miss", checked=False)
                    log_account(
                        model="rule",
                        tier="contract_intent_confirm",
                        cache="miss",
                        token_est=0,
                        first_ms=round((_f0 - t0) * 1000, 1),
                        ms=round((time.perf_counter() - t0) * 1000, 1),
                        ok=True,
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        q_len=len(text),
                    )
                    yield (
                        "data: "
                        + json.dumps({"conversation_id": pre["conv_id"], "sources": pre["sources"]}, ensure_ascii=False)
                        + chr(10)
                        + chr(10)
                    )
                    yield "data: [DONE]" + chr(10) + chr(10)
                    try:
                        await run_in_threadpool(_post, pre, CONTRACT_INTENT_CONFIRM_PROMPT, False)
                        _posted = True
                    except Exception as e:
                        print(f"[chat-post] {e}", flush=True)
                    return
                if cd.get("need_clarify"):
                    # 信息确认闸：触发但无合同全文 → 零 LLM 反问要内容/范围/立场/类型
                    _f0 = time.perf_counter()
                    yield f"data: {json.dumps({'content': CONTRACT_CLARIFY_PROMPT}, ensure_ascii=False)}\n\n"  # gate-exit: E4
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
                            # DB-17（报告 B-48）：请求形状类 4xx（超长上下文/内容审核/模型名错/key 失效）
                            # 走**冷却**通道，不再记进配额账；真耗尽仍走 mark_depleted。
                            if is_request_shape_rejection(_e):
                                registry.mark_rejected(_ccur["key"], "model_failure", status=status_of(_e))
                            else:
                                registry.mark_depleted(_ccur["key"], "model_failure")
                    _rstart = True

                async with ClosingStream(
                    stream_with_retry(
                        _cmake_chain,
                        cm,
                        [(False, 0.0), (True, 0.5), (False, 0.5)],
                        on_model_failure=_cfail if use_router else None,
                    )
                ) as pieces:
                    async for piece in pieces:
                        if _rstart:
                            _rstart = False
                            chunks = []
                            _f0 = None
                            yield f"data: {json.dumps({'type': 'restart'}, ensure_ascii=False)}\n\n"
                        if _f0 is None:
                            _f0 = time.perf_counter()
                        chunks.append(piece)
                        yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"  # gate-exit: E5
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
                    if _time_unverified_hit(pre):
                        # 报告增量已逐段吐出 ⇒ 追加一帧（登记表 E18，与旗舰 E17 同族）。
                        # ⚠️ 别把这里读成"注记跟着进缓存"：`_cacheable` 的 `not pre.get("law_as_of")`
                        # 已把带基准日的请求整个挡在共享答案缓存外 ⇒ 票 H 那个"缓存掉告警"形状在此不成立。
                        answer += NOTE_TIME_UNVERIFIED
                        yield f"data: {json.dumps({'content': NOTE_TIME_UNVERIFIED}, ensure_ascii=False)}\n\n"  # gate-exit: E18
                    bad = citation_verify(answer)
                    # 降级信号（S2 同族）：`_safe_pick` 起初就落到"本身已不可用"的默认模型。
                    # 短路保护：`flag_degraded` 只在 `use_router and not use_light` 那一支被赋过值
                    # （合同分支里 use_router 为真 ⇒ use_light 已被强制 False ⇒ 该支必已执行），
                    # 而本分支在 `use_router` 为假时同样会走到 ⇒ 直接把裸名读出来会 NameError。
                    degraded = use_router and flag_degraded
                    cache_deps_ok = await _cache_write_deps_ok(ldeps)  # W06-B W 阶段：写前 fresh 复核依赖
                    if cache_key and not bad and not degraded and cache_deps_ok:
                        # 继承回答缓存（code-review #5：重复贴同一合同零重烧）。
                        # 两道闸（票 H）：**引用未收录**（bad 非空）与**降级产出**的报告都不得进缓存 ——
                        # 写进去的是追加注记**之前**的那一份，被零 token 复播时告警/免责注会一起丢掉
                        # （同族形状：E10 的注记也在 `put` 之后 ⇒ 该处靠"命中不入缓存"那道闸兜住）。
                        answer_cache.put(
                            cache_key,
                            answer,
                            pre["sources"],
                            model="contract_review",
                            qa_dependencies=ldeps,
                            scope=cache_scope,
                            generation=cache_generation,
                        )
                    if bad:
                        note = "\n\n> 注：报告引用 " + "、".join(bad) + " 未在知识库中检索到，建议核对。"
                        answer += note
                        yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"  # gate-exit: E6
                    if degraded:
                        # 与流式出口同族的"降级明说"（登记表 E13 / S2：不静默烧耗尽模型）。
                        # 本合同分支此前没有任何降级出口 ⇒ 用户看到一份"看起来正常"的报告。
                        answer += NOTE_QUOTA
                        yield f"data: {json.dumps({'content': NOTE_QUOTA}, ensure_ascii=False)}\n\n"  # gate-exit: E15
                if not answer:
                    # 票 H-2 尾支（Owner 2026-09-20 裁定补）：`stream_with_retry` 三次尝试全部
                    # 「空内容、无异常」时，这里此前**既不产 content 帧也不产 error 帧**
                    # （实测探针：`log_tiers=["contract_review"]`、帧序列无 content/error）⇒ 用户端一片空白。
                    # 复用轻量出口（E7 空答支）的现成文案与帧形状。不写缓存（空答本来就不写）；
                    # 之后的 conversation_id/[DONE] 帧照常发 ⇒ 流是**正常收尾**的，只是多了这条 error。
                    yield f"data: {json.dumps({'error': _ERROR_NO_RESPONSE}, ensure_ascii=False)}\n\n"
                routing_metrics.record("contract_review", False, "pass", "miss", checked=False)
                log_account(
                    model="contract_review",
                    tier="contract_review",
                    cache="miss",
                    first_ms=round((_f0 or 0.0) * 1000, 1),
                    ms=round((time.perf_counter() - t0) * 1000, 1),
                    ok=bool(answer),
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

            # W06-B 模型调用前复核（B12）：P 与首次生成之间若 QA 失效，**重建** messages（不是只清 pre，
            # 只清 pre 而继续用含失效 QA 的旧 messages 不合格）。
            lpre, lmsgs, ldeps = await _recheck_before_model(lpre, lmsgs, ldeps)

            # 分支1：轻量缓冲 + 自检 + 至多一次升级旗舰
            if use_light:
                res = await _light_buffered(lpre, lmsgs, _exit_law_as_of(lpre, body))
                answer = res.answer
                # W06-B O（§4.2）：首个非空正文交给 SSE 生成器**之前** fresh 复核实际生成依赖。
                # 已缓冲整答含失效 QA ⇒ 丢弃旧产物（不发送）、重建无失效 QA 的 messages、**最多重做 1 次**；
                # 重做仍空/仍失败 ⇒ 走既有 error 帧（不把旧产物改标签后发送，不写缓存）。
                if answer and await _generation_input_invalid(ldeps):
                    lpre = _drop_tracked_qa(lpre)
                    ldeps = await run_in_threadpool(_input_qa_dependencies, lpre)
                    lmsgs = await run_in_threadpool(_build_messages, lpre)
                    res = await _light_buffered(lpre, lmsgs, _exit_law_as_of(lpre, body))
                    answer = res.answer
                if answer and _time_unverified_hit(pre):
                    # 缓冲整答还没吐出 ⇒ 注记并进 E7 那一帧（`_light_buffered_locked` 里的
                    # NOTE_LAW_VERSION / NOTE_COMPLEX 就是同一形状）。带基准日的请求不进缓存
                    # （`_cacheable`），所以"复播丢注记"和"未核验答复被固化 6 小时"都不会发生。
                    # ⚠️ 但**先后与 E17 相反**：版本注记已在 `res.answer` 内部，这里只能往后贴 ⇒
                    # 两条同时命中时 E7 是"版本在前、时效在后"，合流点那一支才是反过来。载体差异，
                    # 不是笔误；两侧各有一条用例钉住（`test_e7_note_order_is_the_reverse_of_e17`）。
                    answer += NOTE_TIME_UNVERIFIED
                if answer:
                    _f0 = time.perf_counter()  # 轻量缓冲：非流式整答返回，首帧=完成时刻
                    yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"  # gate-exit: E7
                else:
                    yield f"data: {json.dumps({'error': _ERROR_NO_RESPONSE}, ensure_ascii=False)}\n\n"
                # 票 J/J-2：多选漏答症状（决策 8）——**复用**流式那份纯函数
                # （`quality.multi_incomplete` 全仓只此一份规则，见 J-2「不许重写规则」）。
                # 整答已在此刻发完 ⇒ 与流式同族处置：只追加确定性注记（不静默、不收回已发帧）+ 拦缓存。
                multi_bad = bool(answer) and quality.multi_incomplete(pre.get("user_text") or "", answer)
                if multi_bad:
                    answer += NOTE_MULTI_INCOMPLETE
                    yield f"data: {json.dumps({'content': NOTE_MULTI_INCOMPLETE}, ensure_ascii=False)}\n\n"  # gate-exit: E16
                    log_account(
                        kind="multi_incomplete",
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        detail=f"len={len(pre.get('user_text') or '')}",
                    )
                # 写缓存闸（票 J/J-2：把轻量出口的条件集**对齐**到流式 E8 的五条件形状）：
                #   cache_key               —— 安全形态（见 `_cacheable`）
                #   not res.degraded        —— 降级产物不入缓存（票 J 新增的**独立**降级信号）
                #   _cache_write_ok(pre, answer) —— 确定性写闸：study_aid 的引用必须 ⊆ 本轮检索条文
                #   res.verdict == "pass"   —— 自检 PASS（"升级后仍 FAIL"与"配额耗尽"两支都不是 pass）
                #   not multi_bad           —— 多选漏答不入缓存（防错答传播给近重复题）
                #   not res.law_version_hit —— 命中版本绊线不入缓存：分支0 在本门**之前**直返 ⇒
                #                              一条错版答复进了缓存就会被零 token 固化，门再也走不到
                cache_deps_ok = await _cache_write_deps_ok(ldeps)  # W06-B W 阶段：写前 fresh 复核依赖
                if (
                    cache_key
                    and not res.degraded
                    and _cache_write_ok(pre, answer)
                    and res.verdict == "pass"
                    and not multi_bad
                    and not res.law_version_hit
                    and cache_deps_ok
                ):
                    answer_cache.put(
                        cache_key,
                        answer,
                        pre["sources"],
                        qa_dependencies=ldeps,
                        scope=cache_scope,
                        generation=cache_generation,
                    )
                if res.key:
                    # 对抗审计 v2 #20：SQLite 扣减同步阻塞事件循环 → 线程池
                    await run_in_threadpool(registry.deduct, res.key, res.usage)
                routing_metrics.record(res.tier, res.escalated, res.verdict, "miss", checked=True)
                log_account(
                    model=registry.model_of(res.key),
                    tier=res.tier,
                    escalated=res.escalated,
                    verdict=res.verdict,
                    degraded=res.degraded,
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
                        # L8：按**这次生成实际使用的输入**（`ldeps`，O 失效重建后已更新）签发来源包，
                        # 而不是按未清理的原 `pre` 现算——否则会把失效/未使用的 QA 误签进新 assistant。
                        await run_in_threadpool(lambda: _post(pre, answer, qa_dependencies=ldeps))
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
                        # DB-17（报告 B-48）：同上——被拒 ≠ 没钱。见 `_cfail` 处的说明。
                        if is_request_shape_rejection(_e):
                            registry.mark_rejected(current["key"], "model_failure", status=status_of(_e))
                        else:
                            registry.mark_depleted(current["key"], "model_failure")
                _restart_pending = True  # 下一 config 将从零重答：前端需清空半截

            chunks = []
            _f0 = None
            # 票 C/S6：法律版本绊线门的事实集（与缓冲轻量出口同一取法 `_fast_path_fact_texts`，
            # 只含用户自述、**不含** context/sources 里的法条文本 —— 票 C §2d）。
            # 开关关 ⇒ 不做无谓扫描（与 `_light_buffered_locked` 同一省法）。
            fact_texts = _fast_path_fact_texts(pre) if settings.fast_path_law_version_check else []
            # W06-B O（§4.2）：首个**非空正文**交给 SSE 生成器之前 fresh 复核实际生成依赖；
            # 空 chunk 不算开始。失效 ⇒ 关闭旧生成器、丢弃旧产物、重建无失效 QA 的 messages、
            # **最多重做 1 次**；重做仍失败 ⇒ 明确结束（走既有 error 帧，不写缓存、不成功 `_post`）。
            _o_redo_left = 1
            while True:
                _o_gate_open = False
                _discarded = False
                async with ClosingStream(
                    stream_with_retry(
                        make_chain_fn,
                        lmsgs,
                        [(False, 0.0), (True, 0.5), (False, 0.5)],
                        on_model_failure=_on_model_failure,
                    )
                ) as pieces:
                    async for piece in pieces:
                        if _restart_pending:
                            # 上一个模型失败、即将从零重答：先清空已发半截并通知前端（防拼接乱码）
                            _restart_pending = False
                            chunks = []
                            _f0 = None
                            yield f"data: {json.dumps({'type': 'restart'}, ensure_ascii=False)}\n\n"
                        if not _o_gate_open and piece.strip():
                            _o_gate_open = True
                            if await _generation_input_invalid(ldeps):
                                _discarded = True  # 未发任何正文 ⇒ 关闭旧生成器、丢弃旧产物
                                break
                        if _f0 is None:
                            _f0 = time.perf_counter()  # 真流式：首个 token 时刻（首帧埋点）
                        chunks.append(piece)
                        yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"  # gate-exit: E8
                if not _discarded:
                    break
                if _o_redo_left <= 0:
                    chunks = []  # 明确结束：无可用正文 ⇒ 交由下方 `if not answer:` 的 error 帧
                    break
                _o_redo_left -= 1
                lpre = _drop_tracked_qa(lpre)
                ldeps = await run_in_threadpool(_input_qa_dependencies, lpre)
                lmsgs = await run_in_threadpool(_build_messages, lpre)
                chunks = []
                _f0 = None
            answer = "".join(chunks)
            # 票 C/S6：把 S5 那道版本绊线门接到本条**唯一承流量**的生成出口上。三个口径照票面：
            #   §5-4 基准日未指定时由服务端落当日；取数口径走 `_exit_law_as_of(pre, body)`
            #     （本次请求真用来取数的那个日期优先，body 只是回落）；
            #   §4-Q3 判定读 `clean_answer` 之后的模型原文，注记家族（引用/多选/自检/配额）在它之后；
            #   §5-3 本出口有**两个**答案来源（流式 join / `_invoke_llm` 兜底），逐个来源各过一次性门。
            law_version_hit = False
            if not answer:
                try:
                    fb = await _invoke_llm(lmsgs, flag_llm)
                    answer = clean_answer(fb)
                    if answer:
                        if _f0 is None:
                            _f0 = time.perf_counter()
                        yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"  # gate-exit: E9
                        # 来源 2/2：非流式兜底整答。它与流式 join 是两个不同来源，漏接这一行 =
                        # "流式返回空 ⇒ 走兜底时门整体消失"（票 C §2c 点名的漏 return 点换了形状），
                        # 由变异 C-M1（删本行）+ test_fallback_answer_also_passes_the_gate 对偶钉住。
                        answer, law_version_hit = _law_version_gate(
                            answer, fact_texts, _exit_law_as_of(pre, body), exit_label=EXIT_STREAM
                        )
                except Exception:
                    answer = ""
            else:
                answer = clean_answer(answer)
                # 来源 1/2：流式 join。帧已逐段吐出不收回、不重放 ⇒ 命中时只追加一帧确定性注记 +
                # 拦写缓存，与本文件既有四段同形状处置（票 C §2b「已经吐出去的帧怎么算」是已解问题）。
                # 删本行 = 主路径没门（变异 C-M2）。
                answer, law_version_hit = _law_version_gate(
                    answer, fact_texts, _exit_law_as_of(pre, body), exit_label=EXIT_STREAM
                )
            if answer and _time_unverified_hit(pre):
                # 两个答案来源（流式 join / `_invoke_llm` 兜底）在这一点之后合流 ⇒ 一帧覆盖 E8 与 E9，
                # 不必各写一遍（写两遍就是第二份判据）。
                # ⚠️ 位置在 E14 之前：两条注记同时命中时，"版本可能不一致"是更强的告警，压在最后
                # （`test_e17_frame_precedes_the_version_note` 把顺序钉成判据）。
                # 注记不进缓存 —— 带显式基准日的请求本来就被 `_cacheable` 挡在共享答案缓存外。
                answer += NOTE_TIME_UNVERIFIED
                yield f"data: {json.dumps({'content': NOTE_TIME_UNVERIFIED}, ensure_ascii=False)}\n\n"  # gate-exit: E17
            if answer and pre["intent"] == "legal_query":
                # 口径①（2026-10-13 裁定）：点名了、像法源、但不在库的来源要**显形**——只声明"这部分缺依据"，
                # 不整题拒答（判据侧见 clarify.missing_sources）。合同/文书名（《房屋租赁合同》）不进清单。
                # 位置在 E14 之前：`content_frames[-1] == NOTE_LAW_VERSION` 那条顺序判据不许被顶掉。
                _missing_src = clarify.missing_sources(text)
                if _missing_src:
                    _ms_note = (
                        "\n\n> 注：你点名的 "
                        + "、".join(f"《{m}》" for m in _missing_src)
                        + " 不在本库收录范围，涉及该来源的部分缺少条文依据。"
                    )
                    answer += _ms_note
                    yield f"data: {json.dumps({'content': _ms_note}, ensure_ascii=False)}\n\n"  # gate-exit: E20
            if law_version_hit and answer:
                # 空答不注记：门已保证 `answer == ""` 时不追加，这里再挡一次 yield，
                # 免得把下面 `if not answer:` 的"没答上来"error 帧变成"答了但仅供参考"。
                yield f"data: {json.dumps({'content': NOTE_LAW_VERSION}, ensure_ascii=False)}\n\n"  # gate-exit: E14
            # 多选完整性症状（决策 8）：多选题型 + 回答只声明 1 个正确项 → 疑似漏答。
            # 流式已发出，只能追加确定性核对注（不静默）+ 拦缓存（防错答传播）。纯函数零成本。
            multi_bad = bool(answer) and quality.multi_incomplete(pre.get("user_text") or "", answer)
            if answer:
                bad_cites = citation_verify(answer)
                if bad_cites:
                    # B1：中性措辞，不再"建议核对原文"（该句曾是前端 stripUnprovidedHint 要删的噪音）
                    note = "\n\n> 注：回答中引用的 " + "、".join(bad_cites) + " 未收录于本知识库。"
                    answer += note
                    yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"  # gate-exit: E10
                    log_account(
                        kind="citation_anomaly",
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        detail=";".join(bad_cites)[:300],
                    )
                if multi_bad:
                    note = NOTE_MULTI_INCOMPLETE
                    answer += note
                    yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"  # gate-exit: E11
                    log_account(
                        kind="multi_incomplete",
                        conv_id=pre["conv_id"],
                        user_id=user.id,
                        detail=f"len={len(pre.get('user_text') or '')}",
                    )
            if not answer:
                yield f"data: {json.dumps({'error': _ERROR_NO_RESPONSE}, ensure_ascii=False)}\n\n"
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
                    # 写缓存闸（审查 C2/C3 + 票 C §5-6）：非降级（降级答案不入缓存，防缓存用户
                    # 看不到免责注）+ 确定性写闸（study_aid 引用 ⊆ 检索条文）
                    # + 多选漏答不入缓存（决策 8：防错答传播给近重复题）
                    # + 命中版本绊线不入缓存（票 C：分支0 在本门**之前**直返 ⇒ 一条错版答复进了缓存
                    #   就会被后续同题请求零 token 固化，门再也走不到）。四条件 → 五条件。
                    cache_deps_ok = await _cache_write_deps_ok(ldeps)  # W06-B W 阶段：写前 fresh 复核依赖
                    if (
                        cache_key
                        and not flag_degraded
                        and _cache_write_ok(pre, answer)
                        and not multi_bad
                        and not law_version_hit
                        and cache_deps_ok
                    ):
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
                            qa_dependencies=ldeps,
                            scope=cache_scope,
                            generation=cache_generation,
                        )
                else:
                    verdict_flag = sv.reason
                    # 法考题(study_aid)自检 FAIL 只不写缓存，不加"较复杂"注（解析型回答
                    # 常引格式条文/库外表达，注语义违和且误导；审查 I3）
                    if pre["intent"] != "study_aid":
                        answer += NOTE_COMPLEX
                        yield f"data: {json.dumps({'content': NOTE_COMPLEX}, ensure_ascii=False)}\n\n"  # gate-exit: E12
            # S2：回退模型本身已不可用 → 明说降级，不静默烧耗尽模型（闲聊豁免：降级注不适合闲聊语境）
            if use_router and flag_degraded and answer and pre["intent"] != "chitchat":
                verdict_flag = "low_quota"
                answer += NOTE_QUOTA
                yield f"data: {json.dumps({'content': NOTE_QUOTA}, ensure_ascii=False)}\n\n"  # gate-exit: E13
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
                    # L8：旗舰/legacy 出口同样按实际生成输入（`ldeps`）签发来源，不从未清理的 pre 现算。
                    await run_in_threadpool(lambda: _post(pre, answer, qa_dependencies=ldeps))
                    _posted = True
                except Exception as e:
                    print(f"[chat-post] {e}", flush=True)
        except (GeneratorExit, asyncio.CancelledError):
            # D-23：这两支才是"连接被打断"的真信号（用户停止 / 切换会话 / 断网）。
            # 只置标记并原样抛出——GeneratorExit 期间不能再 yield，CancelledError 不能吞。
            _client_gone = True
            raise
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
            yield f"data: {json.dumps({'error': _ERROR_NO_RESPONSE}, ensure_ascii=False)}\n\n"
            # 补偿：_post 未执行 → 占位 assistant 消息保持成对（对抗审计 2026-08-07）
            try:
                await run_in_threadpool(_post_placeholder, pre)
                _posted = True
            except Exception as e:
                print(f"[chat-placeholder] {e}", flush=True)
        finally:
            # 对抗审计 v2 #5/#8：客户端断开（GeneratorExit 不属 Exception）或未走任何落库分支时，
            # close 可以 await 清理但不能 yield；等唯一占位 commit 后才结束响应所有权。
            # _post 已 commit 后即使沉淀/压缩失败，也不能补第二条 assistant。
            if not _posted and not pre.get("assistant_committed"):
                # D-23：只有真断开才说"已停止"；主动 return（含轻量分支的空答）与落库失败
                # 都归"这一轮没给出内容"，不能挂到用户操作上。
                _reason = "stopped" if _client_gone else "no_response"
                with CancelScope(shield=True):
                    try:
                        await run_in_threadpool(_post_placeholder, pre, _reason)
                    except Exception as exc:
                        print(f"[chat-cancel-compensate] failed: {type(exc).__name__}", flush=True)

    async def compensate_unstarted():
        """未进入正文生成器的请求在此补一条 assistant 占位；已进入的由 stream 的 finally 负责。

        两处互斥由 `stream_state` 决定：已进入 ⇒ 这里直接返回，不会重复落库。
        """
        if stream_state["entered"]:
            return
        try:
            # 走到这里说明响应已关闭而正文生成器从未进入 ⇒ 连接在产出任何内容前就断了（D-23）。
            await run_in_threadpool(_post_placeholder, pre, "stopped")
        except Exception as exc:
            # 不吞：占位是这一轮唯一保持 user/assistant 成对的动作，静默失败正是 R1 要消除的。
            # 只落异常类型，不落 str(exc)（可能含路径/内部标识）。门禁看这条标记判失败。
            print(f"[chat-cancel-compensate] failed: {type(exc).__name__}", flush=True)

    # 反缓冲响应头：SSE 经 Cloudflare Tunnel / Nginx 等代理中转时，若上游未显式声明，
    # 代理会攒批到连接关闭才一次性下发（手机端表现为“一次性输出”）。以下头禁用代理缓冲、
    # 禁止 CDN 改写，确保逐帧流式。
    return _ChatStreamingResponse(
        _stream_with_status_preframe(stream()),
        media_type="text/event-stream",
        on_response_close=compensate_unstarted,
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
    out: list[ConversationListItem] = []
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
                agent_run_id=m.agent_run_id if m.role == "assistant" else None,
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


@app.delete("/api/conversations/{conv_id}", name="delete_conversation")
async def _serialized_delete_conversation(
    request: Request, conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _, created_at = await run_in_threadpool(_resolve_chat_conversation, user, conv_id, create_if_missing=False)
    lock = await _acquire_chat_turn(request, user.id, conv_id)
    try:
        await run_in_threadpool(_require_chat_conversation, user.id, conv_id, created_at)
        return await run_in_threadpool(delete_conversation, conv_id, user, db)
    finally:
        lock.release()


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
        # 票 W06-FIX F1/V3：无链（＝撤不回）语料的进程内计数，与日志键 `qa_write_unlinked` 同源。
        # 判据不许把缺链读成放行，但管理面必须读得到它到底有多少条（backfill 之前先有计数）。
        "qa_write_unlinked": ks.qa_write_counts()["unlinked"],
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
    rows: list[Row[Conversation, str]] = (
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
        "status": body.status or "未验证",
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
            "status": "未验证",
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
    r = ks.decide_candidate(db, cand_id, body.decision, reviewed_by=_admin.id)
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
    rows: list[Row[AuditLog, str | None]] = (
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
    # 反馈不再进受控沉淀待审队列（第四轮核对 §10 第 2 条，Owner 裁决 D）。
    # 原形状：`down` 或带纠错 → `ks.create_candidate(..., f"feedback:{rating}")`，采纳后落入
    # **没有版本轴**的 `qa_pairs` ⇒ 按历史基准日产出的答案可被现行查询直返（第 8 节②）。
    # 服务端追溯不到"这条答案当时用的基准日"（`FeedbackIn` 无 message_id、`Message` 无该列），
    # 只能信客户端自报 ⇒ 闭口落在写侧。台账不丢：`feedbacks` 表独立记 question/answer/
    # rating/correction，管理员经 `/api/admin/feedback` 仍全量可查。人工入库语料的正路是另开票
    # （录入时要求条文引用**并**显式声明适用基准日），而不是把这里洗白。
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
