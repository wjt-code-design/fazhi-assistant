"""法考题/案例解析评测（阶段0，ADR-012）：让"像律师的专业度"可度量。

确定性指标（不用 LLM，零成本）：
  - recall@k：检索是否召回金标条文（防漏项，如死刑复核 252）
  - cite_ok：回答是否引用了库内条文（防编造，复用 eval_metrics）
  - golden_hit：回答引用是否**命中金标条号**（防"引错条"——引在库但不对题，
    评审点1；归一化比对，确定性判定，不用 LLM judge）
  - refuse_ok：decide 分类 != refuse（防"说不会"回归，自动断言非一次性）

可选（EVAL_LLM_JUDGE=1）：
  - professional：LLM judge 评 0-3（结构/论证/法理主观维度，不含条文适用——
    条号对错由 golden_hit 确定性判，避免"judge 和 LLM 一起错"同频失真，评审点2）

基线题集冻结：eval_exam.json 记录文件 hash——阶段 1/2/3 只在此冻结集对比，
新题走独立文件（eval_exam_v2.json）另建基线（评审点3）。

用法：cd backend && python scripts/eval_exam.py [EVAL_LLM_JUDGE=1]
输出：落盘 docs/benchmark_results/exam_<ts>.json + 打印冻结 hash
"""

import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import _client  # noqa: E402
import _judge  # noqa: E402

import clarify  # noqa: E402
import eval_metrics as M  # noqa: E402
import intent  # noqa: E402
from retrieval import _normalize_article, extract_citations, retrieve  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_exam.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")


def _freeze_hash() -> str:
    """冻结基线题集：记录 eval_exam.json 的 sha256（阶段1/2/3 对比须同一份题集）。"""
    return hashlib.sha256(open(DATA, "rb").read()).hexdigest()[:12]


def _golden_citation_hit(answer: str, expected_articles: list[str]) -> bool:
    """回答引用是否命中金标条号（归一化比对，命中任一即过）。

    防"引错条"：引了库内但语义不对题的条文（如 A 题该引刑法 20，引了刑法 236）。
    extract_citations 抽《法名》第X条 → 归一化（中文数字/阿拉伯）→ 与金标交集。
    """
    cited = {_normalize_article(a) for _, a, _ in extract_citations(answer or "")}
    golds = {_normalize_article(a) for a in expected_articles}
    return bool(cited & golds)


def main() -> int:
    cases = json.load(open(DATA, encoding="utf-8"))
    do_judge = os.getenv("EVAL_LLM_JUDGE", "0") == "1"
    token = _client.login()
    judge_llm = _judge.pick_text_llm() if do_judge else None
    rows = []
    sums = {"recall": 0.0, "cite": 0, "golden": 0, "refuse_ok": 0, "prof": 0}
    for c in cases:
        q = c["question"]
        docs = retrieve(q, k=6)  # 基线：整题检索；阶段1 后选项题改走 retrieve_exam（按触发）
        arts = [d.metadata.get("article", "") for d in docs]
        rec = M.recall_at_k(arts, c.get("expected_articles", []))
        # decide 断言（防"说不会"回归）：真实意图下不得拒答
        it = intent.classify_intent(q)
        st = clarify.decide(it, q, bool(docs), False)
        refuse_ok = st != "refuse"
        try:
            ans = _client.chat(token, q)
        except Exception as e:
            ans = f"[ERR]{e}"
        cc = M.citation_correct(ans, c.get("expected_articles", []))
        golden = _golden_citation_hit(ans, c.get("expected_articles", []))
        row = {
            "id": c["id"], "intent": it, "decide": st,
            "recall@6": round(rec, 2), "cite_ok": bool(cc),
            "golden_hit": bool(golden), "refuse_ok": bool(refuse_ok),
        }
        sums["recall"] += rec
        sums["cite"] += 1 if cc else 0
        sums["golden"] += 1 if golden else 0
        sums["refuse_ok"] += 1 if refuse_ok else 0
        line = f"[{c['id']}] {it}/{st} recall@6={rec:.2f} cite={int(cc)} golden={int(golden)} refuse_ok={int(refuse_ok)}"
        if do_judge:
            p = _judge.professional(judge_llm, q, ans)
            sums["prof"] += p
            row["professional"] = p
            line += f" prof={p}"
        rows.append(row)
        print(line, flush=True)
        time.sleep(1.2)  # 限流 60/min 退避
    n = len(cases) or 1
    summary = {
        "recall@6": round(sums["recall"] / n, 4),
        "cite_ok": round(sums["cite"] / n, 4),
        "golden_hit": round(sums["golden"] / n, 4),
        "refuse_ok": round(sums["refuse_ok"] / n, 4),
        "freeze_hash": _freeze_hash(),
        "n": n,
    }
    if do_judge:
        summary["professional_avg"] = round(sums["prof"] / n, 4)
    print(f"\n{json.dumps(summary, ensure_ascii=False)}")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"exam_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ts": ts,
                "summary": summary,
                "freeze_hash": _freeze_hash(),
                "judge": "qwen3.7-plus text 档 temp=0" if do_judge else "off",
                "pipeline": "真实 chat API（_client.chat）+ 确定性指标（recall/cite/golden/refuse_ok）",
                "rows": rows,
            },
            f, ensure_ascii=False, indent=1,
        )
        f.write("\n")
    print(f"落盘：{out}")
    print(f"基线题集冻结 hash：{_freeze_hash()}（阶段1/2/3 对比须一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
