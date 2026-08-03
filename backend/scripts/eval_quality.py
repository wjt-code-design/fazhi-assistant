"""手动质量评测（走真实 chat API，与其它评测口径一致；LLM-judge 需 EVAL_LLM_JUDGE=1）。

P0-2 修订（code-review）：原先用自定义 SYS + make_chain 直连 chain.invoke，绕过真实
API 的 intent 路由/生产提示词/来源格式化，faithfulness 测的是离线简化管线而非线上
答案。现改用共享 `_client.chat` 走真 API——与一致性/红队/相关性同口径，0.93 数字不变
但语义从"简化管线"更正为"真实 API 回答 vs 检索条文"。

judge 基建统一在 scripts/_judge.py（text 档 qwen3.7-plus + temperature=0 + 结构化 JSON
判据）。faithfulness 语义边界：证"答案不违背检索条文、无条文外编造"，不证"答对"
（eval_set 无金标答案）。

用法：cd backend && python scripts/eval_quality.py [EVAL_LLM_JUDGE=1]
输出：落盘 docs/benchmark_results/quality_<ts>.json（不覆盖，时间戳追加）
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import _client  # noqa: E402
import _judge  # noqa: E402

import eval_metrics as M  # noqa: E402
from rag_chain import format_docs  # noqa: E402
from retrieval import retrieve  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_set.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")


def main():
    cases = json.load(open(DATA, encoding="utf-8"))
    do_judge = os.getenv("EVAL_LLM_JUDGE", "0") == "1"
    token = _client.login()
    judge_llm = _judge.pick_text_llm() if do_judge else None
    rows = []
    rec_sum = cit_ok = faith_ok = 0
    for c in cases:
        docs = retrieve(c["question"], k=4)
        rev_articles = [d.metadata.get("article", "") for d in docs]
        rec = M.recall_at_k(rev_articles, c.get("expected_articles", []))
        rec_sum += rec
        ctx = format_docs(docs)
        try:
            ans = _client.chat(token, c["question"])
        except Exception as e:
            ans = f"[ERR]{e}"
        cc = M.citation_correct(ans, c.get("expected_articles", []))
        cit_ok += 1 if cc else 0
        line = f"[{c['id']}] recall@4={rec:.2f} cite_ok={int(cc)}"
        row = {"id": c["id"], "question": c["question"], "recall@4": round(rec, 2), "cite_ok": bool(cc)}
        if do_judge:
            f = _judge.faithful(judge_llm, ctx, ans)
            faith_ok += 1 if f else 0
            row["faithful"] = f
            line += f" faithful={int(f)}"
        rows.append(row)
        line += f" Q={c['question']}"
        print(line, flush=True)
        time.sleep(1.2)  # 限流 60/min 退避（chat 生成路径与 judge 各 1 次调用）
    n = len(cases) or 1
    summary = {
        "mean_recall_4": round(rec_sum / n, 4),
        "citation_accuracy": round(cit_ok / n, 4),
    }
    if do_judge:
        summary["faithfulness"] = round(faith_ok / n, 4)
    print(f"\n{json.dumps(summary, ensure_ascii=False)} (n={n})")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"quality_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ts": ts,
                "summary": summary,
                "judge": "qwen3.7-plus text 档 temp=0" if do_judge else "off",
                "pipeline": "真实 chat API（_client.chat，与一致性/红队/相关性同口径）",
                "rows": rows,
            },
            f, ensure_ascii=False, indent=1,
        )
        f.write("\n")
    print(f"落盘：{out}")


if __name__ == "__main__":
    main()
