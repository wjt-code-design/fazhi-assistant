"""G2 引用三分类测试（2026-10-25）。

前端把「检索依据 / 补充依据 / 未收录」分组展示，依赖后端
`citation_grounding_status` 的三组划分；本测试锁定归一化与边界。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from retrieval import citation_grounding_status  # noqa: E402

SOURCES = [{"source": "企业破产法", "article": "第七十五条"}]


def fake_kb(name, art):
    # 模拟 article_in_kb 的源名归一（真实实现内部 canon_source + _source_key）
    name = name.replace("中华人民共和国", "")
    return (name, art) in {("企业破产法", "第八十七条"), ("民法典", "第六百五十八条")}


def test_three_way_split():
    answer = (
        "依据《企业破产法》第七十五条，担保权暂停行使；"
        "另见《企业破产法》第八十七条关于强制批准；"
        "《不存在法》第一百条不成立。"
    )
    out = citation_grounding_status(answer, SOURCES, in_kb=fake_kb)
    assert [x["article"] for x in out["in_context"]] == ["第七十五条"]
    assert [x["article"] for x in out["external"]] == ["第八十七条"]
    assert [x["article"] for x in out["unknown"]] == ["第一百条"]


def test_source_name_normalization():
    answer = "依据《中华人民共和国民法典》第六百五十八条，可以撤销赠与。"
    out = citation_grounding_status(answer, [], in_kb=fake_kb)
    assert [x["article"] for x in out["external"]] == ["第六百五十八条"]


def test_no_citations_returns_empty_groups():
    out = citation_grounding_status("这是一段没有法条引用的回答。", SOURCES, in_kb=fake_kb)
    assert out == {"in_context": [], "external": [], "unknown": []}


def test_source_article_normalization_matches_context():
    sources = [{"source": "中华人民共和国民法典", "article": "第六百五十八条"}]
    out = citation_grounding_status("《民法典》第六百五十八条", sources, in_kb=fake_kb)
    assert len(out["in_context"]) == 1
    assert out["external"] == []


def test_external_citation_chapter_applicability_warning():
    """§1.5（2026-10-29）：external 引用按章节/上下文给适用性标注，不删引用、不改三态。"""

    def fake_kb_all(name, art):
        return True

    def fake_chapter(name, art):
        return {
            "第二百三十二条": "第十八章　公示催告程序",
            "第五百三十八条": "第九章　合同的保全",
        }.get(art)

    answer = (
        "依《民事诉讼法》第二百三十二条，可以提出执行异议；另依《民法典》第五百三十八条，明显不合理低价转让可撤销。"
    )
    out = citation_grounding_status(answer, [], in_kb=fake_kb_all, chapter_lookup=fake_chapter)
    items = {item["article"]: item for item in out["external"]}
    assert items["第二百三十二条"]["chapter"] == "第十八章　公示催告程序"
    assert items["第二百三十二条"]["applicability_warning"]
    assert not items["第五百三十八条"]["applicability_warning"]
