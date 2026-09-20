import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "s5-followup-20260920"))
from run_mutations_full import failed_set, suite_stats

T2 = HERE.parent / "t2-slow-20260920"
for name in ("slow-run.xml", "notslow-run.xml"):
    p = T2 / name
    st = suite_stats(p)
    fs = sorted(failed_set(p))
    print(f"{name}: stats={st} failed_n={len(fs)}")
    for f in fs:
        print("   -", f)
