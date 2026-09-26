"""票 S0-b 的变异跑：§9.9 声称"把 `未验证` 塞回 `contracts.py` 的兜底分支 ⇒ 有用例红"，但那一轮**没留仪器**。

跑法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/s0b-status-default-20260926/mutate.py [变异体名...]

补票原因：09-26 双轴评审指出 s0c/t1/t2 三个驱动都有 `mutation-verdicts.json`，唯独 `161221b` 那句
主张没有 ⇒ 数字不可核。规矩照抄同族驱动：分母由 `--collect-only` 量一次作常量、锚点必须唯一且带行首换行、
每体跑完按字节比对还原。
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TARGET = BACKEND / "tools" / "contracts.py"
HERE = pathlib.Path(__file__).resolve().parent
PY = str(BACKEND / "venv" / "Scripts" / "python.exe")
TARGETS = ["tests/test_tool_gateway.py", "tests/test_status_default_unverified.py"]

MUTANTS = [
    (
        "M1-put-unverified-back-into-fallback",
        "判据原句：把 `未验证` 也算进兜底的「有效」 ⇒ 没人背书的块照样被断言现行有效",
        '    elif status == "现行" and effective_date is None:\n',
        '    elif status in ("现行", "未验证") and effective_date is None:\n',
    ),
]


def run(target_tests: list[str]) -> tuple[int, set[str], int]:
    """返回 (collected 常量, 红集合, 本轮跑了多少)。分母轴只认 `collected`，见票 C r1。"""
    out = subprocess.run(
        [PY, "-m", "pytest", *target_tests, "--collect-only", "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    hit = re.search(r"(\d+) tests? collected", out) or re.search(r"collected (\d+) items", out)
    if not hit:
        raise SystemExit("拿不到 collected 数 ⇒ 仪器坏在这里，别往下跑")
    collected = int(hit.group(1))
    res = subprocess.run(
        [PY, "-m", "pytest", *target_tests, "-q", "--no-header", "-rf", "--tb=no"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    red: set[str] = set()
    for line in (res.stdout or "").splitlines():
        m = re.match(r"^(?:FAILED|ERROR) (.+?::[\w\[\]\-.<>]+)", line)
        if m:
            red.add(m.group(1))
    tally = re.search(r"(\d+) passed.*?(\d+) failed.*?(\d+) skipped", res.stdout or "")
    ran = sum(int(x) for x in tally.groups()) if tally else len(red)
    return collected, red, ran


def main() -> None:
    names = sys.argv[1:]
    original = TARGET.read_bytes()
    verdicts: list[dict] = [{"mutant": "baseline", "red": sorted(run(TARGETS)[1]), "collected": run(TARGETS)[0]}]
    den0 = verdicts[0]["collected"]
    for name, why, old, new in MUTANTS:
        if names and name not in names:
            continue
        text = TARGET.read_text(encoding="utf-8")
        anchors = text.count(old)
        if anchors != 1:
            raise SystemExit(f"{name}: 锚点命中 {anchors} 次（要求恰好 1）⇒ 拒跑，那是打崩整套的形状")
        TARGET.write_text(text.replace(old, new), encoding="utf-8")
        try:
            den, red, ran = run(TARGETS)
        finally:
            TARGET.write_bytes(original)
        restored = TARGET.read_bytes() == original
        if den != den0:
            raise SystemExit(f"{name}: 分母漂移 {den0}→{den} ⇒ 该读数不算杀")
        newly = sorted(red - set(verdicts[0]["red"]))
        verdicts.append(
            {
                "mutant": name,
                "why": why,
                "collected": den,
                "ran": ran,
                "newly_red": newly,
                "killed": bool(newly),
                "restored": restored,
            }
        )
        print(f"{name}: newly_red={len(newly)} collected={den} restored={restored}", flush=True)
        if not restored:
            raise SystemExit(f"{name}: 未还原 ⇒ 停在这里")
    (HERE / "mutation-verdicts.json").write_text(json.dumps(verdicts, ensure_ascii=False, indent=2), encoding="utf-8")
    killed = sum(1 for v in verdicts if v.get("killed"))
    total = len([m for m in MUTANTS if not names or m[0] in names])
    print(f"\n变异 {killed}/{total} 被杀；分母恒 {den0}；产物 {HERE / 'mutation-verdicts.json'}")
    sys.exit(0 if killed == total else 1)


if __name__ == "__main__":
    main()
