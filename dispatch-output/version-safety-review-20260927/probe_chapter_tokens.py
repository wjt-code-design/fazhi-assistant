"""Does the corpus lose the chapter-line / article-number tokens after replacement?

Run once against the pristine copy and once against the copy that already took the
import; both with the same queries. Prints top-6 (source, article) per query.
"""

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
os.environ["CHROMA_DIR"] = sys.argv[1]

from retrieval import retrieve  # noqa: E402

QUERIES = [
    "第十章 建筑物和物件损害责任",
    "建筑物和物件损害责任这一章的最后一条说了什么？",
    "第三章 仲裁 劳动争议",
    "第一千二百六十条",
]
for q in QUERIES:
    docs = retrieve(q, k=6)
    print(f"[{sys.argv[2]}] {q} -> " + " | ".join(f"{(d.metadata or {}).get('source')}/{(d.metadata or {}).get('article')}" for d in docs))
