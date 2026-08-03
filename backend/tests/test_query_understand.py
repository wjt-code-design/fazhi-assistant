"""查询分解单元测试：query_understand + hybrid_retrieve 对同类检索问题的覆盖。

背景（2026-08-04 diagnosing-bugs → 架构改进）：用户实测长题干法考题漏刑法 347/348。
初次修复用「位置切片」解决长题干；架构改进升级为「查询分解」——法条/罪名/概念锚点
独立检索 + 锚点命中保底，覆盖所有同类问题：
  - T1 长题干法考题（场景词淹没罪名）
  - T2 短复合查询（多法律点）
  - T3 口语长描述（借车出事故）
  - T4 罪名字面陷阱（356 抢占 top-1，定罪条款在 top-2）
  - T5 法条引用精确命中
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import query_understand  # noqa: E402

# 用户实测暴露的真实 case：长题干法考题漏刑法 347/348
_EXAM_LONG_Q = (
    "甲乙丙三人结伴到某边境地区旅游，发现当地毒品价格低廉，遂商议购买一些带回居住地供自己吸食。"
    "甲出资购买了6克，乙购买了4克，丙购买了2克，三人将购买的毒品（总计12克）混合后放入同一个行李包中，"
    "由甲负责携带，一同乘坐长途汽车返回。途中被警方查获。下列说法错误的是？"
    "A：甲乙丙构成共同犯罪，构成非法持有毒品罪 "
    "B：因为甲的数额最大，所以需要对乙丙负责，乙丙只需要对自己负责 "
    "C：甲乙丙构成运输毒品罪 "
    "D：甲乙丙不构成非法持有毒品罪"
)


def test_decompose_extracts_anchors():
    """法考题长题干 → 整句 + 罪名锚点（非法持有毒品罪/运输毒品罪）。"""
    units = query_understand.decompose(_EXAM_LONG_Q)
    texts = [t for t, _ in units]
    kinds = [k for _, k in units]
    assert texts[0] == _EXAM_LONG_Q  # 整句保底在首位
    assert kinds[0] == query_understand.KIND_ORIGINAL
    assert "非法持有毒品罪" in texts, f"应含罪名锚点非法持有毒品罪：{texts}"
    assert "运输毒品罪" in texts, f"应含罪名锚点运输毒品罪：{texts}"
    assert any(k == query_understand.KIND_ANCHOR for k in kinds), "应含 anchor 类型单元"


def test_decompose_short_query_unchanged():
    """短查询无锚点 → 仅整句（零开销零行为变化）。"""
    units = query_understand.decompose("网购七天无理由退货有法律依据吗？")
    assert [t for t, _ in units] == ["网购七天无理由退货有法律依据吗？"]
    assert units[0][1] == query_understand.KIND_ORIGINAL


def test_decompose_short_query_with_crime():
    """T2：短查询含罪名 → 提取罪名锚点独立检索（不依赖 >60 字触发）。"""
    units = query_understand.decompose("非法持有毒品罪和运输毒品罪的区别？")
    texts = [t for t, _ in units]
    assert "非法持有毒品罪" in texts and "运输毒品罪" in texts


def test_decompose_law_ref():
    """T5：法条引用锚点精确提取。"""
    units = query_understand.decompose("根据《民法典》第一千零八十七条，离婚财产怎么分割？")
    texts = [t for t, _ in units]
    assert "《民法典》第一千零八十七条" in texts


def test_decompose_no_generic_concept_anchor():
    """泛概念词（如"行政复议"）不做锚点——避免稀释整句措辞桥接（2026-08-04 回归锁定）。

    曾误用 COMPLEX_KEYWORDS 做概念锚点，"行政复议"独立检索 top-3 是泛命中（复议法
    各条），强制保底挤掉整句桥接召回的"第十一条"→ 桥接 case 回归。锚点只保留
    高区分度的法条引用 + 具体罪名两类。
    """
    units = query_understand.decompose("行政复议的受案范围包括哪些情形？")
    kinds = [k for _, k in units]
    assert len(units) == 1, f"无罪名/法条引用 → 应仅整句（无锚点），实际：{units}"
    assert kinds == [query_understand.KIND_ORIGINAL]


def test_decompose_plain_long_text_splits():
    """T3：普通长文本（非选项，>60 字）按句子切分，整句保底。"""
    q = (
        "我朋友去年把车借给一个没有驾照的人开，那人撞了人逃逸了，现在家属要我朋友赔钱，"
        "说因为车主有责任。我朋友想知道这种情况车主要不要负责任，如果需要的话大概要赔多少？"
    )
    units = query_understand.decompose(q)
    assert units[0][0] == q
    assert len(units) >= 2


def test_hybrid_retrieve_exam_long_recalls_core_articles():
    """T1 核心回归：长题干法考题必须召回刑法 347（运输毒品罪）/348（非法持有毒品罪）。"""
    from retrieval import hybrid_retrieve  # 延迟 import（会加载 BGE）

    docs = hybrid_retrieve(_EXAM_LONG_Q, k=6)
    arts = {d.metadata.get("article", "") for d in docs}
    assert "第三百四十七条" in arts, f"应召回刑法347，实际无：{arts}"
    assert "第三百四十八条" in arts, f"应召回刑法348，实际无：{arts}"


def test_hybrid_retrieve_short_crime_query():
    """T4 核心回归：短罪名查询"非法持有毒品罪"独立检索召回 348（不靠整句余弦）。"""
    from retrieval import hybrid_retrieve  # 延迟 import

    docs = hybrid_retrieve("非法持有毒品罪的构成要件", k=6)
    arts = {d.metadata.get("article", "") for d in docs}
    assert "第三百四十八条" in arts, f"短罪名查询应召回刑法348，实际无：{arts}"


def test_hybrid_retrieve_plain_long_text():
    """T3 核心回归：口语长描述（借车出事故）召回出借车辆/逃逸条文。"""
    from retrieval import hybrid_retrieve  # 延迟 import

    q = (
        "我朋友去年把车借给一个没有驾照的人开，那人撞了人逃逸了，现在家属要我朋友赔钱，"
        "说因为车主有责任。我朋友想知道这种情况车主要不要负责任，如果需要的话大概要赔多少？"
    )
    docs = hybrid_retrieve(q, k=6)
    arts = {d.metadata.get("article", "") for d in docs}
    assert "第一千二百零九条" in arts, f"应召回出借车辆责任条文1209，实际无：{arts}"
