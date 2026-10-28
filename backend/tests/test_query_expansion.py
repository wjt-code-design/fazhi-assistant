"""查询扩展（口语 → 法条用语）单测。

覆盖：命中追加、未命中不改、幂等、开关关闭、空词表、多触发词。
背景见 dispatch-output/quality-eval-20261021/report.md §六。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import retrieval
from settings import settings


def test_hit_appends_and_keeps_original():
    q = "我交了十万元定金，卖家后来涨价不卖"
    out = retrieval.expand_query(q)
    assert out.startswith(q), "原文必须保留（口语词本身是有用信号）"
    assert "定金罚则" in out and "双倍返还" in out


def test_miss_returns_unchanged():
    q = "邻居家的猫跑到我家阳台了"
    assert retrieval.expand_query(q) == q


def test_idempotent():
    q = "定金能不能退"
    once = retrieval.expand_query(q)
    assert retrieval.expand_query(once) == once, "已含扩展词时不得重复追加"


def test_multiple_triggers():
    q = "定金和加班费都能要回来吗"
    out = retrieval.expand_query(q)
    assert "定金罚则" in out
    assert "延长工作时间" in out


def test_disabled_switch(monkeypatch):
    monkeypatch.setattr(settings, "query_expansion_enabled", False)
    q = "定金能不能退"
    assert retrieval.expand_query(q) == q


def test_empty_table_is_safe(monkeypatch):
    monkeypatch.setattr(retrieval, "_QUERY_EXPANSIONS", [])
    q = "定金能不能退"
    assert retrieval.expand_query(q) == q


def test_table_loaded_and_nonempty():
    """词表文件存在时必须真的读到条目，否则开关是空转。"""
    assert retrieval._QUERY_EXPANSIONS, "query_expansions.json 未被加载"
    triggers = {t for t, _ in retrieval._QUERY_EXPANSIONS}
    assert {"定金", "加班", "装空调"} <= triggers
