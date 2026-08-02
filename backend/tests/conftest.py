import os
import sys

# 在导入任何 backend 模块之前固定测试环境变量（pytest 收集期即生效）：
# - JWT_SECRET：auth 测试用固定 test secret，不依赖 .env（CI 无 secrets 也能跑）
# - LLM 配置：main 启动强校验要求非空；真实 LLM 调用已被 FakeChain / monkeypatch 取代
# setdefault 不覆盖已存在的值——本地跑测试时仍可用 .env 的真实配置。
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-ci-only")
os.environ.setdefault("LLM_API_KEY", "test-key-not-for-real-calls")
os.environ.setdefault("LLM_BASE_URL", "https://test.invalid/v1")

# 让 tests 能 import backend 顶层模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
