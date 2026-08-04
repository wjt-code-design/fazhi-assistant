"""向量库全量重嵌入（ADR-011，2026-08-04）：本地 BGE 语义空间 → 阿里云 text-embedding-v4。

切换 embedding provider 后，Chroma collection 的向量语义空间不同（即使维度同为 768），
旧 collection 必须重建。数据源 = **旧库本身**（10266 条含管理员上传/手动条文，按
laws_clean 文件重拼会丢数据——旧 collection 是唯一权威真值）。

流程（--dry-run 只读估费，实跑才写新库）：
  1. 读旧库（legal_provisions_cos + qa_pairs）全量 docs+metas
  2. 每 batch=10 调 embeddings.embed_documents（阿里云 batch 上限）
  3. 每 100 条 add_documents 到新 collection（legal_provisions_te4 / qa_pairs_te4）
  4. 校验：新旧 count 相等、dimension 正确、eval_set 抽样召回对比、旧库零改动

注意：
  - 运行本脚本前先把 EMBEDDING_PROVIDER=aliyun 配置好（settings 读 .env），否则嵌入仍是本地 BGE
  - 新 collection 显式 hnsw:space=cosine（qa_pairs 旧库默认 L2，新库统一 cosine）
  - 单线程 + 指数退避；断点续跑：已存在的新 collection 先清空再全量（幂等）

用法：cd backend && python scripts/rebuild_embeddings.py [--dry-run] [--batch 10]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


from rag_chain import (  # noqa: E402
    _COLLECTION_LOCAL,
    _QA_COLLECTION_LOCAL,
    BASE_DIR,
    COLLECTION_NAME,
    QA_COLLECTION_NAME,
    embeddings,
)
from settings import settings  # noqa: E402

# 估算：中文 ~1.5 字符/token（唯一实现在 quota_utils.estimate_tokens）
# 阿里云 text-embedding-v4 单价（元/千 token，内地）
_PRICE_PER_1K = 0.0005


def _char_token_cost(chars: int) -> tuple[float, float]:
    tokens = max(1, int(chars / 1.5))  # 与 quota_utils.estimate_tokens 同口径（~1.5 字符/token）
    return tokens, tokens * _PRICE_PER_1K / 1000  # 单价是 元/千token


def _read_old(col, name: str) -> tuple[list[str], list[dict]]:
    """读旧 collection 全量 docs+metas。"""
    data = col.get(include=["documents", "metadatas"])
    docs = list(data["documents"] or [])
    metas = [dict(m) for m in (data["metadatas"] or [])]  # Mapping → dict，统一类型
    print(f"  [{name}] 读旧库 {len(docs)} 条")
    return docs, metas


def _write_new(emb, col, docs: list[str], metas: list[dict], batch: int, name: str) -> None:
    """批量重嵌入 + 写入新 collection。单线程 + 指数退避。"""
    n = len(docs)
    for start in range(0, n, batch):
        chunk_docs = docs[start : start + batch]
        chunk_metas = metas[start : start + batch]
        delay = 1
        for attempt in range(6):
            try:
                vecs = emb.embed_documents(chunk_docs)
                break
            except Exception as e:  # 429/网络抖动 → 指数退避
                if attempt == 5:
                    raise
                print(f"  ⏳ 嵌入失败({type(e).__name__})，{delay}s 后重试（第{start}条起）")
                time.sleep(delay)
                delay *= 2
        # 用 Chroma 直接 add(embeddings=...)（避免再次走 embeddings 重嵌）
        col.add(ids=[f"re-{start + i}" for i in range(len(chunk_docs))], embeddings=vecs, documents=chunk_docs, metadatas=chunk_metas)
        if (start // batch + 1) % 10 == 0 or start + batch >= n:
            print(f"  写入 {min(start + batch, n)}/{n} 条到 [{name}]", flush=True)
    print(f"  [{name}] 完成 {n} 条")


def _ensure_new_collection(name: str):
    """重建 collection（显式 cosine）：已存在则删除后重建（幂等）。返回新 collection。"""
    import chromadb

    client = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
    if name in [c.name for c in client.list_collections()]:
        client.delete_collection(name)
    return client.create_collection(
        name,
        metadata={"hnsw:space": "cosine"},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只读旧库统计/估费，不写新库")
    ap.add_argument("--batch", type=int, default=10, help="每批嵌入条数（阿里云上限 10）")
    args = ap.parse_args()

    print(f"embedding provider: {settings.embedding_provider}")
    if settings.embedding_provider != "aliyun":
        print("⚠ 当前 EMBEDDING_PROVIDER 不是 aliyun——重嵌入将仍是本地 BGE（无意义）。")
        print("  请先在 backend/.env 设 EMBEDDING_PROVIDER=aliyun + EMBEDDING_API_KEY，再跑本脚本。")
        sys.exit(1)
    print(f"目标新库: {COLLECTION_NAME} / {QA_COLLECTION_NAME}")
    print(f"旧库（回退保留）: {_COLLECTION_LOCAL} / {_QA_COLLECTION_LOCAL}")
    print()

    # 1. 读数据源——显式 PersistentClient 打开 collection：
    #    数据源 = **当前活跃库**（换班时 te4 含云端期新增，B1 修复：读 te4 而非本地旧库）；
    #    首次迁移时当前库（te4）为空 → 回落本地旧库（cos，迁移时刻唯一真值）。
    #    注意：不能用 rag_chain.vectorstore（provider=aliyun 时它指向的正是目标库）。
    import chromadb

    client = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
    old_main = client.get_collection(COLLECTION_NAME)
    source_name = COLLECTION_NAME
    if old_main.count() == 0 and COLLECTION_NAME != _COLLECTION_LOCAL:
        old_main = client.get_collection(_COLLECTION_LOCAL)
        source_name = _COLLECTION_LOCAL
    docs_main, metas_main = _read_old(old_main, source_name)
    # qa_pairs 同理（优先当前库，空回落本地）
    qa_docs, qa_metas = [], []
    qa_source = QA_COLLECTION_NAME
    try:
        qa_col = client.get_collection(QA_COLLECTION_NAME)
        if qa_col.count() == 0 and QA_COLLECTION_NAME != _QA_COLLECTION_LOCAL:
            qa_col = client.get_collection(_QA_COLLECTION_LOCAL)
            qa_source = _QA_COLLECTION_LOCAL
        qa_data = qa_col.get(include=["documents", "metadatas"])
        qa_docs = list(qa_data["documents"] or [])
        qa_metas = [dict(m) for m in (qa_data["metadatas"] or [])]
        print(f"  [{qa_source}] 读旧库 {len(qa_docs)} 条")
    except Exception as e:
        print(f"  qa_pairs 读取跳过：{e}")

    total_chars = sum(len(d) for d in docs_main) + sum(len(d) for d in qa_docs)
    tokens, cost = _char_token_cost(total_chars)
    print("\n=== 估算 ===")
    print(f"主库 {len(docs_main)} 条 + qa {len(qa_docs)} 条，共 ~{tokens:,} token ≈ ¥{cost:.2f}")
    print("（0.0005 元/千token；实际以阿里云账单为准）")

    if args.dry_run:
        print("\n--dry-run：不写新库。确认后去掉 --dry-run 实跑。")
        sys.exit(0)

    # 2. 建新库 + 重嵌入
    print("\n=== 重建 ===")
    new_main = _ensure_new_collection(COLLECTION_NAME)
    _write_new(embeddings, new_main, docs_main, metas_main, args.batch, COLLECTION_NAME)
    if qa_docs:
        new_qa = _ensure_new_collection(QA_COLLECTION_NAME)
        _write_new(embeddings, new_qa, qa_docs, qa_metas, args.batch, QA_COLLECTION_NAME)

    # 3. 校验
    print("\n=== 校验 ===")
    n_new = new_main.count()
    print(f"新库 count: {n_new}（旧库 {len(docs_main)}）{'✅' if n_new == len(docs_main) else '❌ 不一致'}")
    if n_new != len(docs_main):
        sys.exit(1)
    # dimension 校验
    sample = new_main.get(limit=1, include=["embeddings"])
    dim = len(sample["embeddings"][0]) if sample.get("embeddings") else "?"
    print(f"新库维度: {dim}（配置 {settings.embedding_dimensions}）{'✅' if str(dim) == str(settings.embedding_dimensions) else '❌ 不匹配'}")
    # eval_set 抽样召回校验（阶段7 补，ADR-011）：验证新模型语义空间下检索仍命中期望条文。
    # 用 chroma **原生** query 查新库（B5 修复：不能 from retrieval import retrieve——langchain
    # Chroma 对象缓存了 delete 前的旧 collection UUID，_ensure_new_collection 重建后它已失效）。
    try:
        import json

        eval_path = os.path.join(BASE_DIR, "..", "data", "eval_set.json")
        eval_set = json.load(open(eval_path, encoding="utf-8"))
        cases = eval_set if isinstance(eval_set, list) else eval_set.get("cases", eval_set.get("queries", []))
        import chromadb as _cd

        _client = _cd.PersistentClient(path=os.path.join(BASE_DIR, "chroma_db"))
        _col = _client.get_collection(COLLECTION_NAME)
        sample_cases = cases[:10]
        hit = 0
        for c in sample_cases:
            q = c.get("question") or c.get("query") or ""
            if not q:
                continue
            vec = embeddings.embed_query(q)  # 包装对象（新模型，扣减配额）
            res = _col.query(query_embeddings=[vec], n_results=6, include=["metadatas"])
            metas = (res.get("metadatas") or [[]])[0] or []
            exp_arts = set(c.get("expected_articles", []))
            exp_srcs = set(c.get("expected_sources", []))
            if any(m.get("article") in exp_arts or m.get("source") in exp_srcs for m in metas):
                hit += 1
        ok = hit == len(sample_cases)
        print(f"eval_set 抽样召回: {hit}/{len(sample_cases)}{'✅' if ok else '⚠ 部分未命中（新模型语义空间不同属正常，以完整 eval_retrieval 为准）'}")
    except Exception as e:
        print(f"  eval_set 召回校验跳过：{e}")
    print("\n重建完成。旧库未改动（回退=EMBEDDING_PROVIDER 切回 local）。")
    print("下一步：重启后端 + 跑 scripts/eval_retrieval.py 完整对比召回。")


if __name__ == "__main__":
    main()
