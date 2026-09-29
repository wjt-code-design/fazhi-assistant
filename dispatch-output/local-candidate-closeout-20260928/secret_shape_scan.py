"""凭据**形状**普查（只输出路径 + 掩码形态，永不输出值本身）。

为什么不用"读 .env 反查真值"那套：本仓已经因为一次读 `.env` 的检查把 rerank 凭据打印进了工具输出
（见交接书 §6①，它正是当前挡着真实 rerank 的那把 key）。所以这个脚本从结构上不给泄漏机会：

  * 输入是 `git show <rev>:<path>` 的字节流或普通文件；
  * 输出只有 **文件路径、命中条数、长度、首尾各 ≤3 字符、上下文里已被打掉的字母数字串**；
  * 命中值本身**从不**进入 print 的参数——只取 `m[:3]` / `m[-2:]` 与 `len(m)`。

判据口径（三条缺一会假绿）：
  1. **正向对照**：`--selftest` 会造一枚假 key 验证这把尺子**能红**；尺子不能红时"0 命中"没有意义。
  2. **归因上下文**：命中点前 60 字符里的长字母数字串会被 `<MASK>` 打掉，用来区分"真 key" 与
     "URL/哈希里恰好含 `sk-` 的巧合子串"。
  3. **形状只覆盖公开前缀**（sk-/AKIA/LTAI/PRIVATE KEY/JWT 两段），它是**下界**不是全集；
     自定义命名的口令必须靠 Owner 本机按**值**反查（那条命令见交接书"整合准备"节）。

用法：
    python secret_shape_scan.py --selftest                 # 先证尺子能红
    python secret_shape_scan.py master fbc29e8             # 对两棵树的已跟踪内容普查
    python secret_shape_scan.py --file some/path.json      # 单文件
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PATTERNS = {
    "openai-ish sk-": r"sk-[A-Za-z0-9]{20,}",
    "AWS AKIA": r"AKIA[0-9A-Z]{16}",
    "Aliyun LTAI": r"LTAI[A-Za-z0-9]{12,}",
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "JWT (two segments)": r"eyJ[A-Za-z0-9_-]{12,}\.eyJ[A-Za-z0-9_.-]{8,}",
}
MASK_RE = re.compile(r"[A-Za-z0-9+/=_-]{8,}")


def mask(text: str) -> str:
    return MASK_RE.sub("<MASK>", text)


def shape(match: str) -> str:
    """只描述形状，绝不返回原值。"""
    head, tail = match[:3], match[-2:]
    return f"len={len(match)} shape={head}…{tail}"


def scan_text(label: str, text: str) -> list[str]:
    findings: list[str] = []
    for name, pat in PATTERNS.items():
        for m in re.finditer(pat, text):
            i = m.start()
            ctx = mask(text[max(0, i - 60) : i]).replace("\n", " ")[-48:]
            findings.append(f"{label} [{name}] {shape(m.group(0))}  preceded-by: …{ctx}")
    return findings


def git_blob(rev: str, path: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), "show", f"{rev}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout


def tree_files(rev: str, cwd: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(cwd), "ls-tree", "-r", "--name-only", rev],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout
    return [ln for ln in out.splitlines() if ln.strip()]


def selftest() -> int:
    """尺子必须能红：造一枚明显是假值的 key，扫不出来就判本件失效。"""
    fake = 'token = "sk-' + "Z" * 32 + '"'
    got = scan_text("<selftest>", fake)
    files_hit = 0
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        if subprocess.run(["git", "-C", str(repo), "init", "-q"], capture_output=True, check=False).returncode == 0:
            (repo / "probe.txt").write_text(fake, encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "probe.txt"], capture_output=True, check=False)
            head = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, check=False
            )
            if head.returncode != 0:
                subprocess.run(
                    ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                     "commit", "-q", "-m", "probe"],
                    capture_output=True,
                    check=False,
                )
            for p in tree_files("HEAD", repo):
                files_hit += len(scan_text(p, git_blob("HEAD", p, repo)))
    print(f"[selftest] 文本轴命中 {len(got)} 处 / git 树轴命中 {files_hit} 处")
    if len(got) < 1 or files_hit < 1:
        print("[selftest] 🚨 尺子没能红——本件的 0 命中读数不可采信")
        return 1
    print("[selftest] OK（能红）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("revs", nargs="*", help="要普查的 tree-ish（如 master fbc29e8）")
    ap.add_argument("--file", help="单个文件路径")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--root", default=str(Path(r"C:/Users/33393/Desktop/ai-legal-helper")))
    a = ap.parse_args()
    rc = 0
    if a.selftest:
        rc |= selftest()
    if a.file:
        f = Path(a.file)
        found = scan_text(f.name, f.read_text(encoding="utf-8", errors="replace"))
        print(f"### file {a.file}: {len(found)} hit(s)")
        for line in found:
            print("  ", line)
        rc |= 1 if found else 0
    cwd = Path(a.root)
    alt = "|".join(PATTERNS.values())
    for rev in a.revs:
        allf = tree_files(rev, cwd)
        # 先用 git grep 收窄到"可能命中"的文件，再逐文件做掩码归因；不收窄会对几千个文件各起一次 git show。
        prelim = subprocess.run(
            ["git", "-C", str(cwd), "grep", "-l", "-E", alt, rev, "--"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        ).stdout
        cand = sorted({ln.split(":", 1)[1] for ln in prelim.splitlines() if ":" in ln})
        hits: list[str] = []
        for p in cand:
            hits.extend(scan_text(p, git_blob(rev, p, cwd)))
        paths = sorted({h.split(" [")[0] for h in hits})
        print(
            f"### tree {rev}: 已跟踪 {len(allf)} 文件 → 预筛 {len(cand)} → 命中 {len(hits)} 处 / {len(paths)} 个文件"
            f"（预筛用的是同一组形状，漏在预筛=漏在普查）"
        )
        for h in hits:
            print("  ", h)
        rc |= 1 if hits else 0
    if not a.revs and not a.file and not a.selftest:
        print("没给对象：用 --selftest 或传 tree-ish / --file")
        return 2
    print(f"\n[exit] rc={rc}（1=有形状命中；命中≠真凭据，须逐条归因）")
    return rc


if __name__ == "__main__":
    sys.exit(main())
