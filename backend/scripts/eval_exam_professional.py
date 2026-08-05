"""professional judge 基线（ADR-014，2026-08-05）：只跑 judge，不做 rerank 重的 recall。

省 gte-rerank-v2：eval_exam 的 recall 计算约 100 次 rerank 调用（烧 30-40 万 token）；
本脚本跳过检索，只 chat（答案多命中 qa_cache 零 Aliyun）+ judge 评分。
judge 模型固定保趋势可比（JUDGE_MODEL=glm-5.1 走百炼 1M 配额，3s/次）。

用法：cd backend && JUDGE_MODEL=glm-5.1 venv/Scripts/python.exe scripts/eval_exam_professional.py
输出：落盘 docs/benchmark_results/exam_professional_<ts>.json + 追加 trend（与 eval_exam 同格式）。
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

import _client  # noqa: E402
import _judge  # noqa: E402

from multi_extract import multi_ok  # noqa: E402 纯逻辑，不拉 BGE

# 注意：不 import eval_exam / quality / retrieval——它们模块级拉 BGE+Chroma（~440MB），
# 与后端双 BGE 造成内存竞争触发 Windows segfault（2026-08-05 实测）。本脚本只 chat+judge。
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "eval_exam.json")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "benchmark_results")


def _append_professional_trend(out: str, ts: str, summary: dict):
    """追加 professional 趋势（与 eval_exam 同格式，内联避免拉 BGE）。"""
    trend_path = os.path.join(os.path.dirname(out), "exam_professional_trend.json")
    trend: list = []
    if os.path.exists(trend_path):
        try:
            with open(trend_path, encoding="utf-8") as f:
                trend = json.load(f)
        except Exception:
            trend = []
    trend.append(
        {
            "ts": ts,
            "professional_avg": summary.get("professional_avg"),
            "freeze_hash": summary.get("freeze_hash"),
            "n": summary.get("n"),
        }
    )
    with open(trend_path, "w", encoding="utf-8") as f:
        json.dump(trend, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"professional 趋势追加：{trend_path}")


def main() -> int:
    cases = json.load(open(DATA, encoding="utf-8"))
    token = _client.login()
    judge_llm = _judge.pick_text_llm()
    rows = []
    prof_sum = 0.0
    multi_sum = 0
    multi_n = 0
    for c in cases:
        q = c["question"]
        try:
            ans = _client.chat(token, q)
        except Exception as e:
            ans = f"[ERR]{e}"
        p = _judge.professional(judge_llm, q, ans)
        prof_sum += p
        # multi_ok（多选全选对，确定性抽取，零成本）：判非多选 → None
        mok = multi_ok(ans or "", c.get("options_verdict"))
        if mok is not None:
            multi_n += 1
            multi_sum += 1 if mok else 0
        rows.append({"id": c["id"], "professional": p, "multi_ok": mok})
        line = f"[{c['id']}] prof={p}"
        if mok is not None:
            line += f" multi={int(mok)}"
        print(line, flush=True)
        time.sleep(1.2)  # 限流退避
    n = len(cases) or 1
    summary = {
        "professional_avg": round(prof_sum / n, 4),
        "judge": os.getenv("JUDGE_MODEL", "") or os.getenv("JUDGE_MODEL_KEY", "") or "qwen3.7-plus",
        "freeze_hash": hashlib.sha256(open(DATA, "rb").read()).hexdigest()[:12],
        "n": n,
    }
    if multi_n:
        summary["multi_ok"] = round(multi_sum / multi_n, 4)
    print(f"\n{json.dumps(summary, ensure_ascii=False)}")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"exam_professional_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    _append_professional_trend(out, ts, summary)
    print(f"落盘：{out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
