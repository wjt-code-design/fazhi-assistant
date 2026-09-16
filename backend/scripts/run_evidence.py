"""只读证据查询助手 —— 把 2026-09-10 踩过的**三类口径坑**固化成被测试覆盖的实现。

背景（三个坑都真实发生过，详见 docs/code-review-standard.md §1.2 #5 与 handoff §12.13）：
  1. `agent_runs.id` 是 **UUID 字符串**：`ORDER BY id` 是字典序、与插入顺序无关
     ⇒ 按 id 取"最新"会拿到几天前的行。
  2. `agent_runs.created_at` 声明为 **DATETIME**（NUMERIC 亲和性）：`created_at < '9999'`
     会把字面量转成整数，比较退化为 TEXT vs INTEGER（SQLite 里 INTEGER 恒小于 TEXT）⇒ **恒 0 行**。
     上界必须用**格式一致的字符串**（如 "2099-12-31 23:59:59"）。
  3. **预运行失败不产生 agent_run 记录** ⇒ 按"位置切 N 条"会把后一臂的行错配到前一臂缺失的题上。
     题号必须用「会话首条用户消息 ⨯ 题目文本」匹配（归一化空白后全等）。

本模块**只读**：不写库、不改状态；供评测/审计脚本使用，也供 `tests/test_run_evidence.py` 锁死上述三条。

实际消费方（2026-09-11 审查留痕）：
- `dispatch-output/t2-persistence-20260910/writer_axis_audit.py`（双集验收审计）
- `dispatch-output/t2-persistence-20260910/t8_validation_compare.py` / `compare_model_arms_20260910.py`（对照脚本）
- `dispatch-output/t2-persistence-20260910/supplement_survival_probe.py`（§2.1 探针）
- `tests/test_run_evidence.py`（口径锁）
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator, Mapping
from pathlib import Path

_WHITESPACE_RE = re.compile(r"\s+")
# 2026-09-10 实测：'9999' 这类纯数字哨兵在 DATETIME（NUMERIC 亲和性）列上会退化为
# TEXT vs INTEGER 比较 ⇒ 恒 0 行。上界必须用与列内格式一致的字符串。
_FAR_FUTURE = "2099-12-31 23:59:59"


def squeeze(text: str | None) -> str:
    """去掉全部空白（用于题目文本的全等匹配：`，`与`， ` 应视为同一条）。"""
    return _WHITESPACE_RE.sub("", text or "")


def claim_start(run_name: str, evidence_dir: str | Path) -> str:
    """读某轮 `gate2-run-<name>.claim.json` 的 started_at，规整为可字典序比较的 'YYYY-MM-DD HH:MM:SS'。"""
    path = Path(evidence_dir) / f"gate2-run-{run_name}.claim.json"
    raw = json.loads(path.read_text(encoding="utf-8"))["started_at"]
    return raw.replace("T", " ").replace("+00:00", "").split(".")[0]


def all_known_starts(evidence_dir: str | Path) -> list[str]:
    """**全部**已知轮次的 claim 起点（扫描 evidence 目录里所有 claim 文件）。

    为什么必须扫全部而不是只用"被选中的臂"：最后一个臂若拿"未来哨兵"当上界，
    窗口会一直吞到之后的轮次（实测：重跑历史对照时 qwen36 被算成 37，真值 24）。
    """
    d = Path(evidence_dir)
    prefix, suffix = "gate2-run-", ".claim.json"
    return sorted(claim_start(p.name[len(prefix) : -len(suffix)], evidence_dir) for p in d.glob(f"{prefix}*{suffix}"))


def upper_bound_for(run_name: str, evidence_dir: str | Path) -> str:
    """某轮的窗口上界 = **全部已知轮次**中紧邻的下一轮起点；没有则用格式一致的远期哨兵。"""
    mine = claim_start(run_name, evidence_dir)
    later = [s for s in all_known_starts(evidence_dir) if s > mine]
    return later[0] if later else _FAR_FUTURE


def cases_by_question(frozen_cases_path: str | Path) -> dict[str, str]:
    """归一化题目文本 → 题号（供"会话首条用户消息"反查题号）。"""
    raw = json.loads(Path(frozen_cases_path).read_text(encoding="utf-8"))
    cases = raw if isinstance(raw, list) else raw.get("cases", raw)
    items = cases.items() if isinstance(cases, dict) else [(c["id"], c) for c in cases]
    return {squeeze(case["initial_question"]): str(cid) for cid, case in items}


def iter_arm_runs(con: sqlite3.Connection, window: tuple[str, str]) -> Iterator[tuple[int, str, str, str, str]]:
    """按 **rowid** 升序遍历某时间窗内的 agent_runs（不是按 id —— 那是 UUID 字典序）。"""
    lo, hi = window
    for row in con.execute(
        "SELECT rowid, id, conversation_id, created_at, state_json FROM agent_runs "
        "WHERE created_at>=? AND created_at<? ORDER BY rowid",
        (lo, hi),
    ):
        yield row["rowid"], row["id"], row["conversation_id"], row["created_at"], row["state_json"]


def case_by_conversation(
    con: sqlite3.Connection, conversation_id: str | int, question_map: Mapping[str, str]
) -> str | None:
    """用会话的**首条用户消息**反查题号（匹配不上返回 None —— 绝不用位置猜）。"""
    row = con.execute(
        "SELECT content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id LIMIT 1",
        (conversation_id,),
    ).fetchone()
    if row is None:
        return None
    return question_map.get(squeeze(row["content"]))


def per_case_issue_counts(
    con: sqlite3.Connection,
    window: tuple[str, str],
    question_map: Mapping[str, str],
) -> tuple[dict[str, int], list[str]]:
    """某时间窗内、逐题的 issue 数。**返回 (逐题计数, 未映射会话清单)**。

    题号按文本映射；**重复题号保留先出现的**；映射不到的 run **不静默塞给猜测的题号**，
    而是显式返回其会话 id 供人工判读（这正是"位置切分"会出错的地方）。
    """
    per_case: dict[str, int] = {}
    unmapped: list[str] = []
    for _rowid, _run_id, conv, _created, state_json in iter_arm_runs(con, window):
        cid = case_by_conversation(con, conv, question_map)
        if cid is None:
            unmapped.append(f"conv={conv}")
            continue
        if cid in per_case:
            continue
        per_case[cid] = len(json.loads(state_json).get("issues") or [])
    return per_case, unmapped
