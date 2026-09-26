"""票 T1 的变异跑：判据 5 要求"白名单去掉 upload ⇒ 必须红"，另加四条同族。

跑法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/t1-legacy-replace-20260926/mutate.py [变异体名...]

规矩沿用票 C/S6：分母必须相同（漂移的读数不算杀，那是"变异体把整套打崩"的形状）、
每体跑完必须还原并比对字节。锚点一律带**行首换行**——纯缩进前缀会跨站点互相命中
（`" "*20 + "x"` 也是 24 空格那一行的前缀），驱动按"锚点不唯一"拒跑。
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TARGET = BACKEND / "law_versions.py"
HERE = pathlib.Path(__file__).resolve().parent
PY = str(BACKEND / "venv" / "Scripts" / "python.exe")
TARGETS = [
    "tests/test_law_versions.py",
    "tests/test_status_default_unverified.py",
    "tests/test_phase5.py",
    "tests/test_effective_window_roundtrip.py",
    "tests/test_knowledge_service.py",
]

MUTANTS = [
    (
        "M1-drop-upload-from-whitelist",
        '按判据 5：白名单里没有 upload ⇒ 现网那种 upload 遗留块再也不可取代',
        '_LEGACY_REPLACEABLE_ORIGINS = ("upload", "manual")\n',
        '_LEGACY_REPLACEABLE_ORIGINS = ("manual",)\n',
    ),
    (
        "M2-no-normalization",
        "判据 5①：不做归一化 ⇒ 旧块的章节行与全角空格让包含恒不成立",
        '    return re.sub(r"[\\s　]+", "", text or "")\n',
        "    return text or \"\"\n",
    ),
    (
        "M3-containment-to-exact-equality",
        "判据 5②：包含换成逐字相等 ⇒ 正是票面否掉过的那条想当然修法",
        '        contained = bool(new_norm) and new_norm in _norm_text(str(stored_text or ""))\n',
        "        contained = bool(new_norm) and new_content == str(stored_text or \"\")\n",
    ),
    (
        "M4-ignore-missing-time-axis",
        "丢掉「时效轴整个缺失」这一半 ⇒ 带日期的修订版会被误删（最坏的失败方向）",
        "        undated = not stored_effective_from and not stored_effective_to\n",
        "        undated = True\n",
    ),
    (
        "M5-ignore-origin-whitelist",
        "丢掉 origin 白名单 ⇒ seed 副本被吞（它归 knowledge_base.py 重建管）",
        "        if not stored_version_id and undated and origin in _LEGACY_REPLACEABLE_ORIGINS and contained:\n",
        "        if not stored_version_id and undated and contained:\n",
    ),
]


def run_suite() -> tuple[set[str], int]:
    """跑一轮，返回 (红集合, 本轮真跑了多少条)。

    分母轴先前错过两次：① 拿 `passed|failed` 之和当 collected（把 skipped 吞了）；
    ② 拿 `passed + skipped` 当分母 —— 一有失败它就**自己缩小**，于是每个变异体的"分母"都不一样。
    现在：真 collected 由 `--collect-only` 量一次作常量，本轮跑了多少 = passed+failed+skipped+errors。
    """
    p = subprocess.run(
        [PY, "-m", "pytest", *TARGETS, "-q", "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    red = {m.group(1) for m in re.finditer(r"^FAILED tests/\S+::(\S+)", out, re.MULTILINE)}
    ran = 0
    for key in ("passed", "failed", "skipped", "error"):
        hit = re.search(rf"(\d+) {key}", out)
        if hit:
            ran += int(hit.group(1))
    return red, ran


def collected_total() -> int:
    """一次 `--collect-only` 拿到真正的 collected 轴（分母常量）。"""
    p = subprocess.run(
        [PY, "-m", "pytest", *TARGETS, "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (p.stdout or "") + (p.stderr or "")
    # `-q --collect-only` 的收尾行是 "N tests collected in Xs"，不是 verbose 的 "collected N items"
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
            red, den = run_suite()
        finally:
            TARGET.write_bytes(orig)
        newly = sorted(red - base_red)
        restored = TARGET.read_bytes() == orig
        verdicts.append(
            {
                "mutant": name,
                "why": why,
                "newly_red": newly,
                "collected": den,
                "denominator_drift": den != den0,
                "restored": restored,
                "killed": bool(newly) and den == den0 and restored,
            }
        )
        print(f"{name}: newly_red={len(newly)} collected={den} restored={restored}", flush=True)
    assert TARGET.read_bytes() == orig, "law_versions.py 未还原 ⇒ 本轮结果作废"
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
