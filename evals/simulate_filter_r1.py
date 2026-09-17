# -*- coding: utf-8 -*-
"""部门法过滤规则离线模拟（修复预注册的数据步骤，零成本重放 probe-results.json）。

规则 R1「程序法家族隔离」（保守三段）：
- 案例判域：query+题面含刑事指示词（不含"违约/民事"）→ criminal；含行政指示词 → administrative；
  否则 civil；指示词多域冲突 → mixed（不过滤，行为不变）。
- 过滤：仅当判域明确时，从检索结果剔除「他域专属程序法」条文：
    civil 域剔 行政诉讼法/刑事诉讼法；criminal 域剔 民事诉讼法/行政诉讼法；
    administrative 域剔 民事诉讼法（保守：刑事程序在行政案保留——行刑衔接真实存在）。
- 实体法（民法典/刑法/劳动法…）永不过滤（跨域实体适用是真实法律场景，交给 writer/verifier）。

输出：forbidden 杀死数 / required 误杀数 / top-k 非金标条文的移除分布。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBE = json.loads((REPO / "evals" / "probe-results.json").read_text(encoding="utf-8"))
CASES = {c["id"]: c for c in json.loads((REPO / "evals" / "frozen-cases-v2.json").read_text(encoding="utf-8"))["cases"]}

FOREIGN = {
    "civil": {"行政诉讼法", "刑事诉讼法"},
    "criminal": {"民事诉讼法", "行政诉讼法"},
    "administrative": {"民事诉讼法"},
}
CRIM_HINTS = ["刑事", "诈骗", "报警", "判刑", "犯罪", "入罪"]
ADMIN_HINTS = ["行政", "政府", "处罚", "罚款", "执照", "听证"]
CIVIL_HINTS = ["民事", "借款", "买卖", "劳动", "合同", "消费", "赔偿", "时效", "起诉", "装修"]


def domain_of(case_id: str, query: str) -> str:
    text = (query or "") + (CASES[case_id].get("domain") or "") + (CASES[case_id].get("initial_question") or "")
    crim = any(h in text for h in CRIM_HINTS)
    admin = any(h in text for h in ADMIN_HINTS)
    civil = any(h in text for h in CIVIL_HINTS)
    flags = int(crim) + int(admin) + int(civil)
    if flags > 1:
        return "mixed"
    if crim:
        return "criminal"
    if admin:
        return "administrative"
    if civil:
        return "civil"
    return "mixed"


def split_ref(ref: str) -> tuple[str, str]:
    m = re.match(r"^(.+?)#(.+)$", ref)
    return (m.group(1), m.group(2)) if m else (ref, "")


def main() -> int:
    stats = {"forb_killed": 0, "forb_kept": 0, "req_killed": 0, "req_kept": 0, "noise_removed": 0, "kept": 0}
    per_case = []
    for row in PROBE["per_case"]:
        cid = row["case"]
        dom = domain_of(cid, row["query"])
        kill_set = FOREIGN.get(dom, set())
        req_keys = set(row["required_hits"])
        forb_keys = set(row["forbidden_contamination"])
        removed = []
        for ref in row["top_k"]:
            src, art = split_ref(ref)
            if src in kill_set:
                removed.append(ref)
                if ref in forb_keys:
                    stats["forb_killed"] += 1
                elif ref in req_keys and row["required_hits"][ref]:
                    stats["req_killed"] += 1  # 误杀原本命中的 required
                else:
                    stats["noise_removed"] += 1
            else:
                stats["kept"] += 1
                if ref in forb_keys and row["forbidden_contamination"][ref]:
                    stats["forb_kept"] += 1  # 混入漏杀
                if ref in req_keys and row["required_hits"][ref]:
                    stats["req_kept"] += 1
        per_case.append({"case": cid, "domain": dom, "removed": removed})
    print(json.dumps({"R1": stats, "n_cases": len(per_case)}, ensure_ascii=False))
    for pc in per_case:
        if pc["removed"]:
            print(f"  {pc['case']} [{pc['domain']}] remove: {', '.join(pc['removed'])}")
    (REPO / "evals" / "filter-simulation-r1.json").write_text(
        json.dumps({"R1": stats, "per_case": per_case}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
