# -*- coding: utf-8 -*-
"""H0 起点核对：只读。不修改项目文件，不发起付费调用。"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = r"C:\Users\33393\Desktop\ai-legal-helper"
FIXDIR = os.path.join(ROOT, "dispatch-output", "agent-mainline-fix-20260911")
QUALDIR = os.path.join(ROOT, "dispatch-output", "agent-quality-20260911")
OUT = []


def log(*a):
    line = " ".join(str(x) for x in a)
    OUT.append(line)
    print(line, flush=True)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def count_lines(p):
    with open(p, "rb") as f:
        return sum(1 for _ in f)


log("=" * 70)
log("H0 BASELINE CHECK", "time_utc=", __import__("datetime").datetime.utcnow().isoformat())
log("=" * 70)

# 1. 候选清单哈希核验
log("\n[1] candidate-manifest after_sha256 核验")
man = json.load(open(os.path.join(FIXDIR, "candidate-manifest.json"), encoding="utf-8"))
ok_all = True
for e in man:
    p = os.path.join(ROOT, e["path"].replace("/", os.sep))
    if not os.path.exists(p):
        log("  MISSING", e["path"])
        ok_all = False
        continue
    cur = sha256(p)
    nlines = count_lines(p)
    match = cur == e["after_sha256"]
    line_match = nlines == e["after_lines"]
    if not match or not line_match:
        ok_all = False
    log("  %-45s sha_match=%s lines=%d(exp %d,%s)" % (
        e["path"], match, nlines, e["after_lines"], "ok" if line_match else "DIFF"))
    if not match:
        log("      cur =", cur)
        log("      exp =", e["after_sha256"])
log("  => ALL_7_MATCH =", ok_all)

# 2. 第一轮证据目录清单
log("\n[2] agent-mainline-fix-20260911 目录内容")
if os.path.isdir(FIXDIR):
    for n in sorted(os.listdir(FIXDIR)):
        fp = os.path.join(FIXDIR, n)
        sz = os.path.getsize(fp) if os.path.isfile(fp) else -1
        log("   %-55s %s" % (n, sz if sz >= 0 else "<dir>"))
else:
    log("   MISSING DIR")

# 3. 付费 run 证据目录清单
log("\n[3] agent-quality-20260911 目录内容")
if os.path.isdir(QUALDIR):
    for n in sorted(os.listdir(QUALDIR)):
        fp = os.path.join(QUALDIR, n)
        sz = os.path.getsize(fp) if os.path.isfile(fp) else -1
        log("   %-55s %s" % (n, sz if sz >= 0 else "<dir>"))
else:
    log("   MISSING DIR")

# 4. 运行状态：进程
log("\n[4] 进程扫描 (tasklist)")
try:
    ti = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                        timeout=60, encoding="gbk", errors="replace")
    hits = []
    for row in ti.stdout.splitlines():
        low = row.lower()
        if any(k in low for k in ("python", "uvicorn", "serve.py", "gate2_runner")):
            hits.append(row.strip())
    log("  匹配进程数 =", len(hits))
    for h in hits:
        log("   ", h)
except Exception as ex:
    log("  tasklist 失败:", repr(ex))

# 5. 端口监听
log("\n[5] 端口 18111 监听检查 (netstat)")
try:
    ns = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=60,
                        encoding="gbk", errors="replace")
    ls = [l.strip() for l in ns.stdout.splitlines() if "18111" in l]
    log("  18111 相关行数 =", len(ls))
    for l in ls:
        log("   ", l)
except Exception as ex:
    log("  netstat 失败:", repr(ex))

# 6. 关键源码超时常量（只读确认，不修改）
log("\n[6] 关键超时常量现状")
for rel, needles in [
    ("backend/tools/gateway.py", ["TOOL_TIMEOUT", "timeout", "retrieve_laws"]),
    ("backend/retrieval.py", ["timeout", "rerank", "httpx"]),
]:
    fp = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.exists(fp):
        log("  MISSING", rel)
        continue
    log("  ---", rel)
    with open(fp, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            if any(n in line for n in needles):
                s = line.rstrip()
                if len(s) > 130:
                    s = s[:130] + "..."
                log("   %4d| %s" % (i, s))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "h0-baseline.txt"),
          "w", encoding="utf-8") as f:
    f.write("\n".join(OUT))
log("\n[SAVED] h0-baseline.txt")
