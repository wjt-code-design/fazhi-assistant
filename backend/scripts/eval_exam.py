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
import query_understand  # noqa: E402
from multi_extract import _answer_declared_correct  # noqa: E402
from retrieval import (  # noqa: E402
    _normalize_article,
    citation_verify,
    extract_citations,
    retrieve,
    retrieve_exam,
    scenario_supplement_docs,
)
from settings import settings  # noqa: E402

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


def _recall_norm(retrieved_articles: list[str], expected_articles: list[str]) -> float:
    """检索召回（归一化比对）：docs 的 article 元数据 → 归一化集合 → 与金标交集比例。

    与生产口径对齐：scenario 补充/retrieve_exam 的 article 写法（246 / 第二百四十六条）
    经归一化统一为「第246条」，避免 raw 字符串比对失真。
    """
    rev = {_normalize_article(a) for a in retrieved_articles if a}
    exp = [_normalize_article(a) for a in expected_articles if a]
    if not exp:
        return 0.0
    return sum(1 for a in exp if a in rev) / len(exp)


def _production_retrieve(text: str):
    """模拟生产检索路由（main.py Step A）：与线上同款，recall 才反映真实召回。

    - study_aid 具体题 → retrieve_exam（分步：题干主锚 + 每选项补漏）
    - 用户直接贴的选项题（无论 intent）→ retrieve_exam
    - 元问题 → 不检索（短路）
    - 其余 → 整题检索 + scenario_supplement_docs 场景定向补充前置
    """
    it = intent.classify_intent(text)
    is_exam = query_understand._is_exam_question(text)
    if it == "study_aid":
        if settings.feature_study_retrieval and not query_understand.is_meta_study(text):
            return scenario_supplement_docs(text) + retrieve_exam(text)
        return []
    if is_exam:
        # 选项题也前置场景补充（死刑复核/正当防卫题 retrieve_exam 可能漏核心条）
        return scenario_supplement_docs(text) + retrieve_exam(text)
    return scenario_supplement_docs(text) + retrieve(text, k=6)


def main() -> int:
    cases = json.load(open(DATA, encoding="utf-8"))
    do_judge = os.getenv("EVAL_LLM_JUDGE", "0") == "1"
    token = _client.login()
    judge_llm = _judge.pick_text_llm() if do_judge else None
    rows = []
    sums = {"recall": 0.0, "cite": 0, "golden": 0, "refuse_ok": 0, "multi": 0, "multi_n": 0, "prof": 0}
    for c in cases:
        q = c["question"]
        docs = _production_retrieve(q)  # 生产同款路由（retrieve_exam/scenario 补充）
        arts = [d.metadata.get("article", "") for d in docs]
        rec = _recall_norm(arts, c.get("expected_articles", []))
        # decide 断言（防"说不会"回归）：真实意图下不得拒答
        it = intent.classify_intent(q)
        st = clarify.decide(it, q, bool(docs), False)
        refuse_ok = st != "refuse"
        try:
            ans = _client.chat(token, q)
        except Exception as e:
            ans = f"[ERR]{e}"
        # cite_ok：回答**有引用 且 全部真实在库**（防编造，复用生产防线 citation_verify）
        cited_ans = extract_citations(ans or "")
        cc = bool(cited_ans) and not citation_verify(ans or "")
        golden = _golden_citation_hit(ans, c.get("expected_articles", []))
        # multi_ok（决策 8）：多选金标 options_verdict → 回答是否列出全部正确项（防漏答）。
        # 确定性抽取回答判定的正确选项字母（SYSTEM_STUDY 逐项判断格式）。
        ov = c.get("options_verdict") or {}
        true_letters = {k for k, v in ov.items() if v}
        is_multi = len(true_letters) > 1
        declared = _answer_declared_correct(ans or "")
        multi_ok = bool(true_letters and true_letters <= declared) if is_multi else None
        if is_multi:
            sums["multi_n"] += 1
            sums["multi"] += 1 if multi_ok else 0
        row = {
            "id": c["id"], "intent": it, "decide": st,
            "recall@6": round(rec, 2), "cite_ok": bool(cc),
            "golden_hit": bool(golden), "refuse_ok": bool(refuse_ok),
            "multi_ok": multi_ok,
        }
        sums["recall"] += rec
        sums["cite"] += 1 if cc else 0
        sums["golden"] += 1 if golden else 0
        sums["refuse_ok"] += 1 if refuse_ok else 0
        line = f"[{c['id']}] {it}/{st} recall@6={rec:.2f} cite={int(cc)} golden={int(golden)} refuse_ok={int(refuse_ok)}"
        if is_multi:
            line += f" multi={int(bool(multi_ok))}"
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
    if sums["multi_n"]:
        summary["multi_ok"] = round(sums["multi"] / sums["multi_n"], 4)
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
    if do_judge:
        _append_professional_trend(out, ts, summary)
    print(f"基线题集冻结 hash：{_freeze_hash()}（阶段1/2/3 对比须一致）")
    return 0


def _append_professional_trend(out: str, ts: str, summary: dict):
    """professional judge 趋势（2026-08-05）：每次 judge 跑追加 professional_avg，跨跑对比论证深度。"""
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


if __name__ == "__main__":
    sys.exit(main())
