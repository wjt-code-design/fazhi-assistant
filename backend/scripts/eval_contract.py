"""合同评估基线（ADR-014 二期，eval 门控）：量一期文本粘贴合同的真实缺口。

两步运行（Windows 单 BGE 进程纪律：步骤1 的确定性骨架要 BGE 检索，后端也跑 BGE →
双进程冲突，故拆两步，各自独占 BGE）：
  步骤1（先停后端）：python scripts/eval_contract.py --golden
    确定性骨架（build_contract_data，含 BGE 检索）→ 每份合同条款划分/命中条文/rubric，落盘 golden
  步骤2（再起后端）：python scripts/eval_contract.py --report
    调真实 chat API（no_cache）拿报告 → 纯函数 verifier（零 BGE 依赖）判定缺口 → 落盘结果

确定性指标（零 LLM，金标全部由确定性骨架即时生成，防 metric-gaming）：
  - trigger_ok：is_contract_review 触发判定
  - coverage：风险条款覆盖率（漏条款）——报告 R 条目是否覆盖每个真实风险条款
  - fab_count：引号摘录不在合同原文（编造条款）
  - cite_supported：报告条文 ∈ 该点命中集（引对条但不对题）
  - structure_avg：R_n 五要素完整度均值
  - level_match：报告结论等级 vs rubric（防夸大/淡化）

注意：步骤2 严禁 import retrieval / build_contract_data（模块级加载 BGE）。
"""

import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import _client  # noqa: E402

from contract_verify import (  # noqa: E402
    cited_articles,
    coverage,
    fabricated_fragments,
    level_match,
    norm_article,
    parse_risk_entries,
    structure_score,
)

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_contract.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")
GOLDEN = os.path.join(OUT_DIR, "contract_golden.json")


def _load_cases() -> list[dict]:
    return json.load(open(DATA, encoding="utf-8"))["cases"]


# ---------------- 步骤1：确定性骨架（停后端跑，占 BGE） ----------------
def run_golden(cases: list[dict]) -> int:
    # build_contract_data 函数内局部 import retrieval → 触发 BGE 加载（须停后端）
    from domain_rules import build_contract_data, contract_split  # noqa: PLC0415

    golden = []
    for c in cases:
        contract = c["contract"]
        cd = build_contract_data(contract)
        clauses = contract_split(contract)
        hits = sorted(
            {norm_article(d.metadata.get("article", "")) for d in cd.get("docs", []) if d.metadata.get("article")}
        )
        g = {
            "id": c["id"],
            "name": c["name"],
            "rubric_level": cd["level"],
            "basis": cd["basis"],
            "truncated": cd["truncated"],
            "clauses": [[label, seg] for label, seg in clauses],
            "hit_articles": hits,
        }
        golden.append(g)
        print(f"[{c['id']}] {c['name']} rubric={cd['level']} hits={len(hits)} clauses={len(clauses)}", flush=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(GOLDEN, "w", encoding="utf-8") as f:
        json.dump({"ts": time.strftime("%Y%m%d-%H%M%S"), "cases": golden}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"golden 落盘：{GOLDEN}")
    return 0


# ---------------- 步骤2：报告 + 纯函数 verifier（起后端跑，零 BGE） ----------------
def run_report(cases: list[dict]) -> int:
    if not os.path.exists(GOLDEN):
        print(f"缺 golden：{GOLDEN}，先停后端跑 --golden")
        return 2
    by_id = {g["id"]: g for g in json.load(open(GOLDEN, encoding="utf-8"))["cases"]}
    from domain_rules import is_contract_review  # noqa: PLC0415  （顶层无 BGE）

    token = _client.login()
    rows = []
    for c in cases:
        g = by_id.get(c["id"])
        if not g:
            print(f"[{c['id']}] 无 golden，跳过")
            continue
        contract = c["contract"]
        trg = is_contract_review(contract) == c.get("expect_trigger", True)
        try:
            ans = _client.chat(token, contract, no_cache=True)
        except Exception as e:
            ans = f"[ERR]{e}"
        clauses = [tuple(x) for x in g["clauses"]]
        cov, uncovered = coverage(ans, clauses)
        fabs = fabricated_fragments(ans, contract)
        entries = parse_risk_entries(ans)
        struct = [structure_score(e) for e in entries]
        cited = cited_articles(ans)
        hits = set(g["hit_articles"])
        # cited 为空：报告无条文引用（结构/忠实度已由其他指标反映），supported 记 1.0 + note
        supported = len(cited & hits) / len(cited) if cited else 1.0
        row = {
            "id": c["id"],
            "name": c["name"],
            "trigger_ok": trg,
            "rubric_level": g["rubric_level"],
            "level_match": level_match(ans, g["rubric_level"]),
            "coverage": round(cov, 2),
            "uncovered": uncovered,
            "fab_count": len(fabs),
            "fab_frags": fabs[:3],
            "n_entries": len(entries),
            "structure_avg": round(sum(struct) / len(struct), 2) if struct else 0.0,
            "cited_articles": sorted(cited),
            "cite_supported": round(supported, 2),
            "cite_unsupported": sorted(cited - hits),
            "chars": len(contract),
            "answer": ans[:2000],  # 存截断供人工复核（600 太短，R_n 尾条目常被切掉），完整报告不入库
        }
        rows.append(row)
        print(
            f"[{c['id']}] {c['name']} trigger={int(trg)} rubric={g['rubric_level']} lv={row['level_match']} "
            f"coverage={row['coverage']} uncovered={uncovered} fab={len(fabs)} "
            f"cite_sup={row['cite_supported']} unsup={row['cite_unsupported']} struct={row['structure_avg']}",
            flush=True,
        )
        time.sleep(1.2)  # 限流退避
    n = len(rows) or 1
    lm_counts = dict(Counter(r["level_match"] for r in rows))
    summary = {
        "trigger_ok": round(sum(r["trigger_ok"] for r in rows) / n, 4),
        "coverage_avg": round(sum(r["coverage"] for r in rows) / n, 4),
        "fab_total": sum(r["fab_count"] for r in rows),
        "cite_supported_avg": round(sum(r["cite_supported"] for r in rows) / n, 4),
        "structure_avg": round(sum(r["structure_avg"] for r in rows) / n, 4),
        "level_match": lm_counts,
        "n": n,
        "pipeline": "真实 chat API（no_cache）+ 确定性 verifier（零 LLM）",
    }
    print(f"\n{json.dumps(summary, ensure_ascii=False)}")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"contract_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"落盘：{out}")
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--report"
    cases = _load_cases()
    if mode == "--golden":
        return run_golden(cases)
    if mode == "--report":
        return run_report(cases)
    print("用法：--golden（停后端跑，占 BGE）| --report（起后端跑，零 BGE）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
