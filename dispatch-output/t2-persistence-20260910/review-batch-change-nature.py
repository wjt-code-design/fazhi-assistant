"""只读核查：19:40 批量改动（120 个文件）的性质与语义风险。

背景：T7 manifest 于 14:24 采集（17 个候选），T8 manifest 于 20:33 采集（139 个候选）。
期间 19:40 有约 120 个文件被批量修改 ⇒ 这是 A1 "新增候选文件" 声明为 0 却实测 122 的根因。

本脚本判定：
  1) 这批改动是否纯格式化（git diff -w 忽略空白后还剩多少）；
  2) 是否含 ruff --fix 的语义改动（重点：UP017 把 timezone.utc 换成 datetime.UTC）；
  3) datetime.UTC 在 Python 3.10 不存在 ⇒ 若目标服务器为 3.10（auth.py 注释自述），
     则属部署期 ImportError 风险。
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


print("=" * 78)
print("1) 批量改动的性质：含空白 vs 忽略空白")
print("=" * 78)
full = git("diff", "--stat", "--", "backend").strip().splitlines()
nows = git("diff", "-w", "--stat", "--", "backend").strip().splitlines()
print(f"  git diff --stat    末行: {full[-1].strip() if full else '(空)'}")
print(f"  git diff -w --stat 末行: {nows[-1].strip() if nows else '(空)'}")
print(f"  => 忽略空白后仍有实质改动的文件数: {len(nows) - 1 if nows else 0}")

print()
print("=" * 78)
print("2) UP017 类语义改动（timezone.utc -> datetime.UTC）扫描")
print("=" * 78)
diff = git("diff", "-U0", "--", "backend")
added_utc_import = []
removed_tz = []
selfassign = []
for line in diff.splitlines():
    if line.startswith("+++ b/"):
        cur = line[6:]
    elif line.startswith("+") and re.search(r"from datetime import[^\n]*\bUTC\b", line):
        added_utc_import.append((cur, line[1:].strip()))
    elif line.startswith("-") and "timezone.utc" in line:
        removed_tz.append((cur, line[1:].strip()))
    elif line.startswith("+") and re.search(r"^\+\s*UTC\s*=\s*UTC\b", line):
        selfassign.append((cur, line[1:].strip()))

print(f"  新增 'from datetime import ... UTC' 的文件数 = {len(added_utc_import)}")
for f, s in added_utc_import[:12]:
    print(f"      {f:<44} {s[:60]}")
if len(added_utc_import) > 12:
    print(f"      …（共 {len(added_utc_import)} 处）")
print(f"  删除含 'timezone.utc' 行的处数 = {len(removed_tz)}")
for f, s in removed_tz[:8]:
    print(f"      {f:<44} {s[:60]}")
print(f"  出现自赋值 'UTC = UTC' 的处数 = {len(selfassign)}")
for f, s in selfassign[:8]:
    print(f"      {f:<44} {s[:60]}")

print()
print("=" * 78)
print("3) 运行时版本 vs 代码自述的目标版本")
print("=" * 78)
print(f"  本机 venv Python = {sys.version.split()[0]}")
print(f"  datetime.UTC 可用 = {hasattr(__import__('datetime'), 'UTC')}（3.11+ 才有）")
auth = (BACKEND / "auth.py").read_text(encoding="utf-8")
for i, line in enumerate(auth.splitlines(), 1):
    if "UTC" in line and i <= 8:
        print(f"  backend/auth.py L{i}: {line.rstrip()}")
m = re.search(r"#.*服务器为\s*3\.(\d+)", auth)
print(f"  代码自述目标版本: {'3.' + m.group(1) if m else '（未找到）'}")
print()
print("  >>> 风险判定：若部署环境确为 3.10，'from datetime import UTC' 将在导入期抛 ImportError。")
print("      本机 venv 为 3.11 ⇒ 全量测试无法暴露该风险（A3 的 924 passed 不构成反证）。")

print()
print("=" * 78)
print("4) 其他 ruff 自动修复痕迹（抽样统计改动类型）")
print("=" * 78)
kinds = {
    "空行/换行调整": 0,
    "长行拆分(括号包裹)": 0,
    "import 相关": 0,
    "其他": 0,
}
for line in diff.splitlines():
    if not (line.startswith("+") or line.startswith("-")) or line[:3] in ("+++", "---"):
        continue
    body = line[1:].strip()
    if not body:
        kinds["空行/换行调整"] += 1
    elif "import" in body:
        kinds["import 相关"] += 1
    elif body.endswith("(") or body.startswith(")"):
        kinds["长行拆分(括号包裹)"] += 1
    else:
        kinds["其他"] += 1
for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
    print(f"  {k:<22} {v}")
