import os
import sys

# 在导入任何 backend 模块之前固定测试环境变量（pytest 收集期即生效）：
# - JWT_SECRET：auth 测试用固定 test secret，不依赖 .env（CI 无 secrets 也能跑）
# - LLM 配置：main 启动强校验要求非空；真实 LLM 调用已被 FakeChain / monkeypatch 取代
# setdefault 不覆盖已存在的值——本地跑测试时仍可用 .env 的真实配置。
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-ci-only")
os.environ.setdefault("LLM_API_KEY", "test-key-not-for-real-calls")
os.environ.setdefault("LLM_BASE_URL", "https://test.invalid/v1")
# 测试固定本地嵌入 + 关闭 rerank——防 CI 联网（云端 embedding/rerank 需真实 key）
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("RERANK_ENABLED", "false")
# 配额总金额度固定 0（未启用）——防本地跑 pytest 时包装对象把扣减写进真实 quota_used.sqlite
os.environ.setdefault("EMBEDDING_QUOTA_TOTAL", "0")
os.environ.setdefault("RERANK_QUOTA_TOTAL", "0")

# 让 tests 能 import backend 顶层模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch):
    """禁限流（测试基建）：模块级 slowapi Limiter 跨测试共享计数，全量跑时
    login/upload 累计超 10/min → 偶发 429（flaky，2026-08-06 test_phase5 暴露）。
    测试不测限流行为，禁用后契约测试稳定。"""
    import main  # noqa: PLC0415

    monkeypatch.setattr(main.limiter, "enabled", False)
