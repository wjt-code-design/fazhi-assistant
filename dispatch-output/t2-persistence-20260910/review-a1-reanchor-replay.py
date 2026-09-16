"""只读复现 reanchor_t8_manifest.py 的 added / changed / stale 三个计数。
逐行照抄原脚本逻辑，但不写任何文件。目的：验证文档 §3.1 声明的
"变化 15 / 新增 0 / 腐化 0" 是否与脚本在当前工作树下的真实输出一致。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "dispatch-output" / "t2-persistence-20260910"
OLD = D / "candidate-manifest-20260910.json"          # T7，脚本的 OLD
T8 = D / "candidate-manifest-t8-20260910.json"        # 脚本产出的 T8


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


old = json.loads(OLD.read_text(encoding="utf-8"))

# ---- 照抄原脚本 41-46 行：changed ----
changed: list[str] = []
for rel, expect in old["candidate_files_sha256"].items():
    got = sha(rel)
    if got != expect:
        changed.append(rel)

# ---- 照抄原脚本 51-70 行：dirty / untracked_new / added ----
porcelain_lines = git("status", "--porcelain").splitlines()
dirty = sorted(
    line[2:].strip()
    for line in porcelain_lines
    if line[:2].strip() in {"M", "A"} and line[2:].strip()
)
known = set(old["candidate_files_sha256"])
untracked_new = sorted(
    rel
    for rel in (
        line[2:].strip()
        for line in porcelain_lines
        if line[:2].strip() == "??"
    )
    if rel.startswith("backend/") and rel.endswith(".py") and rel not in known
)
added = [rel for rel in dirty if rel not in known] + untracked_new

# ---- 照抄原脚本 79-80 行：stale ----
tracked = set(git("ls-files").splitlines())
new_candidate = dict(old["candidate_files_sha256"])
for rel in added:
    new_candidate[rel] = sha(rel)
stale = [rel for rel in new_candidate if rel in tracked and rel not in dirty]

print("=" * 72)
print("照抄 reanchor 脚本逻辑的只读复算结果")
print("=" * 72)
print(f"  T7(OLD) candidate 键数      = {len(old['candidate_files_sha256'])}")
print(f"  known 集合大小              = {len(known)}")
print(f"  dirty (porcelain M/A)       = {len(dirty)}")
print(f"  untracked_new               = {len(untracked_new)}")
print()
print(f"  >>> changed 复算 = {len(changed)}    文档声明 15")
print(f"  >>> added   复算 = {len(added)}    文档声明 0")
print(f"  >>> stale   复算 = {len(stale)}    文档声明 0")
print()
print(f"  复算后 candidate 总数 = {len(new_candidate)}   T8 manifest 实际 = "
      f"{len(json.loads(T8.read_text(encoding='utf-8'))['candidate_files_sha256'])}")
print()
print("--- added 前 25 个（文档声明此列表应为空）---")
for rel in added[:25]:
    print(f"    {rel}")
if len(added) > 25:
    print(f"    …（共 {len(added)} 个，其余省略）")
print()
print("--- known(17) 中有哪些在 dirty 里 ---")
in_dirty = sorted(known & set(dirty))
print(f"    {len(in_dirty)} 个: {in_dirty}")
print("--- known(17) 中有哪些不在 dirty 里 ---")
not_dirty = sorted(known - set(dirty))
print(f"    {len(not_dirty)} 个: {not_dirty}")
