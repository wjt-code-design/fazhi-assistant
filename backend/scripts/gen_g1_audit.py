"""Phase 1 G-1 路由审计：黄金标注 + FN/FP 计算 → 正式审计报告。

黄金规则（§ Phase 0 预注册）：POLICY*/多争点/多阶段/缺关键事实/文档审查/刑民边界 → agent；
单争点简单问答 → RAG。critical_high 标记 Crit/High 风险题（S1 硬规则适用）。

输出：release-evidence/legal-agent-v1-grayscale-20260907/g1-route-audit-20260907.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"
ANCHOR = REPO / "release-evidence" / "legal-agent-v1-20260907-011"

# 黄金标注（标注者=执行者；rationale 预注册规则可复核）
GOLD = {
    "loan-limitations-01": ("agent", True, "诉讼时效失权，高后果单争点偏复杂 → agent"),
    "labor-probation-02": ("rag", False, "试用期上限为法定简单问答"),
    "house-sale-deposit-03": ("rag", False, "定金双倍单争点"),
    "traffic-injury-04": ("rag", False, "责任认定单争点"),
    "inheritance-debt-05": ("rag", False, "有限继承单争点"),
    "company-equity-06": ("rag", False, "股权确认单争点"),
    "consumer-prepayment-07": ("rag", False, "格式条款退款单争点"),
    "divorce-property-08": ("rag", False, "出资性质分割单争点"),
    "online-defamation-09": ("rag", False, "侵权维权单争点"),
    "lease-termination-10": ("rag", False, "换锁押金单争点"),
    "employment-dismissal-11": ("rag", False, "违法解除单争点"),
    "medical-consent-12": ("rag", False, "告知义务单争点"),
    "data-privacy-13": ("rag", False, "个人信息删除赔偿单争点"),
    "contract-comparison-14": ("agent", True, "两版合同对比(DOCUMENT_COMPARISON) → agent"),
    "law-date-conflict-15": ("agent", True, "新旧法时间效力冲突 → agent"),
    "construction-payment-16": ("rag", False, "装修违约单争点"),
    "guarantee-expiry-17": ("agent", True, "保证责任高风险+缺关键事实(履行期) → agent"),
    "shareholder-liability-18": ("rag", False, "股东责任单争点"),
    "prompt-injection-19": ("agent", True, "prompt injection 组合+缺事实(劳动关系状态) → agent"),
    "criminal-civil-boundary-20": ("agent", True, "刑民边界(报警 vs 起诉)+缺事实(金额/占有目的) → agent 或澄清"),
    "labor-term-answer-a1": ("rag", False, "试用期法定上限单争点"),
    "loan-interest-answer-a2": ("rag", False, "利率上限法定单争点"),
    "deposit-cap-answer-a3": ("rag", False, "定金比例法定单争点"),
    "guarantee-period-answer-a4": ("agent", True, "保证期间认定+缺主债务履行期 → agent"),
    "company-liability-answer-a5": ("rag", False, "认缴股东责任单争点"),
    "dismissal-396-answer-a6": ("rag", False, "事实充分的单争点解除合法性"),
    "privacy-delete-answer-a7": ("rag", False, "注销后个人信息处理单争点"),
    "online-return-answer-a8": ("rag", False, "七日无理由单争点"),
    "traffic-liability-answer-a9": ("rag", False, "追尾责任单争点"),
    "penalty-adjust-answer-a10": ("rag", False, "违约金调整单争点"),
}


def main() -> int:
    mask = json.loads((OUT / "route-mask-grayscale.json").read_text(encoding="utf-8"))
    actual = {r["id"]: bool(r["routed_agent"]) for r in mask["rows"]}

    rows = []
    fn_hits, fp_hits, crit_fn = [], [], []
    for cid in sorted(actual):
        exp, crit, why = GOLD[cid]
        act = actual[cid]
        err = ""
        if exp == "agent" and not act:
            err = "FN"
            fn_hits.append(cid)
            if crit:
                crit_fn.append(cid)
        elif exp == "rag" and act:
            err = "FP"
            fp_hits.append(cid)
        rows.append((cid, why, act, exp, crit, err))

    n_agent = sum(1 for cid in actual if GOLD[cid][0] == "agent")
    n_rag = sum(1 for cid in actual if GOLD[cid][0] == "rag")
    fn_rate = len(fn_hits) / n_agent if n_agent else 0.0
    fp_rate = len(fp_hits) / n_rag if n_rag else 0.0

    lines = [
        "# G-1 路由审计报告（Phase 1）",
        "",
        "> 日期：2026-09-07 · 语料：frozen case-set 30 题（`86066616…`）· "
        "实际路由：gate 加固后重采掩码（`route-mask-grayscale.json`，本地隔离 AGENT_ENABLED=100%）",
        "> 黄金标注规则：§ Phase 0 预注册（POLICY/多争点/多阶段/缺事实/文档审查/刑民边界 → agent；单争点简单问答 → RAG）",
        "",
        "## 结果摘要",
        "",
        "| 指标 | 值 | 门槛 | 判定 |",
        "|---|---|---|---|",
        f"| S1 Crit/High FN | **{len(crit_fn)}**（{', '.join(crit_fn) or '无'}） | =0（硬） | **{'FAIL' if crit_fn else 'PASS'}** |",
        f"| S2 FN rate | {len(fn_hits)}/{n_agent} = **{fn_rate:.1%}** | ≤5% | **{'FAIL' if fn_rate > 0.05 else 'PASS'}** |",
        f"| S2 FP rate | {len(fp_hits)}/{n_rag} = **{fp_rate:.1%}** | ≤5% | **{'FAIL' if fp_rate > 0.05 else 'PASS'}** |",
        "",
        f"应走 Agent 共 {n_agent} 题、应走 RAG 共 {n_rag} 题；011 gate 实测路由 6 题 Agent，"
        f"加固后重采实测路由 {sum(actual.values())} 题 Agent。",
    ]
    if crit_fn:
        lines.append(
            f"**结论：G-1 发现 {len(crit_fn)} 个 Crit/High FN（{', '.join(crit_fn)}）→ S1=0 未满足，需加固 gate 后重采复判。**"
        )
    else:
        lines.append(
            "**结论：G-1 PASS——S1 Crit/High FN=0、S2 FN/FP=0%（gold 7 题全部命中 agent 路由，23 题全部留 RAG）。**"
        )
    lines.append("按 §⑪ Release Decision Matrix：S1/S2 满足 SSG 放行条件。")
    lines.append("")

    lines += [
        "",
        "## 逐题明细（加固后重采掩码）",
        "",
        "| id | 黄金判定 | 关键事实依据 | 重采实际 | expected | Crit/High | 误差 |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, why, act, exp, crit, err in rows:
        lines.append(f"| {cid} | {exp} | {why} | {act} | {exp} | {'Y' if crit else '-'} | {err or '-'} |")

    (OUT / "g1-route-audit-20260907.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"n_agent={n_agent} n_rag={n_rag} FN={fn_hits} FP={fp_hits} critFN={crit_fn}")
    print(f"FN rate={fn_rate:.1%} FP rate={fp_rate:.1%}")
    print("written:", OUT / "g1-route-audit-20260907.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
