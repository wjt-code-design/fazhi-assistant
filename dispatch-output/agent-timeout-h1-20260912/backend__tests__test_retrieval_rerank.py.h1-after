"""检索查准回归测试：余弦精排 + 三路保底 + k6 + 措辞桥接（真实 KB，slow）。

4 个历史 bad case（"对法错条"，roadmap 记录）：高空抛物 1254 / 行政复议 11 / 个人信息 5,6,7 / 股东出资 47
——期望条必须进入 hybrid top-6（模型可引用的窗口），防未来改动回退。
"""

import os
import sys
import time
from types import SimpleNamespace

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest  # noqa: E402

import retrieval  # noqa: E402


def _in_top(docs, source, article):
    return any(d.metadata.get("source") == source and d.metadata.get("article") == article for d in docs)


# ---------------- 措辞桥接（纯函数，非 slow） ----------------
def test_bridge_query_rewrites():
    assert "从建筑物中抛掷物品" in retrieval._bridge_query("高空抛物致人损害，由谁承担责任？")
    assert "申请行政复议" in retrieval._bridge_query("行政复议的受案范围包括哪些情形？")


def test_bridge_query_passthrough():
    assert retrieval._bridge_query("公司股东认缴出资的期限是多长？") == "公司股东认缴出资的期限是多长？"


# ---------------- QuotaTrackingEmbeddings 包装（扣减 + 耗尽 409，纯 mock） ----------------
def test_quota_tracking_embeddings(monkeypatch):
    import quota_store
    import quota_utils
    from rag_chain import QuotaTrackingEmbeddings
    from settings import settings
    from tests._fake_embeddings import FakeEmbeddings

    inner = FakeEmbeddings()
    wrapped = QuotaTrackingEmbeddings(inner)
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(quota_store, "record_delta", lambda key, delta: calls.append((key, delta)))
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)

    settings.embedding_provider = "aliyun"
    settings.embedding_quota_total = 1000
    settings.embedding_quota_initial = 0
    settings.embedding_model = "test-embed"
    key = quota_utils.embedding_model_key()  # per-model key（B4）= settings.embedding_model
    assert key == "test-embed"
    try:
        # 云 provider：embed 扣减（成功调用后才记账，key=模型名）
        wrapped.embed_query("abc")  # estimate_tokens("abc") = 2
        wrapped.embed_documents(["abc", "def"])  # estimate_tokens("abcdef") = 4
        assert (key, 2) in calls
        assert (key, 4) in calls
        # 耗尽（left=0）→ 抛 UtilityQuotaExhausted，不调 inner
        monkeypatch.setattr(quota_store, "get_used", lambda k: 1000)
        try:
            wrapped.embed_query("abc")
            raise AssertionError("耗尽应抛 UtilityQuotaExhausted")
        except quota_utils.UtilityQuotaExhausted:
            pass
        # 本地 provider：即使配额 0 也不抛（本地 BGE 无限用）
        settings.embedding_provider = "local"
        v = wrapped.embed_query("abc")
        assert len(v) == 768
        # 未启用配额（total=0）→ 不抛（防测试污染真实库）
        settings.embedding_quota_total = 0
        settings.embedding_provider = "aliyun"
        assert len(wrapped.embed_query("abc")) == 768
    finally:
        settings.embedding_provider = "local"
        settings.embedding_quota_total = 0
        settings.embedding_quota_initial = 0
        settings.embedding_model = "text-embedding-v4"


