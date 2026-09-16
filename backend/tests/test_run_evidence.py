"""把 2026-09-10 踩过的**三类证据查询口径坑**锁死成测试（`scripts/run_evidence.py`）。

这三个坑都真实发生过，且每个都曾让**报告里的数字出错**：
  1. `agent_runs.created_at` 声明为 DATETIME（NUMERIC 亲和性）⇒ 纯数字上界 `'9999'` 会退化为
     TEXT vs INTEGER 比较（SQLite 里 INTEGER 恒小于 TEXT）⇒ **恒 0 行**。
  2. `agent_runs.id` 是 **UUID 字符串** ⇒ `ORDER BY id` 是字典序、与插入顺序无关。
  3. **预运行失败不产生 agent_run 记录** ⇒ 按"位置切 N 条"会把后一臂的行错配到前一臂缺失的题上。

测试用 **内存 SQLite 复刻真实 schema**（`id TEXT` / `created_at DATETIME`），不依赖 app.db。
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from scripts.run_evidence import (
    _FAR_FUTURE,
    all_known_starts,
    cases_by_question,
    per_case_issue_counts,
    squeeze,
    upper_bound_for,
)

Q1 = "公司拖欠两个月工资"
Q2 = "当天通知解除劳动合同"
CASES_JSON = json.dumps(
    {
        "cases": [
            {"id": "C01", "initial_question": Q1, "required_issues": []},
            {"id": "C02", "initial_question": Q2, "required_issues": []},
        ]
    },
    ensure_ascii=False,
)


@pytest.fixture()
def db() -> sqlite3.Connection:
    """复刻真实 schema 的关键形态：`id TEXT`（UUID）、`created_at DATETIME`（NUMERIC 亲和性）。"""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE agent_runs (
            id TEXT PRIMARY KEY, conversation_id INTEGER, status TEXT,
            created_at DATETIME, state_json TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER, role TEXT, content TEXT
        );
        """
    )
    return con


def seed_run(con: sqlite3.Connection, *, run_id: str, conv: int, created_at: str, issues: int, question: str) -> None:
    state = json.dumps({"issues": [{"issue_id": f"issue-{i}"} for i in range(issues)]})
    con.execute(
        "INSERT INTO agent_runs (id, conversation_id, status, created_at, state_json) VALUES (?,?,?,?,?)",
        (run_id, conv, "completed", created_at, state),
    )
    con.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?,?,?)",
        (conv, "user", question),
    )


def test_datetime_affinity_trap_is_locked(db):
    """坑 1（DATETIME NUMERIC 亲和性）：锁死**正确的上界写法**。

    `'9999'` 会把字面量转成整数 ⇒ TEXT vs INTEGER ⇒ 恒 0 行（2026-09-10 实测）。
    若有人把上界改回纯数字哨兵，本测试立刻红。
    """
    seed_run(db, run_id="r-1", conv=1, created_at="2026-09-10 07:22:46.123456", issues=2, question=Q1)

    n_bad = db.execute("SELECT COUNT(*) FROM agent_runs WHERE created_at < '9999'").fetchone()[0]
    n_good = db.execute("SELECT COUNT(*) FROM agent_runs WHERE created_at < '2099-12-31 23:59:59'").fetchone()[0]
    assert n_bad == 0, "'9999' 触发 NUMERIC 亲和性陷阱（这正是要防的坑）"
    assert n_good == 1, "格式一致的上界必须能取到行"
    assert _FAR_FUTURE == "2099-12-31 23:59:59", "远期哨兵必须是格式一致的字符串，不是纯数字"


def test_uuid_id_ordering_is_not_chronological(db):
    """坑 2（UUID 字典序）：锁死"必须用 rowid/created_at 排序，不能用 id"。

    两枚 UUID 的**字典序与插入顺序相反**（固定值 ⇒ 确定性断言，不靠运气）。
    """
    earlier_id = "ffffffff-1111-4222-8333-444444444444"  # 字典序大
    later_id = "00000000-1111-4222-8333-444444444444"  # 字典序小
    seed_run(db, run_id=earlier_id, conv=1, created_at="2026-09-10 07:00:00.000000", issues=1, question=Q1)
    seed_run(db, run_id=later_id, conv=2, created_at="2026-09-10 08:00:00.000000", issues=1, question=Q2)

    order_by_id = [row[0] for row in db.execute("SELECT id FROM agent_runs ORDER BY id")]
    order_by_rowid = [row[1] for row in db.execute("SELECT rowid, id FROM agent_runs ORDER BY rowid")]

    assert order_by_id != order_by_rowid, "ORDER BY id 是字典序 ⇒ 不能当时间序"
    assert order_by_rowid == [earlier_id, later_id], "rowid 才是插入顺序"
    assert order_by_id == [later_id, earlier_id]


