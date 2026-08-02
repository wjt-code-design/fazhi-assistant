import os
import json
import socket
import time
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import urlparse

from dotenv import load_dotenv

# 必须在导入会读取环境变量的本地模块之前加载 .env
load_dotenv()

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from rag_chain import format_docs, make_chain, stream_with_retry, clean_answer, vectorstore
from database import SessionLocal, init_db, get_db
from models import User, Conversation, Message, QaCandidate, AuditLog, Feedback
from schemas import (
    RegisterIn, LoginIn, UserUpdateIn, KnowledgeAddIn, KnowledgeTestIn, PreviewChunkIn,
    ChatIn, MessageOut, ConversationListItem, ConversationDetail,
    QaDecisionIn, LlmSwitchIn, FeedbackIn,
)
import chunking
from auth import hash_password, verify_password, create_token, get_current_user, require_admin
import knowledge_service as ks
from llm_registry import registry
from memory import load_context, recent_messages, needs_compress, compress, rewrite_query
from retrieval import retrieve, grounded_top_score, retrieve_for_test, citation_verify, exact_article_lookup
from intent import classify_intent
from domain_rules import (
    cheating_docs, consumer_clause_docs, is_consumer_clause_scenario, CITATION_SELECTION_RULE,
)

from multimodal import validate_image, persist_image, build_vision_content, describe_image, MEDIA_DIR
from curation import should_curate
from settings import settings
from observability import RequestIdMiddleware, setup_logging, log_account
from audit import log_audit

# 启动期强校验
if not settings.jwt_secret:
    raise RuntimeError("缺少 JWT_SECRET，请在 .env 中设置")
if not settings.api_key or not settings.llm_base_url:
    raise RuntimeError("缺少 LLM_API_KEY / LLM_BASE_URL，请在 backend/.env 配置")

init_db()

SYSTEM_BASE = (
    "你是一名专业的法律咨询助手。请严格依据提供的法律条文与对话上下文回答用户问题。\n"
    "要求：\n"
    "1. 只依据提供的条文与上下文，不编造；条文不足时说明“根据现有资料无法完整回答”。\n"
    "2. 引用时标注来源（如“根据《劳动合同法》第十九条”）。\n"
    "3. 回答控制在 300 字以内。\n"
    "4. 避免绝对化措辞（如“一定/必然/绝对/100%”）；法律适用常有不确定性，宜用“可能/存在风险/需结合具体案情”。\n"
    "5. 遇灰色地带或法律解释存在分歧时，开头标注“存在法律不确定性”，可简要并列不同解读及倾向，不替用户拍板。\n"
    "6. 本答复仅供参考，不构成正式法律意见。"
)

# 学习辅助意图（Step A）：法学生做题/理解法条，引导推理而非给答案键
SYSTEM_STUDY = (
    "你是一名法律学习辅助助手。用户是法学生或法律学习者，希望理解、分析题目或法条，而非索取现成答案。\n"
    "要求：\n"
    "1. 作为学习辅助：可拆解法律关系、锁定争议焦点、逐选项分析对错依据、指出易混考点，引导用户自行推理。\n"
    "2. 不直接给出“答案键”或代写（学术诚信）。\n"
    "3. 若用户只表达意图（如“能帮我做考试题吗”）而未给出具体题目，先简要说明你能如何帮忙，并邀请其把题干与选项发来。\n"
    "4. 只引用与该问题真正相关的条文并标注来源，绝不堆砌无关法条。\n"
    "5. 本内容仅供学习参考，请核对条文原文。"
)

# 输出格式规则（所有意图统一）：禁用 LaTeX 数学记号，普通文本聊天里 $...$ 会原样显示
OUTPUT_FORMAT_RULE = (
    "\n\n【输出格式】\n"
    "不要使用 LaTeX 数学记号（如 $\\neq$、$\\le$ 之类带 $ 的公式），不要出现 $ 包裹的符号；"
    "需要表达不等/比较等时，直接用普通字符（如 ≠、≤、≥），或用中文（如“不等于”“小于等于”）。"
)

# 图片分析轻量提示（Step D）：omni 原生读图，此处只规范输出结构与追问缺失信息，不做死板模板
IMAGE_GUIDANCE = (
    "\n\n【图片分析要求】用户提供了图片：\n"
    "1. 先客观描述图中与法律相关的关键事实（文字内容/权利主体/客体/使用方式）。\n"
    "2. 逐一指出涉及的法律问题并引用条文依据（只用检索到的相关条文）。\n"
    "3. 对无法从图中确定的关键信息（如使用目的系商用或个人分享、是否已获授权），主动说明或追问。\n"
    "4. 结论措辞留有余地，不绝对化。"
)

