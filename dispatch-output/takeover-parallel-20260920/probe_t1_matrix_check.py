"""独立复算 T1 的矩阵：不读 matrix.json 的结论，直接从 5 份 junit 重算，再与 matrix.json 对格。"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
T1 = HERE.parent / "t1-flaky-20260920"
sys.path.insert(0, str(HERE.parent / "s5-followup-20260920"))
from run_mutations_full import failed_set, suite_stats

m = json.loads((T1 / "matrix.json").read_text(encoding="utf-8"))
cols = {}
for i in range(1, 6):
    xml = T1 / f"run-{i}.xml"
    st = suite_stats(xml)
    fs = failed_set(xml)
    cols[f"run-{i}"] = {"stats": st, "failed": sorted(fs)}
print("junit 复算：")
for k, v in cols.items():
    print(f"  {k}: tests/err/fail={v['stats']} failed_n={len(v['failed'])}")
mj = json.dumps(m, ensure_ascii=False)
print("matrix.json 顶层键:", list(m)[:6] if isinstance(m, dict) else type(m))
# 对格：junit 里的 failed 用例是否都在 matrix 第 i 列标红
for k, v in cols.items():
    miss = [f for f in v["failed"] if f not in mj]
    print(
        f"  对格 {k}: junit_failed 未出现在 matrix.json 的条数 = {len(miss)}", miss[:3]
    )
print("run-4 failed 集合：")
for f in cols["run-4"]["failed"]:
    print("   -", f)
