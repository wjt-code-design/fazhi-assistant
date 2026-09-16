"""复核者只读复算 A1 / A2（不运行实现者的 reanchor 脚本，避免覆盖被复核的锚定文件）。

A1: T8 锚定 manifest 的 candidate + frozen 哈希 vs 当前工作树 → 漂移应为 0
A2: T7 基线 manifest 的 frozen 哈希 vs 当前工作树 → 漂移应为 0
附: 用 T7 vs T8 两份 manifest 只读地复算 "变化 15 / 新增 0 / 腐化 0" 三个 delta 声明
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "dispatch-output" / "t2-persistence-20260910"
T7 = D / "candidate-manifest-20260910.json"
T8 = D / "candidate-manifest-t8-20260910.json"


def sha(rel: str) -> str | None:
    p = ROOT / rel
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def drift(manifest: dict, section: str) -> tuple[int, list[str]]:
    bad: list[str] = []
    for rel, expect in manifest[section].items():
        got = sha(rel)
        if got != expect:
            bad.append(f"{rel} (expect {str(expect)[:12]}…, got {str(got)[:12] if got else 'MISSING'})")
    return len(bad), bad


def main() -> None:
    t7 = json.loads(T7.read_text(encoding="utf-8"))
    t8 = json.loads(T8.read_text(encoding="utf-8"))

    print("=" * 72)
    print("A1 — T8 锚定 manifest vs 当前工作树")
    print("=" * 72)
    print(f"T8 manifest: {T8.name}")
    print(f"  HEAD 记录于 manifest : {t8.get('head')}")
    print(f"  HEAD 实际            : {git('rev-parse', 'HEAD').strip()}")
    print(f"  candidate 文件数     : {len(t8['candidate_files_sha256'])}")
    print(f"  frozen    文件数     : {len(t8['frozen_files_sha256'])}")
    for section in ("candidate_files_sha256", "frozen_files_sha256"):
        n, bad = drift(t8, section)
        flag = "OK" if n == 0 else "DRIFT"
        print(f"  [{flag}] {section}: 漂移 {n}")
        for line in bad:
            print(f"        - {line}")

    print()
    print("=" * 72)
    print("A2 — T7 基线 manifest 的冻结物 vs 当前工作树")
    print("=" * 72)
    print(f"T7 manifest: {T7.name}")
    print(f"  frozen 文件数        : {len(t7['frozen_files_sha256'])}")
    n, bad = drift(t7, "frozen_files_sha256")
    flag = "OK" if n == 0 else "DRIFT"
    print(f"  [{flag}] 冻结漂移 = {n}")
    for line in bad:
        print(f"        - {line}")

    print()
    print("=" * 72)
    print("附 — 只读复算 reanchor 脚本声称的三个 delta（T7 → T8）")
    print("=" * 72)
    c7, c8 = t7["candidate_files_sha256"], t8["candidate_files_sha256"]
    changed = sorted(r for r in c7 if r in c8 and c7[r] != c8[r])
    added = sorted(set(c8) - set(c7))
    print(f"  变化（T7 有且哈希不同）= {len(changed)}   声明 15")
    for rel in changed:
        print(f"        - {rel}")
    print(f"  新增（T8 有 T7 无）    = {len(added)}   声明 0")
    for rel in added:
        print(f"        - {rel}")

    porcelain = git("status", "--porcelain").splitlines()
    dirty = sorted(
        line[2:].strip()
        for line in porcelain
        if line[:2].strip() in {"M", "A"} and line[2:].strip()
    )
    tracked = set(git("ls-files").splitlines())
    stale = [rel for rel in c8 if rel in tracked and rel not in dirty]
    print(f"  清单腐化（锚定集内 tracked 但不脏）= {len(stale)}   声明 0")
    for rel in stale:
        print(f"        - {rel}")

    print()
    print(f"  [口径核对] git status --porcelain 中 M/A 脏文件总数 = {len(dirty)}")
    print(f"  [口径核对] git status --short 总行数               = {len(porcelain)}")
    print(f"  [口径核对] 其中未跟踪(??)条目                      = "
          f"{sum(1 for line in porcelain if line[:2].strip() == '??')}")
    print(f"  [口径核对] T8 manifest 记录的 dirty_tracked        = {len(t8.get('git_status_dirty_tracked', []))}")
    print(f"  [口径核对] T8 manifest 记录的 untracked_new_source = "
          f"{len(t8.get('git_status_new_untracked_source', []))}")


if __name__ == "__main__":
    main()
