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


def test_id5_statutory_inheritance_prepends_1155():
    q = (
        "关于法定继承，下列说法正确的是？A.第一顺序继承人为配偶、子女、父母 "
        "B.第二顺序继承人为兄弟姐妹、祖父母、外祖父母 "
        "C.丧偶儿媳对公婆、丧偶女婿对岳父母尽了主要赡养义务的，不作为第一顺序继承人 "
        "D.遗产分割时，应当为胎儿保留继承份额"
    )
    arts = _ids(scenario_supplement_docs(q))
    assert "第一千一百五十五条" in arts  # 胎儿继承份额（原检索缺口）


def test_id16_labor_dispute_prepends_47_and_53():
    q = (
        "关于劳动争议的解决，下列说法正确的是？A.劳动争议需先申请劳动仲裁，对仲裁裁决不服才可起诉 "
        "B.劳动争议可以直接向人民法院提起诉讼 "
        "C.追索劳动报酬的仲裁裁决为终局裁决 "
        "D.劳动争议仲裁免费"
    )
    arts = _ids(scenario_supplement_docs(q))
    assert "第四十七条" in arts  # 终局裁决
    assert "第五十三条" in arts  # 仲裁不收费


def test_unrelated_scenario_no_trigger():
    q = "关于保证担保，下列说法正确的是？A.当事人约定保证人与债务人对债务承担连带责任的，为连带责任保证"
    assert scenario_supplement_docs(q) == []


def test_company_law_49_no_old_breach_clause():
    """金标版本冲突固化：库内 2023 新公司法 49(3) 无旧法 28(2)'违约责任'表述（id13 检索修不了）。"""
    doc = exact_article_lookup("公司法", "第四十九条")
    assert doc, "公司法第49条应存在于知识库"
    assert "违约责任" not in doc[0].page_content
