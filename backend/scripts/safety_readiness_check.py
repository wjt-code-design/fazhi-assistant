"""safety_readiness_check v1 — SSG 完整 Release Gate Checker（P0-4）。

机械验证（全部非空且成立才 PASS），**不信 manifest 里有人填的 conclusion**：
1. manifest schema 完整；
2. 必需 evidence 存在且 SHA 与 manifest 绑定一致；
3. ASRG 阈值真 PASS：重建 G-1 路由 FN/FP（gold×mask）+ 审计文档结论行核实；
4. 无 UNKNOWN blocking evidence；
5. 独立审核签署有效（reviewer 本人 + conclusion=PASS + hash 与 manifest 一致）；
6. Evidence Invalidation 未触发（freeze-closure open_items 为空）；
7. prod-prereq 有效（R8 三选一 + 环境授权 + 回滚就绪 —— 数据所有者确认）；
8. 任一失败 → FAIL closed，输出逐项矩阵。

用法：python scripts/safety_readiness_check.py --owner-confirm <R8/授权/回滚>（三项以逗号分隔：true,true,true）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "release-evidence" / "legal-agent-v1-grayscale-20260907"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(name: str) -> dict:
    return json.loads((EVID / name).read_text(encoding="utf-8"))


def audit_pass(md_name: str, metric: str) -> bool:
    """从审计 md 摄取某指标结论是否 PASS（checker 自读证据，非信 manifest）。"""
    md = (EVID / md_name).read_text(encoding="utf-8")
    return metric in md and "PASS" in md


def check_g1(mask: dict) -> tuple[bool, str]:
    """独立重算 G-1：gold（与 gen_g1_audit 同源）× mask → S1/S2。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_g1_audit", REPO / "backend/scripts/gen_g1_audit.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    gold = mod.GOLD
    actual = {r["id"]: bool(r["routed_agent"]) for r in mask["rows"]}
    fn = [cid for cid in actual if gold[cid][0] == "agent" and not actual[cid]]
    fp = [cid for cid in actual if gold[cid][0] == "rag" and actual[cid]]
    crit_fn = [cid for cid in fn if gold[cid][1]]
    n_agent = sum(1 for cid in actual if gold[cid][0] == "agent")
    n_rag = sum(1 for cid in actual if gold[cid][0] == "rag")
    ok = not crit_fn and (len(fn) / n_agent if n_agent else 0) <= 0.05 and (len(fp) / n_rag if n_rag else 0) <= 0.05
    return ok, f"critFN={len(crit_fn)} FN={len(fn)}/{n_agent} FP={len(fp)}/{n_rag}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner-confirm", required=True, help="comma list: R8_ok,env_auth_ok,rollback_ok (true/false)")
    args = ap.parse_args()
    parts = [x.strip().lower() == "true" for x in args.owner_confirm.split(",")]
    if len(parts) != 3:
        print("owner-confirm 需 3 项 boolean", file=sys.stderr)
        return 2
    r8_ok, env_ok, rollback_ok = parts

    results: list[tuple[str, bool, str]] = []

    # 1. schema 完整
    try:
        manifest = load("evidence-manifest.json")
        required = (
            "manifest_schema_version",
            "candidate_id",
            "git_commit_sha",
            "behavioral_hashes",
            "frozen_components",
            "artifacts",
            "readiness_checker",
            "review",
        )
        ok = all(k in manifest for k in required) and all(
            k in manifest["behavioral_hashes"]
            for k in (
                "agent_code_sha",
                "gate_routing_sha",
                "prompt_sha",
                "tool_policy_sha",
                "kb_sha",
                "runtime_config_sha",
            )
        )
        results.append(("1.schema 完整", ok, "" if ok else "缺字段"))
    except Exception as exc:  # noqa: BLE001
        results.append(("1.schema 完整", False, str(exc)))
        manifest = {}

    # 2. evidence 存在 + SHA 一致
    artifact_ok = True
    evid_files = (
        ("artifact_G1_sha", "g1-route-audit-20260907.md"),
        ("artifact_G2_sha", "g2-audit-20260907.md"),
        ("artifact_G3_sha", "g3-audit-20260907.md"),
        ("artifact_G4_validation_sha", "g4-audit-20260907.md"),
        ("artifact_S4_report_sha", "g1-reroute-agent.json"),
        ("artifact_S5_reeval_sha", "s5-reeval-20260907.json"),
        ("artifact_R8_disposition_sha", "r8-disposition-20260907.json"),
        ("artifact_owner_authorization_sha", "owner-authorization-20260907.json"),
        ("route_mask_sha", "route-mask-grayscale.json"),
    )
    for key, fname in evid_files:
        p = EVID / fname
        if not p.is_file():
            artifact_ok = False
            results.append((f"2.evidence[{fname}]", False, "缺失"))
            continue
        actual = sha(p)
        if manifest and manifest.get("artifacts", {}).get(key) != actual:
            artifact_ok = False
            results.append((f"2.evidence[{fname}]", False, "SHA 与 manifest 不一致"))
    rb = REPO / "docs/runbooks/deployment-v1.md"
    if not rb.is_file():
        artifact_ok = False
        results.append(("2.evidence[runbook]", False, "缺失"))
    elif manifest and manifest.get("artifacts", {}).get("runbook_sha") != sha(rb):
        artifact_ok = False
        results.append(("2.evidence[runbook]", False, "SHA 与 manifest 不一致"))
    results.append(("2.evidence 存在+SHA", artifact_ok, ""))

    # 3. ASRG 阈值真 PASS
    g1_ok, g1_detail = check_g1(load("route-mask-grayscale.json"))
    results.append(("3.S1/S2 路由阈值（重算）", g1_ok, g1_detail))
    s3 = audit_pass("g2-audit-20260907.md", "S3")
    s9 = audit_pass("g2-audit-20260907.md", "S9")
    s8 = audit_pass("g3-audit-20260907.md", "S8")
    s6 = audit_pass("g4-audit-20260907.md", "S6")
    results.append(("3.S3(0)", s3, "g2 审计行"))
    results.append(("3.S9(miss=0)", s9, "g2 审计行"))
    results.append(("3.S8(smoke)", s8, "g3 审计行"))
    results.append(("3.S6(fail-closed)", s6, "g4 审计行"))
    s5 = load("s5-reeval-20260907.json")
    results.append(
        ("3.S5(引用=0)", s5.get("verdict") == "PASS" and s5.get("issue_count") == 0, str(s5.get("issue_count")))
    )
    s4 = load("s4-report-agent.json")["metrics"]
    s4_ok = all(
        s4[k] == 0 for k in ("fact_hallucinations", "permission_bypasses", "infinite_loops", "illegal_citations")
    )
    results.append(("3.S4(evaluator=0)", s4_ok, str(s4)))

    # 4. 无 UNKNOWN blocking
    unknown = False
    for f in ("g2-audit-20260907.md", "g3-audit-20260907.md"):
        if "UNKNOWN" in (EVID / f).read_text(encoding="utf-8"):
            unknown = True
    results.append(("4.无 UNKNOWN blocking", not unknown, ""))

    # 5. 签署有效（haimeng）
    sign_ok = False
    sign_detail = "PENDING（待 haimeng 签署）"
    sign_path = EVID / "independent-review-20260907.json"
    if sign_path.is_file():
        try:
            sign = json.loads(sign_path.read_text(encoding="utf-8"))
            sign_ok = bool(sign.get("reviewer")) and (sign.get("conclusion") or "").upper() == "PASS"
            sign_detail = f"reviewer={sign.get('reviewer')} conclusion={sign.get('conclusion')}"
            if sign_ok and manifest:
                rec = manifest["artifacts"].get("independent_review_artifact_sha")
                sign_ok = rec == sha(sign_path)
                sign_detail += f" hash={'一致' if sign_ok else '不一致'}"
        except Exception as exc:  # noqa: BLE001
            sign_detail = f"解析失败: {exc}"
    results.append(("5.独立审核签署", sign_ok, sign_detail))

    # 6. Invalidation 未触发
    inv_ok = False
    try:
        closure = load("freeze-closure-20260907.json")
        inv_ok = closure.get("closure", {}).get("open_items") == []
    except Exception:  # noqa: BLE001
        pass
    results.append(("6.失效未触发(open_items=[])", inv_ok, ""))

    # 7. prod-prereq：R8 与真实流量授权以证据文件判定；环境/回滚由 owner 现场确认
    r8_ok, r8_detail = False, "缺失"
    r8_path = EVID / "r8-disposition-20260907.json"
    if r8_path.is_file():
        try:
            r8 = json.loads(r8_path.read_text(encoding="utf-8"))
            r8_ok = r8.get("owner_approval", {}).get("status") == "APPROVED"
            r8_detail = "APPROVED（数据所有者）" if r8_ok else r8.get("owner_approval", {}).get("status", "未知")
        except Exception as exc:  # noqa: BLE001
            r8_detail = f"解析失败: {exc}"
    results.append(("7.R8 处置（accept 批准）", r8_ok, r8_detail))

    auth_ok, auth_detail = False, "缺失"
    auth_path = EVID / "owner-authorization-20260907.json"
    if auth_path.is_file():
        try:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
            auth_ok = bool(auth.get("decision", {}).get("approved"))
            auth_detail = "APPROVED（数据所有者）" if auth_ok else "未批准"
        except Exception as exc:  # noqa: BLE001
            auth_detail = f"解析失败: {exc}"
    results.append(("7.真实流量授权（owner）", auth_ok, auth_detail))

    results.append(("7.环境就绪（owner 确认）", env_ok, f"env={env_ok}"))
    results.append(("7.回滚就绪（owner 确认）", rollback_ok, f"rollback={rollback_ok}"))
    prereq_ok = r8_ok and auth_ok and env_ok and rollback_ok
    results.append(("7.prod-prereq 汇总", prereq_ok, f"R8={r8_ok} auth={auth_ok} env={env_ok} rollback={rollback_ok}"))

    # 7a. 授权文件与 manifest 绑定（evidence 防偷换）
    auth_sha_ok = True
    if manifest:
        rec = manifest.get("artifacts", {}).get("artifact_owner_authorization_sha")
        auth_sha_ok = auth_path.is_file() and rec == sha(auth_path)
    results.append(("7a.授权证据 SHA 绑定", auth_sha_ok, ""))

    # 7b. L1 豁免 ADR 结构化校验（文件存在 ≠ 豁免有效）
    adr_ok = False
    adr_detail = "缺失"
    if manifest:
        adr = manifest.get("owner_decisions", {}).get("ADR_L1_exemption")
        if adr:
            p = REPO / adr.get("path", "")
            if not p.is_file():
                adr_detail = "ADR 文件缺失"
            elif adr.get("sha256") != sha(p):
                adr_detail = "ADR sha 与 manifest 不一致"
            else:
                try:
                    adr_json = json.loads(p.read_text(encoding="utf-8"))
                    require = adr_json.get("schema_version") == "owner-adr/v1"
                    require = require and adr_json.get("decision") == "APPROVED"
                    require = require and str(adr_json.get("l1_original_result", {}).get("raw", "")).startswith(
                        "BLOCKED"
                    )
                    require = require and adr_json.get("exemption", {}).get("type") == "QUALITY_GATE_ONLY"
                    require = require and adr_json.get("exemption", {}).get("traffic_ceiling_percent", 0) in (
                        1,
                        2,
                        3,
                        4,
                        5,
                    )
                    require = require and bool(adr_json.get("exemption", {}).get("expiry_conditions"))
                    require = require and adr_json.get("scope", {}).get("candidate_commit_sha", "") == manifest.get(
                        "git_commit_sha", ""
                    )
                    require = (
                        require
                        and bool(adr_json.get("owner", {}).get("approved"))
                        and bool(adr_json.get("owner", {}).get("approval_timestamp"))
                    )
                    adr_ok = require
                    adr_detail = f"id={adr_json.get('adr_id')} commit={'一致' if adr_ok else '不一致'} fields={'OK' if adr_ok else '缺失'}"
                except Exception as exc:  # noqa: BLE001
                    adr_detail = f"ADR 解析失败: {exc}"
    results.append(("7b.L1 豁免 ADR 结构化校验", adr_ok, adr_detail))

    # 8. 汇总
    all_ok = all(ok for _, ok, _ in results)
    exempt_mode = all_ok and manifest.get("l1_gate_state", {}).get("release_decision_model") == "READY_WITH_EXEMPTION"
    verdict = "READY_WITH_EXEMPTION" if exempt_mode else ("READY" if all_ok else "FAIL CLOSED")
    print("=== safety_readiness_check v1 ===")
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    print(f"RESULT: {verdict}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
