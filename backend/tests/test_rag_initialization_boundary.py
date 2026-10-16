"""W01 / D-52 边界测试：import 期不得构造真实模型，也不得创建生产默认持久目录。

两条 lane 分开报，不许用一条顶另一条（执行书 W01）：

* lane A（纯逻辑 + 冷缓存子进程）——不需要模型权重，CI 无缓存也能跑；
  它钉的是"import 不加载模型、不建库目录、首次使用只构造一次、失败不缓存、并发不给半成品"。
* lane B（真实模型）——需要受信缓存，默认 **skip**，只有显式 `FAZHI_REAL_EMBEDDING_LANE=1`
  才跑；跳过时必须写清"未跑"，不得拿 lane A 的绿当 lane B 的绿。

为什么冷缓存那条走子进程：import 期语义只有一次的"第一次 import"，在本进程里
`importlib.reload` 会把真实 `backend/chroma_db` 打开（本地它就是生产库）。所以这里
把 backend 源码复制进 tmp_path，让 `DEFAULT_CHROMA_DIR` 落在临时目录里——这样
"没被创建"才是可证的，而不是因为本来就存在。
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

SENTINEL = "IMPORT_OK"

# 复制 backend 源码时排除的东西：真实索引/真实库/虚拟环境/缓存产物。
# 复制这些进 tmp 等于把生产语料搬到测试里，且会把测试时长拖到分钟级。
_COPY_IGNORE = shutil.ignore_patterns(
    "chroma_db",
    "data",
    "venv",
    "venv-new",
    ".venv",
    "__pycache__",
    "media",
    "backups",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    ".ptmp-*",
    # .env 必须在排除面内：本仓有人把真实配置放在 backend/.env，而这条腿会把整棵 backend
    # 复制进 %TEMP%。不排除就等于把凭据搬到仓库外的一份副本里（独立复核 B 路 m12 指出）。
    ".env",
    ".env.*",
    "*.env",
    ".coverage",
    ".mypy_cache",
    ".pytest_cache",
)


def _private_cache_env(target: Path, *, keep_chroma_dir: bool = False) -> dict[str, str]:
    """构造一个"冷缓存 + 私有 store"的子进程环境。

    只给假值：这些键的存在性由 settings/main 的校验决定，值本身不参与任何真实认证。
    不读 .env，也不继承任何指向真实供应商的凭据。
    """
    env = dict(os.environ)
    hf = target / "hfcache"
    for key in (
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
        "TORCH_HOME",
        "XDG_CACHE_HOME",
    ):
        env[key] = str(hf / key.lower())
    store = target / "store"
    if not keep_chroma_dir:
        env["CHROMA_DIR"] = str(store / "chroma")
    else:
        env.pop("CHROMA_DIR", None)
    env["DATABASE_URL"] = f"sqlite:///{(store / 'app.db').as_posix()}"
    env["QUOTA_DB"] = str(store / "quota.sqlite")
    env["JWT_SECRET"] = "test-jwt-secret-for-ci-only"
    env["LLM_API_KEY"] = "test-key-not-for-real-calls"
    env["LLM_BASE_URL"] = "https://test.invalid/v1"
    env["EMBEDDING_PROVIDER"] = "local"
    env["RERANK_ENABLED"] = "false"
    env["EMBEDDING_QUOTA_TOTAL"] = "0"
    env["RERANK_QUOTA_TOTAL"] = "0"
    # 故意不设 PYTHONPATH：子进程靠 cwd（python -c 的 sys.path[0]）解析模块，
    # 于是"读的是哪一棵树"由下面那条 __file__ 断言钉死；设了 PYTHONPATH 反而给
    # 跨树回落留门，会把"隔离树里缺某文件"这种真实缺陷吞成绿。
    env.pop("PYTHONPATH", None)
    return env


def _run_import(backend_dir: Path, env: dict[str, str], module: str) -> subprocess.CompletedProcess:
    code = f"import {module} as m; print('MODULE_FILE=' + m.__file__); print('{SENTINEL}')"
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(backend_dir),
        env=env,
        timeout=600,
    )


@pytest.fixture(scope="module")
def isolated_backend(tmp_path_factory) -> Path:
    """把 backend 源码摊到 tmp，DEFAULT_CHROMA_DIR 随之落进 tmp——"未创建"才可证。"""
    dest = tmp_path_factory.mktemp("isolated_backend")
    shutil.copytree(BACKEND, dest / "backend", ignore=_COPY_IGNORE, symlinks=False)
    copied = dest / "backend"
    assert (copied / "rag_chain.py").is_file(), "复制后的树里必须真的有 rag_chain.py，否则这条腿是空跑的"
    return copied


def _assert_measured_this_tree(proc: subprocess.CompletedProcess, backend_dir: Path) -> None:
    """读数必须能归因到隔离树：import 到的文件真在 tmp 里，而不是旁边那棵。"""
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("MODULE_FILE=")]
    assert lines, f"子进程没报模块出处，无法归因：stdout={proc.stdout[:400]} stderr={proc.stderr[-800:]}"
    resolved = Path(lines[0].split("=", 1)[1]).resolve()
    assert resolved.is_relative_to(backend_dir.resolve()), (
        f"子进程 import 的是 {resolved}，不在隔离树 {backend_dir} 内 ⇒ 这条腿的读数不算"
    )


def _count_files(root: Path) -> int:
    return sum(1 for _ in root.rglob("*") if _.is_file()) if root.exists() else 0


# ---------------------------------------------------------------------------
# lane A-1：冷缓存 import —— 这是 D-52 在 CI 上的真实形状
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", ["rag_chain", "retrieval", "knowledge_service"])
def test_cold_cache_import_loads_no_model(isolated_backend, tmp_path, module):
    """无模型缓存 + 产品默认的 HF_HUB_OFFLINE=1 下，import 必须成功。

    修前：`rag_chain.py:108` 在 import 期构造 HuggingFaceEmbeddings ⇒ 无缓存时
    OSError（sentence_transformers/transformers 走到 cached_files）；CI 因此 39 个
    收集期错误、0 条用例跑过。修后：import 只绑定惰性对象。
    私有缓存目录在 import 后仍为 0 只文件 ⇒ 顺带证伪"它其实在下载"。
    """
    env = _private_cache_env(tmp_path)
    hf_root = Path(env["HF_HOME"])
    assert _count_files(hf_root) == 0, "前置：私有缓存起点必须是空的"

    proc = _run_import(isolated_backend, env, module)

    assert proc.returncode == 0, (
        f"import {module} 在无模型缓存时应成功；实际 rc={proc.returncode}\nstderr 尾部：\n{proc.stderr[-2000:]}"
    )
    assert SENTINEL in proc.stdout, f"子进程没打出哨兵，说明它根本没跑到断言：{proc.stdout[:400]}"
    _assert_measured_this_tree(proc, isolated_backend)
    assert _count_files(hf_root) == 0, "冷缓存 import 不该往缓存里写任何东西（不下载）"


def test_import_creates_no_default_store_dir(isolated_backend, tmp_path):
    """不覆盖 CHROMA_DIR 时，import 也不得创建生产默认持久目录。

    修前（ARM E 实测）：温缓存下 `import rag_chain` 会建出 backend/chroma_db/（+1 只文件），
    且 `CHROMA_DIR == DEFAULT_CHROMA_DIR`。修后：目录只在第一次真正用库时才出现。
    """
    default_dir = isolated_backend / "chroma_db"
    env = _private_cache_env(tmp_path, keep_chroma_dir=True)
    assert not default_dir.exists(), "前置：隔离树里默认目录本不该存在"

    proc = _run_import(isolated_backend, env, "rag_chain")

    assert proc.returncode == 0, f"import 失败：rc={proc.returncode}\n{proc.stderr[-2000:]}"
    assert SENTINEL in proc.stdout
    _assert_measured_this_tree(proc, isolated_backend)
    assert not default_dir.exists(), (
        "import 期就创建了生产默认持久目录 "
        f"{default_dir}（现有 {_count_files(default_dir)} 只文件）——惰性接缝没盖住 store"
    )


# ---------------------------------------------------------------------------
# lane A-2：首次使用 / 并发 / 失败（可观测替身，纯逻辑，不碰权重）
# ---------------------------------------------------------------------------


def test_store_lazy_exit_defers_construction_until_first_use():
    """惰性出口的可数判据：没用之前计数为 0，用了之后恒为 1。

    这里故意不读 rag_chain.vectorstore 的私有状态——那个全局早已被同批其它用例解析过，
    拿它当判据只会得到"看运气的绿"。判据挂在**我注入的计数工厂**上。
    """
    import rag_chain

    built: list[int] = []
    sentinel = object()

    def make():
        built.append(1)
        return sentinel

    lazy = rag_chain.lazy_store(make)
    assert built == [], "构造工厂在还没被用之前就跑了 ⇒ 惰性不成立"

    assert lazy._resolve() is sentinel
    assert lazy._resolve() is sentinel
    assert len(built) == 1, f"首次使用应只构造一次，实际构造 {len(built)} 次"


def test_concurrent_first_use_never_exposes_half_constructed_object():
    """并发只构造一次，且任何线程拿到的都是同一个成品（不是半成品）。"""
    import rag_chain

    builds: list[object] = []
    lock = threading.Lock()

    def factory():
        with lock:
            # 放大竞态窗口：构造慢的时候，没写好的对象最容易被抢出去
            import time

            time.sleep(0.05)
            obj = object()
            builds.append(obj)
            return obj

    lazy = rag_chain.lazy_store(factory)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: lazy._resolve(), range(8)))

    assert len(builds) == 1, f"8 路并发首次使用构造了 {len(builds)} 次"
    assert all(r is results[0] for r in results), "不同线程拿到不同对象 ⇒ 单例语义破防"
    assert all(r is not None for r in results)


def test_load_failure_is_not_permanently_cached(monkeypatch):
    """坏对象不永久占位：窗口设为 0 时，下一次调用必须真去重试并成功。"""
    import rag_chain

    monkeypatch.setattr(rag_chain, "_INIT_RETRY_WINDOW_SECONDS", 0.0)
    attempts: list[int] = []
    product_marker = object()

    def flaky_factory():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("simulated cold-cache failure")
        return product_marker

    lazy = rag_chain.lazy_store(flaky_factory)
    with pytest.raises(RuntimeError, match="simulated cold-cache failure"):
        lazy._resolve()
    assert len(attempts) == 1

    first_ok = lazy._resolve()
    assert first_ok is product_marker, "失败被缓存住了 ⇒ 坏对象永久占位"
    assert len(attempts) == 2
    assert lazy._resolve() is product_marker
    assert len(attempts) == 2, "成功后还在重复构造 ⇒ 没记住成品"


def test_failure_retry_is_bounded_and_logged(monkeypatch, caplog):
    """窗口内不重复打工厂/网络，且失败必须留一条 error 日志（不能静默成"查不到结果"）。

    这条是独立复核 B 路 M2/M4 的直接后果：惰性化把"启动就炸"变成了"运行时抛给上游吞掉"，
    所以既要有界重试，也要有痕。
    """
    import logging

    import rag_chain

    monkeypatch.setattr(rag_chain, "_INIT_RETRY_WINDOW_SECONDS", 60.0)
    attempts: list[int] = []

    def always_fails():
        attempts.append(1)
        raise RuntimeError("cold cache and offline")

    lazy = rag_chain.lazy_store(always_fails, name="嵌入模型")
    with caplog.at_level(logging.ERROR, logger="rag_chain"):
        for _ in range(5):
            with pytest.raises(RuntimeError, match="cold cache and offline"):
                lazy._resolve()

    assert len(attempts) == 1, (
        f"窗口内仍重复调用工厂 {len(attempts)} 次 ⇒ 无界重试，一次故障会被放大成每次 embed 都重连"
    )
    logged = [r for r in caplog.records if "初始化失败" in r.getMessage()]
    assert logged, f"失败没有留痕，日志只有：{[r.getMessage() for r in caplog.records]}"

    # 窗口过去之后允许再试一次（不是永久放弃）
    lazy._failed_at -= 120.0
    with pytest.raises(RuntimeError, match="cold cache and offline"):
        lazy._resolve()
    assert len(attempts) == 2


def test_embeddings_wrapper_defers_inner_and_deducts_once():
    """QuotaTrackingEmbeddings 收的是工厂：不 embed 就不构造内层；构造只一次。"""
    import rag_chain

    built: list[int] = []

    class FakeInner:
        def __init__(self):
            built.append(1)

        def embed_query(self, text):
            return [0.0, 1.0]

        def embed_documents(self, texts):
            return [[0.0, 1.0] for _ in texts]

    wrapped = rag_chain.QuotaTrackingEmbeddings(lambda: FakeInner())
    assert built == [], "内层在构造包装对象时就被建出来了 ⇒ import 期同款的错还在"

    vector = wrapped.embed_query("测试")
    assert vector == [0.0, 1.0]
    assert len(built) == 1

    wrapped.embed_documents(["甲", "乙"])
    assert len(built) == 1, f"后续 embed 又构造了内层（累计 {len(built)} 次）"

    def broken():
        raise RuntimeError("cold failure")

    with pytest.raises(RuntimeError, match="cold failure"):
        rag_chain.QuotaTrackingEmbeddings(broken).embed_query("任意")


# ---------------------------------------------------------------------------
# prewarm：惰性化把付账位置挪走了，就必须有人把它接回启动期
# ---------------------------------------------------------------------------


def test_prewarm_resolves_the_embedding_resource(monkeypatch):
    """D-52 把模型加载从 import 期挪走，本条钉"是 prewarm 接住了它"，不是挪给了第一个真问题。

    判据不钉秒数（CI 冷缓存 vs 本机暖缓存差一个量级，钉数就是钉机器），钉的是**调用结构**：
    prewarm 必须真去解析 `retrieval.embeddings` 那个惰性壳。把三个冷启动步骤都换成记录器，
    零 I/O、零权重，CI 也能跑；删掉 `retrieval.py:560` 那行 → 顺序里少一项 → 这条当场红。

    顺序也钉住（嵌入最先）：它是三者里唯一"解析一次就永久受益、且贵到能吃掉整个工具超时"的
    一步，放在检索侧两步之前，才不会因为后面某步先抛而把它跳过。
    """
    import rag_chain
    import retrieval

    order: list[str] = []
    probe = rag_chain._LazyResource("prewarm 探针", lambda: order.append("embeddings") or object())
    monkeypatch.setattr(retrieval, "embeddings", probe)
    monkeypatch.setattr(retrieval, "_ensure_bm25", lambda: order.append("bm25"))
    monkeypatch.setattr(retrieval, "_ensure_src_set", lambda: order.append("src_set"))

    retrieval.prewarm()

    assert order == ["embeddings", "bm25", "src_set"], (
        f"prewarm 覆盖的冷启动步骤/顺序不符：{order}——"
        "嵌入没被解析就意味着模型加载由第一个真实用户的问题付（本机实测 45.76s，"
        "而 tools/gateway.py 给检索工具的外层等待只有 15.0s）"
    )


def test_prewarm_failure_does_not_refuse_startup(monkeypatch, caplog):
    """预热失败必须"降级 + 留痕"，不能把应用拒在启动外——这条性质此前**没有具名用例**。

    现状是隐式覆盖：`with TestClient(main.app)` 的 17 处用例（10 只文件）在冷形状下真的会让
    `prewarm` 抛错，全绿只是因为 `main.py:259` 的 `except Exception` 把它吞成一条 warning。
    ⇒ "有人把 try 删掉"会红一大片，而"有人把 warning 删掉"谁都发现不了。

    实现取 lifespan 的**函数节点单独 exec**（照 `test_llm_lifecycle.py` 的同款做法），
    而不是 import main——`main.py:158` 在 import 期就 `init_db()`，把它整个请进来等于在测试里
    跑迁移，那条通道一直在（见本文件顶部注释）。同时断言三件事：真走到了 yield、留了痕、异常没逃出来。
    """
    import ast
    import asyncio
    import contextlib
    import logging
    from types import SimpleNamespace

    src = (BACKEND / "main.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan")

    async def _aclose():
        return None

    entered = []

    def boom():
        raise OSError("simulated: 冷缓存机上嵌入模型加载失败")

    ns = {
        "asynccontextmanager": contextlib.asynccontextmanager,
        "setup_logging": lambda level: None,
        "settings": SimpleNamespace(log_level="INFO"),
        "run_in_threadpool": lambda fn: fn(),
        "prewarm": boom,  # 故意让它抛：被测的是 lifespan 的降级处理，不是 prewarm 自己
        "registry": SimpleNamespace(aclose=_aclose),
        "logging": logging,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(BACKEND / "main.py"), "exec"), ns)

    async def _drive():
        async with ns["lifespan"](SimpleNamespace()):
            entered.append("yielded")

    with caplog.at_level(logging.WARNING):
        try:
            asyncio.run(_drive())
        except Exception as exc:
            raise AssertionError(f"预热失败把启动打挂了（except 没兜住或已被删）：{exc!r}") from exc

    assert entered == ["yielded"], "lifespan 没走到 yield ⇒ 预热失败等于拒绝启动"
    assert any("[prewarm]" in r.getMessage() for r in caplog.records), "降级没留痕＝静默改路径"


# ---------------------------------------------------------------------------
# lane B：真实模型（默认不跑；跳过不等于通过）
# ---------------------------------------------------------------------------

_REAL_LANE = os.environ.get("FAZHI_REAL_EMBEDDING_LANE") == "1"


@pytest.mark.slow
@pytest.mark.skipif(
    not _REAL_LANE,
    reason=("真实嵌入 lane 未启用（需受信私有缓存）。跳过时按执行书要求写『未跑』，不得用 lane A 的替身绿顶替。"),
)
def test_real_embeddings_construct_once_and_separate_related_from_unrelated():
    """真权重：只构造一次 + 相关/无关文本的向量确实有差别（不是只断维度）。"""
    import numpy as np

    import rag_chain

    first = rag_chain.get_embeddings()
    again = rag_chain.get_embeddings()
    assert first is again, "显式出口每次返回同一个嵌入对象"

    related = first.embed_documents(
        [
            "甲方未按约定交付房屋，乙方能否解除合同并要求赔偿",
            "商品房买卖中出卖人逾期交房的违约责任",
        ]
    )
    unrelated = first.embed_query("唐代官制的三省六部如何分工")

    a, b = np.asarray(related[0]), np.asarray(related[1])
    c = np.asarray(unrelated)
    assert a.shape == b.shape == c.shape, "同一模型输出维度必须一致"

    def cosine(x, y) -> float:
        return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))

    near, far = cosine(a, b), cosine(a, c)
    assert near > far, f"相关文本没有比无关文本更近（{near:.4f} <= {far:.4f}）——只断维度等于没测"


@pytest.mark.slow
@pytest.mark.skipif(
    not _REAL_LANE,
    reason=("真实嵌入 lane 未启用（需受信私有缓存）。这条是 B3 的验收本体，跳过＝未测，不得用替身绿顶替。"),
)
def test_prewarm_pays_the_model_load_before_the_first_embed(monkeypatch):
    """真权重包络：prewarm 之后第一次 embed 必须落在网关等检索工具的外层预算内。

    用一个**新的**惰性壳把真工厂包起来（模块级 `embeddings` 早被别的用例解析过，拿它测等于测缓存），
    所以两种形状只差一件事——`prewarm()` 有没有被调用过：

    * 修前形状（prewarm 不碰嵌入）：45s 量级的加载落在第一次 `embed_query` 上，
      而 `tools/gateway.py` 给 `retrieve_laws` 的外层等待只有 15.0s ⇒ 首问稳定 TOOL_TIMEOUT；
    * 修后形状：加载由 prewarm 付掉，embed 只剩推理。

    判据直接钉外层常量本身，不钉"预算的一半"那种余量线。
    """
    import time

    import rag_chain
    import retrieval
    from tools.gateway import _POLICIES

    outer = _POLICIES["retrieve_laws"].timeout_seconds
    # 用**生产那个形状**（配额包装类）而不是裸壳：裸壳会跳过 quota/全局锁，量出来的就不是产品走的路上。
    fresh = rag_chain.QuotaTrackingEmbeddings(rag_chain._build_embeddings)
    monkeypatch.setattr(retrieval, "embeddings", fresh)
    monkeypatch.setattr(retrieval, "_ensure_bm25", lambda: None)
    monkeypatch.setattr(retrieval, "_ensure_src_set", lambda: None)

    retrieval.prewarm()

    t0 = time.perf_counter()
    vec = retrieval.embeddings.embed_query("工伤保险的认定标准是什么")
    first_embed_s = time.perf_counter() - t0

    assert len(vec) == 768, f"这条 lane 没拿到真嵌入（维度 {len(vec)}）——尺子本身空跑"
    assert fresh._inner_resource._instance is not None, "prewarm 之后内层还没解析 ⇒ 首问仍在付加载费"
    assert first_embed_s < outer, (
        f"预热后首次 embed {first_embed_s:.2f}s 仍超过外层等待 {outer}s ⇒ 首问还是会 TOOL_TIMEOUT"
    )
