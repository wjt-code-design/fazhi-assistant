import os
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from rag_chain import rag_chain

load_dotenv()

# 限流：按客户端 IP，每分钟最多 10 次提问，防止付费 API 被恶意刷量
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

class ChatRequest(BaseModel):
    # 限制输入长度，避免超长文本拖垮服务 / 产生高额 embedding 成本
    question: str = Field(..., min_length=1, max_length=2000)

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: Request, req: ChatRequest):
    async def stream():
        try:
            async for chunk in rag_chain.astream(req.question):
                # 用 JSON 封装，避免回答中的换行符破坏 SSE 格式
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            # 出错时也通知前端，而不是静默断流
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.get("/api/health")
def health():
    return {"status": "ok"}
