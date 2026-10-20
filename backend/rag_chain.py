"""RAG 基础设施：嵌入 + 向量库 + 文档格式化 + 链工厂。

- LLM 不再在此模块单例化，改由 llm_registry 按"是否带图"路由（文本/视觉）。
- 链的输入为 main 组装好的 messages 列表（含 system/历史/带图或纯文本的最终 human），
  以便视觉模型接收 image_url content 数组。
"""

import asyncio
import logging
import os
import re
import threading
import time
from contextlib import aclosing
from typing import TYPE_CHECKING

from anyio import CancelScope

# 运行期默认离线用本地缓存，避免对 huggingface.co 的在线校验（部分环境 SSL 校验失败）。
# 缓存缺失需回退在线时走 HF_ENDPOINT 镜像；建库/种子脚本会显式置 HF_HUB_OFFLINE=0 覆盖此默认。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_huggingface import HuggingFaceEmbeddings

import output_normalize  # noqa: E402
import quota_utils  # noqa: E402
from llm_guard import llm_guard  # noqa: E402
from settings import settings  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logger = logging.getLogger(__name__)

# D-52（2026-10-16）：重量对象（本地 BGE ≈409 MB、Chroma 持久集合）一律推迟到第一次真正使用。
# 失败语义要同时满足两条，缺一条都是假的：
#   ① 不把坏对象永久缓存——一次抖动就毒死整个进程不可接受；
#   ② 不做无界重试——否则每个 embed 调用都重新去加载 409 MB / 再打一次网络（vector_top 会在
#      一次请求里循环 1+N 次，retrieve_exam 还能到 6 次），故障时反而放大开销。
# 折中：失败后在窗口内直接抛同一个异常并留一条 error 日志（M2：静默降级是本仓的老毛病），
# 窗口过后允许再试一次。
_INIT_RETRY_WINDOW_SECONDS = 30.0


class _LazyResource:
    """按名字延迟构造重量对象：构造恰好一次，失败可重试但有窗口。

    用在三处：`QuotaTrackingEmbeddings` 的内层嵌入对象、模块级 `vectorstore`、
    `knowledge_service._qa_store`（都经 `lazy_store` 走同一机制，不各写一份）。

    为什么是转发壳、而不是把消费点都改成函数调用：`vectorstore`/`embeddings` 这两个名字在
    import 期就被 retrieval/main/knowledge_base/scripts 共 10 个模块 `from rag_chain import ...`
    绑走，65 处用法都在函数体内——改完的面远大于收益，而壳本身只需要一次属性访问才付代价。
    """

    __slots__ = ("_name", "_factory", "_instance", "_error", "_failed_at", "_lock")

    def __init__(self, name, factory):
        self._name = name
        self._factory = factory
        self._instance = None
        self._error: BaseException | None = None
        self._failed_at = 0.0
        self._lock = threading.Lock()

    def _resolve(self):
        """双重检查锁：并发下所有调用者拿到同一个成品，不会看到半成品。"""
        instance = self._instance
        if instance is not None:
            return instance
        with self._lock:
            if self._instance is not None:
                return self._instance
            if self._error is not None and (time.monotonic() - self._failed_at) < _INIT_RETRY_WINDOW_SECONDS:
                raise self._error
            try:
                self._instance = self._factory()
            except Exception as exc:
                self._error = exc
                self._failed_at = time.monotonic()
                logger.error(
                    "%s 初始化失败：%r（%.0f 秒内不再重试，之后会再试）",
                    self._name,
                    exc,
                    _INIT_RETRY_WINDOW_SECONDS,
                )
                raise
            self._error = None
            return self._instance

    def warm(self):
        """启动预热用：把重量对象现在就构造出来并返回成品。

        取个动词名而不是让调用方直接读 `_inner`：`_inner` 只有 `QuotaTrackingEmbeddings` 才有，
        裸的 `_LazyResource` 上它会走到属性转发、把"成品自己没有 `_inner`"当成 AttributeError
        抛给启动路径——这个坑由 tests/test_rag_initialization_boundary.py 的两条 prewarm 用例
        实测抓到（2026-10-16），不是假想。
        """
        return self._resolve()

    def __getattr__(self, item):
        # 只有不在 __slots__/方法名单里的名字才会走到这里，转发给已构造的成品
        return getattr(self._resolve(), item)

    def __repr__(self) -> str:
        # 刻意不触发构造：pytest 失败时会 repr 模块级对象，一旦 repr 去建库，
        # "收集期零副作用" 就被自己的调试输出打回原形。
        state = "resolved" if self._instance is not None else "unresolved"
        return f"<LazyResource {self._name} {state}>"