def test_pre_run_failure_gap_breaks_positional_assignment(db):
    """坑 3（位置切分）：预运行失败缺失的题会被**后一臂**的行错配。

    布景：臂 A 只有 C01 的 run（C02 预运行失败、无记录）；臂 B 有 C01、C02 两条。
    - **位置切分（错误做法）**：把臂 B 的第 1 条当臂 A 的 C02（2026-09-10 实测发生过）。
    - **文本映射（正确做法）**：臂 A = {C01}、臂 B = {C01, C02}，缺失题显式可见。
    """
    t0, t1, t2 = "2026-09-10 07:00:00", "2026-09-10 09:00:00", "2026-09-10 11:00:00"
    qmap = {squeeze(Q1): "C01", squeeze(Q2): "C02"}

    # 臂 A：只有 C01（C02 预运行失败 ⇒ 无 agent_run）
    seed_run(db, run_id="a-1", conv=101, created_at="2026-09-10 07:10:00.000000", issues=3, question=Q1)
    # 臂 B：C01、C02 都有 run
    seed_run(db, run_id="b-1", conv=201, created_at="2026-09-10 09:10:00.000000", issues=4, question=Q1)
    seed_run(db, run_id="b-2", conv=202, created_at="2026-09-10 09:20:00.000000", issues=2, question=Q2)

    # ---- 位置切分（错误做法）：把两臂的行按顺序配给 C01/C02 ----
    convs_positional = [
        row[0] for row in db.execute("SELECT conversation_id FROM agent_runs WHERE created_at>=? ORDER BY rowid", (t0,))
    ]
    positional = dict(zip(["C01", "C02"], convs_positional, strict=False))
    assert positional["C02"] == 201, "位置切分会把臂 B 的 C01 错配成臂 A 的 C02（这正是要防的）"

    # ---- 文本映射（正确做法）：按窗口 + 首条用户消息反查 ----
    a_counts, a_unmapped = per_case_issue_counts(db, (t0, t1), qmap)
    b_counts, b_unmapped = per_case_issue_counts(db, (t1, t2), qmap)
    assert a_counts == {"C01": 3} and a_unmapped == []
    assert b_counts == {"C01": 4, "C02": 2} and b_unmapped == []


def test_case_matching_is_whitespace_insensitive(tmp_path):
    """题目匹配必须忽略空白差异（冻结题原文与 DB 首条消息可能有空白差）。"""
    frozen = tmp_path / "frozen-cases.json"
    frozen.write_text(CASES_JSON, encoding="utf-8")
    qmap = cases_by_question(frozen)
    assert qmap.get(squeeze("公司拖欠  两个月工资")) == "C01"  # 多了空格也能匹配
    assert qmap.get(squeeze("完全无关的问题")) is None  # 匹配不上必须显式返回 None（dict 用 get）


def test_upper_bound_uses_next_known_claim_start(tmp_path):
    """上界 = **全部已知轮次**中紧邻的下一轮起点；没有则用格式一致的远期哨兵。

    为什么必须扫全部 claim 文件而不是只用被选中的臂：最后一个臂若拿"未来哨兵"当上界，
    窗口会吞到之后的轮次（实测：重跑历史对照时 qwen36 被算成 37，真值 24）。
    """
    for name, started in (
        ("arm-a", "2026-09-10T07:00:00+00:00"),
        ("arm-b", "2026-09-10T09:00:00+00:00"),
    ):
        (tmp_path / f"gate2-run-{name}.claim.json").write_text(json.dumps({"started_at": started}), encoding="utf-8")
    assert upper_bound_for("arm-a", tmp_path) == "2026-09-10 09:00:00", "上界 = 下一臂起点"
    sentinel = upper_bound_for("arm-b", tmp_path)
    assert sentinel == "2099-12-31 23:59:59"
    assert any(not ch.isdigit() for ch in sentinel), (
        "远期哨兵必须是含分隔符的时间字符串——纯数字会触发 DATETIME NUMERIC 亲和性陷阱（'9999' ⇒ 恒 0 行）"
    )
    assert all_known_starts(tmp_path) == ["2026-09-10 07:00:00", "2026-09-10 09:00:00"]


def test_duplicate_case_rows_keep_first_occurrence(db):
    """同一题号出现多条 run 时保留**先出现**的（rowid 升序 = 时间序），不静默覆盖。"""
    seed_run(db, run_id="r-1", conv=1, created_at="2026-09-10 07:00:00.000000", issues=2, question=Q1)
    seed_run(db, run_id="r-2", conv=2, created_at="2026-09-10 08:00:00.000000", issues=5, question=Q1)
    qmap = {squeeze(Q1): "C01"}
    counts, unmapped = per_case_issue_counts(db, ("2026-09-10 00:00:00", "2099-12-31 23:59:59"), qmap)
    assert counts == {"C01": 2} and unmapped == []
