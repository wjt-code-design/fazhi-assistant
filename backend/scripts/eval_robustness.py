"""措辞鲁棒性评测（组1c，零 LLM）：原句与同义改写的检索 top-k 命中一致性。

判据：原句与改写句各自 retrieve(k=6)，是否都命中同一 expected_articles。
- 稳定：两者命中状态相同（都命中或都不命中）
- 报告 both_hit_rate（都命中，理想态）与 stable_rate（一致率）
bridge 对（依赖 _QUERY_BRIDGE 措辞桥接）单独标注——改写句不含桥接词时可能暴露
桥接依赖（诚实数据，不修饰）。

用法：cd backend && python scripts/eval_robustness.py（离线，不调 LLM）
输出：docs/benchmark_results/robustness_<ts>.json
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from retrieval import retrieve  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "paraphrases.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")
K = 6


def _hits(q: str, expected_articles: list[str]) -> bool:
    docs = retrieve(q, k=K)
    arts = {d.metadata.get("article", "") for d in docs}
    return any(a in arts for a in expected_articles)


def main() -> None:
    pairs = json.load(open(DATA, encoding="utf-8"))["robustness"]
    rows = []
    both_hit = stable = bridge_ok = 0
    bridge_n = 0
    for p in pairs:
        ho = _hits(p["original"], p["expected_articles"])
        hp = _hits(p["paraphrase"], p["expected_articles"])
        s = ho == hp
        stable += s
        both_hit += ho and hp
        if p.get("bridge"):
            bridge_n += 1
            bridge_ok += s
        rows.append(
            {
                "id": p["id"],
                "original": p["original"],
                "paraphrase": p["paraphrase"],
                "orig_hit": ho,
                "para_hit": hp,
                "stable": bool(s),
                "bridge": bool(p.get("bridge")),
            }
        )
        print(f"[{p['id']:>8}] orig={int(ho)} para={int(hp)} stable={int(s)} {p['original'][:20]} → {p['paraphrase'][:20]}", flush=True)
    n = len(rows)
    summary = {
        "n": n,
        "both_hit_rate": round(both_hit / n, 4),
        "stable_rate": round(stable / n, 4),
        "bridge_pairs": bridge_n,
        "bridge_stable": bridge_ok,
        "note": "改写句不含桥接词时，bridge 对暴露措辞桥接依赖（诚实数据）",
    }
    print(f"\nboth_hit_rate={summary['both_hit_rate']}  stable_rate={summary['stable_rate']}（bridge {bridge_ok}/{bridge_n}）")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"robustness_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"落盘：{out}")


if __name__ == "__main__":
    main()