# 作弊索取意图（Step A）：拒绝协助 + 释明法律后果
SYSTEM_CHEATING = (
    "你是一名法律咨询助手。用户似乎在寻求获取考试答案、代考、买卖试题等违背学术诚信与法律的行为。\n"
    "要求：\n"
    "1. 明确、礼貌地拒绝协助作弊、代考、买卖答案。\n"
    "2. 可依据检索条文说明相关法律后果（如组织考试作弊可能涉及《刑法》第二百八十四条之一），引用须标注来源、只用相关条文。\n"
    "3. 引导用户通过正当途径学习备考。\n"
    "4. 本答复仅供参考。"
)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(_app):
    setup_logging(settings.log_level)
    yield


app = FastAPI(title="AI 法律咨询小助手", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# CORS 源可配置（CORS_ORIGINS 逗号分隔）；另用正则放行任意 localhost 开发端口
# （Next dev 端口被占用时会自动 +1，硬编码单端口会导致 "Failed to fetch"）。
_CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"https?://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)  # 纯 ASGI，不缓冲流式 body


# ==================== 健康检查 ====================
@app.get("/api/health")
def health():
    return {"status": "ok"}


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
    def _do():
        db = SessionLocal()
        try:
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
            user = db.query(User).filter(User.username == body.username).first()
            if not user or not verify_password(body.password, user.password_hash):
                raise HTTPException(status_code=401, detail="用户名或密码错误")
            if not user.is_active:
                raise HTTPException(status_code=403, detail="账号已被禁用")
            return {"token": create_token(user), "role": user.role, "username": user.username}
        finally:
            db.close()

    return await run_in_threadpool(_do)


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}


# ==================== 受鉴权的媒体文件（历史图片回显） ====================
@app.get("/api/media/{filepath:path}")
def get_media(filepath: str, _user: User = Depends(get_current_user)):
    base = os.path.dirname(MEDIA_DIR)
    full = os.path.normpath(os.path.join(base, filepath))
    # 防路径穿越：必须落在 media 目录内
    if full != os.path.normpath(MEDIA_DIR) and not full.startswith(os.path.normpath(MEDIA_DIR) + os.sep):
        raise HTTPException(status_code=400, detail="非法路径")
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
    sys_text += OUTPUT_FORMAT_RULE
    sys_text += CITATION_SELECTION_RULE
    if pre.get("image"):
        sys_text += IMAGE_GUIDANCE
    if pre["summary"]:
        sys_text += f"\n\n【此前对话摘要】\n{pre['summary']}"
    history = []
    for m in pre["recent"]:
        if m["role"] == "user":
            history.append(HumanMessage(content=m["content"] or ""))
        elif m["role"] == "assistant":
            history.append(AIMessage(content=m["content"] or ""))
    qa_note = ""
    if pre["qa_hit"]:
        qa_note = (
            f"此前已确认的问答（可优先参考）：\n问：{pre['qa_hit']['question']}\n答：{pre['qa_hit']['answer']}\n\n"
        )
    context_block = f"相关法律条文：\n{pre['context'] or '（无直接命中条文）'}\n\n{qa_note}"
    user_text = pre["user_text"]
    if pre["image"]:
        final_text = f"{context_block}用户问题：{user_text or '请结合图片内容回答相关法律问题。'}"
        final_content = build_vision_content(final_text, pre["image"])
    else:
        final_content = f"{context_block}用户问题：{user_text}"
    return [SystemMessage(content=sys_text)] + history + [HumanMessage(content=final_content)]


