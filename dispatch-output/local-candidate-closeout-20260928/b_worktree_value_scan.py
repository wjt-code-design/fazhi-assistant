"""整工作树按值反查：把"盘上有几处明文、其中几处会被 `git add -A` 带走"两个数一次量清。

为什么要单独一支仪器：我先前那句"未跟踪 528 个文件、按值扫密 0 命中"里，528 是
`git status --porcelain -unormal` 的**折叠条目数**（一整棵未跟踪目录算一条），不是文件数；
而那次只查了 **一个** 键。折叠口径当分母 + 单键 ⇒ 那句"0 命中"不可用。这里量三个面：

- **[A] 未跟踪且未被忽略**（只覆盖新增文件，不含已跟踪/已暂存变更）
- **[B] 盘上全部文件**（含被忽略的，＝真实暴露面；`.env` 族在这里，所以它**必须**命中——不命中就是尺子坏了）
- **[C] 拟外发对象集合**不在本件射程：走 `b_build_snapshot.py` 的 `[5]/[5b]` 段（那是对 commit tree 扫，不是对盘扫）

八个在册输入必须完整；枚举/读取不完整即失败（rc=3）。
**[B] 合计 0 命中即判仪器失效**（rc=2），不许读成"干净"。
rc=0 只表示诊断完整，不表示无命中或允许外发。
值只进变量，永不打印；命中只输出（相对路径, 键名, 该文件命中次数）。

用法：<venv python> b_worktree_value_scan.py [--root PATH]
--root 控制扫描与 Git 枚举；凭据仍从主工作区 backend/.env 读取。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(r"C:/Users/33393/Desktop/ai-legal-helper")
ENV_FILE = "backend/.env"
# 覆盖面必须 >= 汇报里提到的键数；与 b_build_snapshot.py 的 CENSUS_KEYS 同源
CENSUS_KEYS = (
    "ADMIN_PASSWORD",
    "JWT_SECRET",
    "RERANK_API_KEY",
    "LLM_API_KEY",
    "EMBEDDING_API_KEY",
    "ZHIPUAI_API_KEY",
    "DASHSCOPE_API_KEY",
    "SILICONFLOW_API_KEY",
)
CHUNK = 1 << 20


def git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)


def load_values() -> dict[str, bytes]:
    p = REPO / ENV_FILE
    if not p.is_file():
        return {}
    values = dotenv_values(p, interpolate=False, encoding="utf-8")
    return {key: value.encode("utf-8") for key, value in values.items() if key in CENSUS_KEYS and value is not None}


def untracked_files(root: Path) -> list[Path]:
    """NUL 分隔避免 Git 的可打印路径引号/八进制转义；只枚举未跟踪且未忽略文件。"""
    proc = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, "git ls-files")
    return [root / os.fsdecode(name) for name in proc.stdout.split(b"\0") if name]


def safe_path(path: Path, root: Path, needles: dict[str, bytes]) -> str:
    """命中与失败共用路径脱敏；不影响实际文件枚举。"""
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = str(path)
    for value in sorted(needles.values(), key=len, reverse=True):
        relative = relative.replace(value.decode("utf-8"), "[REDACTED]")
    return relative


def scan(path: Path, needles: dict[str, bytes]) -> dict[str, int]:
    """流式扫，命中允许跨块：每块末尾留 len(needle)-1 的重叠。"""
    hits: dict[str, int] = {}
    try:
        with open(path, "rb") as fh:
            tails: dict[str, bytes] = {}
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                for key, needle in needles.items():
                    if not needle:
                        continue
                    buf = tails.get(key, b"") + chunk
                    n = buf.count(needle)
                    if n:
                        hits[key] = hits.get(key, 0) + n
                    keep = len(needle) - 1
                    tails[key] = buf[-keep:] if keep > 0 else b""
    except (OSError, PermissionError):
        return {"UNREADABLE": 1}
    return hits


def sweep(files: list[Path], root: Path, needles: dict[str, bytes], tag: str = "") -> dict[str, object]:
    """tag 非空时打进度：长跑必须**逐段刷出**，否则进程被杀 ⇒ 整只读数一个字都不剩。"""
    per_key: dict[str, int] = {k: 0 for k in needles}
    hit_files = 0
    unreadable = 0
    hits: list[str] = []
    t0 = time.perf_counter()
    for i, p in enumerate(files, 1):
        if tag and i % 5000 == 0:
            print(f"    [{tag}] 进度 {i}/{len(files)} 用时 {time.perf_counter() - t0:.0f}s", flush=True)
        h = scan(p, needles)
        if h.get("UNREADABLE"):
            unreadable += 1
            print(f"    [{tag}] 读取失败 {safe_path(p, root, needles)!r}", flush=True)
            continue
        if h:
            hit_files += 1
            names = []
            for k, n in sorted(h.items()):
                per_key[k] += n
                names.append(f"{k}x{n}")
            hits.append(f"    命中 {safe_path(p, root, needles)}  {' '.join(names)}")
    return {
        "attempted": len(files),
        "read": len(files) - unreadable,
        "unreadable": unreadable,
        "hit_files": hit_files,
        "per_key": per_key,
        "hits": hits,
    }


def print_report(tag: str, r: dict[str, object]) -> int:
    for line in r["hits"]:  # type: ignore[index]
        print(line)
    per_key: dict[str, int] = r["per_key"]  # type: ignore[assignment]
    print(
        f"[{tag}] 尝试={r['attempted']} 读到={r['read']} 打不开={r['unreadable']} 含值文件={r['hit_files']} 命中总数={sum(per_key.values())}"
    )
    print(f"     按键：{' '.join(f'{k}={v}' for k, v in sorted(per_key.items()))}")
    return int(r["hit_files"])  # type: ignore[return-value]


def all_worktree_files(root: Path) -> list[Path]:
    """盘上全部常规文件（只剪 `.git/`）——含被忽略的那些，这才是真实暴露面。"""

    def fail(error: OSError) -> None:
        raise error

    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=fail):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            out.append(Path(dirpath) / name)
    return out


def main() -> int:
    # Windows 下 `>` 重定向按控制台代码页(cp936)落盘 ⇒ 读数进仓就是乱码。钉死 UTF-8。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    ap = argparse.ArgumentParser(description="整工作树按值反查（不打印值）")
    ap.add_argument("--root", default=str(REPO), help="被扫的树根，默认主工作区")
    args = ap.parse_args()
    try:
        root = Path(args.root).resolve()
        if not root.is_dir():
            raise OSError("Invalid scan root")
    except (OSError, ValueError, RuntimeError):
        print("FATAL: 扫描根无法解析或不是可访问目录")
        return 3

    try:
        needles = load_values()
    except (OSError, ValueError):
        print("FATAL: 在册凭据输入无法读取或解析，不许产出结论")
        return 3
    missing = [key for key in CENSUS_KEYS if not needles.get(key, b"").strip()]
    if missing:
        print("FATAL: 在册扫描输入缺失或为空：" + ", ".join(missing))
        return 3
    if any(b"${" in value or b"\n" in value or b"\r" in value for value in needles.values()):
        print("FATAL: 在册凭据含变量引用或换行，无法按确定单值扫描")
        return 3
    print(f"[0] 参与反查的键 {len(CENSUS_KEYS)} 个，读到非空值 {len(needles)} 个（值未打印）")

    stage = "A/Git枚举"
    try:
        untracked = untracked_files(root)
        print(f"[1] 未跟踪且未被忽略的文件={len(untracked)}（不含已跟踪/已暂存变更）")
        print("[A] 面＝未跟踪**且未被忽略**（非全部待提交对象）", flush=True)
        a_report = sweep(untracked, root, needles, "A")
        a = print_report("A", a_report)
        if a_report["unreadable"]:
            print("FATAL: 面 A 读取不完整，本次扫描结论无效")
            return 3
        print("[B] 面＝盘上全部文件（含被忽略；`.env` 族在此面内）", flush=True)
        stage = "B/目录枚举"
        b_report = sweep(all_worktree_files(root), root, needles, "B")
        b = print_report("B", b_report)
        if b_report["unreadable"]:
            print("FATAL: 面 B 读取不完整，本次扫描结论无效")
            return 3
    except (OSError, subprocess.CalledProcessError) as exc:
        # 仅保留阶段、错误类型/返回码及脱敏路径，不回显异常原文或子进程输出。
        detail = f"Git rc={exc.returncode}" if isinstance(exc, subprocess.CalledProcessError) else type(exc).__name__
        if isinstance(exc, OSError) and exc.filename:
            detail += f" 路径={safe_path(Path(exc.filename), root, needles)!r}"
        print(f"FATAL: 文件枚举失败（阶段={stage}；{detail}），本次扫描结论无效")
        return 3

    if b == 0:
        print("VERDICT: 面 B 恒不命中 ⇒ 尺子坏了，本只读数作废（**不是**「干净」）")
        return 2
    print(f"VERDICT: 尺子活着、扫描完整（面 B 命中 {b} 份文件）；面 A={a} 份未跟踪文件含值")
    print("        是否外发另按对象集合判：走 b_build_snapshot.py 的 [5]/[5b] 段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
