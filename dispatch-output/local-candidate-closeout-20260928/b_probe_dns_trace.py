"""一次性诊断件：把"非环回的解析/连接尝试"归因到**具体用例**。

为什么不往 b_runtime_probe.py 里加栈记录：那会改动仪器，按"读数必须晚于最后一次代码编辑"
就得把测试场全部重跑。这个文件是**独立插件**，自己带审计钩子，跑一场只为定位，
主仪器与主读数不动。

记录面：socket.getaddrinfo / socket.connect / http.client.connect / urllib.Request 里
主机**不是环回**的每一次尝试，附当时的用例 nodeid 与栈帧。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

LOOPBACK = {"127.0.0.1", "::1", "0:0:0:0:0:0:0:1", "localhost"}
HERE = Path(__file__).resolve().parent
PY = Path(r"C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928/venv/Scripts/python.exe")
OUT = HERE / "b-probe-dns-trace.json"

STATE = {"current": "<outside-test>", "hits": [], "total_net": 0}


def _host_of(event, args):
    try:
        if event == "socket.getaddrinfo":
            return str(args[0]), str(args[1])
        if event == "socket.connect":
            addr = args[0]
            return str(addr[0]), str(addr[1]) if len(addr) > 1 else ""
        if event == "http.client.connect":
            self = args[0]
            return str(getattr(self, "host", "")), str(getattr(self, "port", ""))
        if event == "urllib.Request":
            url = str(args[0])
            host = url.split("://", 1)[-1].split("/")[0].split(":")[0]
            return host, ""
    except BaseException:
        return "", ""
    return "", ""


def _hook(event, args):
    try:
        if event not in ("socket.getaddrinfo", "socket.connect", "http.client.connect", "urllib.Request"):
            return
        STATE["total_net"] += 1
        host, port = _host_of(event, args)
        if not host or host in LOOPBACK:
            return
        frames = []
        try:
            import inspect

            for f in inspect.stack()[2:12]:
                fn = f.filename.replace("\\", "/")
                if "site-packages" in fn or "importlib" in fn or fn == "<string>":
                    continue
                frames.append(f"{Path(fn).name}:{f.lineno}:{f.function}")
                if len(frames) >= 5:
                    break
        except BaseException:
            pass
        STATE["hits"].append(
            {
                "event": event,
                "host": host,
                "port": port,
                "test": STATE["current"],
                "frames": frames,
                "argv_tail": [str(a)[:80] for a in args[:2]],
            }
        )
    except BaseException:
        pass


if not os.environ.get("DNS_TRACE_NO_HOOK"):
    sys.addaudithook(_hook)


def pytest_runtest_setup(item):
    STATE["current"] = item.nodeid


def pytest_runtest_call(item):
    STATE["current"] = item.nodeid


def pytest_sessionfinish(session, exitstatus):
    OUT.write_text(
        json.dumps(
            {
                "nonloopback_attempts": STATE["hits"],
                "nonloopback_total": len(STATE["hits"]),
                "all_net_events": STATE["total_net"],
                "exitstatus": int(exitstatus),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: b_probe_dns_trace.py <tree>")
        return 2
    tree = Path(sys.argv[1])
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(os.environ.get("TEMP", r"C:/Users/33393/AppData/Local/Temp")) / f"b-probe-dns-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(HERE),
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
            "DATABASE_URL": "sqlite:///" + str(run_dir / "iso-app.db").replace("\\", "/"),
            "QUOTA_DB": str(run_dir / "iso-quota.db"),
        }
    )
    xml = run_dir / "junit.xml"
    cmd = [
        str(PY),
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "b_probe_dns_trace",
        "-m",
        "not slow",
        f"--basetemp={run_dir / 'pt'}",
        f"--junit-xml={xml}",
    ]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(tree / "backend"), env=env, capture_output=True, text=True, timeout=3000)
    dur = round(time.time() - t0, 1)
    cases = -1
    if xml.is_file():
        cases = sum(1 for _ in ET.parse(str(xml)).getroot().iter("testcase"))
    print(f"pytest rc={proc.returncode} junit_cases={cases} duration={dur}s")
    for ln in proc.stdout.splitlines():
        if ln.startswith(("FAILED", "ERROR")):
            print("  " + ln[:160])
    if not OUT.is_file():
        print("FATAL: 插件没落诊断件 —— 插件未被加载")
        return 3
    d = json.loads(OUT.read_text(encoding="utf-8"))
    print(f"全场网络事件 {d['all_net_events']} 次；非环回 {d['nonloopback_total']} 次")
    for h in d["nonloopback_attempts"][:20]:
        print(f"  {h['event']} host={h['host']} port={h['port']} test={h['test']}")
        for f in h["frames"]:
            print(f"      {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
