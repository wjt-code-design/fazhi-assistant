# -*- coding: utf-8 -*-
"""测出「嵌套 ref 被外部进程删除」的决定性证据：轮询观察 ref 文件是否真的出现过。

背景（2026-09-28/29）：本仓库里 `git commit`/`git update-ref` 写 `refs/heads/<目录>/<名>` 后，
ref 会消失，`git log` 报 "your current branch ... does not have any commits yet"。
本脚本用 ~0.5ms 轮询把过程拍下来，区分两种假设：
  (a) git 写失败         -> 文件从不会出现
  (b) 写完被外部删除     -> 文件出现后又在百毫秒级被删
实测结论为 (b)：`.lock` 改名为 ref 成功，其后 113–144 ms 文件与父目录被另一进程删除。

用法（在仓库根执行，或改下面的 REPO）：
  python watch-ref-write.py
副作用：会创建一次 `refs/heads/zzy/one` 并留下同名 reflog；脚本结束时会清掉 reflog 目录。
不要指向 `codex/**` 等真实分支使用。
"""
import os
import shutil
import subprocess
import threading
import time

REPO = r"C:\Users\33393\Desktop\ai-legal-helper"
SHA = "aec8d5c22a202c2b7b711d169096777d316f2932"  # 任意已存在的提交即可
REF = "refs/heads/zzy/one"

GIT = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Git", "cmd", "git.exe")
ref_dir = os.path.join(REPO, ".git", "refs", "heads", "zzy")
ref_path = os.path.join(ref_dir, "one")
lock_path = ref_path + ".lock"
log_dir = os.path.join(REPO, ".git", "logs", "refs", "heads", "zzy")

events = []
stop = threading.Event()


def snap(tag):
    events.append(
        (
            time.time(),
            tag,
            {
                "dir": os.path.isdir(ref_dir),
                "file": os.path.exists(ref_path),
                "lock": os.path.exists(lock_path),
            },
        )
    )


def watcher():
    while not stop.is_set():
        snap("poll")
        time.sleep(0.0005)


snap("before")
th = threading.Thread(target=watcher, daemon=True)
th.start()
proc = subprocess.run([GIT, "-C", REPO, "update-ref", REF, SHA], capture_output=True, text=True)
snap("after-run")
time.sleep(1.5)
stop.set()
th.join(timeout=1)
snap("final")

print(f"rc={proc.returncode} stderr={proc.stderr[:200]!r}")
print("--- 状态变化（只看变化点） ---")
prev = None
t0 = events[0][0]
for ts, tag, st in events:
    if st != prev:
        print(f"  t+{(ts - t0) * 1000:7.1f} ms  {tag:10s} {st}")
        prev = st
print("--- 结论判读 ---")
print("  出现过 file=True 然后变 False ⇒ (b) 外部进程删除；始终 False ⇒ (a) git 写失败")

shutil.rmtree(log_dir, ignore_errors=True)  # 清掉本脚本留下的 reflog
shutil.rmtree(ref_dir, ignore_errors=True)
