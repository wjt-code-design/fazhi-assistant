"""构造并自验"一次性发布快照"——外发给远端 CI 的那个对象集合。

为什么要脚本化：这一轮我三次被同一根绊线咬到——派生的树号/差分计数会随 master 一动静默过期，
而手抄提交号会打出不存在的 ref，让失败的普查读起来像"0 命中"。所以这里：
1) 一切从现量重算（merge-tree 当场算，不接受手抄 SHA）；
2) 两处刻意偏离各自带断言（锚点必须恰好 1 次、剔掉的文件集合必须恰好那两个目录）；
3) 普查必须打印被测命令自己的 rc —— 命令失败不等于"没命中"。

用法：<venv python> b_build_snapshot.py            # 构造 + 自验 + 打印推送命令
      <venv python> b_build_snapshot.py --dry-run   # 只算不写引用
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/33393/Desktop/ai-legal-helper")
BRANCH = "snapshot/ci-fbc29e8-20260930"
MASTER = "master"
CANDIDATE = "codex/local-candidate-closeout"
CI_PATH = ".github/workflows/ci.yml"
TRIM_DIRS = ("diag/frozen-index-004", "diag/frozen-index-005")
SSH_URL = "ssh://git@ssh.github.com:443/wjt-code-design/fazhi-assistant.git"
# 按值普查的键；值只进变量，永不打印
CENSUS_KEYS = ("ADMIN_PASSWORD", "JWT_SECRET", "RERANK_API_KEY", "LLM_API_KEY")
# 活体正对照：这个值确实曾进过 tracked 文件，用它证明尺子能红
POSITIVE_REF = "817e7d3"


def git(*args: str, want_text: bool = True):
    proc = subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=want_text,
        check=False,
    )
    return proc


def load_values() -> dict[str, str]:
    env = REPO / "backend" / ".env"
    out: dict[str, str] = {}
    if not env.is_file():
        return out
    for line in env.read_bytes().decode("utf-8", "replace").splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def tree_size(commit: str) -> tuple[int, float]:
    proc = git("ls-tree", "-r", "-l", commit)
    files = 0
    total = 0
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        meta = parts[0].split()
        files += 1
        if len(meta) >= 4 and meta[3].lstrip("-").isdigit():
            total += int(meta[3])
    return files, round(total / 1048576.0, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只构造对象，不移动分支引用")
    args = ap.parse_args()

    idx_file = (
        Path(os.environ.get("TEMP", r"C:/Users/33393/AppData/Local/Temp"))
        / f"snapidx-{os.getpid()}"
    )
    os.environ["GIT_INDEX_FILE"] = str(idx_file)
    try:
        # 1) 合并树从现量算，不接受任何手抄号
        mt = git("merge-tree", "--write-tree", MASTER, CANDIDATE)
        if mt.returncode != 0:
            print(f"FATAL: 合并不再干净 rc={mt.returncode}\n{mt.stdout[:400]}")
            return 2
        merged = mt.stdout.splitlines()[0].strip()
        print(f"[1] 合并树={merged}（rc=0，冲突 0）")

        # 2) 偏离一：给被推分支自己的 ci.yml 加触发名（锚点必须唯一）
        ci = git("cat-file", "-p", f"{merged}:{CI_PATH}")
        old = "    branches: [main, master]\n"
        new = f'    branches: [main, master, "{BRANCH}"]\n'
        if ci.stdout.count(old) != 1:
            print(
                f"FATAL: ci.yml 触发锚点出现 {ci.stdout.count(old)} 次，形状变了，停手"
            )
            return 3
        p = subprocess.run(
            ["git", "-C", str(REPO), "hash-object", "-w", "--no-filters", "--stdin"],
            input=ci.stdout.replace(old, new).encode("utf-8"),
            capture_output=True,
            check=False,
        )
        if p.returncode != 0:
            print(f"FATAL: hash-object rc={p.returncode} {p.stderr[:200]}")
            return 3
        blob = p.stdout.decode().strip()
        git("read-tree", merged)
        git("update-index", "--cacheinfo", f"100644,{blob},{CI_PATH}")

        # 3) 偏离二：只剔那两个目录，并核对"剔的就是这些"
        listed = git("ls-tree", "-r", "--name-only", merged)
        doomed = [
            f
            for f in listed.stdout.splitlines()
            if any(f.startswith(d + "/") for d in TRIM_DIRS)
        ]
        if not doomed:
            print(f"FATAL: 没找到 {TRIM_DIRS}，说明目录结构变了，剔除范围必须重判")
            return 4
        for f in doomed:
            git("update-index", "--force-remove", f)
        print(f"[3] 剔除 {len(doomed)} 个文件（限 {TRIM_DIRS}）")

        wt = git("write-tree")
        tree = wt.stdout.strip()
        msg = (
            f"snapshot: {CANDIDATE} + {MASTER} 合并树的一次性发布快照（永不合并）\n\n"
            f"两处刻意偏离在册树：1) {CI_PATH} 的 on.push.branches 增本分支名（无共同祖先⇒PR 路按构造关闭）；"
            f"2) 删 {', '.join(TRIM_DIRS)}（凭据轴按值普查为 0，内容轴体积过大）。无父提交⇒远端收不到任何历史 blob。"
        )
        ct = subprocess.run(
            ["git", "-C", str(REPO), "commit-tree", tree, "-m", msg],
            capture_output=True,
            text=True,
            check=False,
        )
        if ct.returncode != 0:
            print(f"FATAL: commit-tree rc={ct.returncode} {ct.stderr[:200]}")
            return 5
        commit = ct.stdout.strip()
    finally:
        if idx_file.exists():
            idx_file.unlink()
        os.environ.pop("GIT_INDEX_FILE", None)

    parents = git("log", "--format=%P", "-1", commit).stdout.strip()
    ncommits = git("rev-list", "--count", commit).stdout.strip()
    objects = len(git("rev-list", "--objects", commit).stdout.splitlines())
    files, mb = tree_size(commit)
    print(f"[4] 快照提交={commit} 树={tree}")
    print(
        f"    父=[{parents}]（必须空） 提交数={ncommits}（必须 1） 对象={objects} 文件={files} 体积={mb}MB"
    )
    if parents or ncommits != "1":
        print("FATAL: 这不是无父快照，推上去会带历史")
        return 6

    # 4) 按值普查：打印被测命令自己的 rc
    vals = load_values()
    print("[5] 按值普查（值不打印；rc=1 才是'没有'，命令失败不是 0 命中）")
    bad = 0
    control_dead = 0
    # 负对照必须**运行时生成**：写死在源码里的对照串，一旦这个脚本被提交，
    # 它就出现在待验树里 ⇒ 对照自己失效（本轮实测：负对照 rc=0，因为我刚把本脚本提交进了 master）。
    nonce = "zz-absent-" + secrets.token_hex(8)
    print(f"[5a] 动态负对照 nonce={nonce}（这个串不该出现在任何树里）")
    ctrl = git("-C", str(REPO), "grep", "-l", "-F", nonce, commit, "--")
    if ctrl.returncode != 1:
        print(
            f"FATAL: 动态负对照 rc={ctrl.returncode}（应为 1=查不到）⇒ 要么它命中了，要么命令本身在报错，两种都不许推"
        )
        return 10
    for k in CENSUS_KEYS:
        v = vals.get(k, "")
        if not v:
            print(f"    {k:<15} 跳过：本机 .env 里该键为空")
            continue
        # ⚠️ 一律带 -C REPO：git grep 在子目录里跑会**隐式收窄到该子目录**（同一棵树同一个值，
        #    仓根命中 1、本子目录命中 0）。不写 -C 就会把"查错了地方"输出成"整棵树都没有"。
        g1 = git("-C", str(REPO), "grep", "-l", "-F", v, commit, "--")
        hits1 = len([x for x in g1.stdout.splitlines() if x])
        g2 = git("-C", str(REPO), "grep", "-l", "-F", v, POSITIVE_REF, "--")
        hits2 = len([x for x in g2.stdout.splitlines() if x])
        note = "（活体正对照：尺子在这个值上能红）" if hits2 else ""
        print(
            f"    {k:<15} len={len(v):<4} 快照命中={hits1}(rc={g1.returncode}) "
            f"正对照@{POSITIVE_REF}={hits2}(rc={g2.returncode}){note}"
        )
        if g1.returncode not in (0, 1) or g2.returncode not in (0, 1) or hits1:
            bad += 1
        if k == "ADMIN_PASSWORD" and hits2 == 0:
            control_dead += 1
    if control_dead:
        print(
            "FATAL: 正对照打不红（ADMIN_PASSWORD 打在 817e7d3 上本应命中）⇒ 尺子失效，"
            "这一轮所有 0 命中一律不可信，不许推"
        )
        return 9
    if bad:
        print(f"FATAL: {bad} 个键在快照里有命中或普查命令本身失败 —— 不许推")
        return 7

    if args.dry_run:
        print(
            f"[6] --dry-run：不移动引用。要推的话：git update-ref refs/heads/{BRANCH} {commit}"
        )
    else:
        ur = git("update-ref", f"refs/heads/{BRANCH}", commit)
        if ur.returncode != 0:
            print(f"FATAL: update-ref rc={ur.returncode} {ur.stderr[:200]}")
            return 8
        print(f"[6] 引用已更新：{BRANCH} -> {commit}")
    print("\n推送命令（真推由 Owner 按回车；永不 force）：")
    print(f"  git push {SSH_URL} {BRANCH}:refs/heads/{BRANCH}")
    print(f"回退： git push {SSH_URL} :refs/heads/{BRANCH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
