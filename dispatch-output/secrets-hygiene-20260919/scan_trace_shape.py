"""S1：递归扫描全仓的**密钥形状**（只报形状，永不打印值）。

为什么要重做：R15 会话的上一次扫描**没有加 -r**（不递归目录内部），所以"命中 1 个"是**下界**。
本脚本递归全部文件，命中只输出 `len / has_digit / charset 前 8 个字母 / sha256 前 12 位`，
**绝不把匹配到的原文写进终端或任何文件**（防值经日志/终端记录外流）。

用法：backend/venv/Scripts/python.exe scan_trace_shape.py [--repo <根>] [--max-mb 50] [--out <json>]
输出：stdout 摘要 + --out 指定的 JSON（形状级，可安全入库；默认脚本同目录 scan-result.json）
退出码：0=无停手指征 / 3=真凭据形状命中受跟踪文件 / 4=仪器失效（git 列表失败，读数作废）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

PATTERNS = {
    "openai_style_sk": re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    "aws_akid": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "jwt_like": re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{5,}"),
    "generic_assign_secret": re.compile(
        rb"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*['\"]([A-Za-z0-9+/_-]{20,})['\"]"
    ),
}
# "真凭据形状" = 这三条；generic_assign_secret **不算**（S1 实测它占 46/71，绝大多数是占位值
# 与第三方库源码）⇒ 它只进报告、不触发停手。判据来自 S1 票面："真形态密钥出现在受跟踪文件 ⇒ 停手"。
STOP_PATTERNS = frozenset({"openai_style_sk", "aws_akid", "jwt_like"})
SKIP_DIR_NAMES = {
    ".git",
    "venv",
    ".venv",
    "node_modules",
    ".next",
    "__pycache__",
    "chroma_db",
    "backups",
    ".pytest_cache",
    "dist",
    "build",
}
OVERLAP = 64  # 分块读时保留的尾部字节，防匹配串被块边界切断
CHUNK = 1 << 20


def shape(tok: bytes) -> dict:
    return {
        "len": len(tok),
        "has_digit": any(c in b"0123456789" for c in tok),
        "letters_head8": "".join(sorted({chr(c) for c in tok if chr(c).isalpha()}))[:8],
        "sha256_12": hashlib.sha256(tok).hexdigest()[:12],
    }


def tracked_paths(repo: Path) -> tuple[set, bool]:
    """受跟踪路径集合 + 该集合是否可信。

    `git ls-files` 失败时返回空集**且** ok=False —— 旧版只有前者，于是"git 挂了"会被
    误读成"所有命中都在未跟踪文件里"（把最坏情况洗成平安无事）。调用方必须看 ok。
    """
    r = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        capture_output=True,
        text=False,
        check=False,
    )
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace")[:200]
        print(f"[INSTRUMENT] git ls-files 失败 rc={r.returncode} stderr={err}")
        return set(), False
    return {p.decode("utf-8", "replace") for p in r.stdout.split(b"\x00") if p}, True


def shape_of_token(name: str, m: re.Match) -> bytes:
    """命中里"哪一段算 token"——generic 的正则把变量名也吃进去了，只取第 2 组。"""
    return m.group(2) if name == "generic_assign_secret" else m.group(0)


def scan_file(path: Path, max_bytes: int) -> tuple[list, str, int | None]:
    """扫单文件，返回 (命中, 计数口径, 字节数)。口径 ∈ scanned/zero_byte/too_big/oserror。

    字节数随读数一起交出去，调用方**不要再 stat 一次**：这是一棵别的会话正在写的树，
    两次 stat 之间文件可以消失，那会让整台仪器以 rc=1 崩在 0/3/4 契约之外。
    去重键 = `(pattern, 绝对起始偏移, token 字节长)`：OVERLAP=64 会让落在块尾的匹配在下一块
    里被**再找一次**，旧版因此双计。绝对偏移 = 已读字节数 - 上一块保留的尾部长度 + 块内位置，
    首块无尾部 ⇒ 退化为块内位置。键里含 pattern ⇒ 同一位置被两条正则各命中一次时不会被误并
    （真键家族 15+6 就是这么分布的）。
    """
    hits: list = []
    try:
        size = path.stat().st_size
    except OSError:
        return hits, "oserror", None
    if size == 0:
        return hits, "zero_byte", size
    if size > max_bytes:
        return hits, "too_big", size
    seen: set = set()
    try:
        with path.open("rb") as fh:
            prev_tail = b""
            offset = 0
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                buf = prev_tail + chunk
                for name, rx in PATTERNS.items():
                    for m in rx.finditer(buf):
                        tok = shape_of_token(name, m)
                        if b"\x00" in tok:
                            continue
                        key = (name, offset - len(prev_tail) + m.start(), len(tok))
                        if key in seen:
                            continue
                        seen.add(key)
                        hits.append({"pattern": name, **shape(tok)})
                prev_tail = buf[-OVERLAP:]
                offset += len(chunk)
    except OSError:
        # 半路读挂：命中如实保留（宁可多报），但本文件不算"读到结尾"
        return hits, "oserror", size
    return hits, "scanned", size


def walk_files(repo: Path) -> tuple[list, list]:
    """一次 os.walk，产出 (保留下来的文件路径, 本层被剪掉的目录名)。剪枝判据仍是 SKIP_DIR_NAMES。"""
    kept: list = []
    pruned: list = []
    for root, dirs, names in os.walk(repo):
        pruned += [d for d in dirs if d in SKIP_DIR_NAMES]
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
        kept += [Path(root) / n for n in names]
    return kept, pruned


def relative_to(repo: Path, path: Path) -> str | None:
    """规范化相对路径（posix 分隔）；不在 repo 内则返回 None。"""
    try:
        return str(path.relative_to(repo)).replace("\\", "/")
    except ValueError:
        return None


def scan_repo(repo: Path, max_bytes: int) -> tuple[list, list]:
    """遍历一次，产出逐文件读数 ``[(rel, 命中, 口径, 字节数)]`` 与目录剪枝名单。只读数，不判定。"""
    paths, pruned_dirs = walk_files(repo)
    rows = [
        (rel, *scan_file(p, max_bytes))
        for p in paths
        if (rel := relative_to(repo, p)) is not None
    ]
    return rows, pruned_dirs


def tracking_of(rel: str, tracked: set, git_ok: bool) -> bool | str:
    """True/False = 可信判定；``"unknown"`` = git 列表失败。

    这是**全局**置 unknown 而非逐文件判断——列表失败时没有任何信息能区分谁被跟踪，
    此时把"尺子坏了"翻译成 False（= 未跟踪 = 不判停）就是 §3#7 那个毛病。
    """
    return "unknown" if not git_ok else rel in tracked


def stop_indicators(per_file: dict) -> list:
    """停手指征 = 真凭据形状命中 **且** 该文件确认为受跟踪，返回 [(rel, pattern)] 有序去重。"""
    return sorted(
        {
            (rel, h["pattern"])
            for rel, info in per_file.items()
            if info["tracked"] is True
            for h in info["hits"]
            if h["pattern"] in STOP_PATTERNS
        }
    )


def build_summary(rows: list, per_file: dict, pruned_dirs: list) -> dict:
    """口径三拆：``files_scanned`` 只数"打开并读到结尾"，其余进 skipped / skipped_dirs。

    旧口径把 0 字节与超限文件也算进 files_scanned ⇒ "71,159" 不是覆盖数。
    """
    status = Counter(s for _, _, s, _ in rows)
    by_pattern: dict = {}
    for rel, info in per_file.items():
        for h in info["hits"]:
            entry = by_pattern.setdefault(h["pattern"], {"files": set(), "n": 0})
            entry["files"].add(rel)
            entry["n"] += 1
    return {
        "files_scanned": status["scanned"],
        "skipped": {
            "zero_byte": status["zero_byte"],
            "too_big": status["too_big"],
            "oserror": status["oserror"],
        },
        "skipped_dirs": dict(sorted(Counter(pruned_dirs).items())),
        "files_with_hits": len(per_file),
        "tracked_with_hits": sorted(
            k for k, v in per_file.items() if v["tracked"] is True
        ),
        "untracked_with_hits": sorted(
            k for k, v in per_file.items() if v["tracked"] is False
        ),
        "unknown_with_hits": sorted(
            k for k, v in per_file.items() if v["tracked"] == "unknown"
        ),
        "by_pattern": {
            k: {"files": sorted(v["files"]), "n": v["n"]} for k, v in by_pattern.items()
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--max-mb", type=int, default=50)
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent / "scan-result.json"),
        help="结果 JSON 落点；标定一律显式指向 temp，避免覆盖 S1 基线",
    )
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    tracked, git_ok = tracked_paths(repo)
    rows, pruned_dirs = scan_repo(repo, args.max_mb << 20)
    per_file = {
        rel: {
            "tracked": tracking_of(rel, tracked, git_ok),
            "bytes": size,
            "hits": hits,
        }
        for rel, hits, _status, size in rows
        if hits
    }
    summary = build_summary(rows, per_file, pruned_dirs)
    stops = stop_indicators(per_file)
    out = Path(args.out)
    out.write_text(
        json.dumps(
            {"summary": summary, "per_file": per_file}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"明细（仅形状）已写: {out}")
    for rel, name in stops:
        print(f"[STOP] 真凭据形状命中受跟踪文件：{rel} pattern={name}")
    if not git_ok:
        return 4  # 仪器失效优先：它让上面 3 的判定不可信，两者同时成立时只能报 4
    return 3 if stops else 0


if __name__ == "__main__":
    sys.exit(main())
