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


# ---------------- citation_verify ----------------
def test_citation_all_in_sources():
    sources = [{"source": "劳动法", "article": "第三条"}, {"source": "民法典", "article": "第一百八十八条"}]
    answer = "根据《劳动法》第三条和《民法典》第一百八十八条，得出结论。"
    assert R.citation_verify(answer, sources) == []


def test_citation_detects_hallucination():
    sources = [{"source": "劳动法", "article": "第三条"}]
    answer = "依据《劳动法》第三条，另见《刑法》第二百三十二条（编造的）。"
    bad = R.citation_verify(answer, sources)
    assert bad == ["《刑法》第二百三十二条"]


def test_citation_fullname_equals_shortname():
    # 答案用全称，sources 用简称 → 视为同一，不报异常
    sources = [{"source": "劳动合同法", "article": "第十九条"}]
    answer = "见《中华人民共和国劳动合同法》第十九条。"
    assert R.citation_verify(answer, sources) == []


def test_citation_zero_variant_normalized():
    # 〇 与 零 归一后相同
    sources = [{"source": "民法典", "article": "第一百零一条"}]
    answer = "依据《民法典》第一百〇一条。"
    assert R.citation_verify(answer, sources) == []


def test_citation_no_citations():
    assert R.citation_verify("这个问题的答案如下……", [{"source": "刑法", "article": "第十三条"}]) == []


def test_citation_empty_sources():
    bad = R.citation_verify("根据《劳动法》第三条。", [])
    assert bad == ["《劳动法》第三条"]


def test_citation_dedup():
    sources = [{"source": "劳动法", "article": "第三条"}]
    answer = "《刑法》第十三条，再说一次《刑法》第十三条。"
    assert R.citation_verify(answer, sources) == ["《刑法》第十三条"]


# ---------------- _num_to_cn ----------------
def test_num_to_cn():
    cases = {1: "一", 10: "十", 13: "十三", 19: "十九", 20: "二十", 100: "一百",
             101: "一百零一", 108: "一百零八", 110: "一百一十", 1260: "一千二百六十"}
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
