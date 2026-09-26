"""票 T2 的变异跑：报警分支、rc 分档、"整批不写入"这三件事各自必须杀得动。

跑法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/t2-preflight-report-20260926/mutate.py [变异体名...]

分母轴与还原纪律同 `../s0c-note-20260926/mutate.py`（那边踩过两次错标轴的坑，这里直接用修好的写法）。
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TARGET = BACKEND / "scripts" / "import_laws.py"
HERE = pathlib.Path(__file__).resolve().parent
PY = str(BACKEND / "venv" / "Scripts" / "python.exe")
TARGETS = ["tests/test_import_laws_preflight.py", "tests/test_law_versions.py"]

MUTANTS = [
    (
        "M1-no-legacy-warning",
        "删掉 ⚠️ 那一行的产生 ⇒ 并存又变回静默（本票要治的就是这个）",
        "    if plan.legacy_undated:\n        lines.append(LINE_LEGACY.format(n=len(plan.legacy_undated), title=title, article=article))\n",
        "",
    ),
    (
        "M5-always-warn",
        "把 ⚠️ 的条件改成恒真 ⇒ 普通同版本重传也被报成并存（控制腿必须杀得掉）",
        "    if plan.legacy_undated:\n",
        "    if True:\n",
    ),
    (
        "M2-no-exit-1",
        "互不包含不再 sys.exit(1) ⇒ 操作者看到 ✗ 却拿到 rc=0",
        '        for b in blocked:\n            print(f"  - {b}")\n        sys.exit(1)\n',
        "        for b in blocked:\n            print(f\"  - {b}\")\n",
    ),
    (
        "M3-blocked-never-fills",
        "blocked 这一桶永不填 ⇒ 整批照写（「不写入任何内容」那条承诺失效）",
        "        if plan.coexist:\n            blocked.append(",
        "        if False:\n            blocked.append(",
    ),
    (
        "M4-write-before-judging",
        "把「先判后写」改回「边判边写」的可达形状 ⇒ 前几条落库之后才发现后面并存",
        "    if blocked:\n",
        "    if False and blocked:\n",
    ),
]


def run_suite() -> tuple[set[str], int]:
    p = subprocess.run(
        [PY, "-m", "pytest", *TARGETS, "-q", "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    red = {m.group(1) for m in re.finditer(r"^FAILED tests/\S+::(\S+)", out, re.M)}
    ran = 0
    for key in ("passed", "failed", "skipped", "error"):
        hit = re.search(rf"(\d+) {key}", out)
        if hit:
            ran += int(hit.group(1))
    return red, ran


def collected_total() -> int:
    """一次 `--collect-only` 拿真正的 collected 轴作分母常量。"""
    p = subprocess.run(
        [PY, "-m", "pytest", *TARGETS, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    hit = re.search(r"(\d+) tests? collected", out) or re.search(r"collected (\d+) items", out)
    if not hit:
        raise SystemExit("拿不到 collected 数 ⇒ 仪器坏在这里，别往下跑")
    return int(hit.group(1))


def main() -> int:
    only = set(sys.argv[1:])
    out_path = HERE / "mutation-verdicts.json"
    orig = TARGET.read_bytes()
    base_red, _ = run_suite()
    den0 = collected_total()
    verdicts = [{"mutant": "baseline", "red": sorted(base_red), "collected": den0}]
    for name, why, old, new in MUTANTS:
        if only and name not in only:
            continue
        src = orig.decode("utf-8")
        hits = src.count(old)
        if hits != 1:
            verdicts.append({"mutant": name, "error": f"锚点命中 {hits} 次（要求恰好 1 次）⇒ 该变异体不成立"})
            continue
        TARGET.write_bytes(src.replace(old, new, 1).encode("utf-8"))
        try:
            red, ran = run_suite()
        finally:
            TARGET.write_bytes(orig)
        newly = sorted(red - base_red)
        restored = TARGET.read_bytes() == orig
        verdicts.append(
            {
                "mutant": name,
                "why": why,
                "newly_red": newly,
                "ran": ran,
                "collected": den0,
                "denominator_drift": ran != den0,
                "restored": restored,
                "killed": bool(newly) and ran == den0 and restored,
            }
        )
        print(f"{name}: newly_red={len(newly)} ran={ran}/{den0} restored={restored}", flush=True)
    assert TARGET.read_bytes() == orig, "import_laws.py 未还原 ⇒ 本轮结果作废"
    if only and out_path.exists():
        order = {"baseline": 0, **{m[0]: i + 1 for i, m in enumerate(MUTANTS)}}
        kept = [
            v
            for v in json.loads(out_path.read_bytes().decode("utf-8"))
            if v["mutant"] not in only and v["mutant"] != "baseline"
        ]
        verdicts = sorted(kept + verdicts, key=lambda v: order.get(v["mutant"], 99))
    out_path.write_bytes(json.dumps(verdicts, ensure_ascii=False, indent=1).encode("utf-8"))
    print("wrote", out_path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