def _pre(user_id: int, conversation_id, text: str, image):
    """流式前的全部准备（独立会话，线程池内执行）。校验失败抛 ValueError。"""
    db = SessionLocal()
    try:
        conv = db.get(Conversation, conversation_id) if conversation_id else None
        if conv is None or conv.user_id != user_id:
            conv = Conversation(user_id=user_id, title="", summary="", message_count=0)
            db.add(conv)
            db.flush()
        summary, recent = load_context(db, conv)
        recent_ser = [{"role": m.role, "content": m.content or ""} for m in recent]

        image_rel = thumb_rel = None
        desc = ""
        if image:
            validate_image(image)  # 失败抛 ValueError（单一全模态模型）
            image_rel, thumb_rel = persist_image(image)
            desc = describe_image(registry.get(), image, text or "")

        raw_query = " ".join(p for p in [text or "", desc] if p).strip()
        if not raw_query:
            raw_query = "请描述并分析图片中的法律相关内容"
        rewritten = rewrite_query(registry.get(), recent, raw_query) if recent_ser else raw_query

        # 意图分流（Step A）：学习辅助/元问题不做条文检索，避免「考试题」被误检索成作弊罪条文堆砌
        intent = classify_intent(text or raw_query)
        if intent == "study_aid":
            docs = []
            qa_hit = None
        elif intent == "cheating_request":
            docs = cheating_docs()
            qa_hit = None
        else:
            docs = retrieve(rewritten, k=4)
            qa_hit = ks.search_qa(rewritten)
            # 格式条款/消费者权利场景：通用检索常召回消保法25/24但漏掉民法典496/497，
            # 定向补充作否定无效条款的兜底依据（与提示词 CITATION_SELECTION_RULE 配套）
            if is_consumer_clause_scenario(text or raw_query):
                docs = consumer_clause_docs() + docs
        context = format_docs(docs)
        sources = [
            {
                "source": d.metadata.get("source", ""),
                "article": d.metadata.get("article", ""),
                # 时效快照（阶段6）：供受控沉淀 evidence 与未来微调数据集使用
                "effective_from": d.metadata.get("effective_from", ""),
                "effective_to": d.metadata.get("effective_to", ""),
                "status": d.metadata.get("status", ""),
            }
            for d in docs
        ]

        user_content = text if text and text.strip() else ("[图片]" if image else "")
        db.add(
            Message(
                conversation_id=conv.id, role="user", content=user_content,
                image_ref=image_rel, thumb_ref=thumb_rel,
            )
        )
        conv.message_count = (conv.message_count or 0) + 1
        conv.last_active_at = datetime.utcnow()
        if not conv.title:
            conv.title = ((text or ("[图片] " + (desc[:20] if desc else ""))) or "新对话")[:200]
        if not conv.question:
            conv.question = (text or user_content)[:2000]
        db.commit()
        return dict(
            conv_id=conv.id, summary=summary, recent=recent_ser, context=context,
            qa_hit=qa_hit, sources=sources, image=image, user_text=text or "",
            image_rel=image_rel, thumb_rel=thumb_rel, rewritten=rewritten, intent=intent,
        )
    finally:
        db.close()


def _post(pre: dict, answer: str):
    """流式后的写库 + 受控沉淀 + 压缩（独立会话，线程池内，不阻塞用户该轮）。"""
    db = SessionLocal()
    try:
        db.add(Message(conversation_id=pre["conv_id"], role="assistant", content=answer))
        conv = db.get(Conversation, pre["conv_id"])
        conv.message_count = (conv.message_count or 0) + 1
        conv.last_active_at = datetime.utcnow()
        if not conv.answer:
            conv.answer = (answer or "")[:2000]
        db.commit()

        # 受控沉淀：高有据 + 含引用 + 非空答 → 入待审
        grounded = grounded_top_score(pre["rewritten"])
        q = pre["user_text"] or pre["rewritten"]
        if q and should_curate(grounded, answer):
            ks.create_candidate(db, q, answer, grounded, json.dumps(pre["sources"], ensure_ascii=False))

        # 增量压缩
        recent = recent_messages(db, conv.id)
        if needs_compress(conv, recent):
            compress(db, conv, registry.get())
    finally:
        db.close()


def _invoke_llm(messages) -> str:
    """非流式兜底：流式不兼容/空答时，用同一模型 invoke 一次拿完整答案（部分模型非流式更稳）。"""
    llm = registry.get()
    resp = llm.invoke(messages)
    return resp.content if resp else ""


@app.post("/api/chat")
@limiter.limit("60/minute")
async def chat(request: Request, body: ChatIn, user: User = Depends(get_current_user)):
    text = (body.content if body.content is not None else body.question) or ""
    text = text.strip()
    image = body.image
    t0 = time.perf_counter()
    if not text and not image:
        raise HTTPException(status_code=400, detail="请输入问题或上传图片")
    try:
        pre = await run_in_threadpool(_pre, user.id, body.conversation_id, text, image)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    messages = _build_messages(pre)

    async def stream():
        try:
            # glm 系列偶发"空生成"（content/reasoning 皆空，间歇/突发），多配置轮换重试降低失败率
            def make_chain_fn(_i, disabled):
                llm = registry.get() if _i == 0 else registry.variant(disabled)
                return make_chain(llm)

            chunks = []
            async for piece in stream_with_retry(make_chain_fn, messages, [(False, 0.0), (True, 0.5), (False, 0.5)]):
                chunks.append(piece)
                yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"
            answer = "".join(chunks)
            if not answer:
                # 流式可能不兼容/被限流：回退一次非流式调用
                try:
                    fb = await run_in_threadpool(_invoke_llm, messages)
                    answer = clean_answer(fb)
                    if answer:
                        yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"
                except Exception:
                    answer = ""
            else:
                answer = clean_answer(answer)
            # 引用校验（优化路线 B0.1，防假引用）：答案引用了知识库中不存在的法条 → 追加核对提示并记账
            if answer:
                bad_cites = citation_verify(answer)
                if bad_cites:
                    note = "\n\n> 注：回答中引用的 " + "、".join(bad_cites) + " 未在知识库中检索到，建议核对条文原文。"
                    answer += note
                    yield f"data: {json.dumps({'content': note}, ensure_ascii=False)}\n\n"
                    log_account(kind="citation_anomaly", conv_id=pre["conv_id"], user_id=user.id, detail=";".join(bad_cites)[:300])
            if not answer:
                # 防御：流式+非流式都空则明确告知。模型名不暴露给普通用户，仅在调用记账日志出现
                yield f"data: {json.dumps({'error': '服务暂时无响应，请稍后重试'}, ensure_ascii=False)}\n\n"
            log_account(
                model=registry.config()["model"],
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
                except Exception as e:
                    # 已发出 [DONE]，此后异常只记日志，不再向客户端追加事件
                    print(f"[chat-post] {e}", flush=True)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


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
            db.query(Message.id)
            .filter(Message.conversation_id == c.id, Message.image_ref.isnot(None))
            .first()
            is not None
        )
        preview = (c.question or (first_user.content if first_user else "") or c.title or "新对话")[:60]
        out.append(
            ConversationListItem(
                id=c.id, title=c.title or preview, preview=preview,
                message_count=c.message_count or 0, has_image=has_image,
                last_active_at=c.last_active_at, created_at=c.created_at,
            )
        )
    return out


