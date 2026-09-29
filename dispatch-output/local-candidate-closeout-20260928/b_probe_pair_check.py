"""两场读数的逐条比对：证明「同一版代码复跑，判定/计数/调用方/实参摘要零差异」。

写成脚本而不是 `python -c` 一次性比：README 里那句"逐条零差异"是要被人复跑的，
分析器不入库 = 数字不可核。

比对轴（逐只桩）：verdict / count / dry_runs / 调用方集合 / 实参摘要集合。
另比全场完整性字段：collected、pytest_exitstatus、compile 事件数、net kinds/total、在场模块数、
别名补钉、装桩前已加载模块，以及 junit 用例数（从该场 run 目录里的 junit.xml 现算，不抄打印）。
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
TEMP = Path(r"C:/Users/33393/AppData/Local/Temp")
AXES = ("verdict", "count", "dry_runs", "callers", "arg_samples")
WHOLE_FIELDS = (
    "collected",
    "pytest_exitstatus",
    "compile_event_total",
    "net_event_kinds",
    "net_event_total",
)


def per_target(d: dict) -> dict:
    out = {}
    for r in d["targets"]:
        out[r["id"]] = {
            "verdict": r["verdict"],
            "count": r["count"],
            "dry_runs": r["dry_runs"],
            "callers": sorted(set(r.get("callers") or [])),
            "arg_samples": sorted(set(r.get("arg_samples") or [])),
            "install": r["install"],
            "patched_at": r["patched_at"],
        }
    return out


def junit_count(stamp: str) -> tuple[str, int]:
    xml = TEMP / f"b-probe-run-{stamp}" / "junit.xml"
    if not xml.is_file():
        return (str(xml), -1)
    return (xml.name, sum(1 for _ in ET.parse(str(xml)).getroot().iter("testcase")))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: b_probe_pair_check.py <readA.json> <readB.json>")
        return 2
    pa, pb = Path(argv[0]), Path(argv[1])
    da = json.loads(pa.read_text(encoding="utf-8"))
    db = json.loads(pb.read_text(encoding="utf-8"))

    ta, tb = per_target(da), per_target(db)
    only_a = sorted(set(ta) - set(tb))
    only_b = sorted(set(tb) - set(ta))
    diffs: list[str] = []
    for tid in sorted(set(ta) & set(tb)):
        for ax in AXES:
            if ta[tid][ax] != tb[tid][ax]:
                diffs.append(f"{tid}.{ax}\n      A={ta[tid][ax]}\n      B={tb[tid][ax]}")
    install_diffs = [tid for tid in set(ta) & set(tb) if ta[tid]["install"] != tb[tid]["install"]]
    patched_diffs = [tid for tid in set(ta) & set(tb) if ta[tid]["patched_at"] != tb[tid]["patched_at"]]

    print(f"A = {pa.name}\nB = {pb.name}\n")
    print(f"逐桩比对：{len(set(ta) & set(tb))} 只在两场均出现；A 独有 {only_a} B 独有 {only_b}")
    print(f"  五轴（判定/计数/干跑/调用方/实参摘要）差异 {len(diffs)} 项")
    for line in diffs[:20]:
        print("  DIFF " + line)
    print(f"  install 差异 {install_diffs or '无'}；patched_at 差异 {patched_diffs or '无'}")

    print("\n全场完整性比对：")
    bad = 0
    for f in WHOLE_FIELDS:
        va, vb = da.get(f), db.get(f)
        same = va == vb
        bad += 0 if same else 1
        print(f"  {'same' if same else 'DIFF'}  {f}: A={va} B={vb}")
    ia = {k: v["count"] for k, v in (da.get("imports_watched") or {}).items()}
    ib = {k: v["count"] for k, v in (db.get("imports_watched") or {}).items()}
    print(f"  在场模块数 A={len(ia)} B={len(ib)} 名称集合相同={set(ia) == set(ib)}")
    bad += 0 if set(ia) == set(ib) else 1
    aa, ab = da.get("alias_repointed") or {}, db.get("alias_repointed") or {}
    print(f"  别名补钉 A={sorted(aa)} B={sorted(ab)} 相同={sorted(aa) == sorted(ab)}")
    bad += 0 if sorted(aa) == sorted(ab) else 1
    for f in ("preloaded_app_at_install", "mode", "python", "interpreter", "candidate_tree", "probe"):
        va, vb = da.get(f), db.get(f)
        same = va == vb
        bad += 0 if same else 1
        print(f"  {'same' if same else 'DIFF'}  {f}: A={va} B={vb}")

    sa = pa.name.replace("b-probe-readings-pytest-", "").replace(".json", "")
    sb = pb.name.replace("b-probe-readings-pytest-", "").replace(".json", "")
    ja, jb = junit_count(sa), junit_count(sb)
    print(f"\n  junit 用例数 A={ja[1]} ({ja[0]}) B={jb[1]} ({jb[0]})")
    if ja[1] < 0 or jb[1] < 0:
        print("  提示：junit.xml 已被清理，该轴本轮不可复算（不拿打印值顶替）")
    else:
        if ja[1] != da.get("collected") or jb[1] != db.get("collected"):
            print("  DIFF junit 数 != collected")
            bad += 1

    net_a = set(da.get("net_events") or {})
    net_b = set(db.get("net_events") or {})
    kinds_a = {k.split(" :: ")[0] for k in net_a}
    kinds_b = {k.split(" :: ")[0] for k in net_b}
    print(f"\n  网络事件：A {len(net_a)} 键 / B {len(net_b)} 键；kind 集合相同={kinds_a == kinds_b} {sorted(kinds_a)}")
    print("  （键里带临时端口号，两场必然不同，故只比 kind 集合与计数合计，不比具体键）")

    ok = not diffs and not only_a and not only_b and not bad and not install_diffs and not patched_diffs
    print("\nPAIR CHECK " + ("PASS: 两读数逐条零差异" if ok else "FAIL: 存在上列差异，不得写'零差异'"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
