"""检索查准回归测试：余弦精排 + 三路保底 + k6 + 措辞桥接（真实 KB，slow）。

4 个历史 bad case（"对法错条"，roadmap 记录）：高空抛物 1254 / 行政复议 11 / 个人信息 5,6,7 / 股东出资 47
——期望条必须进入 hybrid top-6（模型可引用的窗口），防未来改动回退。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest  # noqa: E402

import retrieval  # noqa: E402


def _in_top(docs, source, article):
    return any(
        d.metadata.get("source") == source and d.metadata.get("article") == article for d in docs
    )


# ---------------- 措辞桥接（纯函数，非 slow） ----------------
def test_bridge_query_rewrites():
    assert "从建筑物中抛掷物品" in retrieval._bridge_query("高空抛物致人损害，由谁承担责任？")
    assert "申请行政复议" in retrieval._bridge_query("行政复议的受案范围包括哪些情形？")


def test_bridge_query_passthrough():
    assert retrieval._bridge_query("公司股东认缴出资的期限是多长？") == "公司股东认缴出资的期限是多长？"


# ---------------- 真实 KB 查准（slow：CI 跳过） ----------------
@pytest.mark.slow
def test_high_altitude_fall_precision():
    docs = retrieval.hybrid_retrieve("高空抛物致人损害，由谁承担责任？", k=6)
    assert _in_top(docs, "民法典", "第一千二百五十四条"), "高空抛物应召回 1254，而非高度危险责任噪声"


@pytest.mark.slow
def test_admin_reconsideration_scope():
    docs = retrieval.hybrid_retrieve("行政复议的受案范围包括哪些情形？", k=6)
    assert _in_top(docs, "行政复议法", "第十一条"), "受案范围应召回 11 条正面条款（措辞桥接）"


@pytest.mark.slow
def test_personal_info_principles():
    docs = retrieval.hybrid_retrieve("处理个人信息应当遵循哪些原则？", k=6)
    for art in ("第五条", "第六条", "第七条"):
        assert _in_top(docs, "个人信息保护法", art), f"个人信息原则应召回 {art}"


@pytest.mark.slow
def test_shareholder_capital_deadline():
    docs = retrieval.hybrid_retrieve("公司股东认缴出资的期限是多长？", k=6)
    assert _in_top(docs, "公司法", "第四十七条"), "出资期限应召回 47 条"


@pytest.mark.slow
def test_short_name_exact_lookup():
    # 简称→全称：条号直查也应吃别名（库内 source 是全称「刑事诉讼法」）
    docs = retrieval.exact_article_lookup("刑诉法", "第八十三条")
    assert docs, "刑诉法第八十三条应命中刑事诉讼法第八十三条"
