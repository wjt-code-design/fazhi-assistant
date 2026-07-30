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
    docs = [
        Document(
            page_content=f"{l['title']} {l['article_number']}\n{l['content']}",
            metadata={"source": l["title"], "article": l["article_number"], "category": l.get("category", "")},
        )
        for l in laws
    ]
    vectorstore.add_documents(docs)
    print(f"已入库 {len(docs)} 条")

if __name__ == "__main__":
    build()