def lazy_store(factory, name: str = "vector store") -> _LazyResource:
    """惰性重量对象的唯一出口：主库与 QA 集合共用一套机制与同一套失败语义。"""
    return _LazyResource(name, factory)


# 1. Embeddings — 配置驱动（ADR-011，2026-08-04）：local=本地 BGE CPU（默认，零配置回退）；
#    aliyun=阿里云 text-embedding-v4（OpenAI 兼容端点）。
#    ⚠ 必须 check_embedding_ctx_length=False：langchain 默认本地 token 化长度检查会把文本
#    转成 token 数组发给 DashScope，触发 400 InvalidParameter（"input.contents is neither
#    str nor list of str"，grilling 实测）。
# plan:433「未知权重不加载」——与 `trust_remote_code` 那根轴（`tests/test_loader_trust_gate.py`）分开：
# 那道门问"要不要执行模型目录里的自定义代码"，这道门问"要不要加载**这一份**权重"。
# 本地权重只有一个受信来源，所以册子从构造点用的那个常量导出（单一真源，防第二份清单漂移），
# 加宽册子必须显式改这里。
LOCAL_EMBEDDING_MODEL = "BAAI/bge-base-zh-v1.5"
TRUSTED_LOCAL_EMBEDDING_MODELS: tuple[str, ...] = (LOCAL_EMBEDDING_MODEL,)


def ensure_trusted_local_embedding_model(model_name: str) -> str:
    """构造本地嵌入前核名字：不在册就拒，而不是"先加载再看看像不像"。"""
    if model_name not in TRUSTED_LOCAL_EMBEDDING_MODELS:
        raise RuntimeError(
            f"嵌入模型 {model_name!r} 未在册（plan:433 未知权重不加载）；"
            f"在册＝{TRUSTED_LOCAL_EMBEDDING_MODELS}。"
            "要新增受信权重请先核官方来源、许可与已有摘要，别在这里直接放宽"
        )
    return model_name


def _build_embeddings():
    provider = settings.embedding_provider
    if provider != "aliyun":
        return HuggingFaceEmbeddings(
            model_name=ensure_trusted_local_embedding_model(LOCAL_EMBEDDING_MODEL),
            model_kwargs={"device": "cpu"},
        )
    from langchain_openai import OpenAIEmbeddings

    if not settings.embedding_api_key:
        raise RuntimeError("embedding_provider=aliyun 但缺 EMBEDDING_API_KEY，请在 backend/.env 配置")
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
        dimensions=settings.embedding_dimensions,
        chunk_size=10,  # 阿里云 batch 上限
        max_retries=3,
        timeout=60,
        check_embedding_ctx_length=False,  # 关键：禁用本地 token 化检查（grilling）
    )


