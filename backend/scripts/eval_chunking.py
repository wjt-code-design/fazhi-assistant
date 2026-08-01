"""切分对比评测（阶段6）：同一文档「旧段落切分 vs 结构化切分」的检索 recall 对比。

- 数据：data/sample_laws/sample_law.txt（合成测试夹具，非真实法律文本）。
- 方法：两种切分分别写入主 collection（唯一临时 source），对若干带期望条号的查询跑
  retrieve(k=4) 对比 recall@4；结束时清理临时 chunk 并失效缓存，不污染生产数据。
- 门禁：eval_retrieval.py 在 eval_set.json 上的基线（1.00）不受影响（本脚本自清理）。

用法：cd backend && python scripts/eval_chunking.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402
from langchain_core.documents import Document  # noqa: E402

from rag_chain import vectorstore, embeddings  # noqa: E402
import chunking  # noqa: E402
import retrieval  # noqa: E402
import eval_metrics as M  # noqa: E402

FIXTURE = os.path.join(BACKEND, "..", "data", "sample_laws", "sample_law.txt")
OLD_SOURCE = "tmp_chunk_old"
NEW_SOURCE = "tmp_chunk_new"

# 查询 → 期望条号（与 fixture 内容对应）
CASES = [
    ("示例条例的适用范围是什么", ["第二条"]),
    ("订立示例合同需要什么条件", ["第三条"]),
    ("示例条例的生效日期", ["第六条"]),
    ("第五条之一 的内容", ["第五条之一"]),
    ("第一〇一条 变体条文", ["第一〇一条"]),
    ("示例行为的争议解决途径", ["第三条"]),
]

_OLD_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=600, chunk_overlap=80, separators=["\n\n", "\n", "。", "；", ". ", " ", ""]
)


def _cleanup():
    for src in (OLD_SOURCE, NEW_SOURCE):
        try:
            ids = vectorstore._collection.get(where={"source": src})["ids"]
            if ids:
                vectorstore._collection.delete(ids=ids)
        except Exception:
            pass
    retrieval.invalidate()


def main():
    text = open(FIXTURE, encoding="utf-8").read()

    # 旧：段落优先 600/80，无条号元数据
    old_chunks = _OLD_SPLITTER.split_text(text)
    old_docs = [Document(page_content=c, metadata={"source": OLD_SOURCE, "origin": "tmp"}) for c in old_chunks]
    # 新：结构化切分，条号进元数据
    new_chunks = chunking.split_law_document(text)
    new_docs = [
        Document(page_content=c.page_content, metadata={"source": NEW_SOURCE, "origin": "tmp", **c.meta})
        for c in new_chunks
    ]

    try:
        vectorstore.add_documents(old_docs)
        vectorstore.add_documents(new_docs)
        retrieval.invalidate()

        print(f"旧切分：{len(old_chunks)} chunk（无条号元数据）  新切分：{len(new_chunks)} chunk（{len(set(c.meta.get('article','') for c in new_chunks if c.meta.get('article')))} 个条号）\n")
        def _path_recall(q, arts, src):
            docs = retrieval.retrieve(q, k=8)
            tmp = [d for d in docs if d.metadata.get("source") == src][:4]
            return M.recall_at_k([d.metadata.get("article", "") for d in tmp], arts)

        print(f"{'查询':<22} {'期望条号':<10} {'旧 recall@4':<10} {'新 recall@4':<10}")
        old_sum = new_sum = 0.0
        for q, arts in CASES:
            r_old = _path_recall(q, arts, OLD_SOURCE)
            r_new = _path_recall(q, arts, NEW_SOURCE)
            old_sum += r_old
            new_sum += r_new
            print(f"{q:<22} {','.join(arts):<10} {r_old:<10.2f} {r_new:<10.2f}")
        n = len(CASES) or 1
        print(f"\nmean recall@4: 旧={old_sum/n:.2f}  新={new_sum/n:.2f}")
        if new_sum/n < old_sum/n:
            print("警告：结构化切分 recall 低于旧切分，请检查 chunking.py", file=sys.stderr)
            sys.exit(1)
        print("结论：结构化切分 ≥ 旧切分（门禁通过）")
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
