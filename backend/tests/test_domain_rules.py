"""domain_rules 测试：场景检测（纯函数）+ 条文映射（真实 KB，slow）。

- is_consumer_clause_scenario：关键词命中 / 退货+条款组合 / 普通问题不误判（红→绿回归）。
- cheating_docs / consumer_clause_docs：查真实知识库（@slow，CI 跳过）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

import domain_rules as dr


# ---------------- is_consumer_clause_scenario（纯函数，不依赖库） ----------------
@pytest.mark.parametrize(
    "q",
    [
        "商家标注拆封不退，条款有效吗",
        "概不退款，怎么维权",
        "最终解释权归本店，合法吗",
        "不予退款条款是否有效",
        "这个格式条款对我有效吗",
        "概不退换，能退货吗",
        "拒退条款，消费者怎么办",
    ],
)
def test_scenario_hits_keywords(q):
    assert dr.is_consumer_clause_scenario(q)


@pytest.mark.parametrize(
    "q",
    [
        # 普通退货/退款流程问题，不含条款效力争议 → 不应触发消费者条款增强
        "退货流程怎么走",
        "退款需要多久到账",
        "七天无理由退货需要什么条件",
        "退货邮费谁承担",
        # 完全无关的法律问题
        "劳动合同解除的赔偿金",
        "交通事故怎么处理",
        "如何申请离婚",
        "试用期最长多久",
    ],
)
def test_scenario_does_not_hit_unrelated(q):
    assert not dr.is_consumer_clause_scenario(q)


def test_scenario_combination_return_plus_clause():
    assert dr.is_consumer_clause_scenario("网购退货，商家说拆封不退")
    assert dr.is_consumer_clause_scenario("退款纠纷，商家免责条款")
    assert dr.is_consumer_clause_scenario("退货，商家称概不负责")  # 退货 + 免责语义


def test_scenario_none_safe():
    assert not dr.is_consumer_clause_scenario(None)
    assert not dr.is_consumer_clause_scenario("")


# ---------------- 条文映射（真实 KB，slow：CI 跳过） ----------------
@pytest.mark.slow
def test_cheating_docs_lookup_real_kb():
    docs = dr.cheating_docs()
    arts = {(d.metadata.get("source"), d.metadata.get("article")) for d in docs}
    assert ("刑法", "第二百八十四条之一") in arts
    assert ("治安管理处罚法", "第二十七条") in arts


@pytest.mark.slow
def test_consumer_clause_docs_lookup_real_kb():
    docs = dr.consumer_clause_docs()
    arts = {(d.metadata.get("source"), d.metadata.get("article")) for d in docs}
    assert ("民法典", "第四百九十六条") in arts
    assert ("民法典", "第四百九十七条") in arts
    assert ("消费者权益保护法", "第二十六条") in arts
