"""knowledge_service 并发写测试（slow，真实 chroma）。

回归背景：add_text 的 delete-then-add 非原子（Chroma 无事务），FastAPI 线程池下
并发管理操作可能交错（互删/重复/混版本）。_WRITE_LOCK 串行化写路径后，
同一 (source, article) 并发写应幂等——最终只有一份完整内容，无重复无混版。
"""

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

import knowledge_service as ks

_TEST_SOURCE = "并发写入测试法"


def _cleanup():
    ids = ks._collection().get(where={"source": _TEST_SOURCE})["ids"]
    if ids:
        ks._collection().delete(ids=ids)


@pytest.mark.slow
def test_concurrent_add_text_idempotent():
    _cleanup()
    try:
        # 基线：单次写入的 chunk 数
        base_n = ks.add_text("第一条　这是用于并发测试的条文正文，句子一。句子二。", source=_TEST_SOURCE, article="第一条", origin="manual")
        assert base_n >= 1

        # 并发：4 线程同 (source, article) 写不同版本
        errors = []

        def worker(i):
            try:
                ks.add_text(
                    f"第一条　这是版本{i}的并发测试条文正文，句子一。句子二。",
                    source=_TEST_SOURCE,
                    article="第一条",
                    origin="manual",
                )
            except Exception as e:  # pragma: no cover
                errors.append(e)

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert not errors

        left = ks._collection().get(where={"source": _TEST_SOURCE})
        docs = left["documents"] or []
        # 幂等：无重复（chunk 数=单次写入）
        assert len(docs) == base_n, f"并发写后 chunk 数 {len(docs)} != 基线 {base_n}（重复或丢失）"
        # 无混版：所有 chunk 来自同一版本
        versions = {d[d.find("版本") + 2 : d.find("版本") + 3] for d in docs if "版本" in d}
        assert len(versions) <= 1, f"并发写混版：{versions}"
    finally:
        _cleanup()
