"""LLM 查询改写（1d，2026-09-15）——契约测试（全 mock，非 slow，不调网络）。

背景与机制：`dispatch-output/quality-1d-20260914/recall_generation_diag.py` 实测
16 条硬缺口对真实问句两路 @40 命中 3/78（向量）/0/78（BM25），而条文自检索 78/78 rank-1
⇒ 缺口在 query 侧。本模块把问句改写为"法条语言"检索句，以 **slice 同权**附加进候选池。

钉住的契约：
1. **默认关闭 → 零行为变化**：`query_rewrite_enabled=False` 时 `expand_queries` 一次都不被调用，
   召回路数与历史逐字一致；
2. 开启后改写句按序追加为 **slice 单元**（每句各走双路），`docs[:k]` 返回条数不变；
3. **锚点保底不被稀释**：追加 slice 单元不改变锚点前置的结果（与关闭时逐字一致）；
4. 外层截止点临近 → 传给 `expand_queries` 的预算被收紧（<1s 直接放弃，绝不为改写吃检索预算）；
5. 开关进缓存 key（翻转开关不得命中旧结果）；
6. **fail-open**：模型异常/超时/坏 JSON/短问句/预算不足 → `()`，且**负缓存**不重复烧；
7. 解析器：dedup、>80 字剔除、条数上限 `query_rewrite_max_units`。
"""

import os
import sys
import time
from concurrent.futures import TimeoutError as FuturesTimeout
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document  # noqa: E402

import query_rewrite as QR  # noqa: E402
import retrieval  # noqa: E402
from settings import settings  # noqa: E402

Q = "装修公司延期完工，业主能否要求其承担违约责任？"


# ---------------------------------------------------------------------------
# hybrid_retrieve 接线桩（参考 test_retrieval_pool_k 的 _patch_pipeline，按 query 区分文档）
# ---------------------------------------------------------------------------
def _mk_docs(n: int, tag: str) -> list:
    return [
        (Document(page_content=f"{tag}-{i}", metadata={"source": "民法典", "article": f"第{i}条"}), 1.0)
        for i in range(n)
    ]


def _patch_pipeline(monkeypatch, recorded: list) -> None:
    monkeypatch.setattr(retrieval.query_understand, "decompose", lambda q: [(q, "original")])

    def _vector_top(query, n, category=None, valid=None):
        recorded.append(("v", query, n))
        return _mk_docs(n, f"v:{query}")

    def _bm25_top(query, n, category=None, valid=None):
        recorded.append(("b", query, n))
        return _mk_docs(n, f"b:{query}")

    monkeypatch.setattr(retrieval, "vector_top", _vector_top)
    monkeypatch.setattr(retrieval, "bm25_top", _bm25_top)
    monkeypatch.setattr(settings, "rerank_enabled", False)
    monkeypatch.setattr(retrieval, "_cosine_rank", lambda q, docs: docs)
    monkeypatch.setattr(settings, "retrieval_pool_k", 0)
    retrieval.invalidate()
    QR.reset_cache()


def _patch_expand(monkeypatch, out, calls: list):
    def fake_expand(query, *, timeout_s_override=None):
        calls.append((query, timeout_s_override))
        return tuple(out)

    monkeypatch.setattr(QR, "expand_queries", fake_expand)


# ---------------------------------------------------------------------------
# 1) 默认关闭 → 零行为变化
# ---------------------------------------------------------------------------
def test_default_off_expand_never_called(monkeypatch):
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    calls: list = []
    _patch_expand(monkeypatch, ["定金罚则适用条件"], calls)
    monkeypatch.setattr(settings, "query_rewrite_enabled", False)

    out = retrieval.hybrid_retrieve(Q, k=4)

    assert calls == [], "开关关闭时 expand_queries 不得被调用"
    assert [r[1] for r in recorded] == [Q, Q], recorded  # 仅原问句走双路
    assert len(out) == 4


# ---------------------------------------------------------------------------
# 2) 开启 → slice 单元按序追加，返回条数不变
# ---------------------------------------------------------------------------
def test_enabled_appends_rewrite_units_in_order(monkeypatch):
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    _patch_expand(monkeypatch, ["违约责任及赔偿范围", "逾期履行债务的违约责任"], [])
    monkeypatch.setattr(settings, "query_rewrite_enabled", True)

    out = retrieval.hybrid_retrieve(Q, k=4)

    queries = [r[1] for r in recorded]
    assert queries == [
        Q,
        Q,
        "违约责任及赔偿范围",
        "违约责任及赔偿范围",
        "逾期履行债务的违约责任",
        "逾期履行债务的违约责任",
    ], queries
    assert len(out) == 4, "docs[:k] 返回条数不变（writer payload 不膨胀）"