# ---------------- rerank 聚焦检索词（锚点优先 + 过短兜底，纯函数） ----------------
def test_rerank_query_anchor_preferred():
    import query_understand

    # 罪名锚点 → 用锚点串（聚焦）
    units = [(q, k) for q, k in [("贩卖毒品罪", query_understand.KIND_ANCHOR)]]
    assert retrieval._rerank_query("甲贩卖毒品应该如何处罚？", units) == "贩卖毒品罪"
    # 法名+条号（长度>=8）→ 用锚点
    units = [("《刑法》第三百四十七条", query_understand.KIND_ANCHOR)]
    assert retrieval._rerank_query("《刑法》第三百四十七条讲了什么？", units) == "《刑法》第三百四十七条"
    # 无锚点 → 回落整句（截断）
    units = [("网购七天无理由退货有法律依据吗？", query_understand.KIND_ORIGINAL)]
    assert retrieval._rerank_query("网购七天无理由退货有法律依据吗？", units).startswith("网购七天")
    # 纯条号锚点（短、无语义）→ 回落整句，不硬用条号
    units = [("第三百四十七条", query_understand.KIND_ANCHOR)]
    long_q = "贩卖毒品数量巨大，应当如何量刑？" * 10
    assert retrieval._rerank_query(long_q, units) == long_q[:120]
    assert "第三百四十七条" not in retrieval._rerank_query(long_q, units)


# ---------------- rerank 多模型轮换（配额驱动，纯 mock，非 slow） ----------------
def test_active_rerank_model_rotation(monkeypatch):
    import quota_store
    import quota_utils
    from settings import settings

    settings.rerank_enabled = True
    settings.rerank_api_key = "test"
    settings.rerank_models = "m1,m2,m3"
    settings.rerank_quota_totals = "100,100,100"
    settings.rerank_quota_initial = 0
    settings.rerank_hard_threshold = 0.05
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    try:
        # 全部充足 → 队首 m1
        assert quota_utils.rerank_active_model() == "m1"
        # m1 耗尽（剩 4% < 5%）→ m2
        monkeypatch.setattr(quota_store, "get_used", lambda key: 96 if key == "m1" else 0)
        assert quota_utils.rerank_active_model() == "m2"
        # m1,m2 耗尽 → m3
        monkeypatch.setattr(quota_store, "get_used", lambda key: 96 if key in ("m1", "m2") else 0)
        assert quota_utils.rerank_active_model() == "m3"
        # 全耗尽 → None（降级本地余弦精排）
        monkeypatch.setattr(quota_store, "get_used", lambda key: 96)
        assert quota_utils.rerank_active_model() is None
        # 未启用（rerank_enabled=false）→ None
        settings.rerank_enabled = False
        assert quota_utils.rerank_active_model() is None
    finally:
        settings.rerank_enabled = False
        settings.rerank_api_key = ""
        settings.rerank_models = "qwen3-rerank,gte-rerank-v2,qwen3-vl-rerank"
        settings.rerank_quota_totals = ""


def test_rerank_docs_switches_model_on_failure(monkeypatch):
    """rerank 真实 API 失败 → 标记该模型耗尽 → 自动换下一个（块 2.2 扩展到工具模型）。"""
    from types import SimpleNamespace

    import quota_store
    import quota_utils
    from settings import settings

    settings.rerank_enabled = True
    settings.rerank_api_key = "test"
    settings.rerank_models = "m1,m2"
    settings.rerank_quota_totals = "100,100"
    settings.rerank_quota_initial = 0
    settings.rerank_hard_threshold = 0.05
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    depleted: list[str] = []
    monkeypatch.setattr(quota_utils, "mark_utility_depleted", lambda name: depleted.append(name))

    class FakeClient:
        def __init__(self):
            self.calls = []

        def post(self, path, **kw):
            model = kw["body"]["model"]
            self.calls.append(model)
            if model == "m1":
                raise RuntimeError("InsufficientBalance: 配额耗尽")
            return {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.5}]}

    fc = FakeClient()
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: fc)
    docs = [SimpleNamespace(page_content=f"doc{i}", metadata={}) for i in range(2)]
    try:
        out = retrieval._rerank_docs("q", docs)
        assert fc.calls == ["m1", "m2"]  # m1 失败 → 换 m2
        assert depleted == ["m1"]  # m1 被标记耗尽
        assert [d.page_content for d in out] == ["doc1", "doc0"]  # m2 结果按分降序
    finally:
        settings.rerank_enabled = False
        settings.rerank_api_key = ""
        settings.rerank_models = "qwen3-rerank,gte-rerank-v2,qwen3-vl-rerank"
        settings.rerank_quota_totals = ""