class QuotaTrackingEmbeddings(Embeddings):
    """嵌入包装（ADR-011 code-review 阶段5）：所有 embed 调用统一扣减 embedding 配额。

    - Chroma vectorstore/_qa_store 内部经 embedding_function 自动嵌入 → 自动覆盖向量
      召回 / grounded / QA / 写库 / rebuild 全路径；retrieval.vector_top 显式扣减已移除（防双扣）。
    - provider=aliyun 且配额耗尽 → 抛 UtilityQuotaExhausted（不调云 API），main 捕获转 409。
    - local 不耗云 token：仍按配置总量扣（本地场景 quota_total 通常 0 → no-op，安全）。
    - 扣减在调用成功后（异常不记账）；估算口径 quota_utils.estimate_tokens（~1.5 字符/token）。
    - **并发锁（2026-08-05 稳定性修正）**：BGE（HuggingFaceEmbeddings）是共享单例，
      retrieve_exam 的 ThreadPoolExecutor 多线程并发 encode 在 Windows 偶发原生 segfault
      （onnxruntime 多线程访问不稳）。全局锁串行化编码，消除竞态；嵌入是 CPU 快路径，
      锁开销可忽略。Chroma 查询为并发读（SQLite/HNSW 读安全）不锁。
    - **惰性（D-52，2026-10-16）**：`inner_factory` 收**工厂**而不是实例。`embeddings` 这个名字
      在 import 期就被 main/retrieval/knowledge_service/scripts 等 10 处
      `from rag_chain import embeddings` 绑走，而本地 BGE 的构造（`_build_embeddings()`）
      在无缓存环境会直接抛错——CI 的 39 个收集期错误就是这么来的（见
      tests/test_rag_initialization_boundary.py 的 ARM 记录）。所以内层推迟到第一次真嵌入。
    """

    def __init__(self, inner_factory):
        # D-52（2026-10-16）：收**工厂**而不是实例；失败留痕 + 窗口化重试见 _LazyResource。
        self._inner_resource = _LazyResource("本地嵌入模型", inner_factory)
        self._lock = threading.Lock()

    @property
    def _inner(self) -> Embeddings:
        """首次用到才构造内层：失败留痕、窗口内不重复重试，也不交出半成品。

        `retrieval._query_token_len` 经 `getattr(embeddings, "_inner", ...)` 读真实 tokenizer，
        因此"量 token"这个动作本身会触发构造——这是有意的：没有内层就没有分词器可量（N01）。
        """
        return self._inner_resource._resolve()

    def warm(self) -> Embeddings:
        """预热：与裸壳同名同语义，调用方不必分辨 `embeddings` 绑的是包装类还是壳本身。"""
        return self._inner_resource.warm()

    def _check(self) -> None:
        if settings.embedding_provider == "aliyun" and quota_utils.utility_depleted(quota_utils.embedding_model_key()):
            raise quota_utils.UtilityQuotaExhausted(
                "embedding 配额已耗尽，请切换备用模型重建库，或把 EMBEDDING_PROVIDER 切回 local 用本地 BGE"
            )

    @staticmethod
    def _deduct(text: str) -> None:
        # per-model 记账：key = 当前模型名，换班后新模型从 0 起算（B4）
        quota_utils.deduct_utility(quota_utils.embedding_model_key(), quota_utils.estimate_tokens(text))

    def embed_query(self, text: str):
        self._check()
        with self._lock:
            v = self._inner.embed_query(text)
        self._deduct(text)
        return v

    def embed_documents(self, texts):
        self._check()
        with self._lock:
            v = self._inner.embed_documents(texts)
        self._deduct("".join(texts))
        return v


embeddings = QuotaTrackingEmbeddings(_build_embeddings)


def get_embeddings() -> QuotaTrackingEmbeddings:
    """最小惰性出口（执行书 W01）：返回的始终是同一个包装对象。

    真正的内层模型在它第一次被用到时才构造，所以 `import rag_chain` 本身零模型加载、零写盘；
    老名字 `embeddings` 仍然可用，绑的是同一个对象（消费方 65 处用法不必改）。
    """
    return embeddings


# 2. Vector store — Chroma 持久化。collection 名随 provider 派生（语义空间不同，切云须重建）
_COLLECTION_LOCAL = "legal_provisions_cos"  # hnsw:space=cosine：距离分=1-cos
_COLLECTION_CLOUD = "legal_provisions_te4"  # 云端 text-embedding-v4（重建产物，旧库保留可回退）
_QA_COLLECTION_LOCAL = "qa_pairs"
_QA_COLLECTION_CLOUD = "qa_pairs_te4"
COLLECTION_NAME = _COLLECTION_CLOUD if settings.embedding_provider == "aliyun" else _COLLECTION_LOCAL
QA_COLLECTION_NAME = _QA_COLLECTION_CLOUD if settings.embedding_provider == "aliyun" else _QA_COLLECTION_LOCAL

