"""相关性评测（基准步骤4）：eval_set 抽 10 例真实问答，LLM judge 打分是否答所问。

判定：0=答非所问 1=部分相关 2=完全相关（准确回答）。通过率 = (1+2) 分占比。
诚实标注：单一 judge（qwen3.7-plus）、无人工金标——相关性是主观度量，数字仅供参考。

用法：python scripts/eval_relevance.py（10 例 × chat + judge ≈ 20 次 LLM）
输出：docs/benchmark_results/relevance_<ts>.json
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import _client  # noqa: E402
import _judge  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "..", "docs", "benchmark_results")
N_SAMPLE = 10


def main() -> None:
    token = _client.login()
    # judge 统一走共享基建 _judge（text 档 qwen3.7-plus + temp=0 + 结构化 JSON 判据）——
    # registry.get() 返回 DEFAULT_KEY 是 omni（vision），报告标注的 judge 必须与实际一致
    llm = _judge.pick_text_llm()
    cases = [c for c in json.load(open(os.path.join(DATA, "eval_set.json"), encoding="utf-8")) if c.get("question")]
    sample = cases[:N_SAMPLE]
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for i, c in enumerate(sample, 1):
        q = c["question"]
        ans = _client.chat(token, q)
        score = _judge.relevance(llm, q, ans)
        rows.append({"q": q[:20], "score": score})
        print(f"[{i}/{len(sample)}] score={score} {q[:22]}")
        time.sleep(1.2)  # 限流 60/min 退避

    n_pass = sum(1 for r in rows if r["score"] >= 1)
    n_full = sum(1 for r in rows if r["score"] == 2)
    result = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "n": len(rows),
        "relevance_rate_ge1": round(n_pass / len(rows), 4),  # 完全/部分相关占比
        "full_relevance_rate": round(n_full / len(rows), 4),  # 完全相关占比
        "note": "单一 judge（qwen3.7-plus，temp=0），无人工金标——相关性主观，仅供参考",
        "scores": [r["score"] for r in rows],
    }
    print(f"\n=== 相关性 ===\n相关（≥1）占比 {result['relevance_rate_ge1']}（{n_pass}/{len(rows)}）| 完全相关 {result['full_relevance_rate']}（{n_full}/{len(rows)}）")
    out = os.path.join(OUT_DIR, f"relevance_{result['ts']}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"结果落盘：{out}")


if __name__ == "__main__":
    main()
