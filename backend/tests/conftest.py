import os
import sys
import tempfile

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
# 配额库本身也要隔离（2026-09-17）：上面把总额设为 0 只挡住「扣减」，
# 但 quota_store._connect() 的 `PRAGMA journal_mode=WAL` 与 _ensure() 的
# `CREATE TABLE ... commit()` 本身就是写——只要有任何一次配额读写，就会改真实
# backend/data/quota_used.sqlite（且留下 -wal/-shm）。故此处**无条件**指向进程私有临时库
# （不用 setdefault：开发者 shell 里残留的 QUOTA_DB 会把测试重新指回生产库）。
os.environ["QUOTA_DB"] = os.path.join(tempfile.gettempdir(), f"fazhi_test_quota_{os.getpid()}.sqlite")
# 数据库本体同样隔离（2026-09-17；与上面同样的理由——**无条件**赋值）：
#   database.py:9 在未设 DATABASE_URL 时回落到真实 backend/app.db，而 main.py:158 在
#   **import 期**就调 init_db()（跑迁移）⇒ 「collection 期连接真实库」这条通道一直存在；
#   且将来某次迁移真需加列时，它会**写生产库**。
# 隔离写法与本仓既有离线配置一致（docs/project-quality-guide-20260914.md:302 明确要求
# 隔离 DATABASE_URL/QUOTA_DB/COVERAGE_FILE）；此处只是把它落到 conftest 这个共享点上，
# 避免"每个新 store 都要有人记得单独隔离"这类反复出现的漏配。
_TEST_DB = os.path.join(tempfile.gettempdir(), f"fazhi_test_app_{os.getpid()}.db").replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
#
# ⚠️ 已知且**有意未隔离**的一项副作用（2026-09-17 取证留痕，避免下次重复排查）：
#   `backend/chroma_db/` 仍是**真实**向量库，因为路径在 rag_chain.py:112 与
#   knowledge_service.py:38 **硬编码、无环境变量出口**；而 test_citation.py 的
#   `test_verify_against_real_kb` / `test_classify_answer_defaults_real_kb` **有意**
#   在快测集里使用真实语料（**未打 `@pytest.mark.slow`**）⇒ 全局重定向会直接打挂它们。
#   后果：tests/test_phase5.py 的两个测试会把测试法条 add 进真实 KB 并在 finally 里删。
#   自清理**一直有效**（只读探测 4 个集合，无任何测试残留），代价是索引文件只增不减
#   （约 +16KB/轮）；残余风险仅为「add 与 delete 之间进程崩溃 → 测试法条永久留在生产 KB」。
#   根治需给 rag_chain/knowledge_service 加 `CHROMA_DIR` 出口 + 让有意者显式 opt-in
#   ⇒ 属设计变更（动生产 RAG 主路径 + Docker 卷语义），留独立票据。
#   归因与全部证据：dispatch-output/pytest-full-20260917/db-write-attribution-report.md
# 集成测试会创建普通用户；显式开启注册，避免依赖被忽略的本地 .env。
os.environ.setdefault("FEATURE_SELF_REGISTER", "true")

# 让 tests 能 import backend 顶层模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch):
    """禁限流（测试基建）：模块级 slowapi Limiter 跨测试共享计数，全量跑时
    login/upload 累计超 10/min → 偶发 429（flaky，2026-08-06 test_phase5 暴露）。
    测试不测限流行为，禁用后契约测试稳定。"""
    import main  # noqa: PLC0415

    monkeypatch.setattr(main.limiter, "enabled", False)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh migrated SQLite database for persistence boundary tests."""
    import database
    import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'agent-repository.db'}")
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(migrations, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)

    migrations.run_migrations()
    migrations.run_migrations()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
