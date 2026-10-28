"""相邻条文扩展 + 中文条号转换单测。

覆盖：_cn_to_int 的分段换算（含"一百一十八"这类易错写法）、相邻扩展的去重与限量、
以及"追加在末尾、不改动原顺序"这一核心约定。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document

import retrieval


def _doc(src: str, art: str) -> Document:
    return Document(page_content=f"[{src} {art}] 内容", metadata={"source": src, "article": art})


def test_cn_to_int():
    assert retrieval._cn_to_int("一百一十八") == 118
    assert retrieval._cn_to_int("一千二百五十二") == 1252
    assert retrieval._cn_to_int("二百八十八") == 288
    assert retrieval._cn_to_int("五百八十六") == 586
    assert retrieval._cn_to_int("一千一百九十三") == 1193
    assert retrieval._cn_to_int("九") == 9
    assert retrieval._cn_to_int("〇五") == 5


def test_cn_to_int_rejects_garbage():
    assert retrieval._cn_to_int("") is None
    assert retrieval._cn_to_int("之") is None
    assert retrieval._cn_to_int("甲") is None


def test_article_regex_skips_sub_articles():
    m = retrieval._ART_NUM_RE.match("第一百条之一")
    assert m is not None and m.group(1) == "一百"
    assert retrieval._ART_NUM_RE.match("第一千二百五十二条") is not None


def test_expand_appends_without_reordering(real_kb):
    docs = [_doc("民法典", "第七百二十二条")]
    extra = retrieval._expand_adjacent_articles(docs)
    assert extra, "应取到相邻条文"
    arts = {d.metadata["article"] for d in extra}
    assert arts <= {"第七百二十一条", "第七百二十三条"}
    # 原顺序不变、扩展不改动入参
    assert docs[0].metadata["article"] == "第七百二十二条"
    assert len(docs) == 1


def test_expand_skips_already_present(real_kb):
    docs = [_doc("民法典", "第七百二十二条"), _doc("民法典", "第七百二十一条")]
    extra = retrieval._expand_adjacent_articles(docs)
    arts = {d.metadata["article"] for d in extra}
    assert "第七百二十一条" not in arts


def test_expand_respects_limit(real_kb):
    docs = [_doc("民法典", f"第七百{n}条") for n in range(10, 20)]
    extra = retrieval._expand_adjacent_articles(docs, limit=3)
    assert len(extra) <= 3
