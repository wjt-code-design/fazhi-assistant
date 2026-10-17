"""票 W06-FIX V6/F7：全量重嵌入**不许换 doc id**（换了就把 SQL→向量那条链静默改断）。

失效形状（改前现量，`scripts/rebuild_embeddings.py:83`）：`_read_old` 只读 docs+metas，
`_write_new` 于是自己按批次编号 `ids=[f"re-{start + i}" ...]` ⇒ 新库里每一条的 id 都换了，
而 `qa_candidates.vector_doc_id` 记的是**旧 id**（`knowledge_service.add_qa_pair` 写进去的那个 uuid）。
方向上是 **SQL→向量** 断链：`load_read_state` 返回的 `vector_doc_id` 从此在向量库里指不到任何文档，
`qa_eligibility` 的状态轴照旧放行（它不查这个 id），没有任何测试会响。

本文件用**假 collection**跑真函数（不碰真实 `chroma_db`，也不加载真权重）：
① `_read_old` 必须把 ids 一起读出来、且与 docs/metas 一一对应；
② `_write_new` 默认沿用原 id ⇒ 重建后 `vector_doc_id` 仍解析得到；
③ 反面对照：`reuse_ids=False` 那条分支必须**断链**（证明②咬的是 id 保不保，不是别的东西）；
④ 接线：`main()` 的两个 `_write_new` 调用点都必须把 ids 传进去（只改函数不改调用点＝没修）。
"""

import inspect
import re
import textwrap

import pytest

import scripts.rebuild_embeddings as R


class _FakeCol:
    """Chroma collection 的最小替身：只实现本脚本用到的 get/add/count。"""

    def __init__(self, ids=None, docs=None, metas=None):
        self._ids = list(ids or [])
        self._docs = list(docs or [])
        self._metas = list(metas or [])

    def get(self, include=None, limit=None, ids=None):
        if ids is not None:  # 按 id 取回（`qa_eligibility._as_meta` 走的就是这条形状）
            wanted = set(ids)
            keep = [i for i, v in enumerate(self._ids) if v in wanted]
            return {
                "ids": [self._ids[i] for i in keep],
                "documents": [self._docs[i] for i in keep],
                "metadatas": [self._metas[i] for i in keep],
            }
        n = limit or len(self._ids)
        return {
            "ids": self._ids[:n],
            "documents": self._docs[:n],
            "metadatas": self._metas[:n],
        }

    def count(self):
        return len(self._ids)

    def add(self, ids=None, embeddings=None, documents=None, metadatas=None):
        assert ids is not None and embeddings is not None
        assert len(ids) == len(documents) == len(metadatas) == len(embeddings), "写入形状不对 ⇒ 替身先报错"
        self._ids += list(ids)
        self._docs += list(documents)
        self._metas += list(metadatas)


class _FakeEmb:
    def embed_documents(self, texts):
        return [[0.0, 1.0] for _ in texts]

    def embed_query(self, text):
        return [0.0, 1.0]


_VECTOR_DOC_ID = "3f2c9a1b7d4e5c6a8b0f1e2d3c4b5a69"  # 形状同 uuid4().hex：SQL 里记的就是它


@pytest.fixture
def old_collection():
    return _FakeCol(
        ids=[_VECTOR_DOC_ID, "another-doc-id", "third-doc-id"],
        docs=["试用期最长多久", "借款纠纷怎么处理", "违约金上限是多少"],
        metas=[
            {"answer": "最长六个月", "origin": "qa", "law_as_of_basis": "2026-08-23"},
            {"answer": "a2", "origin": "qa", "law_as_of_basis": "2026-08-23"},
            {"answer": "a3", "origin": "qa", "law_as_of_basis": "2026-08-23"},
        ],
    )


def test_read_old_returns_ids_paired_with_docs_and_metas(old_collection):
    """① 读旧库必须把 ids 一起带出来——不读 ids 就谈不上沿用 ids（改前正是没读）。"""
    ids, docs, metas = R._read_old(old_collection, "qa_pairs_te4")
    assert ids == [_VECTOR_DOC_ID, "another-doc-id", "third-doc-id"], ids
    assert len(ids) == len(docs) == len(metas) == 3