@app.get("/api/conversations/{conv_id}", response_model=ConversationDetail)
def get_conversation(conv_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(Conversation, conv_id)
    if not conv or conv.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    msgs = db.query(Message).filter(Message.conversation_id == conv_id).order_by(Message.created_at.asc()).all()
    return ConversationDetail(
        id=conv.id, title=conv.title or "", summary=conv.summary or "",
        messages=[MessageOut.model_validate(m) for m in msgs],
    )


@app.patch("/api/conversations/{conv_id}")
def rename_conversation(conv_id: int, title: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
            "id": u.id, "username": u.username, "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, body: UserUpdateIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    log_audit(_admin.id, "user.toggle", target=user_id, detail=f"is_active={body.is_active}")
    return {"id": user.id, "username": user.username, "is_active": user.is_active}


# ==================== 管理员：对话审查 ====================
@app.get("/api/admin/conversations")
def admin_conversations(limit: int = 50, offset: int = 0, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = (
        db.query(Conversation, User.username)
        .join(User, Conversation.user_id == User.id)
        .order_by(Conversation.created_at.desc())
        .offset(offset).limit(limit)
        .all()
    )
    return [
        {
            "id": c.id, "username": uname, "question": c.question, "answer": c.answer,
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
    extra = {"effective_from": body.effective_from, "effective_to": body.effective_to, "status": body.status or "现行"}
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
    raw = await file.read()
    try:
        ks.validate_upload(file.filename, raw)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    def _do():
        text = ks.parse_uploaded(file.filename, raw)
        if not text:
            raise HTTPException(status_code=400, detail="未从文件中识别到文字（可能是扫描版或空文件）")
        fh = ks.file_hash(raw)
        source = os.path.splitext(file.filename)[0]
        # 版本递增（阶段6）：同 hash 重传时 version+1，审计语义正确
        try:
            prev = vectorstore._collection.get(where={"file_hash": fh}, include=["metadatas"])["metadatas"]
            version = max((int(m.get("version") or 0) for m in prev), default=0) + 1
        except Exception:
            version = 1
        extra = {
            "filename": file.filename, "uploaded_by": admin.username,
            "uploaded_at": datetime.utcnow().isoformat(), "version": version, "status": "现行",
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
def admin_qa_decision(cand_id: int, body: QaDecisionIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
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
            "id": a.id, "admin": uname or "-", "action": a.action,
            "target": a.target, "detail": a.detail,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a, uname in rows
    ]


# ==================== 用户反馈（点赞/踩/纠错） ====================
@app.post("/api/feedback")
def post_feedback(body: FeedbackIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fb = Feedback(
        user_id=user.id, conversation_id=body.conversation_id,
        question=body.question, answer=body.answer,
        rating=body.rating, correction=body.correction or "",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    # 负反馈或带纠错 → 进受控沉淀待审，供管理员采纳"修正后的答案"（点赞不自动入库，避免污染）
    if body.rating == "down" or (body.correction and body.correction.strip()):
        propose = (body.correction or "").strip() or body.answer
        ks.create_candidate(db, body.question, propose, 0.0, f"feedback:{body.rating}")
    return {"id": fb.id}


@app.get("/api/admin/feedback")
def admin_feedback(limit: int = 100, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = db.query(Feedback).order_by(Feedback.created_at.desc()).limit(min(max(limit, 1), 500)).all()
    return [
        {
            "id": f.id, "user_id": f.user_id, "conversation_id": f.conversation_id,
            "question": f.question, "answer": f.answer, "rating": f.rating,
            "correction": f.correction,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
    ]
