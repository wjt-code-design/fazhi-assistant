"""手动质量评测（真实调用模型；默认只跑免费指标，LLM-judge 需 EVAL_LLM_JUDGE=1）。

judge 基建统一在 scripts/_judge.py（text 档 qwen3.7-plus + temperature=0 + 结构化 JSON
判据，替代旧的 "unfaithful" 单字匹配——防推理句误报）。

语义边界：faithfulness 证"答案不违背检索条文、无条文外编造"，不证"答对"
（eval_set 无金标答案；"答对"靠 full 门禁条号断言 + 引用正确率交叉）。

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

import _judge  # noqa: E402
from langchain_core.messages import HumanMessage, SystemMessage

import eval_metrics as M
from llm_registry import registry
from rag_chain import format_docs, make_chain
from retrieval import retrieve

SYS = (
    "你是法律咨询助手，严格依据提供的法律条文回答，引用时标注来源"
    "（如“根据《劳动合同法》第十九条”）；条文不足时说明“根据现有资料无法完整回答”。"
)
DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_set.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")


def main():
    cases = json.load(open(DATA, encoding="utf-8"))
    do_judge = os.getenv("EVAL_LLM_JUDGE", "0") == "1"
    llm = registry.get()
    chain = make_chain(llm)
    judge_llm = _judge.pick_text_llm() if do_judge else None
    rows = []
    rec_sum = cit_ok = faith_ok = 0
    for c in cases:
        docs = retrieve(c["question"], k=4)
        rev_articles = [d.metadata.get("article", "") for d in docs]
        rec = M.recall_at_k(rev_articles, c.get("expected_articles", []))
        rec_sum += rec
        ctx = format_docs(docs)
        msgs = [SystemMessage(content=SYS), HumanMessage(content=f"相关法律条文：\n{ctx}\n\n用户问题：{c['question']}")]
        try:
            ans = str(chain.invoke(msgs))
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
            {"ts": ts, "summary": summary, "judge": "qwen3.7-plus text 档 temp=0" if do_judge else "off", "rows": rows},
            f, ensure_ascii=False, indent=1,
        )
        f.write("\n")
    print(f"落盘：{out}")


if __name__ == "__main__":
    main()