# ---------------- 外层预算闸门（2026-09-12 修 TOOL_TIMEOUT） ----------------
def _enable_rerank(monkeypatch, models: str = "m1,m2"):
    """开启 rerank 且两模型配额充足；调用方负责在 finally 复原。"""
    from settings import settings

    settings.rerank_enabled = True
    settings.rerank_api_key = "test"
    settings.rerank_models = models
    settings.rerank_quota_totals = "100,100"
    settings.rerank_quota_initial = 0
    settings.rerank_hard_threshold = 0.05
    return settings


def _restore_rerank(settings):
    settings.rerank_enabled = False
    settings.rerank_api_key = ""
    settings.rerank_models = "qwen3-rerank,gte-rerank-v2,qwen3-vl-rerank"
    settings.rerank_quota_totals = ""


def test_rerank_attempt_timeout_is_strictly_below_gateway_wait_limit():
    """不变式：内层 rerank 单次尝试上限（含余量）必须严格小于 retrieve_laws 外层等待上限。

    两条常量分居 retrieval.py 与 tools/gateway.py，任一侧被调大都会复现「外层已放弃等待、
    内层还在开新远程请求」从而稳定 TOOL_TIMEOUT。把它们锁在一起，防止再次静默失配。
    """
    from tools.gateway import _POLICIES

    outer = _POLICIES["retrieve_laws"].timeout_seconds
    inner = retrieval._RERANK_ATTEMPT_TIMEOUT_S + retrieval._RERANK_DEADLINE_MARGIN_S
    assert inner < outer, f"内层预算 {inner}s 必须严格小于外层等待 {outer}s"


def test_rerank_skips_remote_call_when_budget_is_insufficient(monkeypatch):
    """反例：外层预算不足一次完整尝试时，必须 0 次远程调用（降级余弦精排）。"""
    import quota_store
    import quota_utils

    settings = _enable_rerank(monkeypatch)
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_utils, "_depleted_mem", set())
    depleted: list[str] = []
    monkeypatch.setattr(quota_utils, "mark_utility_depleted", lambda name: depleted.append(name))

    class FakeClient:
        def __init__(self):
            self.calls: list[str] = []

        def post(self, path, **kw):
            self.calls.append(kw["body"]["model"])
            return {"results": [{"index": 0, "relevance_score": 0.9}]}

    fc = FakeClient()
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: fc)
    docs = [SimpleNamespace(page_content=f"doc{i}", metadata={}) for i in range(2)]
    need = retrieval._RERANK_ATTEMPT_TIMEOUT_S + retrieval._RERANK_DEADLINE_MARGIN_S
    try:
        # 剩余预算比一次完整尝试少 0.05s → 不得启动（这是「到期后不再开新调用」的闸门）
        out_insufficient = retrieval._rerank_docs("q", docs, deadline_monotonic=time.monotonic() + need - 0.05)
        assert fc.calls == [], "预算不足时不应产生任何远程 rerank 调用"
        assert out_insufficient is None
        assert depleted == [], "预算不足不是模型故障，不得标记耗尽"

        # 再多 0.5s 就够一次完整尝试 → 正常走远程并返回结果
        out = retrieval._rerank_docs("q", docs, deadline_monotonic=time.monotonic() + need + 0.5)
        assert fc.calls == ["m1"]
        assert out is not None and [d.page_content for d in out] == ["doc0"]
    finally:
        _restore_rerank(settings)


