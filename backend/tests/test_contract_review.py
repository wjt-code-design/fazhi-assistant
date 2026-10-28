"""合同评估触发/切分/标签/rubric 单测（纯逻辑——domain_rules 合同函数只依赖 re，秒级不停后端）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import domain_rules as D  # noqa: E402


# ---------------- is_contract_review 触发 ----------------
def test_trigger_long_contract_text():
    t = "租赁合同。甲方将房屋出租给乙方，租金每月三千元。" * 20
    assert D.is_contract_review(t) is True


def test_trigger_review_request_short():
    assert D.is_contract_review("帮我审一下这份租赁合同") is True


def test_no_trigger_short_question():
    assert D.is_contract_review("违约金怎么算？") is False
    assert D.is_contract_review("租赁合同到期怎么办") is False


def test_no_trigger_bare_review_word():
    assert D.is_contract_review("审查起诉阶段，被告人有哪些权利？") is False


# ---------------- 2026-10-25 收紧：提到合同 ≠ 要审合同 ----------------
def test_no_trigger_case_narrative_mentioning_contract():
    """长案情/试题里有「合同、货款、买卖」+「分析风险」，但不是在审一份合同。

    旧版「审查动词 + 合同名词」各自全文命中即触发 → 这类题被领进 R1–R5（本轮回溯的
    第二条通道）。新规要求动宾相邻 + 长文本有真实合同骨架。
    """
    t = (
        "2024年3月，甲公司与乙公司签订买卖合同，约定供货500万元。"
        "同年6月，股东张三将认缴出资300万元的股权以100万元转让给李四。"
        "公司无力清偿到期债务，乙公司申请强制执行。"
        "请分析风险并逐一回答：1、能否主张出资加速到期？2、张三是否承担责任？3、保证人责任如何？"
    )
    assert D.is_contract_review(t) is False


def test_no_trigger_review_verb_far_from_contract_noun():
    """审查动词与合同名词隔开一段话——是「评估案子」，不是「审这份协议」。"""
    t = "请评估本案的胜诉可能性。案情显示，双方之间存在一份租赁协议，争议持续两年。"
    assert D.is_contract_review(t) is False


def test_trigger_contract_by_clause_structure_without_parties():
    """真合同骨架（≥3 个条款标记）即使没写甲方乙方也要进合同路径。"""
    t = (
        "第一条 标的物为设备一台，型号以附件清单为准。\n"
        "第二条 价款十万元，分两期支付。\n"
        "第三条 交付时间为下月十五日前，运费由卖方承担。\n"
        "第四条 验收标准按行业通行标准执行。\n"
    ) * 2
    assert D.is_contract_review(t) is True


def test_no_trigger_single_party_in_case_narrative():
    """长文本只出现单方「甲方」、无乙方、无条款结构 → 是案情而非合同。

    旧版长文本分支是「甲方 或 乙方」即可，案情叙述轻易满足；现要求当事人成对。
    """
    t = "甲方在2024年3月与对方签订供货安排，后因货款发生争议。" * 4
    assert D.is_contract_review(t) is False


# ---------------- contract_split 切分 ----------------
def test_split_by_articles():
    t = "第一条 甲方义务。\n第二条 乙方义务。\n第三条 违约责任。"
    segs = D.contract_split(t)
    assert len(segs) == 3
    assert segs[0][0] == "第一条"
    assert "违约责任" in segs[2][1]


def test_split_no_marker_whole():
    t = "这是一个没有条号的合同文本内容。" * 10
    segs = D.contract_split(t)
    assert len(segs) == 1
    assert segs[0][0] == "全文"


# ---------------- 风险标签 / rubric ----------------
def test_clause_risk_tags():
    assert "违约金" in D.clause_risk_tags("违约金为合同金额的20%")
    assert "免责" in D.clause_risk_tags("任何情况下均免责")
    assert D.clause_risk_tags("本合同自双方签字之日起生效") == []


def test_rubric_high_risk():
    clauses = [("一、", "违约金20%，定金双倍，任何情况下概不负责"), ("二、", "最终解释权归甲方")]
    level, _ = D.rubric_risk_level(clauses)
    assert level == "极高"  # 双 high 词（概不+最终解释权）触发极高


def test_rubric_low_risk():
    clauses = [("一、", "本合同一式两份，双方各执一份")]
    level, _ = D.rubric_risk_level(clauses)
    assert level == "低"


def test_contract_split_keeps_preamble():
    """首条标记前的引言/首段必须保留（2026-08-06 diagnosing-bugs：当前被丢弃，结构性漏条款）。"""
    t = (
        "本合同由甲方与乙方于2026年签订，双方本着自愿原则达成如下协议。\n"
        "第一条 甲方将房屋出租给乙方。\n"
        "第二条 租金每月3000元。"
    )
    segs = D.contract_split(t)
    texts = [c for _, c in segs]
    assert any("本合同由甲方与乙方" in c for c in texts), "引言/首段被丢弃"


# ---------------- 劳动法域隔离（is_labor_clause） ----------------
def test_is_labor_clause_boundary_words():
    """code-review 边界盲区（2026-08-06）：纯"试用期"条款此前未判为劳动 → 含"解除"会错绑民法典563。"""
    assert D.is_labor_clause("试用期三个月，试用期工资按转正工资的80%支付") is True
    assert D.is_labor_clause("甲方为乙方缴纳社会保险及住房公积金") is True
    assert D.is_labor_clause("乙方提前三十日解除劳动合同，应支付赔偿金") is True


def test_is_labor_clause_not_misclassify_services():
    """ "培训"不进特征词：培训服务合同（消费场景）不得判为劳动，保留格式条款映射。"""
    assert D.is_labor_clause("本合同约定培训课程费用一经收取概不退款") is False
    assert D.is_labor_clause("甲方将房屋出租给乙方，租金每月三千元") is False