# 向量库目录 = 单一真源（T-E，2026-09-18）。生产/容器不设 CHROMA_DIR ⇒ 取值与加出口前逐字相同
# （docker-compose.yml:19-44 的 environment 是显式白名单，不含该键）；测试在 conftest 里**无条件**
# 指向进程私有临时目录——因为 ./backend/chroma_db 被 compose:47 bind mount 进容器，
# 本地全量跑写的就是线上容器正在读的那份索引（且 chroma 并发不安全，见 compose:11）。
# DEFAULT_CHROMA_DIR 单独导出：它是「未设环境变量时生产落在哪」的判据本体，
# 供测试断言默认值未漂移，也供需要真实语料的用例（conftest.real_kb）按同一真源打开。
DEFAULT_CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
CHROMA_DIR = os.environ.get("CHROMA_DIR") or DEFAULT_CHROMA_DIR


def _build_vectorstore() -> Chroma:
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )


if TYPE_CHECKING:
    # 类型面保持 Chroma：65 处消费点的属性拼写检查不能因为运行时换成壳就失效。
    # mypy 只分析这一支，运行时走 else（否则 `__getattr__ -> Any` 会把向量层全部变盲）。
    vectorstore: Chroma
else:
    vectorstore = lazy_store(_build_vectorstore, "chroma 主集合")


def format_docs(docs) -> str:
    return "\n\n".join(
        f"[{d.metadata.get('source', '')} {d.metadata.get('article', '')}] {d.page_content}" for d in docs
    )


class ClosingStream(aclosing):
    """只 shield owned 流的关闭；生成仍接受客户端取消。"""

    async def __aexit__(self, exc_type, exc, tb):
        with CancelScope(shield=True):
            try:
                await super().__aexit__(exc_type, exc, tb)
            except Exception:
                if exc_type is None:
                    raise
                logger.exception("Owned stream close failed while propagating %s", exc_type.__name__)


class _OwnedStreamClient:
    """按请求登记 SDK 返回的响应；不关闭共享客户端/连接池。"""

    def __init__(self, client):
        self.client = client
        self.responses = []

    async def create(self, *args, **kwargs):
        response = await self.client.create(*args, **kwargs)
        self.responses.append(response)
        return response

    async def aclose(self):
        error = None
        for response in self.responses:
            try:
                await response.close()
            except Exception as exc:
                if error is None:
                    error = exc
        if error is not None:
            raise error


class _OwnedChain:
    def __init__(self, llm):
        self.llm = llm

    async def astream(self, messages, config=None):
        client = _OwnedStreamClient(self.llm.async_client)
        # 当前 RunnableSequence 的逐项任务边界可使响应已关闭但连接仍占用。
        # 在消费任务内直接迭代公开 model.astream，取消才能到达正在等待的读取。
        # async_client 是此版本可注入但标为 private 的字段：只替换请求内浅副本，
        # 保留公开 astream 的配置/模型回调与原共享传输；版本升级须回归本适配点。
        # dict(model) 保留 exclude=True 的 callbacks/client；copy 创建独立字段字典。
        llm = self.llm.copy(update={**dict(self.llm), "async_client": client})
        parser = StrOutputParser()
        # 不再生成 Sequence 聚合追踪；公开 parser.invoke 对每个 chunk 发出解析事件。
        async with ClosingStream(client), ClosingStream(llm.astream(messages, config=config)) as stream:
            async for chunk in stream:
                yield parser.invoke(chunk, config=config)


def make_chain(llm):
    """输入 = 已组装的 messages；输出 = str 流，显式拥有本次 SDK 响应。"""
    return _OwnedChain(llm)


