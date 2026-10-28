"""T-E 隔离守卫：向量库目录必须只有一个真源，且可由环境变量出口重定向。

票据：docs/execution-plan-entity-precision-20260917.md §4 T-E；
方案与证据：dispatch-output/te-chroma-isolation-20260918/plan-te-chroma-isolation.md

三层判据：
1. 出口存在 + 两处构造点吃同一常量（防"同一事实存在两份拷贝、改一处漏一处"，
   即 [PL#13]——该编号出自**另一个项目**的 lesson-map，本仓 docs/PROBLEM_LOG.md 不用此编号）；
2. 生产默认值未漂移（未设 CHROMA_DIR ⇒ 仍是 BASE_DIR/chroma_db）；
3. 默认层隔离**生效且不失真**：不指真实目录、临时库仍是 cosine、且确实写得进去
   （最后一条防"字节没变是因为根本没碰库"的空过）。

红绿性质（watch-it-fail）：
- 删掉 rag_chain.py 的 CHROMA_DIR 常量 ⇒ 1/2/3 全红；
- 把 knowledge_service.py 的 persist_directory 改回硬编码字面量 ⇒ 第 6 条红；
- 把 conftest 的 `CHROMA_DIR=` 改成 `setdefault`（或删掉 _prepare_test_chroma）⇒ 第 7/8 条红。
"""

import os
from pathlib import Path


def test_chroma_dir_constant_exists():
    """出口必须存在——否则测试 lane 没有任何手段避开真实 backend/chroma_db。"""
    import rag_chain

    assert hasattr(rag_chain, "CHROMA_DIR"), "rag_chain 缺 CHROMA_DIR 出口（T-E）"


def test_chroma_dir_is_env_or_default():
    """两条分支都要锁住。

    - 默认分支：生产/Docker 未设 CHROMA_DIR ⇒ 落点与加出口之前**逐字相同**
      （docker-compose.yml:19-44 的 environment 是显式白名单且不含该键，容器不会被重定向）；
      这条必须读 DEFAULT_CHROMA_DIR 而不是 CHROMA_DIR——后者在测试 lane 已被 conftest 改了。
    - 出口分支：一旦设了环境变量就必须被吃到（conftest 无条件赋值，S3 起恒真）。
    """
    import rag_chain

    assert rag_chain.DEFAULT_CHROMA_DIR == os.path.join(rag_chain.BASE_DIR, "chroma_db")
    assert rag_chain.CHROMA_DIR == (os.environ.get("CHROMA_DIR") or rag_chain.DEFAULT_CHROMA_DIR)


def test_main_vectorstore_uses_the_exported_dir():
    import rag_chain

    actual = Path(rag_chain.vectorstore._persist_directory).resolve()
    assert actual == Path(rag_chain.CHROMA_DIR).resolve()


def test_qa_store_shares_the_same_source_of_truth():
    """两处构造点必须是**同一**常量。

    2026-09-17 之前两行各自硬编码 os.path.join(BASE_DIR, "chroma_db")——
    这正是"多份拷贝"[PL#13] 形态：加出口时若只改一处，另一处会静默继续写真实库。
    """
    import knowledge_service
    import rag_chain

    main_dir = Path(rag_chain.vectorstore._persist_directory).resolve()
    qa_dir = Path(knowledge_service._qa_store._persist_directory).resolve()
    assert qa_dir == main_dir == Path(rag_chain.CHROMA_DIR).resolve()


def test_default_lane_does_not_open_the_real_dir():
    """conftest 的默认隔离必须生效。

    真实 backend/chroma_db 被 docker-compose.yml:47 bind mount 进容器，且 chroma 并发不安全
    （compose:11 为此只跑单 worker）⇒ 测试 lane 与它共享目录不是"略脏"，是撞锁面。
    """
    import rag_chain

    chroma_dir = Path(rag_chain.CHROMA_DIR).resolve()
    assert chroma_dir != Path(rag_chain.DEFAULT_CHROMA_DIR).resolve()
    # 更要紧的是"跑出仓库"：留在 repo 内的任何目录都可能被 compose 以卷/挂载的形式带上
    repo_root = Path(rag_chain.BASE_DIR).resolve().parent
    assert not chroma_dir.is_relative_to(repo_root), f"临时库仍在仓库内：{chroma_dir}"
    assert str(os.getpid()) in chroma_dir.name, f"未按进程隔离，并行会话会撞：{chroma_dir}"


def test_default_lane_keeps_cosine_fidelity():
    """临时库必须与生产同一口径分支，否则快测在"生产不走的那条路"上跑绿。

    langchain_chroma 建集合时传 collection_metadata=None ⇒ 空目录新建的集合是 chromadb
    0.4.24 默认的 l2，而真实 legal_provisions_cos 是 cosine；retrieval 据此换算分数口径
    （_collection_is_cosine → cos = 1 - distance 只在 cosine 成立）。
    qa_pairs 反向：真实库 metadata 就是 {}→l2，所以临时库也必须 False——
    "顺手全建 cosine"同样是静默改路径，本条把它钉住。
    """
    import knowledge_service
    import rag_chain
    import retrieval_core as rc

    assert rc.is_cosine_space(rag_chain.vectorstore._collection) is True
    assert rc.is_cosine_space(knowledge_service._qa_store._collection) is False


def test_temp_store_actually_accepts_writes():
    """证明上面"真实库零字节变化"不是因为测试根本没用到向量库。

    写一条→查得到→删掉。走 add_documents（真实嵌入路径）而不是 _collection.add(伪向量)，
    是为了顺带确认 QuotaTrackingEmbeddings/维度与生产一致；临时库允许任何维度组合，
    但同库内必须一致，故删净不留。
    """
    from langchain_core.documents import Document

    import rag_chain

    col = rag_chain.vectorstore._collection
    marker = {"source": "test_chroma_isolation_probe"}
    before = col.count()
    col_ids = rag_chain.vectorstore.add_documents(
        [Document(page_content="测试隔离探针：本条不属于任何真实法条。", metadata=marker)]
    )
    try:
        assert col.count() == before + 1, "临时库条目数未增加 ⇒ 写入没落到 CHROMA_DIR"
        assert col.get(where=marker)["ids"], "写入后按 metadata 查不到 ⇒ 写到了别处"
    finally:
        if col_ids:
            col.delete(ids=col_ids)
        assert col.get(where=marker)["ids"] == []
