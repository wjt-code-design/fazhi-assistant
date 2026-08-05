"""合同 eval verifier 单测（纯逻辑，零 LLM，秒级不停后端）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contract_verify import (  # noqa: E402
    cited_articles,
    coverage,
    extract_quoted_fragments,
    fabricated_fragments,
    level_match,
    norm_article,
    parse_risk_entries,
    report_level,
    structure_score,
)


# ---------------- parse_risk_entries ----------------
def test_parse_risk_entries_split_by_marker():
    ans = "【结论】可签署。\nR1 第一条|高|违约金|民法典585|建议\nR2 第二条|中|定金|民法典587|建议"
    entries = parse_risk_entries(ans)
    assert len(entries) == 2
    assert "第一条" in entries[0] and "R1" in entries[0]
    assert "第二条" in entries[1]


def test_parse_risk_entries_no_marker_returns_empty():
    assert parse_risk_entries("合同整体风险可控，注意违约金条款。") == []


# ---------------- extract_quoted_fragments ----------------
def test_quoted_fragments():
    ans = '风险：本合同「任何情况下均免责」、另外"违约金过高"。'
    frags = extract_quoted_fragments(ans)
    assert "任何情况下均免责" in frags
    assert "违约金过高" in frags


# ---------------- coverage（漏条款） ----------------
_CLAUSES = [
    ("第一条", "甲方将房屋出租给乙方，月租金三千元，租赁期一年。"),
    ("第二条", "乙方逾期支付租金超过三十日的，甲方有权解除合同，并收取违约金。"),
    ("第三条", "任何情况下，甲方对乙方的人身财产损失概不负责。"),
    ("第四条", "本合同一式两份，双方各执一份，自签字之日起生效。"),
]


def test_coverage_full():
    ans = "R1 第二条 违约金过高\nR2 第三条 概不负责，甲方免责条款不合法"
    rate, uncovered = coverage(ans, _CLAUSES)
    assert rate == 1.0
    assert uncovered == []


def test_coverage_misses_risk_clause():
    ans = "R1 第二条 违约金过高"  # 漏了第三条免责
    rate, uncovered = coverage(ans, _CLAUSES)
    assert rate == 0.5
    assert uncovered == [3]


def test_coverage_no_risk_clauses():
    clauses = [("第一条", "本合同一式两份，双方各执一份。")]
    rate, _ = coverage("无风险", clauses)
    assert rate == 1.0  # 无可漏


# ---------------- fabricated_fragments（编造） ----------------
_CONTRACT = "本合同约定，乙方违约时支付违约金五千元，任何情况下甲方概不负责。"


def test_fab_none_when_quotes_in_contract():
    ans = "风险：约定「乙方违约时支付违约金五千元」，此条属于违约金过高。"
    assert fabricated_fragments(ans, _CONTRACT) == []


def test_fab_catches_invented_clause():
    ans = "风险：合同约定「乙方需向甲方支付押金十万元」——此内容合同并不存在。"
    fabs = fabricated_fragments(ans, _CONTRACT)
    assert any("押金十万元" in f for f in fabs)


# ---------------- structure_score ----------------
def test_structure_full():
    entry = "第二条 | 高 | 违约金过高 | 民法典585 | 建议协商降低违约金比例"
    assert structure_score(entry) == 1.0


def test_structure_label_hits():
    entry = "位置：第二条。严重度：高。原文：违约金过高。法条：民法典585。建议：调整。"
    assert structure_score(entry) == 1.0


def test_structure_partial():
    assert structure_score("违约金过高") < 1.0
    assert structure_score("") == 0.0


def test_structure_full_label_hits_low_pipe():
    """2 个 | 头 + 换行标签正文：五要素全命中应满，不因 pipe 少提前返回 0.5。"""
    entry = (
        "R_1 | 严重度：极高 | 条款位置：四\n"
        "* 原文摘录：免责。\n* 法条依据：民法典506。\n* 修改建议：删除。"
    )
    assert structure_score(entry) == 1.0


# ---------------- report_level / level_match ----------------
def test_report_level_extraction():
    assert report_level("【结论】总体风险等级：高，建议谨慎签署") == "高"
    assert report_level("风险等级：较低，可以签署") == "较低"
    assert report_level("总体风险等级：**高**。建议谨慎") == "高"  # markdown 加粗容忍
    assert report_level("【结论】总体风险等级：**极高**") == "极高"


def test_level_match_variants():
    assert level_match("总体风险等级：高", "高") == "match"
    assert level_match("总体风险等级：极高", "高") == "diff_adj"  # 相邻
    assert level_match("总体风险等级：低", "高") == "diff_far"  # 两级差
    assert level_match("未提等级", "高") == "none"


# ---------------- 条文归一化 / 提取 ----------------
def test_norm_article_cn_to_arab():
    assert norm_article("第五百八十五条") == "第585条"
    assert norm_article("第八十七条") == "第87条"
    assert norm_article("第二百五十四条") == "第254条"
    assert norm_article("第四十条") == "第40条"


def test_norm_article_arabic_passthrough():
    assert norm_article("第585条") == "第585条"


def test_cited_articles_set():
    ans = "依据《民法典》第五百八十五条和《劳动合同法》第八十七条，另引《民法典》第585条。"
    assert cited_articles(ans) == {"第585条", "第87条"}
