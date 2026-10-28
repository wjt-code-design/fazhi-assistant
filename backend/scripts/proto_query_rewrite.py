"""查询改写原型（2026-10-25，只做实验，不接生产）。

目的：验证「口语化问句 → 补法律术语」能否救回检索失败样例。
对 data/eval_set_gen_all.json 里的指定题号：原问 / 改写问 / 原问+改写 三种检索，
比较期望条文的 rank 与 recall@4。结果落盘 docs/benchmark_results/query_rewrite_proto_<ts>.json。

用法：backend\\venv\\Scripts\\python.exe backend\\scripts\\proto_query_rewrite.py [--ids 101,103,...]
"""

import json
import os
import sys
import time

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
sys.path.insert(0, HERE)
os.chdir(BACKEND)
load_dotenv(os.path.join(BACKEND, ".env"))

from _judge import pick_text_llm  # noqa: E402

from retrieval import _rerank_docs, retrieve  # noqa: E402

DATA = os.path.join(BACKEND, "..", "data", "eval_set_gen_all.json")
OUT_DIR = os.path.join(BACKEND, "..", "docs", "benchmark_results")
DEFAULT_IDS = [101, 103, 108, 113, 117]

_REWRITE_PROMPT = (
    "你是法律检索查询改写器。把用户的口语问题改写成适合法条检索的查询：\n"
    "- 保留原问题的全部事实要素（主体、行为、标的、诉求）\n"
    "- 补上最可能对应的法律术语（如「送东西反悔」→「赠与 撤销」）\n"
    "- 只输出一行查询词，不要解释、不要编号、不要引号\n"
    "- 不要编造具体条号"
)


def rewrite(llm, q: str) -> str:
    r = llm.invoke([SystemMessage(content=_REWRITE_PROMPT), HumanMessage(content=q)])
    return str(r.content or "").strip().splitlines()[0][:120]


def rank_of(docs, arts):
    for i, d in enumerate(docs):
        if d.metadata.get("article") in arts:
            return i + 1
    return None


def main():
    ids = DEFAULT_IDS
    cases = {c["id"]: c for c in json.load(open(DATA, encoding="utf-8"))}
    if "--all" in sys.argv:
        ids = sorted(cases)
    elif "--ids" in sys.argv:
        ids = [int(x) for x in sys.argv[sys.argv.index("--ids") + 1].split(",")]
    llm = pick_text_llm()
    rows = []
    for i in ids:
        c = cases[i]
        q = c["question"]
        q2 = rewrite(llm, q)
        runs = {}
        docs_map = {}
        variants = (("orig", q), ("rewrite", q2))
        if len(ids) <= 10:  # 全量只跑 orig/rewrite，省一半检索
            variants += (("both", f"{q} {q2}"),)
        for name, query in variants:
            docs = retrieve(query, k=6)
            docs_map[name] = docs
            runs[name] = {
                "query": query,
                "rank": rank_of(docs, set(c["expected_articles"])),
                "top4": [f"{d.metadata.get('source')}第{d.metadata.get('article')}条" for d in docs[:4]],
            }
        if len(ids) <= 20:  # 小样本额外测 RRF 融合（避免二选一丢召回的候选方案）
            scores = {}
            for name in ("orig", "rewrite"):
                for j, d in enumerate(docs_map[name]):
                    key = (d.metadata.get("source", ""), d.metadata.get("article", ""))
                    scores[key] = scores.get(key, 0) + 1 / (60 + j + 1)
            fused = [k for k, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
            rank = next((j + 1 for j, k in enumerate(fused) if k[1] in set(c["expected_articles"])), None)
            runs["fuse"] = {"query": "rrf(orig,rewrite)", "rank": rank, "top4": [f"{s}第{a}条" for s, a in fused[:4]]}
            # 候选并集再 rerank 一次（最接近生产可落地的多查询方案）
            merged, seen = [], set()
            for name in ("orig", "rewrite"):
                for d in docs_map[name]:
                    key = (d.metadata.get("source", ""), d.metadata.get("article", ""))
                    if key not in seen:
                        seen.add(key)
                        merged.append(d)
            ranked = _rerank_docs(q, merged) or merged
            runs["rerank_union"] = {
                "query": "rerank(union(orig,rewrite))",
                "rank": rank_of(ranked[:6], set(c["expected_articles"])),
                "top4": [f"{d.metadata.get('source')}第{d.metadata.get('article')}条" for d in ranked[:4]],
            }
        rows.append({"id": i, "question": q, "expected": c["expected_articles"], **runs})
        print(
            i,
            "orig",
            runs["orig"]["rank"],
            "rewrite",
            runs["rewrite"]["rank"],
            "fuse",
            runs.get("fuse", {}).get("rank"),
            "rerank_union",
            runs.get("rerank_union", {}).get("rank"),
            "|",
            q2,
        )
    ts = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"query_rewrite_proto_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "ids": ids, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("落盘", out)


if __name__ == "__main__":
    main()
