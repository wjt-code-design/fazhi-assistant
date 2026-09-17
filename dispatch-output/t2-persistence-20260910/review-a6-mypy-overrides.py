"""只读复核 A6 已知限制：pyproject.toml 的 mypy override 范围核查。

文档声明：backend/pyproject.toml 对冻结文件 agent/verifier.py 用了"最窄的"
disable_error_code = ["var-annotated"] override，且复核者应确认该 override **只**涉及这一条。
本脚本列出全部 override 块，并单独核对 verifier.py。
"""

from __future__ import annotations

import json
import pathlib
import re

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
PYPROJECT = BACKEND / "pyproject.toml"
T7 = BACKEND.parent / "dispatch-output" / "t2-persistence-20260910" / "candidate-manifest-20260910.json"

text = PYPROJECT.read_text(encoding="utf-8")
start = text.find("[tool.mypy]")
seg = text[start:]
m = re.search(r"^\[tool\.(?!mypy)", seg, re.M)
if m:
    seg = seg[: m.start()]

print("=" * 72)
print("A6 已知限制核查 — pyproject.toml mypy override 范围")
print("=" * 72)

print("--- mypy 主配置关键项 ---")
for key in ("mypy_path", "explicit_package_bases", "exclude", "python_version"):
    hit = re.search(rf"^{key}\s*=\s*(.+)$", seg, re.M)
    print(f"  {key:<24} = {hit.group(1).strip() if hit else '(未设置)'}")

blocks = re.findall(
    r"\[\[tool\.mypy\.overrides\]\]\s*module\s*=\s*\"([^\"]+)\"\s*"
    r"(?:include_untracked\s*=\s*\w+\s*)?"
    r"disable_error_code\s*=\s*\[([^\]]*)\]",
    seg,
)
print()
print(f"--- 全部 override 块（共 {len(blocks)} 个）---")
for mod, codes in blocks:
    clean = ", ".join(c.strip().strip('"') for c in codes.split(",") if c.strip())
    marker = "  <<< 冻结物" if "verifier" in mod else ""
    print(f"  {mod:<38} -> [{clean}]{marker}")

print()
print("--- verifier.py 专项核对 ---")
verifier = [(mod, codes) for mod, codes in blocks if "verifier" in mod]
if not verifier:
    print("  !! 未找到任何针对 verifier 的 override 块")
else:
    for mod, codes in verifier:
        clean = [c.strip().strip('"') for c in codes.split(",") if c.strip()]
        print(f"  module           = {mod}")
        print(f"  disable_error_code = {clean}")
        print(f"  错误码条数        = {len(clean)}   文档声明: 仅 ['var-annotated'] 一条")
        print(f"  >>> 判定: {'一致 OK' if clean == ['var-annotated'] else '不一致 MISMATCH'}")

# verifier.py 是否确为冻结物
frozen = json.loads(T7.read_text(encoding="utf-8"))["frozen_files_sha256"]
print()
print("--- 冻结物清单（T7 manifest，13 个）---")
for rel in sorted(frozen):
    tag = "  <<< 被 override" if "verifier" in rel else ""
    print(f"  {rel}{tag}")
hits = [rel for rel in frozen if "verifier" in rel]
print(f"  verifier 在冻结清单中的条目: {hits if hits else '无'}")