def test_rerank_timeout_degrades_without_switching_model_or_marking_depleted(monkeypatch):
    """反例：rerank 超时 → 不换下一个模型、不标记耗尽，直接降级（超时 ≠ 模型坏了）。"""
    import quota_store
    import quota_utils

    settings = _enable_rerank(monkeypatch)
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_utils, "_depleted_mem", set())
    depleted: list[str] = []
    monkeypatch.setattr(quota_utils, "mark_utility_depleted", lambda name: depleted.append(name))

    class TimeoutClient:
        def __init__(self):
            self.calls: list[str] = []

        def post(self, path, **kw):
            self.calls.append(kw["body"]["model"])
            raise httpx.ReadTimeout("read timed out")

    tc = TimeoutClient()
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: tc)
    docs = [SimpleNamespace(page_content=f"doc{i}", metadata={}) for i in range(2)]
    try:
        assert retrieval._rerank_docs("q", docs) is None
        assert tc.calls == ["m1"], "超时后不得再换下一个模型继续烧预算"
        assert depleted == [], "超时不得把健康模型标记为耗尽"
    finally:
        _restore_rerank(settings)


def test_rerank_without_deadline_keeps_historical_behaviour(monkeypatch):
    """共享路径回归：不给 deadline 的调用方（如 main.py 的 retrieve(q, k=8)）行为不变。"""
    import quota_store
    import quota_utils

    settings = _enable_rerank(monkeypatch, models="m1")
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_utils, "_depleted_mem", set())

    class FakeClient:
        def __init__(self):
            self.calls: list[str] = []

        def post(self, path, **kw):
            self.calls.append(kw["body"]["model"])
            return {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]}

    fc = FakeClient()
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: fc)
    docs = [SimpleNamespace(page_content=f"doc{i}", metadata={}) for i in range(2)]
    try:
        out = retrieval._rerank_docs("q", docs)  # 无 deadline
        assert fc.calls == ["m1"]
        assert [d.page_content for d in out] == ["doc1", "doc0"]
    finally:
        _restore_rerank(settings)


# ---------------- 真实 KB 查准（slow：CI 跳过） ----------------
@pytest.mark.slow
def test_high_altitude_fall_precision():
    docs = retrieval.hybrid_retrieve("高空抛物致人损害，由谁承担责任？", k=6)
    assert _in_top(docs, "民法典", "第一千二百五十四条"), "高空抛物应召回 1254，而非高度危险责任噪声"


@pytest.mark.slow
def test_admin_reconsideration_scope():
    docs = retrieval.hybrid_retrieve("行政复议的受案范围包括哪些情形？", k=6)
    assert _in_top(docs, "行政复议法", "第十一条"), "受案范围应召回 11 条正面条款（措辞桥接）"


@pytest.mark.slow
def test_personal_info_principles():
    docs = retrieval.hybrid_retrieve("处理个人信息应当遵循哪些原则？", k=6)
    for art in ("第五条", "第六条", "第七条"):
        assert _in_top(docs, "个人信息保护法", art), f"个人信息原则应召回 {art}"


@pytest.mark.slow
def test_shareholder_capital_deadline():
    docs = retrieval.hybrid_retrieve("公司股东认缴出资的期限是多长？", k=6)
    assert _in_top(docs, "公司法", "第四十七条"), "出资期限应召回 47 条"


@pytest.mark.slow
def test_short_name_exact_lookup():
    # 简称→全称：条号直查也应吃别名（库内 source 是全称「刑事诉讼法」）
    docs = retrieval.exact_article_lookup("刑诉法", "第八十三条")
    assert docs, "刑诉法第八十三条应命中刑事诉讼法第八十三条"


@pytest.mark.slow
def test_short_name_citation_verify():
    # code-review P1：引用校验（article_in_kb）也应归一——答案引《民诉法》第X条
    # 不应被判假引用（此前 source_in_kb/article_in_kb 走 _source_key 不接别名）
    bad = retrieval.citation_verify("根据《民诉法》第一百二十条，采取强制措施的决定权专属人民法院。")
    assert bad == [], f"《民诉法》应归一审诉法而非判假引用: {bad}"
