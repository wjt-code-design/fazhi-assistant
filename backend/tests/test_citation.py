"""引用校验（B0.1 防假引用）+ 条号直查路由归一化测试（Step 7）。

覆盖：
- citation_verify：命中/异常/全称简称归一/〇零归一/无引用。
- _num_to_cn / _normalize_article / parse_article_query 边界。

绝大多数用例是纯函数测试（注入 in_kb/article_ok，不碰向量库）。
只有下面三条标了 `real_kb` 的用例判据**必须**来自真实知识库（conftest.real_kb 显式 opt-in，
只读；2026-09-18 前默认层未隔离时它们隐式吃真实库）。
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


def test_extract_composite_citation_continuation():
    # 合成引用：同法多条的顿号续写（回归 q119——旧实现只抽得到首条）
    answer = "依据《海事诉讼特别程序法》第十七条、第五十八条、第六十九条，可申请设立基金。"
    cites = R.extract_citations(answer)
    assert [c[1] for c in cites] == ["第十七条", "第五十八条", "第六十九条"]
    assert cites[0][2] == "《海事诉讼特别程序法》第十七条"  # 单条保留原文写法
    assert cites[1][2] == "《海事诉讼特别程序法》第五十八条"


def test_extract_composite_shared_tiao():
    # 合并条号（整串只有一个「条」）：第23、54条 → 展开成两条
    assert [c[1] for c in R.extract_citations("《公司法》第23、54条有规定。")] == ["第二十三条", "第五十四条"]


def test_extract_composite_stops_at_intervening_text():
    # 中间夹文字 ⇒ 不并入：防把裸名法（刑法第二百六十四条）的条号错挂到前一部法
    answer = "《民法典》第五百七十七条，而刑法第二百六十四条另有规定。"
    assert [c[1] for c in R.extract_citations(answer)] == ["第五百七十七条"]


def test_verify_composite_flags_later_articles():
    # 合成引用的后续条号也要进存在性校验（E10 注记不能只列首条）
    def in_kb(name, art):
        return R._normalize_article(art) == "第十七条"

    bad = R.citation_verify("《海事诉讼特别程序法》第十七条、第五十八条。", in_kb)
    assert bad == ["《海事诉讼特别程序法》第五十八条"]


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
def test_verify_against_real_kb(real_kb):
    assert R.citation_verify("依据《刑法》第十三条。") == []  # 在库 → 不报
    assert R.citation_verify("依据《刑法》第九百九十九条。") == ["《刑法》第九百九十九条"]  # 不存在 → 报
    assert R.citation_verify("《宪法》第二条规定国家性质。") == []  # 宪法括注边界 → 在库不报


# ---------------- classify_citation（三态分级，2026-09-07 法条引用精度修复） ----------------
def test_classify_ok_numeric_variant():
    # ASCII 记法变体（第801条）与中文（第八百零一条）同属在库 → 判 ok（误报消除）
    kb_arts = {"第八百零一条", "第八百零三条"}

    def article_ok(name, art):
        return R._normalize_article(art) in kb_arts

    def source_ok(name):
        return True

    assert R.classify_citation("民法典", "第801条", article_ok=article_ok, source_ok=source_ok) == R.REF_OK
    assert R.classify_citation("民法典", "第八百零三条", article_ok=article_ok, source_ok=source_ok) == R.REF_OK


def test_classify_article_missing():
    # 法名在库但条号不在库 → 真条号错误（第一百零十三条 不存在）
    def article_ok(name, art):
        return False

    def source_ok(name):
        return True

    assert R.classify_citation("民事诉讼法", "第一百零十三条", article_ok=article_ok, source_ok=source_ok) == (
        R.REF_ARTICLE_MISSING
    )


def test_classify_source_missing():
    # 法名本身不在库（已废止）→ 库外/已废止引用
    def article_ok(name, art):
        return False

    def source_ok(name):
        return False

    assert (
        R.classify_citation("合同法", "第一百零七条", article_ok=article_ok, source_ok=source_ok)
        == R.REF_SOURCE_MISSING
    )


def test_classify_answer_citations_mixed():
    def article_ok(name, art):
        return R._normalize_article(art) == "第八百零一条"

    def source_ok(name):
        return name == "民法典"

    answer = "《民法典》第801条有效，《税务法》第九条、《民法典》第十二条无效。"
    statuses = {
        item["literal"]: item["status"]
        for item in R.classify_answer_citations(answer, article_ok=article_ok, source_ok=source_ok)
    }
    assert statuses["《民法典》第801条"] == R.REF_OK
    assert statuses["《民法典》第十二条"] == R.REF_ARTICLE_MISSING  # 在库法、条号不在
    assert statuses["《税务法》第九条"] == R.REF_SOURCE_MISSING  # 库外法


def test_classify_answer_defaults_real_kb(real_kb):
    # 默认判据=真实知识库：801 记法变体不误报；虚构条号/库外法报对应状态
    statuses = {
        item["literal"]: item["status"]
        for item in R.classify_answer_citations("《民法典》第801条有效，《刑法》第九百九十九条无效。")
    }
    assert statuses["《民法典》第801条"] == R.REF_OK  # 真实在库 → 格式变体不误报
    assert statuses["《刑法》第九百九十九条"] == R.REF_ARTICLE_MISSING  # 法在库、条号虚构


# ---------------- _cn_article_to_num（中文条号→数字，capture_eval 同口径） ----------------
def test_cn_article_to_num():
    cases = {
        "第十条": "10",
        "第十九条": "19",
        "第一百零三条": "103",
        "第一百零十三条": "113",  # 字面解释（错位写法也照字面转数字）
        "第一百八十八条": "188",
        "第五百七十七条": "577",
        "第八百零一条": "801",
        "第一千二百六十条": "1260",
    }
    for art, exp in cases.items():
        assert R._cn_article_to_num(art) == exp, f"{art} → {R._cn_article_to_num(art)} != {exp}"


# ---------------- expected_laws 前置（题集预期法条加权，2026-09-07） ----------------
def test_expected_law_keys():
    keys = R._expected_law_keys(["民法典:577", "民法典:1260", "坏条目"])
    assert ("民法典", "577") in keys
    assert ("民法典", "1260") in keys
    assert len(keys) == 2  # 非法条目静默跳过


def test_frontload_expected_keeps_match_front():
    from langchain_core.documents import Document

    docs = [
        Document(page_content="噪声一", metadata={"source": "民法典", "article": "第五十七条"}),
        Document(page_content="精确577", metadata={"source": "民法典", "article": "第五百七十七条"}),
        Document(page_content="噪声二", metadata={"source": "民法典", "article": "第五十八条"}),
    ]
    keys = R._expected_law_keys(["民法典:577"])
    out = R._frontload_expected(docs, keys)
    assert out[0].page_content == "精确577"
    assert [d.page_content for d in out[1:]] == ["噪声一", "噪声二"]  # 其余相对顺序不変


def test_frontload_expected_no_match_unchanged():
    from langchain_core.documents import Document

    docs = [
        Document(page_content="a", metadata={"source": "民法典", "article": "第五十七条"}),
        Document(page_content="b", metadata={"source": "民法典", "article": "第五十八条"}),
    ]
    assert R._frontload_expected(docs, frozenset()) == docs  # 空期望 → 原样


def test_hybrid_retrieve_expected_laws_weights_topk(real_kb):
    # 真实 KB 集成：无期望 → 577 是否在 top-k 看语义；给期望 577 → 必须前置出现
    with_expected = R.hybrid_retrieve("合同违约后继续履行的法律后果", k=4, expected_laws=["民法典:577"])
    arts = [d.metadata.get("article", "") for d in with_expected]
    assert "第五百七十七条" in arts  # 期望条文被强制前置进 top-4


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


# ---------------- cited_article_specs（多问试题一次点名多条，2026-10-25） ----------------
def test_cited_specs_expands_comma_list():
    """六问股东出资题的「考查规范提示」：一次点名多条，单条路由只取得到第一条。"""
    specs = R.cited_article_specs("《公司法》（2023 修订）第 23、54 条")
    assert specs == [("公司法", "第二十三条"), ("公司法", "第五十四条")]


def test_cited_specs_expands_range_without_inner_tiao():
    """「第 17—21、32 条」：中间项没有「条」字，区间要展开到 21，32 单独算。"""
    specs = R.cited_article_specs("《变更追加当事人规定》第 17—21、32 条")
    arts = [a for _, a in specs]
    assert arts == ["第十七条", "第十八条", "第十九条", "第二十条", "第二十一条", "第三十二条"]


def test_cited_specs_multiple_laws_in_order():
    text = "《民法典》第 535、537 条，《破产法》第 40 条"
    assert R.cited_article_specs(text) == [
        ("民法典", "第五百三十五条"),
        ("民法典", "第五百三十七条"),
        ("企业破产法", "第四十条"),
    ]


def test_cited_specs_chinese_numerals_and_no_duplicates():
    specs = R.cited_article_specs("《刑法》第二十条与《刑法》第20条")
    assert specs == [("刑法", "第二十条")]


def test_cited_specs_ignores_bare_law_names():
    """只认书名号内的法名；裸名（无书名号）不产出条文需求。

    书名号里写合同名（《房屋租赁合同》第五条）会抽出一对 (合同名, 第五条)，
    但下游 `exact_article_lookup` 对不在库的源名返回空 ⇒ 不进上下文，故不做名称过滤。
    """
    assert R.cited_article_specs("根据劳动合同法第五十二条怎么处理") == []


def test_cited_specs_requires_tiao():
    """「条」不可省：旧版把「条」写成可选，`《公司法》第一个问题` 会被抽成 第一条。"""
    assert R.cited_article_specs("《公司法》第一个问题，第三个争点怎么答") == []


def test_cited_specs_stops_at_sentence_end():
    """窗口截到句末：同一段里换法名（无书名号）的条号不得错记到前一部法。"""
    text = "《公司法》第五十四条。另依据民法典第五百三十五条，乙可代位。"
    assert R.cited_article_specs(text) == [("公司法", "第五十四条")]