class _ThinkStripper:
    """流式有状态剥 <think>...</think>，跨 piece 半截标签安全（B4，2026-08-07）。

    之前是先流出再 clean_answer 剥——thinking 块会漏进 SSE；改为在 yield 处逐 piece 剥，
    用尾部 carry 处理 <think>/</think> 被截断在 piece 边界的半截标签。
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._in_think = False
        self._carry = ""

    def feed(self, text: str) -> str:
        buf = self._carry + text
        self._carry = ""
        out: list[str] = []
        i = 0
        n = len(buf)
        while i < n:
            if self._in_think:
                j = buf.find(self._CLOSE, i)
                if j == -1:
                    tail = buf[i:]
                    keep = _prefix_suffix_len(self._CLOSE, tail)
                    if keep:
                        self._carry = tail[-keep:]
                    i = n  # think 块未闭合 → 丢弃
                else:
                    i = j + len(self._CLOSE)
                    self._in_think = False
            else:
                j = buf.find(self._OPEN, i)
                if j == -1:
                    tail = buf[i:]
                    keep = _prefix_suffix_len(self._OPEN, tail)
                    emit = len(tail) - keep
                    out.append(tail[:emit])
                    if keep:
                        self._carry = tail[emit:]
                    i = n
                else:
                    out.append(buf[i:j])
                    self._in_think = True
                    i = j + len(self._OPEN)
        return "".join(out)


def _prefix_suffix_len(prefix: str, tail: str) -> int:
    """tail 尾部是 prefix 的前缀的最大长度（半截标签 carry 用）。"""
    for k in range(min(len(prefix) - 1, len(tail)), 0, -1):
        if prefix.startswith(tail[-k:]):
            return k
    return 0


async def stream_with_retry(make_chain_fn, messages, configs, on_model_failure=None):
    """流式生成 + 空答多配置重试（异步生成器，边收边 yield，真流式）。

    make_chain_fn(i, disabled) -> 可 astream 的链；configs = [(disabled, wait_seconds), ...]。
    依次尝试：首个产生非空内容即返回；全部为空则 yield 结束后返回（调用方据此判定为空）。

    自动换模型（块 2.2，用户核心要求——没人盯梢也能切）：astream 抛**任何**异常
    （配额耗尽 / 模型名错误 / 瞬时失败）→ 调 on_model_failure(err)（调用方 mark_depleted
    当前 key）→ 下一次循环重新 make_chain_fn（内部重新 pick 落后备）→ 用下一模型重试。
    只有最后一个 config 仍失败才上抛。

    ⚠️ F7（2026-09-14）语义变更：调用方原先对**任何**异常都 `mark_depleted`，代价是
    「瞬时错误也会暂时标记该模型耗尽（重启/校准恢复，19 模型队列容忍个别误伤）」。
    但本项目 `.env` 的 `LLM_MODELS_JSON` 已把队列覆盖成 **1 主 + 6 回退**，该前提变弱；
    且限速**是暂时性**故障（同 1k 修复口径）。现约定：调用方**仅对非瞬时错误**标记耗尽，
    瞬时错误改用 `registry.pick(exclude=<已试过的 key>)` 推进到下一个模型 —— 既换模型、
    又不把仍可用的模型标死，且避免 pick 选回同一模型造成死循环。
    本函数只负责「调回调 + 换 config 重试」，不做异常分类（分类在调用方 main.py 两处）。

    并发门控：整个生成过程占一个全局 LLM 并发位（async 路径），超限排队超时抛
    LLMBusyError → 调用方降级「服务繁忙」。突增时不会无界并发打向供应商。
    """
    async with llm_guard:
        for i, (disabled, wait) in enumerate(configs):
            # R16：剥 think 的解析状态**每次尝试独立**。改前 stripper 建在循环外、跨尝试共用：
            # 首模型若吐了未闭合的 `<think>`（换模型前就断流），`_in_think` 会带进下一次尝试，
            # 后备模型的正文被判为"仍在 think 块内"而被整段吞掉（用户看到空答或半截）。
            stripper = _ThinkStripper()
            try:
                chain = make_chain_fn(i, disabled)
                chunks = []
                async with ClosingStream(chain.astream(messages)) as stream:
                    async for piece in stream:
                        if not piece:
                            continue
                        # B4（2026-08-07）：流式剥 <think>（有状态，跨 piece 安全）+ 币种 $/¥→元
                        # （不再等流完 clean_answer——thinking 块曾漏进 SSE；_post 会再对整答幂等归一）
                        piece = output_normalize.money_normalize(stripper.feed(piece))
                        if piece:
                            chunks.append(piece)
                            yield piece
                if "".join(chunks):
                    return
                if wait:
                    await asyncio.sleep(wait)
            except Exception as e:
                if on_model_failure and i < len(configs) - 1:
                    on_model_failure(e)  # mark_depleted 当前模型 → 下次循环重新 pick 落后备
                    if wait:
                        await asyncio.sleep(wait)
                    continue
                raise


_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def clean_answer(text: str) -> str:
    """去掉模型内联的 <think>...</think> 推理块（thinking 模型可能把思考混进正文）。"""
    if not text:
        return text
    return _THINK_RE.sub("", text).strip()
