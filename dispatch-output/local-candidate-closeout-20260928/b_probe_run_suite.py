"""B 档探针全量运行器：在副本树上带桩跑现有测试，并先证明「这一场真的跑完了」。

闸门（缺一就不许写读数）：
  1. `--collect-only` 分母可解析；
  2. junit 用例数 >= 分母（收集期中断会让 junit 只剩 1 条伪用例，那种「全 0 调用」是假阴性机器）；
  3. 收集、pytest、JUnit 与探针的退出状态均成功；失败场保留为 INVALID。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# B_PROBE_EVIDENCE_DIR 把读数落点搬到本轮目录，默认仍是历史证据目录（不覆盖旧读数）。
EVIDENCE = Path(
    os.environ.get("B_PROBE_EVIDENCE_DIR")
    or "C:/Users/33393/Desktop/ai-legal-helper/dispatch-output/local-candidate-closeout-20260928"
)
# 解释器可用 B_PROBE_PY 覆盖（O-6 用它把 pytest 从 8.4.2 换到 9.1.1 复跑同一套门禁）。
# ⚠️ 覆盖后读数属**另一套环境**：打印时必须连解释器路径与 pytest 版本一起落盘，否则两个版本的答案会被读成同一场。
PY = Path(
    os.environ.get("B_PROBE_PY")
    or r"C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe"
)


def build_env(tree: Path, run_dir: Path, probe_out: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(EVIDENCE),
            "JWT_SECRET": "test-jwt-secret-for-ci-only",
            "LLM_API_KEY": "test-key-not-for-real-calls",
            "LLM_BASE_URL": "https://test.invalid/v1",
            "EMBEDDING_PROVIDER": "local",
            "RERANK_ENABLED": "false",
            "EMBEDDING_QUOTA_TOTAL": "0",
            "RERANK_QUOTA_TOTAL": "0",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "LANGCHAIN_TRACING_V2": "false",
            "LANGSMITH_TRACING": "false",
            "DATABASE_URL": "sqlite:///"
            + str(run_dir / "iso-app.db").replace("\\", "/"),
            "QUOTA_DB": str(run_dir / "iso-quota.db"),
            "PROBE_OUT": str(probe_out),
            "PROBE_CAND": str(tree),
            "PROBE_MODE": "pytest",
        }
    )
    # 任何指向真实库的变量都不该带进来
    for key in ("CHROMA_PATH", "CHROMA_DB_PATH", "KB_PATH"):
        env.pop(key, None)
    return env


def junit_stats(xml_path: Path) -> dict[str, object]:
    root = ET.parse(str(xml_path)).getroot()
    cases = root.iter("testcase")
    names: list[str] = []
    bad: list[str] = []
    total = 0
    for case in cases:
        total += 1
        label = f"{case.get('classname', '?')}::{case.get('name', '?')}"
        names.append(label)
        for child in case:
            if child.tag in ("failure", "error"):
                bad.append(
                    f"{label} [{child.tag}] {str(child.get('message') or '')[:160]}"
                )
    return {"junit_cases": total, "failed_or_error": bad[:60], "failed_total": len(bad)}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(
            "usage: b_probe_run_suite.py <tree> [--live]  (--live = 在候选工作区本树上跑，仅诊断用)"
        )
        return 2
    tree = Path(argv[0])
    backend = tree / "backend"
    if not backend.is_dir():
        print(f"FATAL: 副本树缺 backend/ -> {backend}")
        return 2

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = (
        Path(os.environ.get("TEMP", r"C:/Users/33393/AppData/Local/Temp"))
        / f"b-probe-run-{stamp}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    probe_out = EVIDENCE / f"b-probe-readings-pytest-{stamp}.json"
    xml_path = run_dir / "junit.xml"
    env = build_env(tree, run_dir, probe_out)

    ver = subprocess.run(
        [
            str(PY),
            "-c",
            "import sys,pytest;print(sys.version.split()[0],pytest.__version__)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(
        f"[B-PROBE 环境] interpreter={PY}  py/pytest={ver.stdout.strip() or ver.stderr.strip()[:120]}"
    )
    if not PY.is_file():
        print(f"FATAL: 解释器不存在 -> {PY}")
        return 2

    collect = subprocess.run(
        [
            str(PY),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-m",
            "not slow",
        ],
        cwd=str(backend),
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    m = re.search(r"(\d+)(?:/(\d+))? tests? collected", collect.stdout)
    if collect.returncode != 0 or not m:
        print(collect.stdout[-2500:])
        print(collect.stderr[-1500:])
        print("FATAL: 分母解析失败 —— 没有分母就没有差分，本场不成立")
        return 3
    # `1660/1678 tests collected (18 deselected)` —— 分子才是「本场会跑的条数」，
    # 拿分母当闸会把一场有效运行误判成收集期中断。上一版就是读错了轴。
    selected = int(m.group(1))
    total = int(m.group(2) or m.group(1))
    deselected = total - selected
    collected = selected
    print(
        f"collected: selected={selected} total={total} deselected={deselected} (rc={collect.returncode})"
    )
    if collected <= 0:
        print("FATAL: selected 分母为 0 —— 没有任何用例会跑，本场不成立")
        return 3

    cmd = [
        str(PY),
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "b_runtime_probe",
        "-m",
        "not slow",
        f"--basetemp={run_dir / 'pt'}",
        f"--junit-xml={xml_path}",
    ]
    t0 = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(backend),
        env=env,
        capture_output=True,
        text=True,
        timeout=3000,
        check=False,
    )
    dur = round(time.time() - t0, 1)
    log_path = EVIDENCE / f"b-probe-pytest-{stamp}.log"
    with open(str(log_path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"cmd = {' '.join(cmd)}\ntree = {tree}\ncollected = {collected}\n"
            f"duration_s = {dur}\nrc = {proc.returncode}\n"
        )
        fh.write("\n----- STDOUT -----\n" + proc.stdout)
        fh.write("\n----- STDERR -----\n" + proc.stderr)
    print(f"pytest rc={proc.returncode} duration={dur}s log={log_path}")

    stats = (
        junit_stats(xml_path)
        if xml_path.is_file()
        else {"junit_cases": -1, "failed_or_error": ["<no junit>"], "failed_total": -1}
    )
    print(
        f"junit_cases = {stats['junit_cases']}  failed_total = {stats['failed_total']}"
    )
    for line in stats["failed_or_error"]:
        print("  FAIL " + line)
    tail = [
        ln
        for ln in proc.stdout.splitlines()
        if ln.startswith(("FAILED", "ERROR", "SyntaxError"))
    ]
    for ln in tail[:40]:
        print("  RAW " + ln)

    valid = (
        proc.returncode == 0
        and stats["failed_total"] == 0
        and stats["junit_cases"] >= collected
    )
    preloaded: list[str] = []
    if valid and probe_out.is_file():
        probe_json = json.loads(probe_out.read_text(encoding="utf-8"))
        if probe_json.get("pytest_exitstatus") != 0:
            valid = False
        preloaded = list(probe_json.get("preloaded_app_at_install") or [])
        if preloaded:
            valid = False
            print(
                f"实验无效：装桩时这些模块已经在 sys.modules 里 -> {preloaded} ⇒ 装桩前的调用看不见，ZERO-CALL 不作证据"
            )
    if not valid:
        invalid_path = str(probe_out) + ".INVALID"
        if probe_out.is_file():
            shutil.move(str(probe_out), invalid_path)
        print(
            f"\n实验无效：pytest rc={proc.returncode}，JUnit失败数={stats['failed_total']}，"
            f"用例数={stats['junit_cases']}/{collected}；并检查探针退出码/预加载状态 "
            f"—— 读数已改名为 {invalid_path}，不得计入结论"
        )
        return 4

    if probe_out.is_file():
        readings = json.loads(probe_out.read_text(encoding="utf-8"))
        installed_n = sum(
            1 for r in readings["targets"] if str(r["install"]).startswith("INSTALLED")
        )
        print(
            f"\n[B-PROBE 有效场] installed={installed_n}/{len(readings['targets'])}"
            f" 装桩前已加载={readings.get('preloaded_app_at_install') or '无'} "
            f"compile事件={readings.get('compile_event_total')}"
        )
        for r in readings["targets"]:
            print(
                f"  {r['id']} {r['verdict']:16s} count={r['count']:4d} "
                f"dry={r['dry_runs']:3d} patched_at={r['patched_at']}"
            )
        print(
            f"  imports 在场 {len(readings['imports_watched'])} 个；"
            f"net 事件种类 {readings['net_event_kinds']}，总数 {readings['net_event_total']}"
        )
        for key, cnt in list(readings["net_events"].items())[:25]:
            print(f"    {cnt:5d}  {key[:150]}")
    else:
        print("FATAL: 闸门说有效，但探针没写读数 —— 插件未加载？")
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
