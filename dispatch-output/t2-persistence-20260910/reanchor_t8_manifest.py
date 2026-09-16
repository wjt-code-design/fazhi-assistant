"""V2-T8 重采候选锚定（改候选后必须重锚，不得沿用旧哈希）。

沿用 T7 manifest 的**文件集合**（candidate + frozen 两组），逐文件重算 SHA256，
输出新的 candidate-manifest-t8-20260910.json/.md，并打印与 T7 的 delta。
**取代**（不覆盖）candidate-manifest-20260910.json —— 旧文件保留留痕。
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = ROOT / "dispatch-output" / "t2-persistence-20260910"
OLD = D / "candidate-manifest-20260910.json"


def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    old = json.loads(OLD.read_text(encoding="utf-8"))
    new = {
        "collected_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "role": "V2-T8 候选锚定（分解契约加固后重采）",
        "supersedes": "candidate-manifest-20260910.json（T7 锚定，保留留痕）",
        "head": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "candidate_files_sha256": {},
        "frozen_files_sha256": {},
    }

    changed: list[str] = []
    for rel, expect in old["candidate_files_sha256"].items():
        got = sha(rel)
        new["candidate_files_sha256"][rel] = got
        if got != expect:
            changed.append(rel)

    # 防漏：旧清单只覆盖已知文件；若本轮**新增**了脏文件，必须一并纳入锚定（曾差点静默漏掉 settings.py）。
    # 注意：git() 对整体 stdout 做了 strip，首行状态码前的空格会被吃掉 ⇒ 用 line[2:].strip() 取路径，
    # 对 " M path" 与 "M path" 两种形态都成立（line[3:] 会在首行把路径吃成 'ackend/...'）。
    dirty = sorted(
        line[2:].strip()
        for line in git("status", "--porcelain").splitlines()
        if line[:2].strip() in {"M", "A"} and line[2:].strip()
    )
    known = set(old["candidate_files_sha256"])
    # 防漏（同类第二个缺口）：**新增的未跟踪候选源码**不出现在 porcelain 的 M/A 里
    # （本轮就新增了 backend/tests/test_log_field_whitelist.py）。按"backend/ 下的 .py 且未跟踪"纳入。
    untracked_new = sorted(
        rel
        for rel in (
            line[2:].strip()
            for line in git("status", "--porcelain").splitlines()
            if line[:2].strip() == "??"
        )
        if rel.startswith("backend/") and rel.endswith(".py") and rel not in known
    )
    for rel in untracked_new:
        new["candidate_files_sha256"][rel] = sha(rel)
    added = [rel for rel in dirty if rel not in known] + untracked_new
    for rel in dirty:
        if rel not in known:
            new["candidate_files_sha256"][rel] = sha(rel)
    new["git_status_dirty_tracked"] = dirty
    new["git_status_new_untracked_source"] = untracked_new

    # 反向核对：锚定集里的 **tracked** 文件必须都是脏的（否则清单已腐化）。
    # 未跟踪源码（review_sidecar.py 等）本就是候选的一部分，不出现在 porcelain 的 M/A 中，属正常。
    tracked = set(git("ls-files").splitlines())
    stale = [rel for rel in new["candidate_files_sha256"] if rel in tracked and rel not in dirty]
    new["untracked_candidate_files"] = sorted(
        rel for rel in new["candidate_files_sha256"] if rel not in tracked
    )

    frozen_drift: list[str] = []
    for rel, expect in old["frozen_files_sha256"].items():
        got = sha(rel)
        new["frozen_files_sha256"][rel] = got
        if got != expect:
            frozen_drift.append(rel)

    (D / "candidate-manifest-t8-20260910.json").write_text(
        json.dumps(new, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )

    lines = [
        "# V2-T8 候选锚定（分解契约加固后重采）— 2026-09-10",
        "",
        f"采集时间（UTC）：{new['collected_at_utc']}",
        f"HEAD：`{new['head']}`　分支：{new['branch']}",
        f"取代：`candidate-manifest-20260910.json`（T7 锚定，**保留留痕，未覆盖**）",
        "",
        "## 与 T7 锚定的 delta（本次改动的候选文件）",
        "",
    ]
    lines += [f"- `{rel}` —— **已变化**" for rel in changed] or ["- （候选文件无变化）"]
    if added:
        lines += ["", "## ⚠️ 新增候选文件（旧清单未覆盖 ⇒ 已纳入锚定）", ""] + [f"- `{rel}`" for rel in added]
    if stale:
        lines += ["", "## ⚠️ 锚定集中的 tracked 文件已不脏 ⇒ 清单腐化，需人工复核", ""] + [f"- `{rel}`" for rel in stale]
    lines += [
        "",
        f"候选文件总数：{len(new['candidate_files_sha256'])}；冻结文件总数：{len(new['frozen_files_sha256'])}",
        f"**冻结文件漂移：{len(frozen_drift)}**"
        + (f" —— ⚠️ {frozen_drift}" if frozen_drift else " ✅（冻结物未被本次改动触碰）"),
        "",
        "## 本次改动说明",
        "",
        "- `backend/agent/runtime.py`：分解契约加固（穷尽性提示词 + 事实分句覆盖度确定性检查 + 有界修复环）",
        "- `backend/observability.py`：登记 `agent_coverage_*` 与 `agent_pre_run_*` 诊断字段（修 handoff §12.3 的静默丢弃缺陷）",
        "- `backend/tests/test_agent_runtime.py`：新增 10 个用例（含终止性回归与白名单回归）",
        "",
        "## 复算方式",
        "",
        "```bash",
        "python - <<'PY'",
        "import json,hashlib,pathlib",
        "m=json.load(open('dispatch-output/t2-persistence-20260910/candidate-manifest-t8-20260910.json',encoding='utf-8'))",
        "for sec in ('candidate_files_sha256','frozen_files_sha256'):",
        "    for rel,exp in m[sec].items():",
        "        got=hashlib.sha256(pathlib.Path(rel).read_bytes()).hexdigest()",
        "        assert got==exp, (sec, rel)",
        "print('anchor OK')",
        "PY",
        "```",
        "",
        "## 红线（沿用）",
        "",
        "- 不 commit / 不 stash / 不 reset（候选 = 脏工作树 + 哈希锚定）",
        "- 不修改冻结物；不并行跑共享数据库 / 端口 / 付费账户",
        "- 反悔方式：`git apply --reverse candidate-post-t8.patch`（2650 行，已 `--reverse --check` 通过）",
    ]
    (D / "candidate-manifest-t8-20260910.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"候选文件 {len(new['candidate_files_sha256'])} 个；变化 {len(changed)} 个：")
    for rel in changed:
        print(f"  - {rel}")
    print(f"冻结文件漂移：{len(frozen_drift)}  {'✅' if not frozen_drift else frozen_drift}")
    print(f"新增候选文件：{len(added)}  {added if added else '（无）'}")
    print(f"清单腐化（锚定集内但不脏）：{len(stale)}  {stale if stale else '（无）'}")


if __name__ == "__main__":
    main()
