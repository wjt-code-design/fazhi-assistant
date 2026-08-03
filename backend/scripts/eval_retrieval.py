"""检索层评测（阶段1种子 + 基准步骤5增强）。

对 data/eval_set.json 跑 recall@1/2/4/6 + MRR + 关键词命中，作为检索/切片/embedding
变更后的防回归基线。仅评估检索，不调用 LLM，离线即可运行。结果落盘
docs/benchmark_results/retrieval_<ts>.json（多 k 曲线 / MRR）。

用法：在 backend/ 下 `python scripts/eval_retrieval.py`（或任意目录，脚本会自定位）。
"""

import json
import os
import sys
import time

from dotenv import load_dotenv  # noqa: E402

# 评测阶段需联网下载模型（缓存缺失时）；显式关闭离线模式，覆盖 rag_chain 的运行期离线默认。
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)
# 关键（ADR-011）：settings 只读 os.environ，不读 .env 文件——不显式 load_dotenv 则
# embedding/rerank 全走本地默认，评测会假性复现旧基线。与其它 eval 脚本对齐。
load_dotenv(os.path.join(BACKEND, ".env"))

from retrieval import retrieve  # noqa: E402

DATA = os.path.join(BACKEND, "..", "data", "eval_set.json")
OUT_DIR = os.path.join(BACKEND, "..", "docs", "benchmark_results")
KS = (1, 2, 4, 6)


def norm(s: str) -> str:
    return (s or "").replace(" ", "").replace("\n", "")


def main():
    cases = json.load(open(DATA, encoding="utf-8"))
    n = len(cases) or 1
    recall = {k: 0 for k in KS}
    mrr_sum = 0.0
    hit_kw = 0
    rows = []
    for c in cases:
        docs = retrieve(c["question"], k=max(KS))
        srcs = [d.metadata.get("source", "") for d in docs]
        arts = [d.metadata.get("article", "") for d in docs]
        exp_src = set(c.get("expected_sources", []))
        exp_art = set(c.get("expected_articles", []))
        text = norm(" ".join(d.page_content for d in docs))
        for k in KS:
            recall[k] += int(any(a in exp_art for a in arts[:k]))
        # MRR@6：首个期望条文的最小 rank（k=max(KS)=6 截断——实为 MRR@6 而非全量 MRR）
        rank = next((i + 1 for i, a in enumerate(arts) if a in exp_art), None)
        if rank:
            mrr_sum += 1.0 / rank
        kw = all(norm(kw) in text for kw in c.get("expected_keywords", []))
        hit_kw += kw
        rows.append({"id": c.get("id"), "source_ok": bool(srcs[:4] and any(s in exp_src for s in srcs[:4])), "mrr_rank": rank, "question": c["question"]})
    print(f"样本 n={n}")
    for k in KS:
        print(f"  recall_article@{k} = {recall[k] / n:.3f}")
    print(f"  recall_source@4 = {sum(1 for r in rows if r['source_ok']) / n:.3f}")
    print(f"  MRR@6 = {mrr_sum / n:.3f}")
    print(f"  keyword_hit = {hit_kw / n:.3f}")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"retrieval_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ts": ts,
                "n": n,
                "recall_article": {str(k): round(recall[k] / n, 4) for k in KS},
                "recall_source_4": round(sum(1 for r in rows if r["source_ok"]) / n, 4),
                "mrr_at_6": round(mrr_sum / n, 4),  # k=max(KS)=6 截断，非全量 MRR
                "keyword_hit": round(hit_kw / n, 4),
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
        f.write("\n")
    print(f"结果落盘：{out}")


if __name__ == "__main__":
    main()
