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
# 2026-10-13 修：文件名带 PID 的旧库会被**复用的 PID** 捡起来——10-13 全量跑出现 9 条
# `test_reset_admin_password` 红（`UNIQUE constraint failed: users.username`），根因就是
# 种子用户撞上陈旧库；当时 %TEMP% 里已积了 323 个同名文件（最早 10-09）。开跑前先删掉同名残留。
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
# 向量库目录同样隔离（T-E，2026-09-18；与上面两条同款**无条件**赋值，理由同款）：
#   真实 backend/chroma_db 被 docker-compose.yml:47 bind mount 进容器，而 chroma 并发不安全
#   （compose:11 就为此只跑单 worker）⇒「本地 pytest 写真实索引」同时是污染面与撞锁面：
#   test_phase5 的两个测试会往真实集合 add/delete，并行会话的全量跑也曾观测到同窗写入。
#   2026-09-17 之前这里只留了「有意未隔离」的说明，因为路径硬编码在 rag_chain.py:120 与
#   knowledge_service.py:38、没有出口；出口常量落地后本行才可能生效。
_TEST_CHROMA = os.path.join(tempfile.gettempdir(), f"fazhi_test_chroma_{os.getpid()}")
os.environ["CHROMA_DIR"] = _TEST_CHROMA


def _prepare_test_chroma() -> None:
    """预建主集合为 **cosine**，保持与生产同一条分数口径分支。

    rag_chain 的 Chroma(...) 在 **import 期** 建集合，而 langchain_chroma 把
    collection_metadata=None 原样传给 get_or_create_collection ⇒ 空目录里新建的集合是
    chromadb 0.4.24 默认的 **l2**；真实 legal_provisions_cos 是 cosine。若不预建，
    retrieval._collection_is_cosine() 会在测试 lane 读到 False，整轮跑在生产**不走**的
    那条分支上（静默失真，比写错库更坏）。qa_pairs 故意不预建：真实库它就是 {}→l2。
    集合名与 rag_chain._COLLECTION_LOCAL 是两处字面量，由
    test_chroma_isolation.py::test_default_lane_keeps_cosine_fidelity 钉住——名字一旦分叉
    该测试直接红，不会退化成"跑在错分支上还以为过了"。

    Settings 必须**逐字复刻** langchain_chroma/vectorstores.py:305-307 的构造
    （`Settings(is_persistent=True)` 再赋 persist_directory）：chromadb 0.4.24 按
    `persist_directory` 缓存 SharedSystemClient，同一路径第二次以不同 settings 打开会直接
    `ValueError: An instance of Chroma already exists for ... with different settings`
    （⇒ 整个测试收集期炸掉）。所以这里不能"顺手关掉遥测"，只能与生产同一份 settings。
    """
    import chromadb  # noqa: PLC0415

    settings = chromadb.config.Settings(is_persistent=True)
    settings.persist_directory = _TEST_CHROMA
    client = chromadb.Client(settings)
    client.get_or_create_collection(name="legal_provisions_cos", metadata={"hnsw:space": "cosine"})


_prepare_test_chroma()

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


@pytest.fixture
def real_kb(monkeypatch):
    """**显式 opt-in** 真实语料（T-E，2026-09-18）：把 retrieval 的库引用指回真实 chroma_db。

    默认层已把 CHROMA_DIR 隔离到进程私有临时库，所以「判据必须来自真实知识库」的用例
    只能靠把本 fixture 写进签名才拿得到真实内容——谁依赖真实语料，从此可读、可数。

    构造与 rag_chain.py:119-123 逐字相同（同 collection 名、同嵌入函数），只差
    persist_directory：这样这些用例走的仍是生产那条分支（cosine 口径 + 真实 1024 维向量），
    而不是假向量的近似物。BGE 在 rag_chain import 期就已加载，这里不额外付模型成本。
    只读约定：用例只做检索/按元数据 get，不 add/delete ⇒ 不写真实库。

    两个缓存必须处理，否则跨库串味：
    - BM25 与源名集（`_ensure_bm25`/`_ensure_src_set` 是全量扫描后的模块级缓存）——
      前序测试可能已用**空临时库**建好，会让真实语料检索返回 0 条；用 `invalidate()` 丢弃，
      teardown 再来一次，免得**真实库口径**的缓存反向泄漏回默认 lane；
    - `_COLLECTION_IS_COSINE`：`invalidate()` 明确**不清**它（retrieval.py:596-606 vs :628-640），
      必须自己置 None（置回 None 后按当前库惰性重算，成本是一次 metadata 读）。

    真实语料缺失时 skip 而不是硬跑：`backend/chroma_db/` 被 .gitignore:31 忽略、只存在于本机，
    空库上「查不到」会让否定式断言恒过——那是假绿，比红更坏。

    覆盖面边界（诚实标注）：本 fixture 只重绑 `retrieval.vectorstore`。生产里另有
    `knowledge_base.py:11` / `knowledge_service.py:24` / `main.py:106` 各自持有一份同名引用
    （模块级 `from rag_chain import vectorstore` 拷贝），走那三条路径的用例**不受**本 fixture 影响。
    已核：`domain_rules` 的 `_lookup_all` 经 `from retrieval import exact_article_lookup`
    （domain_rules.py:18-25）间接走 retrieval ⇒ 在其覆盖内。新增持副本的模块时，要么改走
    retrieval，要么把该模块一并加进本 fixture。
    """
    from langchain_chroma import Chroma  # noqa: PLC0415

    import rag_chain
    import retrieval

    vs = Chroma(
        persist_directory=rag_chain.DEFAULT_CHROMA_DIR,
        embedding_function=rag_chain.embeddings,
        collection_name=rag_chain.COLLECTION_NAME,
    )
    n = vs._collection.count()
    if n < 1000:
        pytest.skip(f"真实语料不可用（{rag_chain.DEFAULT_CHROMA_DIR} 主库仅 {n} 条）——不得在空库上假绿")
    retrieval.invalidate()
    monkeypatch.setattr(retrieval, "vectorstore", vs)
    monkeypatch.setattr(retrieval, "_COLLECTION_IS_COSINE", None)
    try:
        yield vs
    finally:
        retrieval.invalidate()
