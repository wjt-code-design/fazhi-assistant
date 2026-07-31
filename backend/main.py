import os
import json
from datetime import datetime

from dotenv import load_dotenv

# 必须在导入会读取环境变量的本地模块之前加载 .env
load_dotenv()

from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy import func
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from rag_chain import format_docs, make_chain, stream_with_retry
from database import SessionLocal, init_db, get_db
from models import User, Conversation, Message, QaCandidate
from schemas import (
    RegisterIn, LoginIn, UserUpdateIn, KnowledgeAddIn, KnowledgeTestIn,
    ChatIn, MessageOut, ConversationListItem, ConversationDetail,
    QaDecisionIn, LlmSwitchIn,
)
from auth import hash_password, verify_password, create_token, get_current_user, require_admin
import knowledge_service as ks
from llm_registry import registry
from memory import load_context, recent_messages, needs_compress, compress, rewrite_query
from retrieval import retrieve, grounded_top_score, retrieve_for_test
from multimodal import validate_image, persist_image, build_vision_content, describe_image, MEDIA_DIR
from curation import should_curate

# 启动期强校验
if not os.getenv("JWT_SECRET"):
    raise RuntimeError("缺少 JWT_SECRET，请在 .env 中设置")

init_db()

SYSTEM_BASE = (
    "你是一名专业的法律咨询助手。请严格依据提供的法律条文与对话上下文回答用户问题。\n"
    "要求：\n"
    "1. 只依据提供的条文与上下文，不编造；条文不足时说明“根据现有资料无法完整回答”。\n"
    "2. 引用时标注来源（如“根据《劳动合同法》第十九条”）。\n"
    "3. 回答控制在 300 字以内。\n"
    "4. 本答复仅供参考，不构成正式法律意见。"
)

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="AI 法律咨询小助手")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================
@app.get("/api/health")
def health():
    return {"status": "ok"}


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
    sys_text = SYSTEM_BASE
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
            validate_image(image, registry.vision_cfg())  # 失败抛 ValueError
            image_rel, thumb_rel = persist_image(image)
            desc = describe_image(registry.get("vision"), image, text or "")

        raw_query = " ".join(p for p in [text or "", desc] if p).strip()
        if not raw_query:
            raw_query = "请描述并分析图片中的法律相关内容"
        rewritten = rewrite_query(registry.get("text"), recent, raw_query) if recent_ser else raw_query

        docs = retrieve(rewritten, k=4)
        context = format_docs(docs)
        qa_hit = ks.search_qa(rewritten)
        sources = [
            {"source": d.metadata.get("source", ""), "article": d.metadata.get("article", "")}
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
            image_rel=image_rel, thumb_rel=thumb_rel, rewritten=rewritten,
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
            compress(db, conv, registry.get("text"))
    finally:
        db.close()


@app.post("/api/chat")
@limiter.limit("60/minute")
async def chat(request: Request, body: ChatIn, user: User = Depends(get_current_user)):
    text = (body.content if body.content is not None else body.question) or ""
    text = text.strip()
    image = body.image
    if not text and not image:
        raise HTTPException(status_code=400, detail="请输入问题或上传图片")
    try:
        pre = await run_in_threadpool(_pre, user.id, body.conversation_id, text, image)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    messages = _build_messages(pre)
    kind = "vision" if pre["image"] else "text"

    async def stream():
        try:
            # glm 系列偶发"空生成"（content/reasoning 皆空，间歇/突发），多配置轮换重试降低失败率
            def make_chain_fn(_i, disabled):
                llm = registry.get(kind) if _i == 0 else registry.variant(kind, disabled)
                return make_chain(llm)

            chunks = []
            async for piece in stream_with_retry(make_chain_fn, messages, [(False, 0.0), (True, 0.5), (False, 0.5)]):
                chunks.append(piece)
                yield f"data: {json.dumps({'content': piece}, ensure_ascii=False)}\n\n"
            answer = "".join(chunks)
            if not answer:
                # 防御：多配置重试仍空则明确告知，而非静默无输出
                yield f"data: {json.dumps({'error': '模型暂时无响应，请稍后重试'}, ensure_ascii=False)}\n\n"
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
        "llm_model": registry.config()["text"]["model"],
        "vision_model": registry.config()["vision"]["model"],
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
def admin_knowledge(_admin: User = Depends(require_admin)):
    return ks.list_docs()


@app.post("/api/admin/knowledge")
def admin_add_knowledge(body: KnowledgeAddIn, _admin: User = Depends(require_admin)):
    extra = {"effective_from": body.effective_from, "effective_to": body.effective_to, "status": body.status or "现行"}
    n = ks.add_text(body.content, source=body.title, article=body.article, origin="manual", extra_meta=extra)
    return {"added_chunks": n}


@app.delete("/api/admin/knowledge/{doc_id}")
def admin_delete_knowledge(doc_id: str, _admin: User = Depends(require_admin)):
    ks.delete_doc(doc_id)
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
        extra = {
            "filename": file.filename, "uploaded_by": admin.username,
            "uploaded_at": datetime.utcnow().isoformat(), "version": 1, "status": "现行",
        }
        n = ks.add_text(text, source=source, origin="upload", extra_meta=extra, file_hash_value=fh)
        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), source)
        preview = retrieve_for_test(first_line[:200], k=3)
        return {"filename": file.filename, "added_chunks": n, "preview": preview}

    return await run_in_threadpool(_do)


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
    return {"id": r.id, "status": r.status}


# ==================== 管理员：模型在线切换 ====================
@app.post("/api/admin/llm")
@limiter.limit("10/minute")
async def admin_llm_switch(request: Request, body: LlmSwitchIn, _admin: User = Depends(require_admin)):
    if not body.text_model and not body.vision_model:
        raise HTTPException(status_code=400, detail="请至少提供 text_model 或 vision_model")
    cfg = registry.reload(text_model=body.text_model, vision_model=body.vision_model)
    return cfg
