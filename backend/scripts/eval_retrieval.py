"""检索层评测骨架（阶段1种子）。

对 data/eval_set.json 跑 recall@k / 关键词命中，作为检索/切片/embedding 变更后的防回归基线。
仅评估检索，不调用 LLM，离线即可运行。

用法：在 backend/ 下 `python scripts/eval_retrieval.py`（或任意目录，脚本会自定位）。
"""
import json
import os
import sys

# 评测阶段需联网下载模型（缓存缺失时）；显式关闭离线模式，覆盖 rag_chain 的运行期离线默认。
os.environ["HF_HUB_OFFLINE"] = "0"
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from retrieval import retrieve  # noqa: E402

DATA = os.path.join(BACKEND, "..", "data", "eval_set.json")


def norm(s: str) -> str:
    return (s or "").replace(" ", "").replace("\n", "")


def main():
    cases = json.load(open(DATA, encoding="utf-8"))
    hit_src = hit_art = hit_kw = 0
    for c in cases:
        docs = retrieve(c["question"], k=4)
        srcs = {d.metadata.get("source", "") for d in docs}
        arts = {d.metadata.get("article", "") for d in docs}
        text = norm(" ".join(d.page_content for d in docs))
        s = any(e in srcs for e in c.get("expected_sources", []))
        a = any(e in arts for e in c.get("expected_articles", []))
        k = all(norm(kw) in text for kw in c.get("expected_keywords", []))
        hit_src += s
        hit_art += a
        hit_kw += k
        print(f"[{c['id']}] source={int(s)} article={int(a)} keywords={int(k)}  Q={c['question']}")
    n = len(cases) or 1
    print(
        f"\nrecall_source@4={hit_src / n:.2f} recall_article@4={hit_art / n:.2f} "
        f"keyword_hit={hit_kw / n:.2f} (n={n})"
    )


if __name__ == "__main__":
    main()
