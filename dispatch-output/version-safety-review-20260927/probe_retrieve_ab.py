"""Retrieval A/B across the T1 replacement, on a PRIVATE copy of the real corpus.

Usage: python -B probe_retrieve_ab.py <out.jsonl>
Emits one JSON line per (query, rank) with source/article and a short text head,
so 'before import' and 'after import' runs can be diffed mechanically.
"""

import json
import os
import sys

BACKEND = "C:/Users/33393/Desktop/ai-legal-helper/backend"
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["RERANK_ENABLED"] = "false"
os.environ.setdefault("LLM_API_KEY", "not-for-real-calls")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")
os.environ.setdefault("JWT_SECRET", "vsr-ci-only")

from retrieval import retrieve  # noqa: E402

QUERIES = [
    "民法典第一千二百六十条什么时候施行，同时废止了哪些法律？",
    "物权法侵权责任法民法总则这些旧法还有效吗？",
    "劳动争议申请仲裁的时效期间是多久？",
    "拖欠劳动报酬的仲裁时效怎么算？",
    "劳动仲裁 时效 一年 中断 中止",
    "周末加班，加班费怎么算？",
    "公司违法解除劳动合同，赔偿金怎么算？",
    "机动车发生交通事故，交强险先赔还是商业险先赔？",
]

out = open(sys.argv[1], "w", encoding="utf-8")
for q in QUERIES:
    docs = retrieve(q, k=6)
    for rank, d in enumerate(docs, 1):
        m = d.metadata or {}
        out.write(
            json.dumps(
                {
                    "q": q,
                    "rank": rank,
                    "source": m.get("source"),
                    "article": m.get("article"),
                    "ef": m.get("effective_from"),
                    "et": m.get("effective_to"),
                    "origin": m.get("origin"),
                    "head": (d.page_content or "")[:28],
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    print(f"{q[:18]}... -> " + " | ".join(f"{(d.metadata or {}).get('source')}/{(d.metadata or {}).get('article')}" for d in docs))
out.close()
print("WROTE", sys.argv[1])
