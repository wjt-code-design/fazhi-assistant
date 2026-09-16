# -*- coding: utf-8 -*-
"""evals/retrieval_probe.py — v2 题集检索层双轨探针（零成本：本地 embedding，rerank 按现状）

目的（对齐 2026-09-13 根因报告漏洞 2/3 修正）：
- 正向轨：每案例 1 条 Agent 风格子查询，测 required_laws 各条是否进 top-K（尺子可用性）
- 负向轨：含 forbidden_articles 的案例，测禁引条文是否混进 top-K（混入率——缺陷量化）
- 排序路径记录：settings.rerank_enabled 配置 + 本次探测实际观察（rerank 配额耗尽自动降级
  池内余弦精排时，结论适用于降级路径；云 rerank 路径待配额换班后重跑对比）

用法（backend venv，仓库根）：
  backend\\venv\\Scripts\\python.exe evals\\retrieval_probe.py
输出：evals/probe-results.json（UTF-8，机器可读）+ 控制台 ASCII 统计。
退出码：探针本身跑完=0（混入是缺陷度量不是脚本报错）；脚本异常≠0。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)

from retrieval import _num_to_cn, retrieve  # noqa: E402  # 复用后端条号中文转换
from settings import settings  # noqa: E402

K = 6

CASES_PATH = REPO / "evals" / "frozen-cases-v2.json"

# Agent 风格子查询（每案例 1 条；模拟 planner 拆出的争点问句而非整段案情）
SUBQUERIES: dict[str, str] = {
    "C01": "用人单位以不胜任工作为由解除劳动合同的条件与程序",
    "C02": "休息日加班工资计算标准与举证",
    "C03": "未签书面劳动合同二倍工资的期间计算",
    "C04": "认购定金卖方拒绝签约能否适用定金罚则双倍返还",
    "C05": "承租人迟延支付租金出租人换锁解除合同的条件",
    "C06": "固定总价装修合同单方要求加价停工的违约责任",
    "C07": "借款到期后微信催收和承诺还款对诉讼时效的影响",
    "C08": "保证合同未约定保证期间和保证方式的责任认定",
    "C09": "健身房关门预付卡概不退款格式条款效力",
    "C10": "卖家收钱不发货失联是合同违约还是诈骗",
    "E01": "提起民事诉讼应当符合哪些起诉条件",
    "E02": "朋友借钱不还起诉立案需要什么材料和费用",
    "E03": "装修工程烂尾要求加价停工怎么解除合同追究违约责任",
    "E04": "交通事故对方轻微伤医疗费误工费如何赔偿",
    "E05": "虚假宣传保健品没有效果可以要求退一赔三吗",
    "E06": "公司解散清算时拖欠职工工资的清偿顺序",
    "E07": "商铺租约到期房东要涨价不续租押金如何退还",
    "E08": "没有约定还款日期的借款诉讼时效从何时起算",
    "E09": "口头承诺的销售提成公司不发能否要求支付劳动报酬",
    "E10": "民间借贷利率超过多少不受法律保护",
}


def main() -> int:
    cases = {c["id"]: c for c in json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]}
    rerank_enabled = bool(settings.rerank_enabled)
    results: list[dict] = []
    n_req = n_req_hit = n_forb = n_forb_contam = 0

    for cid, q in SUBQUERIES.items():
        case = cases[cid]
        docs = retrieve(q, k=K)
        meta = [((d.metadata or {}).get("source", ""), (d.metadata or {}).get("article", "")) for d in docs]
        top = [f"{s}#{a}" for s, a in meta]

        req_hits = {}
        for src, n in case.get("required_laws", []):
            art = f"第{_num_to_cn(n)}条"
            n_req += 1
            hit = (src, art) in meta
            req_hits[f"{src}#{art}"] = hit
            n_req_hit += int(hit)

        forb_contam = {}
        for src, n in case.get("forbidden_articles", []):
            art = f"第{_num_to_cn(n)}条"
            n_forb += 1
            contam = (src, art) in meta
            forb_contam[f"{src}#{art}"] = contam
            n_forb_contam += int(contam)

        results.append({
            "case": cid, "query": q, "top_k": top,
            "required_hits": req_hits, "forbidden_contamination": forb_contam,
        })
        print(f"[{cid}] req {sum(req_hits.values())}/{len(req_hits)} forb {sum(forb_contam.values())}/{len(forb_contam)}")

    out = {
        "probe": "evals-v2-retrieval",
        "k": K,
        "rerank_config_enabled": rerank_enabled,
        "path_note": ("rerank 云配额已见耗尽告警时实际走池内余弦精排（降级路径）；"
                      "云 rerank 路径行为待配额换班后重跑对比"),
        "summary": {
            "required_total": n_req, "required_in_topk": n_req_hit,
            "required_recall_rate": round(n_req_hit / n_req, 4) if n_req else None,
            "forbidden_total": n_forb, "forbidden_contaminated": n_forb_contam,
            "forbidden_contam_rate": round(n_forb_contam / n_forb, 4) if n_forb else None,
        },
        "per_case": results,
    }
    (REPO / "evals" / "probe-results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    s = out["summary"]
    print(f"DONE required {s['required_in_topk']}/{s['required_total']} "
          f"recall={s['required_recall_rate']} forb {s['forbidden_contaminated']}/{s['forbidden_total']} "
          f"contam={s['forbidden_contam_rate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
