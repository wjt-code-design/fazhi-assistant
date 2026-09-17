"""评测批次网络健康工具（B5，2026-09-17）。

两个模式：
- `check`：跑批**前**预检 LLM 端点连通性（curl 探测，连续 3 次）——全通 exit 0，任一失败 exit 1。
  （注意：只能排除"开跑时就断"；中途窗口防不住——由 failover + 41364db 无连锁兜底。）
- `report <serve.log>`：跑批**后**网络事件小结——统计 failover_switch / failover_exhausted /
  QuotaExhausted 次数与时间分布，供批次报告标注"网络因素"。

用法：
  backend/venv/Scripts/python.exe backend/scripts/net_health.py check
  backend/venv/Scripts/python.exe backend/scripts/net_health.py report <serve.log 路径>

实现说明：联网探测用 **curl 子进程**（本机沙箱下 Python 直连 urllib 会被拦；curl 在白名单内）。
端点取 backend/.env 的 LLM_BASE_URL（不打印 key——本工具不读 key）。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _base_url() -> str:
    env = REPO / "backend" / ".env"
    for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("LLM_BASE_URL="):
            return line.split("=", 1)[1].strip()
    return ""


def check() -> int:
    url = _base_url()
    if not url:
        print("LLM_BASE_URL 未配置（backend/.env）——无法预检")
        return 2
    # 探测 https 根路径（401/404 均代表"网络通"；超时/连接失败=不通）
    ok = 0
    for i in range(3):
        r = subprocess.run(
            ["curl", "-sS", "-o", os.devnull, "-w", "%{http_code}", "--max-time", "8", url],
            capture_output=True,
            text=True,
            timeout=20,
        )
        code = (r.stdout or "").strip()
        reachable = r.returncode == 0 and code not in ("000", "")
        print(f"  probe {i + 1}/3: http_code={code or '(conn fail)'} -> {'OK' if reachable else 'FAIL'}")
        ok += reachable
        if i < 2:
            time.sleep(2)
    verdict = ok == 3
    print(f"NET_HEALTH_CHECK: {'PASS' if verdict else 'FAIL'} ({ok}/3)")
    return 0 if verdict else 1


def report(log_path: str) -> int:
    p = Path(log_path)
    if not p.exists():
        print(f"日志不存在: {p}")
        return 2
    t = p.read_text(encoding="utf-8", errors="replace")
    pat_switch = re.findall(r'"llm_adapter_stage": "failover_switch"', t)
    pat_trans = re.findall(r'"llm_invoke_mode": "transient"', t)
    pat_perm = re.findall(r'"llm_invoke_mode": "permanent"', t)
    pat_exh = re.findall(r'"llm_adapter_stage": "failover_exhausted"', t)
    pat_quota = len(re.findall(r"QuotaExhausted", t))
    print(f"=== 网络事件小结：{p.name} ===")
    print(f"  failover_switch 总次数 : {len(pat_switch)}（transient={len(pat_trans)} permanent={len(pat_perm)}）")
    print(f"  failover_exhausted 次数: {len(pat_exh)}  ← 每次=一个'全部模型不可达'窗口")
    print(f"  QuotaExhausted 提及    : {pat_quota}  ← 修复后应恒 0（连锁指标）")
    if len(pat_exh):
        print("  提示：本批撞上网络窗口——报告需标注网络因素（非实现失败）")
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("check", "report"):
        print("用法: net_health.py check | net_health.py report <serve.log>")
        return 2
    if sys.argv[1] == "check":
        return check()
    return report(sys.argv[2])


if __name__ == "__main__":
    sys.exit(main())
