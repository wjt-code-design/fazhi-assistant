"""评测器纠偏回归测试（T1/T2/T3/T8）：事实投放协议——轮次隔离 / 去重 / schema / 双 runner 一致。

任务书：docs/evaluation-harness-correction-taskbook-20260908.md §6 T1/T2/T3/T8。
实现前后各跑一次：旧实现必须因正确原因失败（red），新实现通过（green）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE2 = _load_module("gate2_runner_mod", REPO / "backend/scripts/gate2_runner.py")
HIDDEN = _load_module("hidden_runner_mod", REPO / "dispatch-output/task1/hidden_runner.py")

C05_PROMPT_HITS_R12 = "我转账后对方退款退回，合同约定每月5日付款，押金怎么算"

# H01 侧的最小脱敏夹具体（**假数据**，非真实盲测集）。
# 为什么必须自带：hidden_runner 的事实表只在**运行期**从 hidden-round-protocol-v1.json 读取
# （该 JSON 不入库，`.gitignore:77` 整目录忽略 dispatch-output/task1/，见 hidden_runner._read_json），
# 干净检出里它不存在——测试若去读真值，就又把"未入库资产"变成依赖。
# schema 与真题集协议逐字段一致（fact_units → roundN → {fact_id, text, match_keywords}），
# 由 hidden_runner 自己的 `facts_meta_from_protocol` 解析 ⇒ 被锁的是"两个 runner 共用同一投放语义"，
# 与具体题目无关。r1 关键词对下面的 T8 探针 prompt 命中、r2 刻意不命中 ⇒ 该断言不再空转。
HIDDEN_FIXTURE_PROTOCOL = {
    "schema_version": "hidden-round-protocol-fixture-v1",
    "purpose": "tests/test_harness_fact_reveal.py 自带的脱敏夹具（假数据；不含任何真实盲测内容）",
    "no_match_reply": "我没有保留这方面的信息。",
    "fact_units": {
        "H01": {
            "round1": [
                {
                    "fact_id": "H01-r1-f1",
                    "text": "夹具事实（假）：押金与付款时间已在书面合同中约定。",
                    "match_keywords": ["押金", "付款", "约定"],
                },
                {
                    "fact_id": "H01-r1-f2",
                    "text": "夹具事实（假）：双方另有一份口头补充说明。",
                    "match_keywords": ["口头", "补充"],
                },
            ],
            "round2": [
                {
                    "fact_id": "H01-r2-f1",
                    "text": "夹具事实（假）：第二轮的退回记录。",
                    "match_keywords": ["押金", "退回"],
                },
            ],
        }
    },
}


@pytest.fixture()
def shared_module():
    """共享事实投放模块（单一实现）。red 阶段该模块不存在 → 本组测试整体失败（接口缺失红）。"""
    spec = importlib.util.spec_from_file_location(
        "harness_fact_reveal", REPO / "backend/scripts/harness_fact_reveal.py"
    )
    if spec is None or spec.loader is None:
        pytest.fail("harness_fact_reveal 模块缺失：单一事实投放入口未实现")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_t1_round2_fact_not_revealed_on_round1():
    """T1：第一轮 prompt 同时命中 r1 与 r2 关键词时，只能返回 r1 事实。"""
    text, ids = GATE2._match_facts("C05", C05_PROMPT_HITS_R12)
    assert "C05-r2-f1" not in ids, f"第一轮泄露第二轮事实: {ids}"
    assert any(i.startswith("C05-r1-") for i in ids)


def test_t2_answered_fact_not_returned_again(shared_module):
    """T2：已回答事实不得重复投放（同 prompt 语义重复时不再返回）。"""
    res1 = shared_module.match_revealable_facts(
        case_id="C05",
        prompt=C05_PROMPT_HITS_R12,
        current_round=2,
        answered_fact_ids=set(),
        facts=_c05_facts(),
    )
    first = set(res1.answered_fact_ids)
    assert first, "第一轮应至少命中一个事实"
    res2 = shared_module.match_revealable_facts(
        case_id="C05",
        prompt=C05_PROMPT_HITS_R12,
        current_round=2,
        answered_fact_ids=first,
        facts=_c05_facts(),
    )
    assert not (set(res2.answered_fact_ids) & first), f"已答事实被重复投放: {first}"


def test_t3_unmatched_schema_is_correct(shared_module):
    """T3：未命中问题记录 {round, prompt, reason}；*_ids 字段只承载字符串 ID。"""
    res = shared_module.match_revealable_facts(
        case_id="C05",
        prompt="完全没有命中任何关键词的问题",
        current_round=2,
        answered_fact_ids=set(),
        facts=_c05_facts(),
    )
    assert res.answered_fact_ids == []
    assert res.unmatched_questions, "未命中应有记录"
    entry = res.unmatched_questions[0]
    assert set(entry.keys()) == {"round", "prompt", "reason"}
    assert isinstance(entry["prompt"], str)
    assert entry["reason"] == "no_rule_match"
    for fid in res.answered_fact_ids:
        assert isinstance(fid, str)


def test_t8_both_runners_share_same_reveal_semantics(shared_module):
    """T8：开发集与公开隐藏回归 runner 使用一致投放协议（轮次隔离 + 去重 + schema）。"""
    gate2_res = shared_module.match_revealable_facts(
        case_id="C05",
        prompt="押金与付款时间怎么约定",
        current_round=1,
        answered_fact_ids=set(),
        facts=_c05_facts(),
    )
    hidden_res = shared_module.match_revealable_facts(
        case_id="H01",
        prompt="押金与付款时间怎么约定",
        current_round=1,
        answered_fact_ids=set(),
        facts=_h01_facts(),
    )
    # 语义同一：输出结构类型一致；开发集命中未含 r2；隐藏集同样不含 r2
    assert all(isinstance(x, list) for x in (gate2_res.answered_fact_ids, hidden_res.answered_fact_ids))
    assert not any(i.startswith("C05-r2-") for i in gate2_res.answered_fact_ids)
    assert not any(i.startswith("H01-r2-") for i in hidden_res.answered_fact_ids)


def _c05_facts():
    return _facts_from_protocol("C05", GATE2)


def _h01_facts():
    """隐藏侧 facts：由**自带脱敏夹具**经 hidden_runner 自己的解析函数构建（不读未入库真值）。"""
    return HIDDEN.facts_meta_from_protocol(HIDDEN_FIXTURE_PROTOCOL)


def _facts_from_protocol(case_id: str, mod) -> dict:
    """从 runner 自带的**冻结关键词表**构建 facts: fid -> FactData(round, keywords, text)。

    只适用于把关键词表写在源码里的 runner（gate2_runner）；hidden_runner 的关键词表来自不入库的
    真协议，故其 H01 侧改走 `_h01_facts()` 的夹具路径。
    """
    facts: dict = {}
    for fid, kws in mod.KEYWORDS.items():
        if not fid.startswith(case_id + "-"):
            continue
        import re as _re

        m = _re.search(r"-r(\d+)-f", fid)
        rnd = int(m.group(1)) if m else 99
        facts[fid] = {"round": rnd, "keywords": list(kws), "text": mod.FACT_TEXT.get(fid, "")}
    assert facts, f"{case_id} 无可用事实"
    return facts
