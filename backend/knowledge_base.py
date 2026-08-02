import json
import os

# 建库/种子阶段需联网下载模型（缓存缺失时）；显式关闭离线模式，覆盖 rag_chain 的运行期离线默认。
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_core.documents import Document

from rag_chain import vectorstore

# 数据路径锚定到项目根目录，避免依赖启动目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "laws.json")


def build(json_path: str = DATA_PATH):
    with open(json_path, encoding="utf-8") as f:
        laws = json.load(f)

    # 幂等：只删除旧的种子条文（origin=seed），保留管理员上传/手动添加的内容
    try:
        existing = vectorstore._collection.get(where={"origin": "seed"})
        if existing["ids"]:
            vectorstore._collection.delete(ids=existing["ids"])
    except Exception:
        pass

    docs = [
        Document(
            page_content=f"{law['title']} {law['article_number']}\n{law['content']}",
            metadata={
                "source": law["title"],
                "article": law["article_number"],
                "category": law.get("category", ""),
                "origin": "seed",
                # 时效种子（阶段1占位，阶段5治理；None/缺失 coerce 成空串，Chroma 不接受 None）
                "effective_from": law.get("effective_from") or "",
                "effective_to": law.get("effective_to") or "",
                "status": law.get("status") or "现行",
            },
        )
        for law in laws
    ]
    vectorstore.add_documents(docs)
    print(f"已入库 {len(docs)} 条种子条文（origin=seed，可安全重跑）")


if __name__ == "__main__":
    build()
