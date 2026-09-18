"""S1：递归扫描全仓的**密钥形状**（只报形状，永不打印值）。

为什么要重做：R15 会话的上一次扫描**没有加 -r**（不递归目录内部），所以"命中 1 个"是**下界**。
本脚本递归全部文件，命中只输出 `len / has_digit / charset 前 8 个字母 / sha256 前 12 位`，
**绝不把匹配到的原文写进终端或任何文件**（防值经日志/终端记录外流）。

用法：backend/venv/Scripts/python.exe scan_trace_shape.py [--repo <根>] [--max-mb 50]
输出：stdout 摘要 + scan-result.json（形状级，可安全入库）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "openai_style_sk": re.compile(rb"sk-[A-Za-z0-9]{20,}"),
    "aws_akid": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "jwt_like": re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{5,}"),
    "generic_assign_secret": re.compile(
        rb"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*['\"]([A-Za-z0-9+/_-]{20,})['\"]"
    ),
}
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


def shape(tok: bytes) -> dict:
    return {
        "len": len(tok),
        "has_digit": any(c in b"0123456789" for c in tok),
        "letters_head8": "".join(sorted({chr(c) for c in tok if chr(c).isalpha()}))[:8],
        "sha256_12": hashlib.sha256(tok).hexdigest()[:12],
    }


def tracked_paths(repo: Path) -> set:
    r = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        capture_output=True,
        text=False,
        check=False,
    )
    return {p.decode("utf-8", "replace") for p in r.stdout.split(b"\x00") if p}


def scan_file(path: Path, max_bytes: int) -> list:
    hits = []
    try:
        size = path.stat().st_size
        if size == 0 or size > max_bytes:
            return hits
        with path.open("rb") as fh:
            prev_tail = b""
            offset = 0
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                buf = prev_tail + chunk
                for name, rx in PATTERNS.items():
                    for m in rx.finditer(buf):
                        tok = (
                            m.group(2)
                            if name == "generic_assign_secret"
                            else m.group(0)
                        )
                        if b"\x00" in tok:
                            continue
                        hits.append({"pattern": name, **shape(tok)})
                prev_tail = buf[-OVERLAP:]
                offset += len(chunk)
    except OSError:
        return hits
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--max-mb", type=int, default=50)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    tracked = tracked_paths(repo)
    files_scanned = 0
    per_file = {}
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
        for n in names:
            p = Path(root) / n
            try:
                rel = str(p.relative_to(repo)).replace("\\", "/")
            except ValueError:
                continue
            files_scanned += 1
            hits = scan_file(p, args.max_mb << 20)
            if hits:
                per_file[rel] = {
                    "tracked": rel in tracked,
                    "bytes": p.stat().st_size,
                    "hits": hits,
                }
    summary = {
        "files_scanned": files_scanned,
        "files_with_hits": len(per_file),
        "tracked_with_hits": sorted(k for k, v in per_file.items() if v["tracked"]),
        "untracked_with_hits": sorted(
            k for k, v in per_file.items() if not v["tracked"]
        ),
        "by_pattern": {},
    }
    for rel, info in per_file.items():
        for h in info["hits"]:
            entry = summary["by_pattern"].setdefault(
                h["pattern"], {"files": set(), "n": 0}
            )
            entry["files"].add(rel)
            entry["n"] += 1
    summary["by_pattern"] = {
        k: {"files": sorted(v["files"]), "n": v["n"]}
        for k, v in summary["by_pattern"].items()
    }
    out = Path(__file__).resolve().parent / "scan-result.json"
    out.write_text(
        json.dumps(
            {"summary": summary, "per_file": per_file}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"明细（仅形状）已写: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
