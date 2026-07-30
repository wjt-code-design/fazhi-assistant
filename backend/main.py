import os
from dotenv import load_dotenv

# 必须在导入会读取环境变量的本地模块（rag_chain 读 ZHIPUAI_API_KEY、auth 读 JWT_SECRET）之前加载 .env
load_dotenv()

import json
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from rag_chain import rag_chain
from database import SessionLocal, init_db, get_db
from models import User, Conversation
from schemas import RegisterIn, LoginIn, UserUpdateIn, KnowledgeAddIn
from auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    require_admin,
)
from knowledge_service import list_docs, count_docs, add_text, delete_doc, parse_uploaded

# 启动期强校验：缺密钥直接报错，避免带病运行
if not os.getenv("JWT_SECRET"):
    raise RuntimeError("缺少 JWT_SECRET，请在 .env 中设置（可用 python -c \"import secrets;print(secrets.token_hex(32))\" 生成）")

# 幂等建表
init_db()

# 限流：按客户端 IP，防止付费 API 与认证接口被刷
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="AI 法律咨询小助手")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 上线时收紧为真实域名
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
    # 异步端点 + 线程池内做同步 DB（slowapi 限流器在异步端点上才稳定）
    def _do():
        db = SessionLocal()
        try:
            if db.query(User).filter(User.username == body.username).first():
                raise HTTPException(status_code=400, detail="用户名已存在")
            # 开放注册仅产生 user 角色，禁止自助注册管理员
            user = User(
                username=body.username,
                password_hash=hash_password(body.password),
                role="user",
            )
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


# ==================== 问答（需登录，记录对话） ====================
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


async def _save_conversation(user_id: int, question: str, answer: str):
    """在线程池中写库，避免阻塞事件循环 / SQLite 并发锁。"""
    def _write():
        db = SessionLocal()
        try:
            db.add(Conversation(user_id=user_id, question=question, answer=answer))
            db.commit()
        finally:
            db.close()
    await run_in_threadpool(_write)


@app.post("/api/chat")
@limiter.limit("60/minute")
async def chat(request: Request, req: ChatRequest, user: User = Depends(get_current_user)):
    async def stream():
        chunks = []
        try:
            async for chunk in rag_chain.astream(req.question):
                chunks.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            await _save_conversation(user.id, req.question, "".join(chunks))
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")


# ==================== 我的历史（登录用户） ====================
@app.get("/api/conversations")
def my_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": c.id,
            "question": c.question,
            "answer": c.answer,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in rows
    ]


# ==================== 管理员：统计 ====================
@app.get("/api/admin/stats")
def admin_stats(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return {
        "user_count": db.query(User).count(),
        "conversation_count": db.query(Conversation).count(),
        "knowledge_count": count_docs(),
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


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    body: UserUpdateIn,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    return {"id": user.id, "username": user.username, "is_active": user.is_active}


# ==================== 管理员：对话审查 ====================
@app.get("/api/admin/conversations")
def admin_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
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


# ==================== 管理员：知识库管理 ====================
@app.get("/api/admin/knowledge")
def admin_knowledge(_admin: User = Depends(require_admin)):
    return list_docs()


@app.post("/api/admin/knowledge")
def admin_add_knowledge(body: KnowledgeAddIn, _admin: User = Depends(require_admin)):
    n = add_text(body.content, source=body.title, article=body.article, origin="manual")
    return {"added_chunks": n}


@app.delete("/api/admin/knowledge/{doc_id}")
def admin_delete_knowledge(doc_id: str, _admin: User = Depends(require_admin)):
    delete_doc(doc_id)
    return {"deleted": doc_id}


@app.post("/api/admin/knowledge/upload")
async def admin_upload(file: UploadFile = File(...), _admin: User = Depends(require_admin)):
    raw = await file.read()
    text = parse_uploaded(file.filename, raw)
    if not text:
        raise HTTPException(status_code=400, detail="未从文件中识别到文字（可能是扫描版或空文件）")
    source = os.path.splitext(file.filename)[0]
    # embedding 是 CPU 密集操作，放线程池避免阻塞
    n = await run_in_threadpool(add_text, text, source, "", "upload")
    return {"filename": file.filename, "added_chunks": n}
