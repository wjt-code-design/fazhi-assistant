"""跨来源取并集后算「无修复版本」的通报集合。

存在的理由：同一通报在 pip-audit 的 JSON 里可能有多条来源行，其中一行 fix_versions 为空
并不构成「无补丁」。按单行判空会把有修复版本的通报误算进 NOFIX，反之亦不可信。
判据 = 先按 id ∪ aliases 分组、再对组内所有行的 fix_versions 取并集、并集为空才算 NOFIX。

用法：
  python b_no_fix_union.py                      # 用登记表在册的那 4 条做期望，不符则 rc=1
  python b_no_fix_union.py --expect A,B         # 自定义期望
  python b_no_fix_union.py --selftest            # 演示「按单行判空」会得到不同的数

随登记表入库：residual-risk-review.md 里「fix_versions 为空的 N 条」那句的复算件。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SCAN = HERE / "B-candidate-requirements-pip-audit-refresh-20260929-164555.json"

# 登记表在册的无修复版本通报（2026-09-29 由本件算出）
REGISTER_NOFIX = [
    "CVE-2024-7774",
    "CVE-2025-14929",
    "CVE-2026-45830",
    "CVE-2026-45833",
]

CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")


def load_scan(path: Path) -> list[dict]:
    """pip-audit 的 JSON 前面可能带一行 stderr 横幅，从第一个 { 起解析。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.index("{")
    data = json.loads(text[start:])
    rows: list[dict] = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            rows.append(
                {
                    "name": dep.get("name"),
                    "version": dep.get("version"),
                    "ids": {vuln.get("id"), *vuln.get("aliases", [])},
                    "fix": set(vuln.get("fix_versions") or []),
                }
            )
    return rows


def _cves(ids: set[str]) -> set[str]:
    return {x for x in ids if x and CVE_RE.fullmatch(x)}


def group(rows: list[dict]) -> dict[tuple[str, ...], dict]:
    groups: dict[tuple[str, ...], dict] = defaultdict(
        lambda: {"fix": set(), "cves": set(), "sources": 0, "empty_rows": 0}
    )
    for row in rows:
        key = tuple(sorted(x for x in row["ids"] if x))
        g = groups[key]
        g["fix"] |= row["fix"]
        g["cves"] |= _cves(row["ids"])
        g["sources"] += 1
        if not row["fix"]:
            g["empty_rows"] += 1
    return groups


def cluster(rows: list[dict]) -> list[dict]:
    """把「共享任一 ID」的来源行并成同一条通报。

    不能用 id∪aliases 的整组集合作键：同一通报的两行若别名集合不完全相同（一行带 GHSA、
    一行只带 PYSEC），会被拆成两组，各自的 fix 并集都可能为空 ⇒ NOFIX 被算高。
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for row in rows:
        ids = [x for x in row["ids"] if x]
        for x in ids:
            find(x)
        for x in ids[1:]:
            union(ids[0], x)

    groups: dict[str, dict] = {}
    for row in rows:
        ids = sorted(x for x in row["ids"] if x)
        root = find(ids[0]) if ids else "(empty)"
        g = groups.setdefault(
            root, {"fix": set(), "cves": set(), "sources": 0, "empty_rows": 0, "ids": set()}
        )
        g["fix"] |= row["fix"]
        g["cves"] |= _cves(row["ids"])
        g["ids"] |= set(ids)
        g["sources"] += 1
        if not row["fix"]:
            g["empty_rows"] += 1
    return list(groups.values())


def nofix_union(rows: list[dict]) -> set[str]:
    """正确判据：同一条通报的所有来源行，fix 并集为空才算无补丁。"""
    out: set[str] = set()
    for g in cluster(rows):
        if not g["fix"]:
            out |= g["cves"]
    return out


def nofix_per_row(rows: list[dict]) -> set[str]:
    """错误判据（仅 --selftest 用来证明尺子能红）：任一来源行 fix 为空就算。"""
    out: set[str] = set()
    for row in rows:
        if not row["fix"]:
            out |= _cves(row["ids"])
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan", type=Path, default=DEFAULT_SCAN)
    ap.add_argument("--expect", default=None, help="逗号分隔的 CVE，默认取登记表在册那 4 条")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    rows = load_scan(args.scan)
    got = nofix_union(rows)
    expect = (
        set(args.expect.split(","))
        if args.expect
        else set(REGISTER_NOFIX)
    )

    groups = cluster(rows)
    naive = group(rows)
    multi = sum(1 for g in groups if g["sources"] > 1)
    print(f"扫描件：{args.scan.name}")
    print(
        f"来源行数：{len(rows)}  聚类后唯一通报：{len(groups)}  多来源通报：{multi}"
        f"（按整组 ID 集合为键会误拆成 {len(naive)} 组）"
    )
    all_cves: set[str] = set()
    for g in groups:
        all_cves |= g["cves"]
    print(f"唯一 CVE：{len(all_cves)}")
    print(f"NOFIX（并集判据）：{len(got)}  {sorted(got)}")

    rc = 0
    if got != expect:
        print("MISMATCH 期望与现量不符")
        print(f"  仅期望有：{sorted(expect - got)}")
        print(f"  仅现量有：{sorted(got - expect)}")
        rc = 1
    else:
        print("MATCH 与登记表在册集合一致")

    if args.selftest:
        bad = nofix_per_row(rows)
        tup = {x for g in naive.values() if not g["fix"] for x in g["cves"]}
        print("--selftest 三种判据对照（后两种都是本件要防的错）：")
        print(f"  聚类 + 并集（对）：{len(got)}  {sorted(got)}")
        print(f"  整组键 + 并集   ：{len(tup)}  {sorted(tup)}")
        print(f"  单行判空        ：{len(bad)}  {sorted(bad)}")
        alive = []
        if tup != got:
            alive.append(f"整组键会多出 {sorted(tup - got)}")
        if bad != got:
            alive.append(f"单行判空会多出 {sorted(bad - got)}")
        if alive:
            print(f"  SELFTEST_OK 尺子能红：{'；'.join(alive)}")
        else:
            print("  SELFTEST_FAIL 三种判据同解——本件已无区分能力，读数里不存在多来源行")
            rc = 1

    blind = [sorted(g["ids"]) for g in groups if not g["fix"] and not g["cves"]]
    print(
        f"无 CVE 别名且 fix 为空的通报（本件按 CVE 打印时会漏掉的）：{len(blind)}  {blind}"
    )
    print(f"通报总数：{len(groups)}  其中带 CVE 的：{sum(1 for g in groups if g['cves'])}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
