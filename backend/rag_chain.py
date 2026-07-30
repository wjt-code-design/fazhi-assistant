"""RAG 基础设施：嵌入 + 向量库 + 文档格式化 + 链工厂。

- LLM 不再在此模块单例化，改由 llm_registry 按"是否带图"路由（文本/视觉）。
- 链的输入为 main 组装好的 messages 列表（含 system/历史/带图或纯文本的最终 human），
  以便视觉模型接收 image_url content 数组。
"""
import os

# 运行期默认离线用本地缓存，避免对 huggingface.co 的在线校验（部分环境 SSL 校验失败）。
# 缓存缺失需回退在线时走 HF_ENDPOINT 镜像；建库/种子脚本会显式置 HF_HUB_OFFLINE=0 覆盖此默认。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Embeddings — BGE-base-zh 本地（CPU）
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-base-zh-v1.5",
    model_kwargs={"device": "cpu"},
)

# 2. Vector store — Chroma 持久化
vectorstore = Chroma(
    persist_directory=os.path.join(BASE_DIR, "chroma_db"),
    embedding_function=embeddings,
    collection_name="legal_provisions",
)


def format_docs(docs) -> str:
    return "\n\n".join(
        f"[{d.metadata.get('source', '')} {d.metadata.get('article', '')}] {d.page_content}"
        for d in docs
    )


def make_chain(llm):
    """输入 = 已组装的 messages 列表；输出 = str 流（StrOutputParser 取 content）。"""
    return llm | StrOutputParser()
