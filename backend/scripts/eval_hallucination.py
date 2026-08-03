"""幻觉/自检量化（基准步骤3）：eval_set 真实问答 → 引用合法率 + 自检通过率。

定义：
- 答案级引用非法率 = citation_verify(答案) 非空的答案比例（期望 0）
- 引用级合法率 = 在库引用数 / 全部引用数（全部引用应都在库）
- 自检通过率 = quality.self_check(answer, context_present=True).ok 的比例

用法：python scripts/eval_hallucination.py（28 例真实 LLM，约 3-4 分钟）
输出：docs/benchmark_results/hallucination_<ts>.json
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import _client  # noqa: E402

import quality  # noqa: E402
from retrieval import citation_verify, extract_citations  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "..", "docs", "benchmark_results")


def main() -> None:
    token = _client.login()
    cases = json.load(open(os.path.join(DATA, "eval_set.json"), encoding="utf-8"))
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for i, c in enumerate(cases, 1):
        q = c.get("question", "")
        ans = _client.chat(token, q)
        bad = citation_verify(ans)
        cites = extract_citations(ans)
        v = quality.self_check(ans, context_present=True)
        rows.append({"q": q[:24], "cites": len(cites), "bad": bad, "self_check": v.reason or "ok", "answer": ans[:600]})
        print(f"[{i}/{len(cases)}] cites={len(cites):2d} bad={bad!s:20s} self_check={v.reason or 'ok':12s} {q[:18]}")
        if not ans:
            print("  ⚠ 空答案（可能限流/服务异常）")

    total = len(rows)
    cite_all = sum(r["cites"] for r in rows)
    bad_all = sum(len(r["bad"]) for r in rows)
    ans_bad = sum(1 for r in rows if r["bad"])
    self_ok = sum(1 for r in rows if r["self_check"] == "ok")
    result = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "n": total,
        "citation_legal_rate": round(1 - bad_all / cite_all, 4) if cite_all else None,  # 引用级合法率
        "answer_level_bad_cite_rate": round(ans_bad / total, 4),  # 答案级含非法引用比例
        "self_check_pass_rate": round(self_ok / total, 4),
        "total_cites": cite_all,
        "bad_cites": bad_all,
    }
    print("\n=== 量化结果 ===")
    print(f"样本 {total} | 引用级合法率 {result['citation_legal_rate']}（{cite_all - bad_all}/{cite_all}）")
    print(f"答案级含非法引用 {result['answer_level_bad_cite_rate']}（{ans_bad}/{total}）")
    print(f"自检通过率 {result['self_check_pass_rate']}（{self_ok}/{total}）")
    out = os.path.join(OUT_DIR, f"hallucination_{result['ts']}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"summary": result, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"结果落盘：{out}")


if __name__ == "__main__":
    main()
