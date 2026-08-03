"""查询切片单元测试：query_understand + hybrid_retrieve 对长题干法考题的召回。

背景（2026-08-04 diagnosing-bugs）：法考题长题干整句检索时，场景词（"边境旅游/
6克4克2克/行李包"）在向量与 BM25 两侧淹没核心罪名（"非法持有毒品罪"/"运输毒品罪"），
关键条文（刑法 347/348）双路排名第 9/16，掉出候选池 → agent 拿不到定罪条款。

修复：query_understand.slice_query 把超长查询切成独立检索单元（选项段/句子），
hybrid_retrieve 每段独立召回进候选池，精排用"切片段 top-2 保底 + RRF 排名"——
含罪名的选项段必然命中核心条文，从机制上杜绝（不依赖正则提取精度）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import query_understand  # noqa: E402

# 用户实测暴露的真实 case（2026-08-04）：长题干法考题漏刑法 347/348
_EXAM_LONG_Q = (
    "甲乙丙三人结伴到某边境地区旅游，发现当地毒品价格低廉，遂商议购买一些带回居住地供自己吸食。"
    "甲出资购买了6克，乙购买了4克，丙购买了2克，三人将购买的毒品（总计12克）混合后放入同一个行李包中，"
    "由甲负责携带，一同乘坐长途汽车返回。途中被警方查获。下列说法错误的是？"
    "A：甲乙丙构成共同犯罪，构成非法持有毒品罪 "
    "B：因为甲的数额最大，所以需要对乙丙负责，乙丙只需要对自己负责 "
    "C：甲乙丙构成运输毒品罪 "
    "D：甲乙丙不构成非法持有毒品罪"
)


def test_slice_query_detects_exam_question():
    """长法考题 → 按选项切分为多段（题干 + A/B/C/D），不整句糊在一起。"""
    segs = query_understand.slice_query(_EXAM_LONG_Q)
    assert len(segs) >= 5, f"应切成题干+4选项，实际 {len(segs)} 段"
    assert segs[0] == _EXAM_LONG_Q  # 整句保底在首位
    joined = "".join(segs)
    assert "运输毒品罪" in joined and "非法持有毒品罪" in joined


def test_slice_query_short_query_unchanged():
    """短查询（<=60 字）不切片——零开销零行为变化。"""
    assert query_understand.slice_query("网购七天无理由退货有法律依据吗？") == [
        "网购七天无理由退货有法律依据吗？"
    ]


def test_slice_query_plain_long_text_splits():
    """普通长文本（非选项，>60 字）按句子切分，仍保留整句保底。"""
    q = (
        "我朋友去年把车借给一个没有驾照的人开，那人撞了人逃逸了，现在家属要我朋友赔钱，"
        "说因为车主有责任。我朋友想知道这种情况车主要不要负责任，如果需要的话大概要赔多少？"
    )
    segs = query_understand.slice_query(q)
    assert segs[0] == q
    assert len(segs) >= 2


def test_hybrid_retrieve_exam_long_recalls_core_articles():
    """核心回归：长题干法考题必须召回刑法 347（运输毒品罪）/348（非法持有毒品罪）定罪条款。

    修复前：348 双路排名 9/16 掉出候选池 → top-6 无 348 → agent 拒答。
    """
    from retrieval import hybrid_retrieve  # 延迟 import（会加载 BGE）

    docs = hybrid_retrieve(_EXAM_LONG_Q, k=6)
    arts = {d.metadata.get("article", "") for d in docs}
    assert "第三百四十七条" in arts, f"应召回刑法347（运输毒品罪），实际 top6 无：{arts}"
    assert "第三百四十八条" in arts, f"应召回刑法348（非法持有毒品罪），实际 top6 无：{arts}"
