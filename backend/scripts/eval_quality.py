"""手动质量评测（真实调用模型；默认只跑免费指标，LLM-judge 需 EVAL_LLM_JUDGE=1）。

用法：cd backend && python scripts/eval_quality.py
默认输出：每条 recall@k + citation_correct，及均值。
设 EVAL_LLM_JUDGE=1 时额外用 LLM 判忠实度（每条多 1 次模型调用，消耗 token）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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

JUDGE = "你是评测裁判。仅依据【条文】判断【答案】是否忠实（不含条文外的编造）。只输出一个词：faithful 或 unfaithful。"


def _faithful(llm, context: str, answer: str) -> bool:
    try:
        r = llm.invoke(
            [SystemMessage(content=JUDGE), HumanMessage(content=f"【条文】\n{context}\n\n【答案】\n{answer}")]
        )
        return "unfaithful" not in (r.content or "").lower()
    except Exception:
        return False


def main():
    cases = json.load(open(DATA, encoding="utf-8"))
    do_judge = os.getenv("EVAL_LLM_JUDGE", "0") == "1"
    llm = registry.get()
    chain = make_chain(llm)
    rec_sum = cit_ok = faith_ok = 0
    njudge = 0
    for c in cases:
        docs = retrieve(c["question"], k=4)
        rev_articles = [d.metadata.get("article", "") for d in docs]
        rec = M.recall_at_k(rev_articles, c.get("expected_articles", []))
        rec_sum += rec
        ctx = format_docs(docs)
        msgs = [SystemMessage(content=SYS), HumanMessage(content=f"相关法律条文：\n{ctx}\n\n用户问题：{c['question']}")]
        try:
            ans = chain.invoke(msgs)
        except Exception as e:
            ans = f"[ERR]{e}"
        cc = M.citation_correct(ans, c.get("expected_articles", []))
        cit_ok += 1 if cc else 0
        line = f"[{c['id']}] recall@4={rec:.2f} cite_ok={int(cc)}"
        if do_judge:
            f = _faithful(llm, ctx, ans)
            faith_ok += 1 if f else 0
            njudge += 1
            line += f" faithful={int(f)}"
        line += f" Q={c['question']}"
        print(line)
    n = len(cases) or 1
    tail = f"mean_recall@4={rec_sum / n:.2f} citation_accuracy={cit_ok / n:.2f}"
    if do_judge:
        tail += f" faithfulness={faith_ok / (njudge or 1):.2f}"
    print(f"\n{tail} (n={n})")


if __name__ == "__main__":
    main()
