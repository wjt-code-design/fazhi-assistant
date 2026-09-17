"""SiliconFlow rerank 分支单测（离线，mock httpx，零网络）。

期望独立来源：SiliconFlow /v1/rerank 的公开响应形状
（顶层 results[{index, relevance_score}]，index 为 documents 下标）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from langchain_core.documents import Document

import quota_utils
import retrieval
import settings as _s


def test_siliconflow_rerank_branch_orders_by_relevance(monkeypatch):
    monkeypatch.setattr(_s.settings, "rerank_enabled", True)
    monkeypatch.setattr(_s.settings, "rerank_api_key", "")  # 走 provider 级 key 回退
    monkeypatch.setattr(_s.settings, "siliconflow_api_key", "test-sf-key")
    monkeypatch.setattr(_s.settings, "rerank_base_url", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(_s.settings, "rerank_models", "BAAI/bge-reranker-v2-m3")
    monkeypatch.setattr(quota_utils, "rerank_model_list", lambda: ["BAAI/bge-reranker-v2-m3"])
    monkeypatch.setattr(quota_utils, "utility_quota_ok", lambda model, hard: True)
    monkeypatch.setattr(quota_utils, "_depleted_mem", set())
    monkeypatch.setattr(quota_utils, "deduct_utility", lambda model, tokens: None)

    captured = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.5},
                    {"index": 1, "relevance_score": 0.1},
                ]
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["auth"] = (headers or {}).get("Authorization", "")
        captured["model"] = (json or {}).get("model")
        return _Resp()

    monkeypatch.setattr(retrieval.httpx, "post", fake_post)
    retrieval._rerank_client = None
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: object())

    docs = [Document(page_content="甲"), Document(page_content="乙"), Document(page_content="丙")]
    out = retrieval._rerank_docs("试用期上限", docs)

    assert [d.page_content for d in out] == ["丙", "甲", "乙"]
    assert captured["url"] == "https://api.siliconflow.cn/v1/rerank"
    assert captured["auth"] == "Bearer test-sf-key"
    assert captured["model"] == "BAAI/bge-reranker-v2-m3"


def test_siliconflow_failure_marks_depleted_and_returns_none(monkeypatch):
    monkeypatch.setattr(_s.settings, "rerank_enabled", True)
    monkeypatch.setattr(_s.settings, "rerank_api_key", "")
    monkeypatch.setattr(_s.settings, "siliconflow_api_key", "test-sf-key")
    monkeypatch.setattr(_s.settings, "rerank_base_url", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(_s.settings, "rerank_models", "BAAI/bge-reranker-v2-m3")
    monkeypatch.setattr(quota_utils, "rerank_model_list", lambda: ["BAAI/bge-reranker-v2-m3"])
    monkeypatch.setattr(quota_utils, "utility_quota_ok", lambda model, hard: True)
    depleted = set()
    monkeypatch.setattr(quota_utils, "_depleted_mem", depleted)
    marked = []
    monkeypatch.setattr(quota_utils, "mark_utility_depleted", lambda model: marked.append(model))

    def fake_post(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(retrieval.httpx, "post", fake_post)
    retrieval._rerank_client = None
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: object())

    docs = [Document(page_content="甲")]
    assert retrieval._rerank_docs("q", docs) is None
    assert marked == ["BAAI/bge-reranker-v2-m3"]


def test_gate_accepts_siliconflow_only_key_without_monkeypatched_client(monkeypatch):
    """只配 SILICONFLOW_API_KEY（rerank_api_key 空）时门禁必须放行——
    回归：原门禁只查 rerank_api_key，导致 provider key 被静默跳过。"""
    monkeypatch.setattr(_s.settings, "rerank_enabled", True)
    monkeypatch.setattr(_s.settings, "rerank_api_key", "")
    monkeypatch.setattr(_s.settings, "siliconflow_api_key", "test-sf-key")
    retrieval._rerank_client = None
    try:
        client = retrieval._get_rerank_client()
        assert client is not None  # 门禁放行（真实 OpenAI 对象构建不发起网络请求）
        assert client.api_key == "test-sf-key"
    finally:
        retrieval._rerank_client = None


def test_gate_returns_none_when_no_key_at_all(monkeypatch):
    monkeypatch.setattr(_s.settings, "rerank_enabled", True)
    monkeypatch.setattr(_s.settings, "rerank_api_key", "")
    monkeypatch.setattr(_s.settings, "siliconflow_api_key", "")
    retrieval._rerank_client = None
    try:
        assert retrieval._get_rerank_client() is None
    finally:
        retrieval._rerank_client = None


# ---------------- 瞬时故障 vs 真实失败（2026-09-14，报告 §2c） ----------------
# 动机：该模型免费但**会限速**；原实现把 429/5xx/连接抖动一律当"模型坏了"永久标记，
# 实测一次偶发失败导致同进程内后续 35 次全部静默降级。以下四条钉住新的边界。
def _enable_siliconflow(monkeypatch) -> list[str]:
    """复用本文件既有 harness，返回 mark_utility_depleted 的调用记录。"""
    monkeypatch.setattr(_s.settings, "rerank_enabled", True)
    monkeypatch.setattr(_s.settings, "rerank_api_key", "")
    monkeypatch.setattr(_s.settings, "siliconflow_api_key", "test-sf-key")
    monkeypatch.setattr(_s.settings, "rerank_base_url", "https://api.siliconflow.cn/v1")
    monkeypatch.setattr(_s.settings, "rerank_models", "BAAI/bge-reranker-v2-m3")
    monkeypatch.setattr(quota_utils, "rerank_model_list", lambda: ["BAAI/bge-reranker-v2-m3"])
    monkeypatch.setattr(quota_utils, "utility_quota_ok", lambda model, hard: True)
    monkeypatch.setattr(quota_utils, "_depleted_mem", set())
    monkeypatch.setattr(quota_utils, "deduct_utility", lambda model, tokens: None)
    marked: list[str] = []
    monkeypatch.setattr(quota_utils, "mark_utility_depleted", lambda model: marked.append(model))
    retrieval._rerank_client = None
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: object())
    return marked


def _status_error(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://api.siliconflow.cn/v1/rerank")
    resp = httpx.Response(status, request=req, text=f"status {status}")
    return httpx.HTTPStatusError(f"{status}", request=req, response=resp)


def _resp_raising(status: int):
    class _Resp:
        status_code = status

        def raise_for_status(self):
            raise _status_error(status)

        def json(self):  # pragma: no cover - 不会走到
            return {}

    return _Resp()


def test_rate_limit_429_degrades_without_marking_depleted(monkeypatch):
    """限速 429 → 本次降级（None），但**不得**把模型标记为永久耗尽（否则下次不再尝试）。"""
    marked = _enable_siliconflow(monkeypatch)
    monkeypatch.setattr(retrieval.httpx, "post", lambda *a, **k: _resp_raising(429))

    assert retrieval._rerank_docs("q", [Document(page_content="甲")]) is None
    assert marked == [], "429 属瞬时故障，不应标记模型耗尽"


def test_server_error_503_degrades_without_marking_depleted(monkeypatch):
    marked = _enable_siliconflow(monkeypatch)
    monkeypatch.setattr(retrieval.httpx, "post", lambda *a, **k: _resp_raising(503))

    assert retrieval._rerank_docs("q", [Document(page_content="甲")]) is None
    assert marked == [], "5xx 属服务端临时不可用，不应标记模型耗尽"


def test_connection_error_degrades_without_marking_depleted(monkeypatch):
    marked = _enable_siliconflow(monkeypatch)

    def _boom(*args, **kwargs):
        raise httpx.ConnectError("conn refused", request=httpx.Request("POST", "https://x/rerank"))

    monkeypatch.setattr(retrieval.httpx, "post", _boom)

    assert retrieval._rerank_docs("q", [Document(page_content="甲")]) is None
    assert marked == [], "连接抖动属瞬时故障，不应标记模型耗尽"


def test_client_error_400_still_marks_depleted(monkeypatch):
    """反例（防过度放宽）：4xx 中的"请求/模型名/鉴权错"是真实失败，必须仍按永久处理。"""
    marked = _enable_siliconflow(monkeypatch)
    monkeypatch.setattr(retrieval.httpx, "post", lambda *a, **k: _resp_raising(400))

    assert retrieval._rerank_docs("q", [Document(page_content="甲")]) is None
    assert marked == ["BAAI/bge-reranker-v2-m3"], "400 属真实失败，应标记模型耗尽"


def test_transient_probe_covers_openai_compat_status_errors(monkeypatch):
    """第三分支走 OpenAI 兼容客户端，抛的是 `openai.APIStatusError`（**不是** httpx 类型）。

    若无这条覆盖，该路径上的 429/5xx 会被判成"真实失败"→ 永久标记（即 1k 缺陷在这条路上复活）。
    期望独立来源：openai SDK 的 `APIStatusError.status_code` 属性（其异常契约），非我复算实现。
    """
    from openai import APIStatusError

    req = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-api/v1/reranks")
    exc429 = APIStatusError("rate limited", response=httpx.Response(429, request=req), body=None)
    exc400 = APIStatusError("bad model", response=httpx.Response(400, request=req), body=None)

    # 前提断言：openai 异常确实带 status_code（若 SDK 契约变了，这条会先红）
    assert getattr(exc429, "status_code", None) == 429
    assert retrieval._is_transient_rerank_error(exc429) is True
    assert retrieval._is_transient_rerank_error(exc400) is False


def test_openai_compat_429_degrades_without_marking_depleted(monkeypatch):
    """端到端（第三分支）：OpenAI 兼容客户端抛 429 → 不标记；抛 400 → 标记。"""
    from openai import APIStatusError

    req = httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-api/v1/reranks")

    def _client_raising(status: int):
        class _Client:
            def post(self, path, **kw):
                raise APIStatusError("x", response=httpx.Response(status, request=req), body=None)

        return _Client()

    # 429：模型名不在 SiliconFlow/原生两份名单里 → 走 client.post 分支
    marked = _enable_siliconflow(monkeypatch)
    monkeypatch.setattr(_s.settings, "rerank_models", "qwen3-rerank")
    monkeypatch.setattr(quota_utils, "rerank_model_list", lambda: ["qwen3-rerank"])
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: _client_raising(429))
    assert retrieval._rerank_docs("q", [Document(page_content="甲")]) is None
    assert marked == [], "OpenAI 兼容路径的 429 也属瞬时故障，不应标记"

    # 400：同路径的真实失败 → 必须标记
    marked2 = _enable_siliconflow(monkeypatch)
    monkeypatch.setattr(_s.settings, "rerank_models", "qwen3-rerank")
    monkeypatch.setattr(quota_utils, "rerank_model_list", lambda: ["qwen3-rerank"])
    monkeypatch.setattr(retrieval, "_get_rerank_client", lambda: _client_raising(400))
    assert retrieval._rerank_docs("q", [Document(page_content="甲")]) is None
    assert marked2 == ["qwen3-rerank"], "同路径的 400 仍属真实失败"
