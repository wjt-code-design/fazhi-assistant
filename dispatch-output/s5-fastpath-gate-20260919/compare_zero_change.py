"""S5 §6-③：默认关 ⇒ 逐字零变化比对。

baseline = 改前树跑出来的 light-baseline-baseline.json
after    = 改后树（开关保持默认 False）跑出来的同名产物
判据：dump_sha256 必须相同；不同时逐条列出差异（条数必须为 0）。

用法（cwd 必须是 backend/）：
    ./venv/Scripts/python.exe ../dispatch-output/s5-fastpath-gate-20260919/compare_zero_change.py after.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str) -> dict:
    p = HERE / name
    return json.loads(p.read_bytes().decode("utf-8"))


def diff_records(base: dict, after: dict) -> list[str]:
    rows = []
    by_id_b = {r["input"]["id"]: r for r in base["records"]}
    by_id_a = {r["input"]["id"]: r for r in after["records"]}
    only_b = sorted(set(by_id_b) - set(by_id_a))
    only_a = sorted(set(by_id_a) - set(by_id_b))
    for k in only_b:
        rows.append(f"仅改前有该样本: {k}")
    for k in only_a:
        rows.append(f"仅改后有该样本: {k}")
    for k in sorted(set(by_id_b) & set(by_id_a)):
        b, a = by_id_b[k]["run1"], by_id_a[k]["run1"]
        if b != a:
            for field in sorted(set(b) | set(a)):
                if b.get(field) != a.get(field):
                    rows.append(f"{k}.{field}: 改前={b.get(field)!r} → 改后={a.get(field)!r}")
    return rows


def main(after_name: str) -> int:
    base = load("light-baseline-baseline.json")
    after = load(after_name)
    rows = diff_records(base, after)
    same_sha = base["dump_sha256"] == after["dump_sha256"]
    print(f"case_count: before={base['case_count']} after={after['case_count']}", flush=True)
    print(f"dump_sha256 before={base['dump_sha256']}", flush=True)
    print(f"dump_sha256 after ={after['dump_sha256']}", flush=True)
    print(f"sha_identical={same_sha}", flush=True)
    print(f"switch_present_in_settings: before={base['switch_present_in_settings']} after={after['switch_present_in_settings']}", flush=True)
    print(f"switch_effective_value: before={base['switch_effective_value']} after={after['switch_effective_value']}", flush=True)
    print(f"nondeterministic: before={base['nondeterministic_cases']} after={after['nondeterministic_cases']}", flush=True)
    print(f"DIFF_COUNT={len(rows)}", flush=True)
    for r in rows:
        print("  DIFF " + r, flush=True)
    (HERE / "zero-change-verdict.txt").write_bytes(
        (
            f"diff_count={len(rows)} sha_identical={same_sha}\n"
            f"before_sha={base['dump_sha256']}\nafter_sha={after['dump_sha256']}\n" + "\n".join(rows) + "\n"
        ).encode("utf-8")
    )
    print("rc=0", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "light-baseline-after.json"))
