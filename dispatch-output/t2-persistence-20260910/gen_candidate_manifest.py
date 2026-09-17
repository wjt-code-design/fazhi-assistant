"""生成 T7 候选 manifest（post-C01fix）——把当前工作树重新锚定。

用法：在仓库根运行。
    backend/venv/Scripts/python.exe dispatch-output/t2-persistence-20260910/gen_candidate_manifest.py

背景：项目方法论把"候选"定义为**脏工作树 + 哈希锚定**（T0 manifest 原文：
"W1–W4 脏改动就地保留，未 commit、未 stash、未 reset"），**不是** git commit。
因此 C01 修复后候选已漂移，必须重新采集哈希，而不是提交。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = pathlib.Path(__file__).parent
REL = "release-evidence/legal-agent-v1-complex-v1-20260907"

# 本轮实现所编辑的 tracked 文件（git status 为准，脚本会校验实际一致性）
TRACKED_EXPECTED = [
    "backend/agent/controller.py",
    "backend/observability.py",
    "backend/agent/runtime.py",
    "backend/agent/service.py",
    "backend/agent/writer.py",
    "backend/scripts/gate2_runner.py",
    "backend/tests/test_agent_chat_integration.py",
    "backend/tests/test_agent_controller.py",
    "backend/tests/test_agent_gate.py",
    "backend/tests/test_agent_resume.py",
    "backend/tests/test_agent_runtime.py",
    "backend/tests/test_agent_writer.py",
    "docs/v2-optimization-execution-taskbook-20260909.md",
]

# 关键未跟踪源码/测试（属候选的一部分，按 T0 惯例列出并锚定；不 git add）
UNTRACKED_SOURCES = [
    "backend/scripts/review_sidecar.py",
    "backend/tests/test_agent_coverage_loop.py",
    "backend/tests/test_gate2_runner.py",
    "backend/tests/test_review_sidecar.py",
]

FROZEN = [
    ("backend/agent/verifier.py", "判定逻辑"),
    ("backend/agent/chat_integration.py", "equality guard / CAS / ownership"),
    ("backend/agent/state_machine.py", "状态机"),
    ("backend/agent/repository.py", "compare_and_save"),
    ("backend/prompts.py", "系统提示词常量"),
    ("backend/scripts/gate5_judge.py", "冻结判分器"),
    (f"{REL}/frozen-cases-v1.json", "冻结题集 C01-C10"),
    (f"{REL}/frozen-fact-ids-v1.json", "冻结事实 ID"),
    (f"{REL}/frozen-round-protocol-v1.json", "冻结轮次协议"),
    (f"{REL}/hidden-cases-v1.json", "hidden 题集") if (ROOT / f"{REL}/hidden-cases-v1.json").exists() else ("dispatch-output/task1/hidden-cases-v1.json", "hidden 题集"),
    ("dispatch-output/task1/hidden-round-protocol-v1.json", "hidden 协议"),
    ("dispatch-output/task1/hidden-commitment.json", "hidden 承诺"),
    ("dispatch-output/task1/salt.txt", "salt"),
]


def sha(rel: str) -> str | None:
    p = ROOT / rel
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> None:
    head = git("rev-parse", "HEAD")
    # 注意：不要对 status 整体 .strip()（会吃掉第一行的前导空格，把路径切错一位）。
    raw_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    ).stdout.splitlines()
    # 每行形如 "XY path"（XY 为 2 字符状态位）→ 取 [2:] 再 strip，兼容首行被 strip 的情形
    tracked_actual = sorted(l[2:].strip() for l in raw_status if l and l[:2].strip() in ("M", "A", "D", "R"))
    untracked_actual = sorted(l[2:].strip() for l in raw_status if l.startswith("??"))

    warn = []
    if tracked_actual != sorted(TRACKED_EXPECTED):
        warn.append("tracked 修改集合与预期不符：\n  实际=%s\n  预期=%s" % (tracked_actual, sorted(TRACKED_EXPECTED)))
    for f in [*tracked_actual, *UNTRACKED_SOURCES, *(p for p, _ in FROZEN)]:
        if not (ROOT / f).exists():
            warn.append(f"锚定文件不存在：{f}")

    lines = []
    a = lines.append
    a("# T7 候选 manifest（post-C01fix）—— 2026-09-10 重采")
    a("")
    a(f"采集时间（UTC）：{datetime.now(timezone.utc).isoformat()}")
    a(f"采集方式：Git Bash `git rev-parse HEAD` / `git status --porcelain` + Python hashlib SHA256")
    a("")
    a("## 这份 manifest 为什么存在")
    a("")
    a("T7 预登记用的 `t7-run12-manifest.json` 是在 **C01 修复之前**采集的，其 `dirty_files_sha256`")
    a("已不能锚定当前候选（`controller.py` 新增改动、`test_agent_chat_integration.py` 已漂移）。")
    a("按项目方法论（T0 manifest：\"脏改动就地保留，未 commit、未 stash、未 reset\"），")
    a("**修正候选的正确做法是重新采集哈希，而不是 git commit**——本文件即该重采结果，**取代**")
    a("`t7-run12-manifest.json` 中的 `dirty_files_sha256` 用于候选锚定。")
    a("")
    a("## HEAD 与工作区")
    a("")
    a(f"- HEAD：`{head}`")
    a(f"- 分支：`{git('branch','--show-current')}`（工作树**有意保持脏**，不 commit / 不 stash / 不 reset）")
    a(f"- tracked 修改（{len(tracked_actual)}）：")
    for f in tracked_actual:
        a(f"  - `{f}`")
    a(f"- 关键未跟踪源码/测试（{len(UNTRACKED_SOURCES)}）：属候选的一部分，列出并锚定，**不 git add**")
    for f in UNTRACKED_SOURCES:
        a(f"  - `{f}`")
    a("")
    a("## 候选代码 SHA256")
    a("")
    a("| 文件 | SHA256（全 64 位） | 角色 |")
    a("|---|---|---|")
    for f in tracked_actual:
        h = sha(f)
        a(f"| `{f}` | `{h}` | 本轮编辑 |")
    for f in UNTRACKED_SOURCES:
        h = sha(f)
        a(f"| `{f}` | `{h}` | 未跟踪（候选的一部分） |")
    a("")
    a("## 冻结物 SHA256（本轮不得变化）")
    a("")
    a("| 产物 / 文件 | SHA256（全 64 位） | 说明 |")
    a("|---|---|---|")
    for f, note in FROZEN:
        h = sha(f) or "（缺失）"
        a(f"| `{f}` | `{h}` | {note} |")
    a("")
    a("## 与上一份 manifest 的差异（候选 delta）")
    a("")
    a("| 相对 `t7-run12-manifest.json` | 说明 |")
    a("|---|---|")
    a("| `backend/agent/controller.py` | **新增改动**（C01 修复：`_every_issue_retrieval_attempted` + 幂等转移短路，+64 行） |")
    a("| `backend/tests/test_agent_chat_integration.py` | **已漂移**（新增 3 条 C01 回归测试 / `_MultiIssueTransport` 护栏） |")
    a("| 其余 12 个 tracked 文件 | 与预登记一致 |")
    a("")
    a("## 本轮实现质量证据（离线，非付费）")
    a("")
    a("- 全量 `tests/`（70 模块）：**903 passed / 0 failed**（`dispatch-output/t2-persistence-20260909/fix-v2-final-junit.xml`）")
    a("- agent 17 模块子集：**362 passed / 0 failed**（`fix-v2-agent17-junit.xml`）")
    a("- 冻结物复核脚本：`dispatch-output/t2-persistence-20260909/verify_frozen_for_handoff.py`")
    a("")
    a("## 红线（沿用 T0，仍然有效）")
    a("")
    a("- 不 commit / 不 stash / 不 reset（候选 = 脏工作树）")
    a("- 不清扫、不 git add `diag/`、`dispatch-output/`、`release-evidence/`、`.workbuddy/`")
    a("- 不修改冻结物（verifier / chat_integration / state_machine / repository / prompts / gate5_judge / frozen-* / hidden-* / 历史 sessions）")
    a("- 不并行跑共享数据库 / 端口 / 付费账户")
    a("")
    if warn:
        a("## ⚠️ 采集告警")
        a("")
        for w in warn:
            a(f"- {w}")
        a("")

    out = OUT_DIR / "candidate-manifest-20260910.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("written:", out.relative_to(ROOT))
    print("HEAD:", head)
    print("tracked 修改:", len(tracked_actual), " 未跟踪源码:", len(UNTRACKED_SOURCES), " 冻结物:", len(FROZEN))
    if warn:
        print("!! 告警：")
        for w in warn:
            print("  ", w)

    # 顺带产出机器可读版，便于后续脚本比对
    machine = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "branch": git("branch", "--show-current"),
        "candidate_files_sha256": {f: sha(f) for f in [*tracked_actual, *UNTRACKED_SOURCES]},
        "frozen_files_sha256": {f: sha(f) for f, _ in FROZEN},
        "supersedes": "t7-run12-manifest.json#dirty_files_sha256",
    }
    (OUT_DIR / "candidate-manifest-20260910.json").write_text(
        json.dumps(machine, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("written:", (OUT_DIR / "candidate-manifest-20260910.json").relative_to(ROOT))


if __name__ == "__main__":
    main()
