"""F5 claim 级引用核验单测（2026-10-27）。"""

import claim_support as cs


class Doc:
    def __init__(self, text: str):
        self.page_content = text


ARTICLE_658 = (
    "赠与人在赠与财产的权利转移之前可以撤销赠与。"
    "经过公证的赠与合同或者依法不得撤销的具有救灾、扶贫、助残等公益、道德义务性质的赠与合同，不适用前款规定。"
)
ARTICLE_289 = (
    "聚众“打砸抢”，致人伤残、死亡的，依照本法第二百三十四条、第二百三十二条的规定定罪处罚。"
    "毁坏或者抢走公私财物的，除判令退赔外，对首要分子，依照本法第二百六十三条的规定定罪处罚。"
)
BOOK = {"刑法": {"第二百八十九条": ARTICLE_289}, "民法典": {"第六百五十八条": ARTICLE_658}}


def lookup(source: str, article: str):
    text = BOOK.get(source, {}).get(article)
    return [Doc(text)] if text else []


def test_split_sentences_keeps_citations():
    answer = "第一句没有引用。第二句依据《民法典》第六百五十八条。\n第三句也引用《刑法》第二百八十九条！"
    sentences = cs.split_sentences(answer)
    assert len(sentences) == 3
    assert "第六百五十八条" in sentences[1]


def test_check_emits_one_pair_per_citation():
    answer = "依据《民法典》第六百五十八条与《刑法》第二百八十九条，可以得出结论。"
    results = cs.check(answer, lookup)
    assert len(results) == 2
    assert {item.literal for item in results} == {"《民法典》第六百五十八条", "《刑法》第二百八十九条"}


def test_missing_article_yields_undetermined():
    answer = "依据《刑法》第二百三十四条，构成故意伤害罪。"
    results = cs.check(answer, lookup)
    assert results[0].article_found is False
    assert results[0].supported is None
    assert results[0].method == "none"


def test_lexical_baseline_supports_matching_article():
    answer = "依据《民法典》第六百五十八条，赠与人在财产权利转移之前可以撤销赠与。"
    results = cs.check(answer, lookup)
    assert results[0].article_found is True
    assert results[0].lexical > 0.4
    assert results[0].supported is True


def test_judge_overrides_lexical_for_special_clause_misuse():
    """289 事故形态：词面高度重叠（lexical 会判支持），judge 必须判不支持。"""
    answer = (
        "根据《刑法》第二百八十九条中“致人伤残、死亡的，依照本法第二百三十四条……的规定定罪处罚”的表述，"
        "可以确认法律体系中对于致人伤残行为的刑事评价主要依托于故意伤害罪的相关规定。"
    )

    def judge(claim: str, article: str):
        return False, "289 是聚众打砸抢的特别规定，不能作为一般规则"

    lexical_only = cs.check(answer, lookup)
    assert lexical_only[0].lexical > cs.LEXICAL_THRESHOLD
    assert lexical_only[0].supported is True  # 词面基线会误判

    judged = cs.check(answer, lookup, judge=judge)
    assert judged[0].method == "judge"
    assert judged[0].supported is False


def test_parse_judge_response_variants():
    assert cs.parse_judge_response('{"supported": false, "reason": "特别条款"}') == (False, "特别条款")
    assert cs.parse_judge_response('{"supported": true, "reason": "直接规定"}') == (True, "直接规定")
    assert cs.parse_judge_response("不支持：条文未规定该条件")[0] is False
    assert cs.parse_judge_response("支持")[0] is True
    assert cs.parse_judge_response("无法判断")[0] is None


def test_v2_prompt_is_candidate_and_covers_core_rules():
    assert cs.JUDGE_SYSTEM_PROMPT_V2 != cs.JUDGE_SYSTEM_PROMPT
    for phrase in ("核心法律命题", "排除式引用", "总则性", "一律"):
        assert phrase in cs.JUDGE_SYSTEM_PROMPT_V2