def test_enabled_expand_receives_bridged_query(monkeypatch):
    """接线传的是 `_bridge_query` 之后的问句（与缓存 key / 单元召回同口径）。"""
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    calls: list = []
    _patch_expand(monkeypatch, [], calls)
    monkeypatch.setattr(settings, "query_rewrite_enabled", True)

    retrieval.hybrid_retrieve(Q, k=4)
    assert calls == [(retrieval._bridge_query(Q), None)], calls


def test_deadline_schedules_tighter_budget(monkeypatch):
    """外层截止点剩 ~0.5s → 传给 expand 的预算 = deadline-now-margin（实现内 <1s 即放弃）。"""
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    calls: list = []
    _patch_expand(monkeypatch, [], calls)
    monkeypatch.setattr(settings, "query_rewrite_enabled", True)

    retrieval.hybrid_retrieve(Q, k=4, deadline_monotonic=time.monotonic() + 0.5)

    (q_used, budget) = calls[0]
    assert budget is not None and budget < 1.0, calls
    assert budget <= 0.5


# ---------------------------------------------------------------------------
# 3) 锚点保底不被稀释（slice 同权 = 只扩池，不占保底位）
# ---------------------------------------------------------------------------
def test_rewrite_units_do_not_dilute_anchor_guarantee(monkeypatch):
    anchor = "业主能否依据《民法典》第五百七十七条主张违约责任"
    recorded: list = []
    monkeypatch.setattr(retrieval.query_understand, "decompose", lambda q: [(anchor, "anchor")])

    def _vector_top(query, n, category=None, valid=None):
        recorded.append(("v", query))
        return _mk_docs(n, f"v:{query}")

    def _bm25_top(query, n, category=None, valid=None):
        recorded.append(("b", query))
        return _mk_docs(n, f"b:{query}")

    monkeypatch.setattr(retrieval, "vector_top", _vector_top)
    monkeypatch.setattr(retrieval, "bm25_top", _bm25_top)
    monkeypatch.setattr(settings, "rerank_enabled", False)
    monkeypatch.setattr(retrieval, "_cosine_rank", lambda q, docs: docs)
    monkeypatch.setattr(settings, "retrieval_pool_k", 0)
    retrieval.invalidate()
    QR.reset_cache()

    out_off = retrieval.hybrid_retrieve(anchor, k=4)
    assert all(f"v:{anchor}" in d.page_content or f"b:{anchor}" in d.page_content for d in out_off[:2])

    retrieval.invalidate()
    _patch_expand(monkeypatch, ["违约责任及赔偿范围"], [])
    monkeypatch.setattr(settings, "query_rewrite_enabled", True)
    out_on = retrieval.hybrid_retrieve(anchor, k=4)

    assert [d.page_content for d in out_on] == [d.page_content for d in out_off], (
        "追加 slice 单元后锚点保底的 top-4 必须不变（改写句不得挤占保底位）"
    )


# ---------------------------------------------------------------------------
# 5) 开关进缓存 key
# ---------------------------------------------------------------------------
def test_switch_part_of_cache_key(monkeypatch):
    recorded: list = []
    _patch_pipeline(monkeypatch, recorded)
    _patch_expand(monkeypatch, ["格式条款排除消费者主要权利无效"], [])
    query = "商家声称概不退款的条款是否有效呢"

    monkeypatch.setattr(settings, "query_rewrite_enabled", False)
    retrieval.hybrid_retrieve(query, k=4)
    assert len(recorded) == 2

    retrieval.hybrid_retrieve(query, k=4)
    assert len(recorded) == 2, "同参数应命中缓存"

    monkeypatch.setattr(settings, "query_rewrite_enabled", True)
    retrieval.hybrid_retrieve(query, k=4)
    # 翻转开关 → 重算：原问句双路 + 改写句双路 = +4（累计 2+0+4=6）
    assert len(recorded) == 6, recorded
    assert {r[1] for r in recorded[-4:]} == {query, "格式条款排除消费者主要权利无效"}


# ---------------------------------------------------------------------------
# 6) fail-open（expand 内部）
# ---------------------------------------------------------------------------
def test_expand_invoker_exception_returns_empty_and_negative_caches(monkeypatch):
    QR.reset_cache()
    calls: list = []

    def boom(prompt, timeout_s):
        calls.append(1)
        raise RuntimeError("llm down")

    monkeypatch.setattr(QR, "_invoke_llm", boom)
    assert QR.expand_queries("这个合同里的定金条款到底有没有效力？") == ()
    assert QR.expand_queries("这个合同里的定金条款到底有没有效力？") == ()
    assert len(calls) == 1, "负缓存：同一问句失败后不得每请求重复烧"


