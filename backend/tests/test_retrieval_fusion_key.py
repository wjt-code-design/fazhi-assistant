"""R18：检索融合键必须能区分出处（来源/条号/版本），不得只按正文融合。

改前 `retrieval._doc_id(d) = d.page_content`：正文相同、来源/条号/版本不同的两条会在
`pool.setdefault(did, d)` 处被融合成一条（后到的被静默丢掉）⇒ 检索结果丢失出处，
甚至把不同法源的条文当成同一条。

判据分两侧：
- 纯函数侧：`_doc_id` 对"同正文不同出处"给不同键、对"同一片段"给相同键；
- 消费侧：按生产同款 `pool.setdefault(_doc_id(d), d)` 循环，两条必须都留下。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document  # noqa: E402

from retrieval import _doc_id  # noqa: E402

BODY = "第一条 为了保护合法权益，制定本法。"


def _doc(source: str, article: str = "第一条", **extra) -> Document:
    return Document(page_content=BODY, metadata={"source": source, "article": article, **extra})


def test_same_body_different_source_gets_different_key():
    """改前失败：两条只用正文作键 → 键相同。"""
    a = _doc("甲法")
    b = _doc("乙法")
    assert _doc_id(a) != _doc_id(b), "同正文不同来源被判成同一片段 ⇒ 融合时丢出处"


def test_same_body_different_version_gets_different_key():
    """同一法名同一条号的不同版本（version_id / 施行期间不同）也必须分开。"""
    v1 = _doc("民法典", version_id="v1", effective_from="2021-01-01")
    v2 = _doc("民法典", version_id="v2", effective_from="2024-01-01")
    assert _doc_id(v1) != _doc_id(v2)


def test_identical_fragment_merges():
    """同一片段被向量路与 BM25 路各召回一次 ⇒ 键必须相同（否则同一段落会重复占位）。"""
    assert _doc_id(_doc("甲法")) == _doc_id(_doc("甲法"))


def test_bare_document_without_provenance_falls_back_to_body_key():
    """没有出处字段的裸 Document 退回正文键，保持旧行为（不凭空造出处）。"""
    bare = Document(page_content=BODY, metadata={})
    assert _doc_id(bare) == BODY


def test_production_fusion_pool_keeps_both_docs():
    """按生产同款 `pool.setdefault(_doc_id(d), d)` 循环：两条都必须留下。"""
    pool: dict[str, Document] = {}
    for d in (_doc("甲法"), _doc("乙法")):
        pool.setdefault(_doc_id(d), d)
    assert len(pool) == 2, "两条同正文不同来源的条文被融合成一条 ⇒ 其中一条静默消失"
