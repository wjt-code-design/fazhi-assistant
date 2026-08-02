"""引用校验（B0.1 防假引用）+ 条号直查路由归一化测试（Step 7）。

纯函数测试，不碰数据库。覆盖：
- citation_verify：命中/异常/全称简称归一/〇零归一/无引用。
- _num_to_cn / _normalize_article / parse_article_query 边界。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 先加载 .env 再 import retrieval（→settings 单例），避免早于 load_dotenv 实例化出空 LLM 配置污染后续测试
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import retrieval as R


# ---------------- extract_citations（去重，纯函数） ----------------
def test_extract_dedup_fullname_and_abbreviation():
    # 同一条文全称+简称 → 去重为 1，保留首次原文写法
    answer = "根据《中华人民共和国民法典》第一百八十二条以及《民法典》第一百八十二条的规定……"
    cites = R.extract_citations(answer)
    assert len(cites) == 1
    assert cites[0][2] == "《中华人民共和国民法典》第一百八十二条"


def test_extract_dedup_chinese_and_arabic_numeral():
    # 中文数字 + 阿拉伯数字同一条 → 去重为 1（数字归一）
    answer = "《刑法》第二十条与《刑法》第20条都规定了正当防卫……"
    assert len(R.extract_citations(answer)) == 1


def test_extract_no_citations():
    assert R.extract_citations("这个问题的答案如下……") == []


# ---------------- citation_verify（知识库存在性校验，可注入 in_kb） ----------------
def test_verify_in_kb_not_flagged():
    def in_kb(name, art):
        return R._normalize_article(art) in {"第十三条", "第二十条"}

    assert R.citation_verify("依据《刑法》第十三条和第二十条。", in_kb) == []


def test_verify_not_in_kb_flagged():
    def in_kb(name, art):
        return False

    assert R.citation_verify("依据《刑法》第九百九十九条。", in_kb) == ["《刑法》第九百九十九条"]


def test_verify_mixed():
    def in_kb(name, art):
        return R._normalize_article(art) == "第十三条"

    bad = R.citation_verify("《刑法》第十三条真实，《刑法》第九百九十九条编造。", in_kb)
    assert bad == ["《刑法》第九百九十九条"]


def test_verify_dedup_fullname_abbreviation():
    # 全称+简称都不在库 → 只报一次
    def in_kb(name, art):
        return False

    assert len(R.citation_verify("《中华人民共和国刑法》第二十条、《刑法》第二十条。", in_kb)) == 1


def test_source_key_handles_xianfa_bracket():
    # 宪法（1982年）括注：去前缀+去括注后与「宪法」匹配
    assert R._source_key("宪法（1982年）") == "宪法"
    assert R._source_key("中华人民共和国宪法（1982年）") == "宪法"
    kb_sources = {"宪法"}  # 已去括注的库存源名

    def in_kb(name, art):
        return R._source_key(name) in kb_sources

    assert R.citation_verify("《宪法》第二条。", in_kb) == []


def test_verify_cross_law_fabrication():
    # 跨法编造：第1260条只在民法典，挂到电子商务法名下 → 判不在库
    kb = {("民法典", "第一千二百六十条")}

    def in_kb(name, art):
        return (R._source_key(name), R._normalize_article(art)) in kb

    assert R.citation_verify("《电子商务法》第一千二百六十条。", in_kb) == ["《电子商务法》第一千二百六十条"]
    assert R.citation_verify("《民法典》第一千二百六十条。", in_kb) == []


# ---------------- citation_verify 真实知识库集成（默认 in_kb=article_in_kb） ----------------
def test_verify_against_real_kb():
    assert R.citation_verify("依据《刑法》第十三条。") == []  # 在库 → 不报
    assert R.citation_verify("依据《刑法》第九百九十九条。") == ["《刑法》第九百九十九条"]  # 不存在 → 报
    assert R.citation_verify("《宪法》第二条规定国家性质。") == []  # 宪法括注边界 → 在库不报


# ---------------- _num_to_cn ----------------
def test_num_to_cn():
    cases = {
        1: "一",
        10: "十",
        13: "十三",
        19: "十九",
        20: "二十",
        100: "一百",
        101: "一百零一",
        108: "一百零八",
        110: "一百一十",
        1260: "一千二百六十",
    }
    for n, exp in cases.items():
        assert R._num_to_cn(n) == exp, f"{n} → {R._num_to_cn(n)} != {exp}"


# ---------------- _normalize_article ----------------
def test_normalize_article():
    assert R._normalize_article("第13条") == "第十三条"
    assert R._normalize_article("第一百〇一条") == "第一百零一条"
    assert R._normalize_article("第十九条") == "第十九条"
    assert R._normalize_article("第293条之一") == "第二百九十三条之一"


# ---------------- parse_article_query ----------------
def test_parse_bracket():
    assert R.parse_article_query("《劳动法》第三条 讲了什么") == ("劳动法", "第三条")


def test_parse_no_bracket():
    assert R.parse_article_query("刑法第13条的内容") == ("刑法", "第十三条")


def test_parse_full_name():
    assert R.parse_article_query("中华人民共和国劳动合同法第十九条") == ("劳动合同法", "第十九条")


def test_parse_dian_suffix():
    assert R.parse_article_query("民法典第1260条 施行") == ("民法典", "第一千二百六十条")


def test_parse_zhi_suffix():
    assert R.parse_article_query("《刑法》第二百九十三条之一 讲什么") == ("刑法", "第二百九十三条之一")


def test_parse_pure_semantic_none():
    assert R.parse_article_query("试用期最长多久") is None
    assert R.parse_article_query("离婚需要什么条件") is None