def test_expand_timeout_returns_empty(monkeypatch):
    """调用挂起 → 硬超时抛 futures TimeoutError → 吞掉返回 ()（绝不拖住检索线程）。"""
    QR.reset_cache()

    def hang(prompt, timeout_s):
        raise FuturesTimeout()

    monkeypatch.setattr(QR, "_invoke_llm", hang)
    assert QR.expand_queries("对方以欺诈手段订立的合同我能不能撤销？") == ()


def test_expand_short_query_and_small_budget_skip(monkeypatch):
    QR.reset_cache()
    calls: list = []
    monkeypatch.setattr(QR, "_invoke_llm", lambda *a, **k: calls.append(1) or ((), 0))
    assert QR.expand_queries("有效吗？") == ()  # <5 字
    assert QR.expand_queries("这个合同里的定金条款到底有没有效力？", timeout_s_override=0.5) == ()
    assert calls == [], "短问句与预算不足都不得发起调用"


def test_expand_success_caches_positive_result(monkeypatch):
    QR.reset_cache()
    calls: list = []

    def fake(prompt, timeout_s):
        calls.append(prompt)
        return ("定金罚则适用条件及双倍返还规定",), 42

    monkeypatch.setattr(QR, "_invoke_llm", fake)
    q = "对方违约我主张双倍返还定金有没有法律依据？"
    assert QR.expand_queries(q) == ("定金罚则适用条件及双倍返还规定",)
    assert QR.expand_queries(q) == ("定金罚则适用条件及双倍返还规定",)
    assert len(calls) == 1, "正缓存：命中后不再调用"


def test_deduct_falls_back_to_estimate_when_usage_missing(monkeypatch):
    """R2（2026-09-15 审查）：端点不返回 usage（tokens=0）→ 用 estimate_tokens 兜底并照常 deduct。

    直接测 _invoke_llm 内部的记账分支：桩掉 registry（pick/deduct），假 llm.invoke 返回
    无 usage_metadata 的响应 → deduct 必须收到 >0 的估算值（改写消耗对配额闸门可见）。
    """
    from langchain_core.messages import AIMessage

    import llm_registry

    deducted: list[tuple[str, int]] = []
    fake_llm = SimpleNamespace(invoke=lambda msgs: AIMessage(content='{"queries": ["表见代理的构成要件"]}'))
    monkeypatch.setattr(llm_registry.registry, "pick", lambda m, t: ("k-test", fake_llm))
    monkeypatch.setattr(llm_registry.registry, "deduct", lambda k, n: deducted.append((k, n)))
    out, tokens = QR._invoke_llm("争点问句：测试问句", timeout_s=5.0)
    assert out == ("表见代理的构成要件",)
    assert deducted == [("k-test", tokens)] and tokens > 0, (deducted, tokens)


# ---------------------------------------------------------------------------
# 7) 解析器
# ---------------------------------------------------------------------------
def test_parse_valid_and_tolerates_prose_wrapping():
    txt = '好的，结果如下：\n```json\n{"queries": ["违约责任及损害赔偿范围", "定金罚则适用条件"]}\n```\n供参考。'
    assert QR.parse_rewrite_response(txt) == ("违约责任及损害赔偿范围", "定金罚则适用条件")


def test_parse_bad_shapes_fail_open():
    assert QR.parse_rewrite_response("not json at all") == ()
    assert QR.parse_rewrite_response('{"queries": "字符串不是列表"}') == ()
    assert QR.parse_rewrite_response('{"other": []}') == ()
    assert QR.parse_rewrite_response("") == ()


def test_parse_dedup_truncation_and_cap(monkeypatch):
    monkeypatch.setattr(settings, "query_rewrite_max_units", 2)
    long_s = "长" * 81
    got = QR.parse_rewrite_response(
        f'{{"queries": ["定金罚则", "定金罚则  ", "  ", "{long_s}", "违约损害赔偿", "另一条"]}}'
    )
    assert got == ("定金罚则", "违约损害赔偿"), got  # 去重/去空白/剔超长/上限 2


def test_parse_collapses_internal_whitespace():
    assert QR.parse_rewrite_response('{"queries": ["格式条款 排除\\n消费者 主要权利无效"]}') == (
        "格式条款 排除 消费者 主要权利无效",
    )
