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
    """"培训"不进特征词：培训服务合同（消费场景）不得判为劳动，保留格式条款映射。"""
    assert D.is_labor_clause("本合同约定培训课程费用一经收取概不退款") is False
    assert D.is_labor_clause("甲方将房屋出租给乙方，租金每月三千元") is False
