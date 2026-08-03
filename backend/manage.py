"""后端运维脚本：start / stop / status / test（阶段4）。

用法（backend 目录，用 venv 的 python 跑）：
  python manage.py status                # 端口是否被监听
  python manage.py start                 # 启动后端（日志 logs/backend.log）
  python manage.py stop                  # 停止后端
  python manage.py test                  # 测试前置检查：端口被占 → 提示退路
  PORT=8001 python manage.py start       # 换端口启动（端口冲突退路）

设计：测试不无脑杀进程——端口被占时仅警告，提示 `--force` 或 `PORT=` 退路。
依赖纯标准库（netstat/taskkill 为 Windows 实现，跨平台有兜底）。
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

PY = sys.executable
PORT = int(os.getenv("PORT", "8000"))
LOG_DIR = os.path.join(HERE, "logs")
LOG_FILE = os.path.join(LOG_DIR, "backend.log")
# 日志轮转阈值：backend.log 超过该大小，启动时轮转为 .1/.2 并保留最近 3 份（防磁盘被吃光）
LOG_ROTATE_BYTES = int(os.getenv("LOG_ROTATE_BYTES", str(50 * 1024 * 1024)))  # 默认 50MB
LOG_KEEP = 3


def _listening_pids(port: int) -> list[int]:
    """返回监听该端口的 PID 列表（netstat 解析，跨平台兜底返回空）。"""
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
    except Exception:
        return []
    pids: list[int] = []
    for line in out.splitlines():
        if f":{port}" in line and "LISTEN" in line:
            parts = line.split()
            if parts:
                try:
                    pid = int(parts[-1])
                    if pid and pid not in pids:
                        pids.append(pid)
                except ValueError:
                    pass
    return pids


def _health(port: int) -> bool:
    try:
        urllib.request.urlopen(f"http://localhost:{port}/api/health", timeout=1)
        return True
    except Exception:
        return False


def cmd_status(port: int) -> int:
    pids = _listening_pids(port)
    if pids:
        ok = "（healthz OK）" if _health(port) else "（healthz 无响应）"
        print(f"后端运行中：端口 {port}，PID {pids} {ok}")
        return 0
    print(f"后端未运行：端口 {port} 空闲")
    return 1


def _rotate_log() -> None:
    """backend.log 超阈值时轮转 .1/.2（保留 LOG_KEEP 份）。启动时调用，防日志无限增长吃光磁盘。"""
    if not os.path.exists(LOG_FILE):
        return
    try:
        if os.path.getsize(LOG_FILE) < LOG_ROTATE_BYTES:
            return
    except OSError:
        return
    for i in range(LOG_KEEP - 1, 0, -1):  # .2 → .3, .1 → .2
        src = f"{LOG_FILE}.{i}" if i > 1 else LOG_FILE
        dst = f"{LOG_FILE}.{i + 1}"
        if os.path.exists(src):
            os.replace(src, dst)
    os.replace(LOG_FILE, f"{LOG_FILE}.1")
    print(f"日志已轮转（超 {LOG_ROTATE_BYTES // (1024 * 1024)}MB，保留最近 {LOG_KEEP} 份）", flush=True)


def cmd_start(port: int) -> int:
    pids = _listening_pids(port)
    if pids:
        print(f"端口 {port} 已被占用（PID {pids}）。")
        print("提示：用 PORT=8001 python manage.py start 换端口，或先 python manage.py stop。")
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)
    _rotate_log()
    log = open(LOG_FILE, "a", encoding="utf-8")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)],
        stdout=log,
        stderr=log,
        creationflags=flags,
    )
    print(f"后端启动中 PID {proc.pid}（日志 {LOG_FILE}）")
    for _ in range(60):
        if _health(port):
            print(f"后端就绪：http://localhost:{port}/api/health")
            return 0
        time.sleep(1)
    print(f"等待超时（60s），请检查日志：{LOG_FILE}")
    return 1


def cmd_stop(port: int) -> int:
    pids = _listening_pids(port)
    if not pids:
        print(f"后端未运行：端口 {port} 无监听")
        return 1
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=False, capture_output=True)
        except Exception:
            subprocess.run(["kill", str(pid)], check=False)
    time.sleep(0.5)
    print(f"已停止：端口 {port}，PID {pids}")
    return 0


def cmd_test(port: int, force: bool) -> int:
    pids = _listening_pids(port)
    if pids:
        print(f"端口 {port} 被占用（PID {pids}）——测试需要独占端口。")
        if force:
            print("--force：停止占用进程后重试。")
            return 0
        print("退路：python manage.py test --force 自动停止；或 PORT=8001 python manage.py test 换端口。")
        return 1
    print(f"端口 {port} 空闲，可以跑测试（pytest / smoke_citation_fast）。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="后端运维：start/stop/status/test")
    ap.add_argument("cmd", choices=["start", "stop", "status", "test"])
    ap.add_argument("--port", type=int, default=PORT, help=f"端口（默认 {PORT}，也可用环境变量 PORT）")
    ap.add_argument("--force", action="store_true", help="test 时允许停止占用端口的进程")
    args = ap.parse_args()

    mapping = {
        "start": lambda: cmd_start(args.port),
        "stop": lambda: cmd_stop(args.port),
        "status": lambda: cmd_status(args.port),
        "test": lambda: cmd_test(args.port, args.force),
    }
    sys.exit(mapping[args.cmd]())


if __name__ == "__main__":
    main()
