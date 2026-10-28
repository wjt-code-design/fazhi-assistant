"""手动质量评测（走真实 chat API，与其它评测口径一致；LLM-judge 需 EVAL_LLM_JUDGE=1）。

P0-2 修订（code-review）：原先用自定义 SYS + make_chain 直连 chain.invoke，绕过真实
API 的 intent 路由/生产提示词/来源格式化，faithfulness 测的是离线简化管线而非线上
答案。现改用共享 `_client.chat` 走真 API——与一致性/红队/相关性同口径。

口径对齐（2026-08-04 修正，2026-10-27 再修）：judge 的 ctx 必须与服务器生成答案时的
**实际上下文**一致——不是只对齐 k。生产快路径（request_bootstrap.prepare_fast_path）是
`scenario_supplement_docs(q) + retrieve(q, k=10)`（单轮无历史 ⇒ rewritten==q）。
历史实现用 `retrieve(q, k=6)` 且不含 scenario 补充，实测把 59 题 faithfulness 从
0.8644 压低到 0.4407（25 题误判 unfaithful、0 题反向，2026-10-27 T1b 复判）。

judge 基建统一在 scripts/_judge.py（text 档 + temperature=0 + 结构化 JSON 判据，
模型由 LLM_MODELS_JSON 决定，落盘时记录实际模型名）。faithfulness 语义边界：证"答案不违背检索条文、无条文外编造"，不证"答对"
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

# override=True 与 main.py 一致：本机 Machine 作用域存着旧 RERANK_API_KEY，默认不覆盖会让
# 「评测进程」和「被测服务」用两把不同的 key 调 rerank——实测同题期望条文在服务里排第 1，
# 在评测里直接不在结果中（recall@4 0.9562 → 0.8701 全是这个偏差，2026-10-26 定位）。
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

import _client  # noqa: E402
import _judge  # noqa: E402

import eval_metrics as M  # noqa: E402
from rag_chain import format_docs  # noqa: E402
from retrieval import retrieve, scenario_supplement_docs  # noqa: E402

# EVAL_SET 允许切换题库（新增题集用独立文件，不覆盖 28 题回归基线）
DATA = os.environ.get("EVAL_SET") or os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_set.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")


def main():
    cases = json.load(open(DATA, encoding="utf-8"))
    track = os.environ.get("EVAL_TRACK", "")
    if track:
        cases = [c for c in cases if c.get("track", "regression") == track]
    do_judge = os.getenv("EVAL_LLM_JUDGE", "0") == "1"
    # EVAL_NO_CACHE=1：绕过答案缓存，测当前管线的真实生成（2026-10-26）。
    # 默认不绕过是与历史基线同口径；但缓存里可能是旧提示词/旧逻辑生成的答案，
    # 会把「历史答案」当成「当前状态」测。
    no_cache = os.getenv("EVAL_NO_CACHE", "0") == "1"
    token = _client.login()
    judge_llm = _judge.pick_text_llm() if do_judge else None
    rows = []
    rec_sum = cit_ok = faith_ok = 0
    for c in cases:
        q = c["question"]
        docs4 = retrieve(q, k=4)
        rev_articles = [d.metadata.get("article", "") for d in docs4]
        rec = M.recall_at_k(rev_articles, c.get("expected_articles", []))
        rec_sum += rec
        # judge 上下文必须与答案的真实上下文一致：服务器组装顺序
        # `scenario_supplement_docs(q) + retrieve(q, k=10)`（request_bootstrap.py:549,600）。
        # 单轮评测无历史 ⇒ rewrite 不生效，用原问题即可。旧版 k=6 会漏第 7-10 条与场景补充，
        # 把真实在库但不在 k=6 的引用判成 unfaithful（2026-10-27 实测 0.8644→0.4407）。
        docs_ctx = scenario_supplement_docs(q) + retrieve(q, k=10)
        ctx = format_docs(docs_ctx)
        try:
            ans = _client.chat(token, q, no_cache=no_cache)
        except Exception as e:
            ans = f"[ERR]{e}"
        cc = M.citation_correct(ans, c.get("expected_articles", []))
        cit_ok += 1 if cc else 0
        line = f"[{c['id']}] recall@4={rec:.2f} cite_ok={int(cc)}"
        row = {"id": c["id"], "question": q, "recall@4": round(rec, 2), "cite_ok": bool(cc)}
        if do_judge:
            f = _judge.faithful(judge_llm, ctx, ans)
            faith_ok += 1 if f else 0
            row["faithful"] = f
            line += f" faithful={int(f)}"
        rows.append(row)
        line += f" Q={q}"
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
                "dataset": os.path.basename(DATA),
                "answer_cache": "bypass" if no_cache else "allow",
                "summary": summary,
                "judge": _judge.model_label(judge_llm) if do_judge else "off",
                "judge_context": ("scenario_supplement_docs(q) + retrieve(q,k=10)" if do_judge else None),
                "judge_context_note": (
                    "单轮无历史 ⇒ rewritten==q；未含 consumer clause/fraud 与 QA 注入" if do_judge else None
                ),
                "pipeline": "真实 chat API（_client.chat，与一致性/红队/相关性同口径）",
                "rows": rows,
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
        f.write("\n")
    print(f"落盘：{out}")


if __name__ == "__main__":
    main()
