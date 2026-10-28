"""F1 法条覆盖闸门单测（2026-10-27）。

只测纯函数：注入式 lookup，不碰向量库/BGE。
"""

import coverage_gate as gate


class Doc:
    def __init__(self, source: str, article: str):
        self.metadata = {"source": source, "article": article}


CATALOG = {
    "topics": [
        {
            "id": "intentional_injury",
            "triggers": ["故意伤害", "打致", "伤残"],
            "required": [
                {"source": "中华人民共和国刑法", "article": "第二百三十四条"},
                {"source": "中华人民共和国刑法", "article": "第九十五条"},
            ],
        },
        {
            "id": "instigation",
            "triggers": ["教唆"],
            "required": [
                {"source": "中华人民共和国刑法", "article": "第二十五条"},
                {"source": "中华人民共和国刑法", "article": "第二十九条"},
            ],
        },
    ]
}


def test_article_number_accepts_chinese_and_arabic():
    assert gate.article_number("第二百三十四条") == 234
    assert gate.article_number("第234条") == 234
    assert gate.article_number("234") == 234
    assert gate.article_number("第九十五条") == 95
    assert gate.article_number("不是条号") is None


def test_source_key_strips_version_and_prefix():
    assert gate.source_key("中华人民共和国刑法（2023年修正）") == "刑法"
    assert gate.source_key("中华人民共和国刑法") == "刑法"


def test_detect_topics_respects_exclude():
    catalog = {"topics": [{"id": "fraud", "triggers": ["诈骗"], "exclude": ["合同诈骗"], "required": []}]}
    assert gate.detect_topics("对方合同诈骗怎么报案", catalog) == []
    assert [topic["id"] for topic in gate.detect_topics("我被诈骗了", catalog)] == ["fraud"]


def test_detect_topics_matches_triggers():
    topics = gate.detect_topics("李四教唆王五把张三打致一级伤残", CATALOG)
    assert [topic["id"] for topic in topics] == ["intentional_injury", "instigation"]


def test_missing_requirements_uses_normalized_keys():
    docs = [Doc("中华人民共和国刑法", "第二百三十四条")]
    missing = gate.missing_requirements(docs, CATALOG["topics"][0]["required"])
    assert missing == [{"source": "中华人民共和国刑法", "article": "第九十五条"}]


def test_ensure_coverage_supplements_and_reports():
    docs = [Doc("中华人民共和国刑法", "第二百三十四条")]
    calls = []

    def lookup(source, article):
        calls.append((source, article))
        return [Doc(source, article)]

    merged, report = gate.ensure_coverage("故意伤害致人重伤", docs, lookup, mode="warn", catalog=CATALOG)
    assert len(merged) == 2
    assert report["added"] == ["中华人民共和国刑法第九十五条"]
    assert report["unresolved"] == []
    assert calls == [("中华人民共和国刑法", "第九十五条")]


def test_ensure_coverage_caps_lookups_and_stops_on_empty():
    docs = []
    calls = []

    def lookup(source, article):
        calls.append(article)
        return []

    merged, report = gate.ensure_coverage("李四教唆王五", docs, lookup, mode="warn", catalog=CATALOG, max_lookup=2)
    assert merged == []
    assert len(calls) == 2
    assert report["unresolved"] == ["中华人民共和国刑法第二十五条", "中华人民共和国刑法第二十九条"]


def test_ensure_coverage_marks_cap_skipped_as_unresolved():
    catalog = {
        "topics": [
            {
                "id": "cap",
                "triggers": ["测试"],
                "required": [
                    {"source": "中华人民共和国刑法", "article": "第二百三十四条"},
                    {"source": "中华人民共和国刑法", "article": "第九十五条"},
                    {"source": "中华人民共和国刑法", "article": "第二十九条"},
                ],
            }
        ]
    }
    calls = []

    def lookup(source, article):
        calls.append(article)
        return [Doc(source, article)]

    _, report = gate.ensure_coverage("测试问题", [], lookup, mode="warn", catalog=catalog, max_lookup=1)
    assert calls == ["第二百三十四条"]
    assert len(report["unresolved"]) == 2
    assert all("补检上限" in item for item in report["unresolved"])


def test_ensure_coverage_off_is_noop():
    docs = [Doc("中华人民共和国刑法", "第二百三十四条")]

    def lookup(source, article):  # pragma: no cover - 不应被调用
        raise AssertionError("off 模式不得触发补检")

    merged, report = gate.ensure_coverage("故意伤害", docs, lookup, mode="off", catalog=CATALOG)
    assert merged is docs
    assert report["mode"] == "off"
    assert report["matched_topics"] == []


def test_ensure_coverage_normalizes_mode_case():
    """大小写/空格是配置常态，归一后按合法模式执行。"""
    docs = [Doc("中华人民共和国刑法", "第二百三十四条")]
    merged, report = gate.ensure_coverage(
        "故意伤害", docs, lambda source, article: [Doc(source, article)], mode=" WARN ", catalog=CATALOG
    )
    assert report["mode"] == "warn"
    assert report["added"] == ["中华人民共和国刑法第九十五条"]
    assert len(merged) == 2


def test_ensure_coverage_unknown_mode_falls_back_to_off():
    """枚举外值不得让每个法律请求 500：退化为 off。"""
    docs = [Doc("中华人民共和国刑法", "第二百三十四条")]

    def lookup(source, article):  # pragma: no cover - 不应被调用
        raise AssertionError("未知模式应退化为 off，不得触发补检")

    merged, report = gate.ensure_coverage("故意伤害", docs, lookup, mode="loud", catalog=CATALOG)
    assert merged is docs
    assert report["mode"] == "off"
    assert report["matched_topics"] == []


def test_ensure_coverage_fills_only_missing_234():
    """F1 验收原场景：上下文有 95 条、缺 234 条 → 必须只补 234。"""
    docs = [Doc("中华人民共和国刑法", "第九十五条")]
    merged, report = gate.ensure_coverage(
        "故意伤害致人重伤", docs, lambda source, article: [Doc(source, article)], mode="warn", catalog=CATALOG
    )
    assert report["missing_before"] == ["中华人民共和国刑法第二百三十四条"]
    assert report["added"] == ["中华人民共和国刑法第二百三十四条"]
    assert len(merged) == 2


def test_gap_notice_only_when_unresolved():
    assert gate.gap_notice({"unresolved": []}) == ""
    notice = gate.gap_notice({"unresolved": ["中华人民共和国刑法第二百三十四条"]})
    assert "不得以总则条文替代分则条文" in notice