def test_read_old_refuses_ragged_counts(tmp_path):
    """①b 数量不齐就直接失败：按顺序猜 id 会把链指到**别的条文**上，那比断链更坏（fail-fast）。"""

    class _Ragged(_FakeCol):
        def get(self, include=None, limit=None):
            return {"ids": ["only-one"], "documents": ["a", "b"], "metadatas": [{}, {}]}

    with pytest.raises(RuntimeError, match="数量不齐"):
        R._read_old(_Ragged(), "legal_provisions_te4")


def test_write_new_keeps_the_original_doc_ids(old_collection):
    """② 主判据：重建后新库里的 id **逐字等于**旧库的 id ⇒ `vector_doc_id` 仍解析得到。"""
    ids, docs, metas = R._read_old(old_collection, "qa_pairs_te4")
    new_col = _FakeCol()
    R._write_new(_FakeEmb(), new_col, ids, docs, metas, batch=2, name="qa_pairs_te4")

    assert sorted(new_col._ids) == sorted(ids), f"新库换了 id ⇒ SQL 的 vector_doc_id 全指空：{new_col._ids}"
    # 端到端那一读：拿着 SQL 记的 vector_doc_id 去**新库**取，必须取回同一条内容（这才叫"仍可解析"）
    resolved = new_col.get(ids=[_VECTOR_DOC_ID], include=["documents", "metadatas"])
    assert resolved["documents"] == ["试用期最长多久"], resolved
    assert (resolved["metadatas"] or [{}])[0].get("answer") == "最长六个月", resolved


def test_write_new_reuse_ids_false_is_the_mutation_control(old_collection):
    """③ 反面对照（watch-it-fail）：把 `reuse_ids` 关掉，同一份数据就**必然断链**。

    没有这半条，②可能只是"替身 add 恰好记住了我传的任何东西"。这里要求：
    关掉保链 ⇒ 旧 id 一个都不在 ⇒ ②那条判据真的在咬 id 保不保这件事。
    """
    ids, docs, metas = R._read_old(old_collection, "qa_pairs_te4")
    new_col = _FakeCol()
    R._write_new(_FakeEmb(), new_col, ids, docs, metas, batch=2, name="qa_pairs_te4", reuse_ids=False)
    assert new_col._ids == ["re-0", "re-1", "re-2"], new_col._ids
    assert _VECTOR_DOC_ID not in new_col._ids, "关掉保链却还留着旧 id ⇒ ②那条判据是空的"


def test_write_new_refuses_ids_docs_length_mismatch(old_collection):
    """③b 带缺 id 就拒跑：ids 少一条 ⇒ 不许默默按 `re-<n>` 补位（那正是改前的行为）。"""
    ids, docs, metas = R._read_old(old_collection, "qa_pairs_te4")
    with pytest.raises(RuntimeError, match="数量不一致"):
        R._write_new(_FakeEmb(), _FakeCol(), ids[:-1], docs, metas, batch=2, name="qa_pairs_te4")


def test_main_wires_ids_into_both_write_calls():
    """④ 接线：`main()` 里两处 `_write_new(...)` 调用点都必须把 ids 传进去。

    只把函数改了、调用点还传 `docs, metas` ⇒ 生产路径照旧换 id（本仓教训：改实现不改接线＝没改）。
    """
    src = textwrap.dedent(inspect.getsource(R.main))
    calls = re.findall(r"_write_new\([^\n]*\)", src)
    assert len(calls) == 2, f"重建调用点应当两处（条文库＋qa_pairs），现量 {len(calls)}：{calls}"
    for call in calls:
        assert "ids" in call, f"调用点没传 ids ⇒ 保链只活在函数签名里：{call}"
    assert "new_main.get(" in src and "in new_ids" in src, "重建后没有 id 保链校验这一步 ⇒ 断链照样打印成功"
