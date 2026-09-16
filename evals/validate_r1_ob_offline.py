"""R1-OB 离线验证（预注册 docs/preregistration-dept-guard-r1-optionB-20260916.md §2.2）。

零模型调用、零付费、零网络。三个部分：

P0 复现（重放器可信度）：以 simulate_filter_r1.py 同口径（同指示词表 + 同 kill 表）
  重算 20 案例基线，断言与 filter-simulation-r1.json 存档逐字段一致。
P1 反例（E01/E04）：真实 Agent run 的 per-issue 判域——生产 R1（issue 问句单源）vs
  R1-OB（tier-1 域码 / tier-2 用户原始问题+issue 问句拼接）。判域函数一律导入生产
  backend/agent/dept_guard.domain_of_text（单一真源）。
P2 回归（20 案例探针）：R1-OB 判域输入（探针数据无 issue 问句 → tier-2 代理 =
  initial_question + query）重放过滤，对比基线：required 误杀必须 0、forbidden
  漏杀不得新增、判域翻转逐例列出。

通过标准（预注册 §2.2，冻结）：反例 2/2 修复 + required 误杀 0 + 无新增 forbidden 漏杀。
退出码：全 PASS=0，否则 1。

运行：backend/venv/Scripts/python.exe evals/validate_r1_ob_offline.py（cwd=backend 或仓库根均可）
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from agent.dept_guard import PROC_LAW_DOMAIN, domain_of_text

# T2（2026-09-16）：复用本脚本时结果不得覆盖历史 validation-result.json——
# 设 R1OB_OUT_DIR 指向新证据目录；缺省保留 20260916 原目录（历史行为不变）。
OUT = Path(os.environ.get("R1OB_OUT_DIR") or (REPO / "dispatch-output" / "r1-ob-offline-20260916"))
PROBE = json.loads((REPO / "evals" / "probe-results.json").read_text(encoding="utf-8"))
CASES = {
    c["id"]: c
    for c in json.loads((REPO / "evals" / "frozen-cases-v2.json").read_text(encoding="utf-8"))["cases"]
}
BASELINE = json.loads((REPO / "evals" / "filter-simulation-r1.json").read_text(encoding="utf-8"))
CE = json.loads((OUT / "counterexamples.json").read_text(encoding="utf-8"))

DOMAIN_CODES = {"civil", "criminal", "administrative", "special-maritime"}
# 反例真实域（勘误后口径，来源 frozen-cases-v2.json forbidden/required 构成）
GROUND_TRUTH = {"E01": "civil", "E04": "civil"}
# D2 模拟：评测 harness 为案例提供的域码字段（现状数据无此字段，验证按设计假设置值）
D2_SIMULATED_CODE = GROUND_TRUTH

# ---- simulate_filter_r1.py 的指示词表与 kill 表（P0 复现专用，逐字拷贝防漂移） ----
SIM_CRIM = ["刑事", "诈骗", "报警", "判刑", "犯罪", "入罪"]
SIM_ADMIN = ["行政", "政府", "处罚", "罚款", "执照", "听证"]
SIM_CIVIL = ["民事", "借款", "买卖", "劳动", "合同", "消费", "赔偿", "时效", "起诉", "装修"]
SIM_FOREIGN = {
    "civil": {"行政诉讼法", "刑事诉讼法"},
    "criminal": {"民事诉讼法", "行政诉讼法"},
    "administrative": {"民事诉讼法"},
}


def sim_domain_of(text: str) -> str:
    crim = any(h in text for h in SIM_CRIM)
    admin = any(h in text for h in SIM_ADMIN)
    civil = any(h in text for h in SIM_CIVIL)
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
    m = ref.split("#", 1)
    return (m[0], m[1]) if len(m) == 2 else (ref, "")


def ob_tier1(meta_code: str | None) -> str | None:
    return meta_code if meta_code in DOMAIN_CODES else None


def ob_tier2(user_q: str, issue_q: str) -> str | None:
    return domain_of_text(f"{user_q or ''} {issue_q or ''}")


def ob_domain(meta_code: str | None, user_q: str, issue_q: str) -> str | None:
    return ob_tier1(meta_code) or ob_tier2(user_q, issue_q)


def dept_guard_removals(refs: list[str], domain: str | None) -> list[str]:
    """生产 filter_docs_by_domain 语义：专属程序法且不在当前域 → 剔除。"""
    if domain is None:
        return []
    out = []
    for ref in refs:
        src, _ = split_ref(ref)
        doms = PROC_LAW_DOMAIN.get(src)
        if doms is not None and domain not in doms:
            out.append(ref)
    return out


failures: list[str] = []
report: dict = {"P0": {}, "P1": {}, "P2": {}}

# ================= P0 复现 =================
stats = {"forb_killed": 0, "forb_kept": 0, "req_killed": 0, "req_kept": 0, "noise_removed": 0, "kept": 0}
per_case = []
for row in PROBE["per_case"]:
    cid = row["case"]
    text = row["query"] + (CASES[cid].get("domain") or "") + (CASES[cid].get("initial_question") or "")
    dom = sim_domain_of(text)
    kill = SIM_FOREIGN.get(dom, set())
    req_keys = set(row["required_hits"])
    forb_keys = set(row["forbidden_contamination"])
    removed = []
    for ref in row["top_k"]:
        src, _ = split_ref(ref)
        if src in kill:
            removed.append(ref)
            if ref in forb_keys:
                stats["forb_killed"] += 1
            elif ref in req_keys and row["required_hits"][ref]:
                stats["req_killed"] += 1
            else:
                stats["noise_removed"] += 1
        else:
            stats["kept"] += 1
            if ref in forb_keys and row["forbidden_contamination"][ref]:
                stats["forb_kept"] += 1
            if ref in req_keys and row["required_hits"][ref]:
                stats["req_kept"] += 1
    per_case.append({"case": cid, "domain": dom, "removed": removed})

stored = BASELINE["R1"]
repro_ok = all(stats[k] == stored[k] for k in stats) and all(
    a["case"] == b["case"] and a["domain"] == b["domain"] and a["removed"] == b["removed"]
    for a, b in zip(per_case, BASELINE["per_case"])
)
report["P0"] = {"reproduced": repro_ok, "recomputed": stats, "stored": stored}
print(f"[P0] 基线复现：{'PASS' if repro_ok else 'FAIL'} {stats}")
if not repro_ok:
    failures.append("P0 基线复现不一致——重放器与 simulate_filter_r1.py 口径漂移")

# ================= P1 反例 =================
p1: dict = {}
for case in ("E01", "E04"):
    user_q = CE[case]["user_question"]
    issues = CE[case]["issues"]
    old = [domain_of_text(i["question"]) for i in issues]
    t2 = [ob_tier2(user_q, i["question"]) for i in issues]
    t1 = ob_tier1(D2_SIMULATED_CODE[case])
    forb = CASES[case]["forbidden_articles"]
    forb_refs = [f"{law}#{art}" for law, art in forb]
    # forbidden 全部为「他域专属程序法 or 实体法」分类（相对真实域）
    truth = GROUND_TRUTH[case]
    killable = [r for r in forb_refs if split_ref(r)[0] in PROC_LAW_DOMAIN and truth not in PROC_LAW_DOMAIN[split_ref(r)[0]]]
    unkillable = [r for r in forb_refs if r not in killable]
    p1[case] = {
        "user_question": user_q,
        "old_domain_per_issue": old,
        "ob_tier2_per_issue": t2,
        "ob_tier1": t1,
        "forbidden": forb_refs,
        "forbidden_killable_under_truth": killable,
        "forbidden_out_of_r1ob_scope": unkillable,  # 实体法永不过滤（设计边界）
    }
    print(f"[P1] {case}: old={old} tier2={t2} tier1={t1}")
    print(f"     forbidden={forb_refs} → OB 域下可滤={killable} 超范围(实体法)={unkillable}")

# E01 断言：旧口径存在 None 漏网；tier-2 全部 issue → civil；forbidden 属可滤程序法
e01 = p1["E01"]
if not (any(d is None for d in e01["old_domain_per_issue"])):
    failures.append("E01 旧口径未见 None 漏网——与 DB 取证结论矛盾，需复查数据")
if not (all(d == "civil" for d in e01["ob_tier2_per_issue"])):
    failures.append(f"E01 tier-2 未全 civil：{e01['ob_tier2_per_issue']}")
if e01["forbidden_killable_under_truth"] != e01["forbidden"]:
    failures.append(f"E01 forbidden 未全落在可滤集：{e01['forbidden_killable_under_truth']}")
# E04 断言：tier-2 单独不足（issue 含行政指示词）；tier-1 修复；run 池内实际污染
# （行政诉讼法/行政复议法——accept-r1-dept-law-filter-20260914.md §E04）在 OB civil 域下全部可滤
e04 = p1["E04"]
if "administrative" not in e04["ob_tier2_per_issue"]:
    failures.append("E04 tier-2 预期仍判 administrative（双域文本陷阱）未复现，需复查")
if e04["ob_tier1"] != "civil":
    failures.append(f"E04 tier-1 未判 civil：{e04['ob_tier1']}")
run_contamination = ["行政诉讼法", "行政复议法"]
pool = set(CE["E04"].get("evidence_law_names", []))
for law in run_contamination:
    if law not in pool:
        failures.append(f"E04 证据池未见污染法 {law}——反例前提不成立，需复查池数据")
        continue
    doms = PROC_LAW_DOMAIN.get(law)
    if doms is None or "civil" in doms:
        failures.append(f"E04 污染法 {law} 在 OB tier-1 civil 域下不可滤——守卫对其无效")
# E01 池内同样核对污染法存在性（行诉法家族曾入池，probe 与 run 双口径）
e01_pool = set(CE["E01"].get("evidence_law_names", []))
if "行政诉讼法" not in e01_pool:
    failures.append("E01 证据池未见行政诉讼法——反例前提需复查")

# ================= P2 回归 =================
p2_cases = []
totals = {"req_killed": 0, "forb_kept_base": 0, "forb_kept_ob": 0, "forb_killed_base": 0, "forb_killed_ob": 0}
flips = []
for row in PROBE["per_case"]:
    cid = row["case"]
    initial_q = CASES[cid].get("initial_question") or ""
    base_dom = sim_domain_of(row["query"] + (CASES[cid].get("domain") or "") + initial_q)
    ob_dom = ob_domain(None, initial_q, row["query"])  # 探针无域码→tier-1 跳过；无 issue 问句→tier-2 代理
    req_keys = set(row["required_hits"])
    forb_keys = set(row["forbidden_contamination"])
    rem_base = set(dept_guard_removals(row["top_k"], base_dom))
    rem_ob = set(dept_guard_removals(row["top_k"], ob_dom))
    rk_ob = sum(1 for r in rem_ob if r in req_keys and row["required_hits"][r])
    fk_base = sum(1 for r in row["top_k"] if r in forb_keys and row["forbidden_contamination"][r] and r not in rem_base)
    fk_ob = sum(1 for r in row["top_k"] if r in forb_keys and row["forbidden_contamination"][r] and r not in rem_ob)
    kd_base = sum(1 for r in rem_base if r in forb_keys and row["forbidden_contamination"][r])
    kd_ob = sum(1 for r in rem_ob if r in forb_keys and row["forbidden_contamination"][r])
    totals["req_killed"] += rk_ob
    totals["forb_kept_base"] += fk_base
    totals["forb_kept_ob"] += fk_ob
    totals["forb_killed_base"] += kd_base
    totals["forb_killed_ob"] += kd_ob
    if base_dom != ob_dom:
        flips.append({"case": cid, "base": base_dom, "ob": ob_dom})
    p2_cases.append(
        {
            "case": cid,
            "base_domain": base_dom,
            "ob_domain": ob_dom,
            "removed_base": sorted(rem_base),
            "removed_ob": sorted(rem_ob),
            "req_killed_ob": rk_ob,
        }
    )
report["P2"] = {"totals": totals, "flips": flips, "per_case": p2_cases}
print(f"[P2] required 误杀={totals['req_killed']}  forbidden 漏杀 base→ob：{totals['forb_kept_base']}→{totals['forb_kept_ob']}  杀死 base→ob：{totals['forb_killed_base']}→{totals['forb_killed_ob']}")
print(f"[P2] 判域翻转 {len(flips)} 例：{flips}")
if totals["req_killed"] != 0:
    failures.append(f"P2 required 误杀 {totals['req_killed']} ≠ 0")
if totals["forb_kept_ob"] > totals["forb_kept_base"]:
    failures.append(f"P2 forbidden 漏杀新增：{totals['forb_kept_base']}→{totals['forb_kept_ob']}")

# ================= 裁决 =================
p1_pass = not any(f.startswith(("E01", "E04")) for f in failures)
report["P1"]["verdict"] = "PASS" if p1_pass else "FAIL"
report["failures"] = failures
verdict = "PASS" if not failures else "FAIL"
report["verdict"] = verdict
print(f"\n=== R1-OB 离线验证裁决：{verdict} ===")
for f in failures:
    print("FAIL:", f)

(OUT / "validation-result.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
)
sys.exit(0 if verdict == "PASS" else 1)
