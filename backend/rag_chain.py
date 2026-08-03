"""RAG 基础设施：嵌入 + 向量库 + 文档格式化 + 链工厂。

- LLM 不再在此模块单例化，改由 llm_registry 按"是否带图"路由（文本/视觉）。
- 链的输入为 main 组装好的 messages 列表（含 system/历史/带图或纯文本的最终 human），
  以便视觉模型接收 image_url content 数组。
"""

import asyncio
import os
import re

# 运行期默认离线用本地缓存，避免对 huggingface.co 的在线校验（部分环境 SSL 校验失败）。
# 缓存缺失需回退在线时走 HF_ENDPOINT 镜像；建库/种子脚本会显式置 HF_HUB_OFFLINE=0 覆盖此默认。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_huggingface import HuggingFaceEmbeddings

from llm_guard import llm_guard  # noqa: E402
from settings import settings  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Embeddings — 配置驱动（ADR-011，2026-08-04）：local=本地 BGE CPU（默认，零配置回退）；
#    aliyun=阿里云 text-embedding-v4（OpenAI 兼容端点）。
#    ⚠ 必须 check_embedding_ctx_length=False：langchain 默认本地 token 化长度检查会把文本
#    转成 token 数组发给 DashScope，触发 400 InvalidParameter（"input.contents is neither
#    str nor list of str"，grilling 实测）。
def _build_embeddings():
    provider = settings.embedding_provider
    if provider != "aliyun":
        return HuggingFaceEmbeddings(
            model_name="BAAI/bge-base-zh-v1.5",
            model_kwargs={"device": "cpu"},
        )
    from langchain_openai import OpenAIEmbeddings

    if not settings.embedding_api_key:
        raise RuntimeError("embedding_provider=aliyun 但缺 EMBEDDING_API_KEY，请在 backend/.env 配置")
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimensions=settings.embedding_dimensions,
        chunk_size=10,  # 阿里云 batch 上限
        max_retries=3,
        timeout=60,
        check_embedding_ctx_length=False,  # 关键：禁用本地 token 化检查（grilling）
    )


embeddings = _build_embeddings()

# 2. Vector store — Chroma 持久化。collection 名随 provider 派生（语义空间不同，切云须重建）
_COLLECTION_LOCAL = "legal_provisions_cos"  # hnsw:space=cosine：距离分=1-cos
_COLLECTION_CLOUD = "legal_provisions_te4"  # 云端 text-embedding-v4（重建产物，旧库保留可回退）
_QA_COLLECTION_LOCAL = "qa_pairs"
_QA_COLLECTION_CLOUD = "qa_pairs_te4"
COLLECTION_NAME = _COLLECTION_CLOUD if settings.embedding_provider == "aliyun" else _COLLECTION_LOCAL
QA_COLLECTION_NAME = _QA_COLLECTION_CLOUD if settings.embedding_provider == "aliyun" else _QA_COLLECTION_LOCAL
vectorstore = Chroma(
    persist_directory=os.path.join(BASE_DIR, "chroma_db"),
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
)


def format_docs(docs) -> str:
    return "\n\n".join(
        f"[{d.metadata.get('source', '')} {d.metadata.get('article', '')}] {d.page_content}" for d in docs
    )


def make_chain(llm):
    """输入 = 已组装的 messages 列表；输出 = str 流（StrOutputParser 取 content）。"""
    return llm | StrOutputParser()


async def stream_with_retry(make_chain_fn, messages, configs):
    """流式生成 + 空答多配置重试（异步生成器，边收边 yield，真流式）。

    make_chain_fn(i, disabled) -> 可 astream 的链；configs = [(disabled, wait_seconds), ...]。
    依次尝试：首个产生非空内容即返回；全部为空则 yield 结束后返回（调用方据此判定为空）。

    并发门控：整个生成过程占一个全局 LLM 并发位（async 路径），超限排队超时抛
    LLMBusyError → 调用方降级「服务繁忙」。突增时不会无界并发打向供应商。
    """
    async with llm_guard:
        for i, (disabled, wait) in enumerate(configs):
            chain = make_chain_fn(i, disabled)
            chunks = []
            async for piece in chain.astream(messages):
                if piece:
                    chunks.append(piece)
                    yield piece
            if "".join(chunks):
                return
            if wait:
                await asyncio.sleep(wait)


_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def clean_answer(text: str) -> str:
    """去掉模型内联的 <think>...</think> 推理块（thinking 模型可能把思考混进正文）。"""
    if not text:
        return text
    return _THINK_RE.sub("", text).strip()
