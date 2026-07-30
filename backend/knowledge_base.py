import json
import os
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
            page_content=f"{l['title']} {l['article_number']}\n{l['content']}",
            metadata={
                "source": l["title"],
                "article": l["article_number"],
                "category": l.get("category", ""),
                "origin": "seed",
            },
        )
        for l in laws
    ]
    vectorstore.add_documents(docs)
    print(f"已入库 {len(docs)} 条种子条文（origin=seed，可安全重跑）")


if __name__ == "__main__":
    build()
