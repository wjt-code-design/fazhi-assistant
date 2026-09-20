"""票 C §6-⑤：`agent_enabled` 两态都跑定向集，并**先证两态的 effective 值真的不同**。

为什么"先证不同"：本仓吃过一次"两态其实同态"的亏 —— 若 env 没真正落到 `settings`，
两遍跑的是同一个状态，报告里的"两态都过"就是一句空话。所以本脚本对每一态都
① 单独 import `settings` 读 effective 值（与 pytest 同一 env、同一解释器、同一 cwd），
② 再跑 pytest，末行计数原样落盘。

⚠️ `AGENT_TRAFFIC_PERCENT=0` 是本脚本显式设的：Owner 边界 §0「不重跑付费三臂、所有断言离线、
不调模型」。若 `.env` 里的灰度比例非 0，`AGENT_ENABLED=true` 就会让 `/api/chat` 真去跑 agent
（付费 + 联网）。这一条是**为了守住边界**，不是为了让两态好看；两态的差别仍真实存在：
`main.py` 里 `if not settings.agent_enabled: pre = _pre(...)` 与 else 分支的
`request_bootstrap` + `decide_gate` 是两条不同的进入路径（后者仍落 fast_path，traffic 0%）。

用法（cwd 任意）：
    backend/venv/Scripts/python.exe dispatch-output/s6-stream-gate-20260920/run_two_state.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
BACKEND = REPO / "backend"
PY = BACKEND / "venv" / "Scripts" / "python.exe"

FILES = [
    "tests/test_stream_exit_law_version_gate.py",
    "tests/test_fast_path_law_version_gate.py",
    "tests/test_gate_exit_registry.py",
    "tests/test_flagship_quality.py",
    "tests/test_tiering.py",
]


def effective(env: dict[str, str]) -> dict[str, object]:
    """在给定 env 下单独 import settings，读三个生效值（不打印任何密钥）。"""
    code = (
        "import json, settings as s; "
        "print(json.dumps({'agent_enabled': s.settings.agent_enabled, "
        "'agent_traffic_percent': s.settings.agent_traffic_percent, "
        "'fast_path_law_version_check': s.settings.fast_path_law_version_check}))"
    )
    p = subprocess.run(
        [str(PY), "-c", code],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return {
        "stdout": p.stdout.strip(),
        "rc": p.returncode,
        "stderr_tail": p.stderr[-300:],
    }


def run(env: dict[str, str], tag: str) -> tuple[str, int]:
    cmd = [
        str(PY),
        "-m",
        "pytest",
        *FILES,
        "-q",
        "-p",
        "no:cacheprovider",
        f"--basetemp=/tmp/fz_s6_{tag}",
    ]
    p = subprocess.run(
        cmd,
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    tail = [ln for ln in p.stdout.splitlines() if ln.strip()][-1:]
    (HERE / f"log-two-state-{tag}.txt").write_text(
        f"$ {' '.join(cmd)}\nrc={p.returncode}\n\n{p.stdout}\n",
        encoding="utf-8",
        newline="\n",
    )
    return (tail[0] if tail else "(空)"), p.returncode


def main() -> int:
    lines = ["票 C §6-⑤ agent_enabled 两态", ""]
    eff_values: list[str] = []
    rcs: list[int] = []
    switch_off_both: list[bool] = []
    for state, tag in (("false", "agent-off"), ("true", "agent-on")):
        env = dict(os.environ)
        env["AGENT_ENABLED"] = state
        env["AGENT_TRAFFIC_PERCENT"] = "0"
        eff = effective(env)
        tail, rc = run(env, tag)
        eff_values.append(eff["stdout"])
        rcs.append(rc)
        switch_off_both.append('"fast_path_law_version_check": false' in eff["stdout"])
        lines += [
            f"{tag}: AGENT_ENABLED={state} env 设定",
            f"  effective 读数 = {eff['stdout']} (rc={eff['rc']})",
            f"  pytest rc={rc} 末行={tail}",
            "",
        ]
    differ = (
        eff_values[0] != eff_values[1]
        and "true" in eff_values[1]
        and "false" in eff_values[0]
    )
    ok = differ and all(r == 0 for r in rcs) and all(switch_off_both)
    lines += [
        f"两态 effective 是否真的不同 = {differ}（相同 ⇒ 本判据作废，两遍跑的是同一个状态）",
        f"两态下被测开关都仍为默认 False = {all(switch_off_both)}（Owner 纪律：不许为了验证改默认值）",
        f"两态 pytest 都 rc=0 = {all(r == 0 for r in rcs)}",
        f"VERDICT={'TWO_STATE_OK' if ok else 'TWO_STATE_VOID'}",
    ]
    text = "\n".join(lines) + "\n"
    (HERE / "07-two-state-readings.txt").write_text(
        text, encoding="utf-8", newline="\n"
    )
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
