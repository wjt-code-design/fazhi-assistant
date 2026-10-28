"""scenario 定向补充测试（slow：拉 BGE + Chroma，pytest -m 'not slow' 跳过；跑前停后端单 BGE）。

验证 2026-08-05 multi_ok Step 2 的检索缺口修复（病灶分类 + Plan agent 实测）：
- id5（法定继承）题干命中 → 前置 民法典 第一千一百五十五条（胎儿继承份额，原检索缺口）
- id16（劳动争议）题干命中 → 前置 劳动争议调解仲裁法 第四十七条（终局裁决）+ 第五十三条（仲裁不收费）
- 负例：保证担保题不误触发任一 scenario
- 金标版本冲突固化：库内 2023 新公司法 第四十九条第三款无旧法（2018）第 28 条第 2 款
  "向已按期足额缴纳出资的股东承担违约责任"表述 —— id13 的 B 选项检索层修不了，归金标层裁决。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from retrieval import exact_article_lookup, scenario_supplement_docs  # noqa: E402

pytestmark = pytest.mark.slow


def _ids(docs) -> list[str]:
    return [d.metadata.get("article", "") for d in docs]


def test_id5_statutory_inheritance_prepends_1155(real_kb):
    q = (
        "关于法定继承，下列说法正确的是？A.第一顺序继承人为配偶、子女、父母 "
        "B.第二顺序继承人为兄弟姐妹、祖父母、外祖父母 "
        "C.丧偶儿媳对公婆、丧偶女婿对岳父母尽了主要赡养义务的，不作为第一顺序继承人 "
        "D.遗产分割时，应当为胎儿保留继承份额"
    )
    arts = _ids(scenario_supplement_docs(q))
    assert "第一千一百五十五条" in arts  # 胎儿继承份额（原检索缺口）


def test_id16_labor_dispute_prepends_47_and_53(real_kb):
    q = (
        "关于劳动争议的解决，下列说法正确的是？A.劳动争议需先申请劳动仲裁，对仲裁裁决不服才可起诉 "
        "B.劳动争议可以直接向人民法院提起诉讼 "
        "C.追索劳动报酬的仲裁裁决为终局裁决 "
        "D.劳动争议仲裁免费"
    )
    arts = _ids(scenario_supplement_docs(q))
    assert "第四十七条" in arts  # 终局裁决
    assert "第五十三条" in arts  # 仲裁不收费


def test_unrelated_scenario_no_trigger(real_kb):
    # 负例样本二次更新（2026-10-21，民间借贷时效案修复）：原样本"民法典规定普通诉讼时效是几年？"
    # 此前靠"向量检索、无专门补充组"成立；新增 limitation_period 组后它**应当命中**，
    # 不再是"不触发"样本。本用例的本来意图不变——"未命中任何场景时一条都不注入"——
    # 换用真不触发任何组的话句（民法典宣告失踪，40 组关键词均不含该语义）。
    q = "民法典规定宣告失踪的条件是什么？"
    # 先红守卫（拆假绿）：本例是**否定式**断言，空库上必然成立 ⇒ 必须先证明本环境
    # 确实能取到补充条文（正例可得），否则这条用例在漏 real_kb/空库时是假绿。
    assert scenario_supplement_docs("关于正当防卫，下列说法正确的是？") != [], (
        "补充机制在本环境不可得（空库？）⇒ 下面的否定式断言是假绿"
    )
    assert scenario_supplement_docs(q) == []


def test_undetermined_period_lending_prepends_510_511(real_kb):
    """未定还款期限的借贷时效题 → 定向补充 510/511（2026-10-21 评审案回归锚）。

    病灶：时效类问题的向量检索 top-10 被民法典第九章（188–198）占满，而 510/511 在
    "合同履行"章、字面写"履行期限不明确"而非"未约定履行期限" ⇒ 永远进不了上下文，
    模型只能用 188/192/195 硬凑，产出"尚未起算却称中断"的自相矛盾论证。
    """
    q = (
        "2022年5月张三借给李四5万元现金，没有利息，借条上没写还款日期。"
        "2025年11月张三催款，李四说再过两个月一定还。2026年3月张三起诉，李四主张过时效。"
    )
    arts = _ids(scenario_supplement_docs(q))
    assert "第五百一十条" in arts  # 补充确定履行期限的入口
    assert "第五百一十一条" in arts  # 期限不明确的兜底规则（随时履行 + 必要准备时间）
    assert "第六百七十五条" in arts  # 借款人返还义务


def test_guarantee_contract_triggers_692_693(real_kb):
    """保证期间题（连带责任保证）→ 命中 guarantee_contract 组核心条文（2026-08-07 召回缺口修复）。"""
    q = "连带责任保证未约定保证期间，保证期间怎么算？"
    arts = _ids(scenario_supplement_docs(q))
    assert "第六百九十二条" in arts  # 保证期间
    assert "第六百九十三条" in arts  # 保证责任消灭


def test_company_law_49_no_old_breach_clause(real_kb):
    """金标版本冲突固化：库内 2023 新公司法 49(3) 无旧法 28(2)'违约责任'表述（id13 检索修不了）。"""
    doc = exact_article_lookup("公司法", "第四十九条")
    assert doc, "公司法第49条应存在于知识库"
    assert "违约责任" not in doc[0].page_content


def test_all_supplement_articles_exist(real_kb):
    """补充组每条 (source, article) 必须在知识库（对抗审计 v2 #16：数据文件在库一致性）。

    纯数据校验（JSON 结构/关键词/跨组重复）在非 slow 的 test_scenario_data.py；
    本用例需拉 BGE（exact_article_lookup），保持 slow，CI 由 -m 'not slow' 之外的覆盖层补齐。
    """
    import json
    import os

    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scenario_supplements.json")
    data = json.load(open(data_path, encoding="utf-8"))
    missing = []
    for g in data:
        for a in g["articles"]:
            if not exact_article_lookup(a["source"], a["article"]):
                missing.append((g["scenario"], a["source"], a["article"]))
    assert not missing, f"补充组条文不在知识库: {missing}"
