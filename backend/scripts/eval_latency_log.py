"""服务端日志时延统计（交付级可复现源）：BENCHMARK.md 首帧 1.3s / 总 3.8s 的数字来源。

从 logs/backend.log 的 legal.chat 记录统计：
- 仅非缓存首问（model != "cache"）
- **剔除 rule 样本（tier=clarify/refuse，零 LLM 即时返回）**——否则污染"首字时延"口径
- 输出 first_ms / ms 的 p50/p90 + 样本数，落盘 docs/benchmark_results/latency_log_<ts>.json

用法：python scripts/eval_latency_log.py [日志路径，默认 logs/backend.log]
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(HERE), "logs", "backend.log")
OUT_DIR = os.path.join(os.path.dirname(HERE), "..", "docs", "benchmark_results")


def _pctl(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(int(p * len(s)), len(s) - 1)]


def main() -> None:
    log_path = sys.argv[1] if len(sys.argv) > 1 else LOG
    firsts, totals = [], []
    excluded = {"cache": 0, "rule": 0}
    for line in open(log_path, encoding="utf-8"):
        if "legal.chat" not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("model") == "cache":
            excluded["cache"] += 1
            continue
        if d.get("tier") in ("clarify", "refuse"):
            excluded["rule"] += 1
            continue
        if "first_ms" not in d:
            continue
        firsts.append(d["first_ms"])
        totals.append(d.get("ms", 0))
    n = len(firsts)
    result = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "log": os.path.basename(log_path),
        "n_generation": n,  # 纯生成（非缓存、非 rule）样本
        "excluded": excluded,
        "first_ms_p50": round(_pctl(firsts, 0.5), 1),
        "first_ms_p90": round(_pctl(firsts, 0.9), 1),
        "first_ms_p99": round(_pctl(firsts, 0.99), 1),
        "total_ms_p50": round(_pctl(totals, 0.5), 1),
        "total_ms_p90": round(_pctl(totals, 0.9), 1),
    }
    print(f"日志 {os.path.basename(log_path)} | 纯生成样本 n={n}（剔除缓存 {excluded['cache']}、rule {excluded['rule']}）")
    print(f"首帧 p50={result['first_ms_p50']}ms p90={result['first_ms_p90']}ms p99={result['first_ms_p99']}ms")
    print(f"总时延 p50={result['total_ms_p50']}ms p90={result['total_ms_p90']}ms")
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"latency_log_{result['ts']}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"落盘：{out}")


if __name__ == "__main__":
    main()
