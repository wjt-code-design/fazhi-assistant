"""knowledge_service 写路径回归（并发幂等 + 法版本判定降级）。

库口径：本模块全部用例都走 conftest 的**隔离 lane**——`CHROMA_DIR` 被无条件指向进程私有
临时库（tests/conftest.py:33-40），真实 `backend/chroma_db` 只有显式 opt-in 的 `real_kb`
夹具（tests/conftest.py:114-163）够得着 ⇒ 这里既不是"真实 chroma"，也没有写真实库的风险。
标记：`:31` 的并发用例标 slow（4 线程 × 多次真实嵌入，wall time 大）；版本判定那两条**不标**，
故 CI（`-m "not slow"`）也跑得到——回归得有人跑才算数。

回归背景：
- 并发：add_text 的 delete-then-add 非原子（Chroma 无事务），FastAPI 线程池下并发管理操作
  可能交错（互删/重复/混版本）。_WRITE_LOCK 串行化写路径后，同一 (source, article) 并发写
  应幂等——最终只有一份完整内容，无重复无混版。
- 判定降级：替换判据整段包在 `except Exception: stale_ids = []` 里 ⇒"判据崩塌"与"判定后决定
  不替换"在库侧结果相同，必须靠一条结构化告警分开，且旧块不得被误删；该告警**不得**携带
  `exc_info`——异常原文 + traceback 会被 `_JsonFormatter` 整体写进内置键 `exc`，而此处被捕获的
  `replaceable_version_ids(...)` 入参含条文正文（票 T-A，2026-09-27）。
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
        base_n = ks.add_text(
            "第一条　这是用于并发测试的条文正文，句子一。句子二。",
            source=_TEST_SOURCE,
            article="第一条",
            origin="manual",
            extra_meta={"effective_from": "2024-01-01"},
        )
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
                    extra_meta={"effective_from": "2024-01-01"},
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


# ---------------- 受控沉淀自动收录（2026-08-07） ----------------
def test_create_candidate_is_always_pending(monkeypatch, db):
    """W06-P0 新契约：**所有分数一律 pending、一律不写向量**（高分不再自动收录、不自签来源）。

    2026-09-17 修复：此前直接 `database.SessionLocal()` —— 未设 DATABASE_URL 时
    database.py 回落到真实 backend/app.db，导致**每次全量跑批都写生产裸机库**
    （归因确证：贡献 3 次写事务，落 qa_candidates；见
    dispatch-output/pytest-full-20260917/db-write-attribution-report.md）。
    改用 conftest 的 `db` fixture（tmp_path 建库 + engine/SessionLocal 替换）实现隔离。

    换契约（C03=P 写侧，2026-10-18）：原「≥0.89 自动 approved 且写 QA 向量」已废除。高分腿
    （原「自动收录」腿）现与低分腿同判：`status=="pending"` 且 `add_qa_pair` 调用数为 0。
    """
    import retrieval
    from models import QaCandidate

    added = []
    # add_qa_pair 替身放宽到能吃 cand_id/doc_id 等 kwargs，只记调用；新契约下应恒为 0 次。
    monkeypatch.setattr(ks, "add_qa_pair", lambda q, a, e="", fp="", *more, **link: added.append(q))
    monkeypatch.setattr(retrieval, "invalidate", lambda: None)

    q1, q2 = f"_auto_{id(object())}", f"_pend_{id(object())}"
    try:
        c1 = ks.create_candidate(db, q1, "答案", 0.95, "证据")
        assert c1.status == "pending" and added == []
        c2 = ks.create_candidate(db, q2, "答案", 0.70, "证据")
        assert c2.status == "pending" and added == []
    finally:
        # 库已隔离到 tmp_path（fixture 负责 close/dispose），此处清理仅为语义完整
        db.rollback()
        db.query(QaCandidate).filter(QaCandidate.question.in_([q1, q2])).delete(synchronize_session=False)
        db.commit()


# ---------------- W2：版本判定崩溃 ⇒ 旧块不许少，崩溃必须看得见 ----------------
_W2_SOURCE = "版本判定崩溃测试法"
# 每条正文里埋一个独有记号，用来断言"条文正文没有落进日志"（不断言分块后的整段文本，
# 因为 chunking 会改写空白/前缀，拿全文比对是脆的）。
_W2_BODIES = (
    "第一条　版本判定崩溃测试初版条文正文，W2TOKENA 句。乙句。",
    "第一条　版本判定崩溃测试修订条文正文，丙句。W2TOKENB 句。",
    "第一条　版本判定崩溃测试再修订条文正文，戊句。W2TOKENC 句。",
)

# 合成敏感文本（票 T-A）：钉"异常原文不许进日志"。用记号而不是真密文/真密钥，
# 断言是全 payload 序列化后的子串比对，不需要知道它的形态。
_SECRET_MARKER = "SECRET-MARKER-条文正文片段"


def _w2_ids() -> set[str]:
    return set(ks._collection().get(where={"source": _W2_SOURCE})["ids"])


def _w2_cleanup() -> None:
    ids = _w2_ids()
    if ids:
        ks._collection().delete(ids=list(ids))


def _w2_add(body: str) -> int:
    return ks.add_text(
        body, source=_W2_SOURCE, article="第一条", origin="manual", extra_meta={"effective_from": "2024-01-01"}
    )


def _w2_boom(*args, **kwargs):
    """判据依赖的替身：抛 `RuntimeError`，且**把入参正文复述进异常消息**。

    这不是造出来的刁钻形态：`replaceable_version_ids` 的入参就有 `new_content`（新条文正文）
    与 `documents`（旧条文正文），异常消息里带一段正文完全现实；而 `_JsonFormatter` 会把
    `exc_info` 的异常原文 + traceback 整体写进**内置键** `exc`（不受 `_ACCOUNT_FIELDS` 约束）
    ⇒ 只要带了 `exc_info=True`，正文就随 `exc` 落进 JSON 日志（票 T-A 实测复现）。
    """
    new_content = str(kwargs.get("new_content") or "")
    raise RuntimeError(f"injected judgment boom | {_SECRET_MARKER} | {new_content or '(no content)'}")


@pytest.fixture(scope="module")
def w2_crash_run():
    """跑一次"判据崩溃下的重传"，把现场交给两条用例各查一半（现场要 3 次真写库，别付两遍）。

    `add_text` 的判据整段包在 `except Exception: stale_ids = []` 里：崩溃与"判定后不替换"
    在库侧同形，判据哪天整体失效都没人知道
    （`version-safety-review-findings-20260927.md` 低-2，§6 已用变异确证写侧那条用例是瞎的）。
    "旧块没被误删"和"崩溃看得见"是两件事，所以拆成两条用例分别钉 —— 合成一条时，
    两半同时坏只会看到先红的那条，另一半年检不出来。

    产出 `(records, surviving, after, n)`：捕获到的日志 / 崩溃前存活的旧块 id / 崩溃后的 id / 返回值。
    """
    import logging

    import rag_chain
    from tests._fake_embeddings import FakeEmbeddings, embeddings_double

    # C15 分流（2026-10-16）：本 fixture 是 module 级，用不上函数级 double_embeddings，
    # 所以在装/拆上走同一个构造处（tests/_fake_embeddings.embeddings_double）。
    # 这两条用例判的是"判据崩溃时旧块不被误删 + 崩溃看得见"，与向量语义无关。
    _previous_inner = rag_chain.embeddings._inner_resource
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("legal.knowledge")
    handler = Capture()
    # 复核 B 路 MINOR：从"装上替身"到 `try:` 之间的任何一行抛错（例如
    # `ks.replaceable_version_ids` 哪天被改名），都会让替身永久留在进程里、后续真向量用例悄悄变假。
    # 所以整段挪进 try，回收只可能走 finally。
    try:
        rag_chain.embeddings._inner_resource = embeddings_double()
        assert isinstance(rag_chain.embeddings._inner, FakeEmbeddings), "w2 现场没换成替身，这条腿会去加载 BGE"
        original = ks.replaceable_version_ids
        _w2_cleanup()  # 替身就位后再清，免得清理动作去加载真模型
        # 对照腿：判据正常时，同 (法名, 条号, 生效日) 的重传**会**替换旧块。
        # 缺了这条，下面的"旧块仍在"可能只是判据本来就不替换 ⇒ 恒真断言。
        _w2_add(_W2_BODIES[0])
        seeded = _w2_ids()
        assert seeded, "夹具未建出旧块"
        _w2_add(_W2_BODIES[1])
        assert not (seeded & _w2_ids()), "对照腿失效：判据正常时旧块应被替换，否则被测腿没有区分度"

        # 被测腿：把判定依赖换成抛错。此时剩下的块就是"将被误删的旧块"。
        surviving = _w2_ids()
        assert surviving, "对照腿应留下一个新块"
        ks.replaceable_version_ids = _w2_boom
        logger.addHandler(handler)
        try:
            n = _w2_add(_W2_BODIES[2])
        finally:
            logger.removeHandler(handler)
            ks.replaceable_version_ids = original
        yield records, surviving, _w2_ids(), n
    finally:
        rag_chain.embeddings._inner_resource = _previous_inner  # 替身必须收回，否则泄漏给同模块后续用例
        _w2_cleanup()


def test_version_judgment_crash_keeps_old_chunks(w2_crash_run):
    """一半：`stale_ids = []` 的保守行为仍在——旧块一块不少、新块照样写入。"""
    _records, surviving, after, n = w2_crash_run
    assert n >= 1, "判定崩溃不该影响写入本身"
    assert surviving <= after, f"判定崩溃时旧块被删了——安全侧塌陷：{sorted(surviving - after)}"
    assert after - surviving, "新块应写入成功"


def test_version_judgment_crash_is_visible_in_structured_log(w2_crash_run):
    """另一半：崩溃必须从结构化日志里读得出来，且**异常原文/traceback/条文正文都不进日志**。

    断言读的是**格式化之后**的 payload —— 键只挂在 record 上而没登记进
    `observability._ACCOUNT_FIELDS` 会被 `_JsonFormatter` 静默丢弃（本仓踩过两次，
    见 `test_log_field_whitelist.py` 的说明），所以只断言属性存在等于没断言。

    泄露通道（票 T-A，2026-09-27）：`_JsonFormatter.format` 会把 `exc_info` 的异常原文 +
    完整 traceback 写进**内置键** `exc`（内置键，不占 `_ACCOUNT_FIELDS`，登记与否都拦不住），
    而此处被捕获的 `replaceable_version_ids(...)` 入参含 `new_content`/`documents`（条文正文）
    ⇒ 原实现（`exc_info=True`）下 `exc` 里能读到合成敏感标记与正文记号。本用例把这条通道钉死：
    `exc` 键必须为空、标记与正文记号都不得出现，同时保留异常**类名** + 法名/条号的定位能力。
    """
    import json
    import logging

    from observability import _JsonFormatter

    records, _surviving, _after, _n = w2_crash_run
    warned = [r for r in records if r.levelno == logging.WARNING]
    assert len(warned) == 1, (
        f"判定崩溃应恰好留一条 warning，实际 {len(warned)} 条；全部日志：{[r.getMessage() for r in records]}"
    )
    payload = json.loads(_JsonFormatter().format(warned[0]))
    assert payload.get("law_version_judgment_failed") is True, (
        f"归因键没登记进 observability._ACCOUNT_FIELDS ⇒ 被 JSON formatter 静默丢弃：{payload}"
    )
    # 可定位：异常**类名** + 法名 + 条号要能在日志里读到（"有一条 warning"不算）
    msg = payload.get("msg", "")
    assert "RuntimeError" in msg, f"异常类名没落进日志 ⇒ 崩溃无法归因：{payload}"
    assert _W2_SOURCE in msg and "第一条" in msg, f"日志缺法名/条号定位标识：{payload}"
    # 不泄原文：异常原文（含 traceback）与条文正文一个字都不许进日志
    dumped = json.dumps(payload, ensure_ascii=False)
    assert payload.get("exc") in (None, ""), (
        f"exc_info 仍把异常原文/traceback 写进 JSON（内置键 exc，不受白名单约束）：{payload.get('exc')!r}"
    )
    assert _SECRET_MARKER not in dumped, f"异常原文（合成敏感文本）落进了日志：{_SECRET_MARKER}"
    assert "injected judgment boom" not in dumped, f"异常消息原文落进了日志：{payload}"
    assert "Traceback" not in dumped, f"traceback 落进了日志：{payload}"
    for token in ("W2TOKENA", "W2TOKENB", "W2TOKENC"):
        assert token not in dumped, f"条文正文落进了日志：{token}"
