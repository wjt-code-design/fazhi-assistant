"""W07-IMPL 新契约（C04＝甲 已裁）：识图失败**可见**——异常不再收敛成空串，两个出口分得开。

⚠️ 「可见」的适用范围（票 W7-FIX W7-B3 要求如实写明）：甲的**用户可见**那条腿只覆盖
「识图调用抛异常 ⇒ 本轮 502 不作答」这一支。「模型正常返回但内容为空」那一支**仍然继续作答、
没有面向用户的声明**——本轮按票 §3 V-B3 的第二选项给它落一条**可观测降级计数**
（`main._note_empty_image_description` 读 `RequestBootstrap.image_failure` ⇒ `image_desc_empty_degraded`），
所以这一腿的措辞是「降级可读」，不是「失败可见」。

与 `test_image_failure_visibility.py`（特征化轮，钉的是「失败与空内容同形、契约里没有失败位」）的分工：
那只文件量改前的现量，本文件量改后应有的行为。票 §3 第 1、2 条在这里成对：

1. 带图问答在识图失败时 ⇒ 用户看到明确失败（HTTP 502 ＋ 结构化信号），**不是**「正常答案」，也不许进入检索/生成阶段；
2. 注入异常亮键 A（`image_describe_failed`）、返回空内容亮键 B（`image_content_empty`）
   ⇒ 断言**是哪个键亮了**（两个键各自单独判，不只断言「有键亮」）。

外加本票特有的几条：`RequestBootstrap` 的失败位（§1 ⑦ 穷举证明改前没有）与其**读者**（V-B3）、
两个归因键在 `observability._ACCOUNT_FIELDS` 里真的登记过（上一票就是漏这格被全量门打回）、
吞异常普查的尺子与作用域（W7-B10/B4）、502 普查尺子的两种写法（F12）。

零外发：所有异常与空内容都由记账假对象注入，DB 是 in-memory SQLite；HTTP 腿走 TestClient，
识图能力本身换成假对象、检索/生成整段换成记账桩——一个字节都不出机器。
"""

import ast
import dataclasses
import inspect
import json
import logging
import os
import re
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import multimodal  # noqa: E402
from models import Base, Message, User  # noqa: E402
from observability import _ACCOUNT_FIELDS, _JsonFormatter  # noqa: E402
from request_bootstrap import BootstrapDependencies, RequestBootstrap, bootstrap_request  # noqa: E402

_DESCRIPTION = "图片里是一份两页合同，含甲方乙方与违约金条款。"
_PNG = "data:image/png;base64,AAAA"
_QUESTION = "这份合同有效吗"

# 跨面判据对象（先例：`test_multimodal_transport_contract.py` 第 4 条读 recorder.ts）
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
BACKEND = Path(__file__).resolve().parents[1]


class _Llm:
    def __init__(self, content):
        self._content = content

    def invoke(self, messages, **kwargs):
        return SimpleNamespace(content=self._content)


class _BoomLlm:
    def __init__(self, exc: BaseException):
        self._exc = exc
        self.calls = 0

    def invoke(self, messages, **kwargs):
        self.calls += 1
        raise self._exc


class _Capture:
    """直挂 logger 抓记录，不用 caplog：`setup_logging` 把 `legal.chat` 的 propagate 关成 False。"""

    def __init__(self, logger: logging.Logger, level: int = logging.WARNING):
        self.logger = logger
        self.level = level
        self.items: list[logging.LogRecord] = []

        class _Handler(logging.Handler):
            def __init__(self, owner):
                super().__init__(level=owner.level)
                self._owner = owner

            def emit(self, record):
                self._owner.items.append(record)

        self._handler = _Handler(self)

    def __enter__(self):
        self._previous = self.logger.level
        self.logger.addHandler(self._handler)
        self.logger.setLevel(self.level)
        return self

    def __exit__(self, *exc_info):
        self.logger.removeHandler(self._handler)
        self.logger.setLevel(self._previous)

    def lit(self, key: str) -> bool:
        """某个归因键是否在记录里亮着。

        顺带把「亮了但没登记」当成红：未登记的键会被 JSON formatter 静默丢掉，
        那正是上一票在全量门上被打回的那一格。
        """
        for record in self.items:
            if getattr(record, key, None):
                if key not in _ACCOUNT_FIELDS:
                    raise AssertionError(f"键 {key} 亮了但没登记进 _ACCOUNT_FIELDS ⇒ formatter 会丢掉它")
                return True
        return False


def _boom_describer(llm: _BoomLlm):
    def _describer(_image, _text):
        return llm.invoke([])

    return _describer


def _failure_bit(bootstrap: RequestBootstrap) -> str | None:
    """读 `RequestBootstrap` 的失败位；缺位时红在断言上而不是红在 AttributeError 上（票 §6）。"""
    fields = {f.name for f in dataclasses.fields(RequestBootstrap)}
    assert "image_failure" in fields, f"契约里仍没有失败位，现有字段面：{sorted(fields)}"
    return bootstrap.image_failure


@pytest.fixture
def store():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = sessions()
    user = User(username="w07impl", password_hash="x")
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()
    return SimpleNamespace(sessions=sessions, user_id=user_id)


def _deps(store, **overrides):
    values = dict(
        session_factory=store.sessions,
        load_context=lambda db, conv: ("", []),
        validate_image=lambda image: image,
        persist_image=lambda image: ("media/image.png", "media/thumb.jpg"),
        cleanup_persisted_image=lambda image_rel, thumb_rel: None,
        describe_image=lambda image, text: _DESCRIPTION,
        classify_intent=lambda query: "legal_query",
        is_exam_question=lambda query: False,
        has_exam_options=lambda query: False,
        is_contract_review=lambda query: False,
        contract_trigger_reason=lambda query: None,
        feature_multi_analyze=False,
        contract_conversations=set(),
        contract_reviewed_conversations=set(),
        is_contract_exit=lambda query: False,
    )
    values.update(overrides)
    return BootstrapDependencies(**values)


# ---------------------------------------------------------------- 甲：两个出口分得开


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("401 Unauthorized"),
        ValueError("400 InvalidParameter: model not support"),
        TimeoutError("connect timeout"),
        ZeroDivisionError("无任何关键词的本地异常"),
    ],
)
def test_describe_image_lets_each_failure_kind_through(exc):
    """甲的第 1 半：四类异常（鉴权／形状／超时／无状态码本地异常）都不再被收敛成空串。

    `llm.calls == 1` 是这条判据的阳性自证：根本没发请求就「失败」，会在空转上假绿。
    """
    llm = _BoomLlm(exc)
    with pytest.raises(type(exc)):
        multimodal.describe_image(llm, _PNG)
    assert llm.calls == 1


def test_failure_and_empty_content_are_two_different_outcomes():
    """甲的第 2 半：失败＝抛，空内容＝返回空串；判据形态本身就把两者分开了。

    正对照：真描述原样回来，否则前四条会因为「函数恒抛」而全部假绿。
    """
    with pytest.raises(RuntimeError):
        multimodal.describe_image(_BoomLlm(RuntimeError("boom")), _PNG)

    assert multimodal.describe_image(_Llm(""), _PNG) == ""
    assert multimodal.describe_image(_Llm("   "), _PNG) == ""
    assert multimodal.describe_image(_Llm(None), _PNG) == ""
    assert multimodal.describe_image(_Llm(_DESCRIPTION), _PNG) == _DESCRIPTION


def test_voice_and_vision_now_share_one_failure_discipline():
    """卡 §1 ⑥ 的反向腿：改前两个模态的失败纪律相反，甲把它们对齐成「都向上抛」。"""
    with pytest.raises(RuntimeError):
        multimodal.transcribe_audio(_BoomLlm(RuntimeError("429 rate limited")), "aGVsbG8=", "wav")
    with pytest.raises(RuntimeError):
        multimodal.describe_image(_BoomLlm(RuntimeError("429 rate limited")), _PNG)


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("401 Unauthorized"),
        ValueError("400 InvalidParameter: model not support"),
        TimeoutError("connect timeout"),
        ZeroDivisionError("无任何关键词的本地异常"),
    ],
    ids=["runtime", "value", "timeout", "bare-local"],
)
def test_both_lanes_reject_the_same_exception_set(exc):
    """§5 的防「单边吞」判据：同一发异常在**语音腿与视觉腿各判一次**，两侧必须同样拒绝。

    为什么不只判视觉：上面那条只拿 `RuntimeError` 各打一发，视觉侧的四类异常由另一条用例判——
    于是「只把 TimeoutError 在语音侧悄悄吞掉」这种**单边**回归可以穿过整排判据。
    这条把异常集合与模态做成笛卡儿积：两侧共用同一只 `_BoomLlm` 双（不是各造一个形状），
    任何一侧单独改回降级就红。`calls == 1` 是同一条判据的阳性自证（根本没发请求就"拒绝"＝空转）。
    """
    voice = _BoomLlm(exc)
    with pytest.raises(type(exc)):
        multimodal.transcribe_audio(voice, "aGVsbG8=", "wav")
    assert voice.calls == 1, "语音腿没调到模型就拒绝 ⇒ 这条腿在空转"

    vision = _BoomLlm(exc)
    with pytest.raises(type(exc)):
        multimodal.describe_image(vision, _PNG)
    assert vision.calls == 1, "视觉腿没调到模型就拒绝 ⇒ 这条腿在空转"


def _swallow_sites(source: str) -> dict[str, int]:
    """按**最内层函数**归属数「捕获之后不把异常抛出去」的 except 处理器（票 W7-B10 的尺）。

    判据从「处理器里有 `Return` 且子树内无 `Raise`」改成「**处理器顶层没有 re-raise**」——
    旧尺漏掉五种形状，其中第三种恰好是"只继续吞某一类"那种回退：
      ① `except Exception: pass` ＋ try 之后再 return；
      ② `except Exception: out = ""` 赋值后返回 / 委托 helper（`return _fallback(e)`）；
      ③ 条件 re-raise：`if not isinstance(e, X): raise` 然后 return ⇒ 顶层没有 raise；
      ④ `with contextlib.suppress(X):`（另由 `_suppress_sites` 数）；
      ⑤ 处理器里根本没有 Return 的那种降级。
    换类型上抛（`except KeyError as e: raise ValueError(...) from e`）顶层就有 raise ⇒ 不算吞（旧尺那条不误伤）。
    """
    tree = ast.parse(source)
    out: dict[str, int] = {}

    def walk(node, fname):
        for ch in ast.iter_child_nodes(node):
            nf = fname
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nf = ch.name
            if isinstance(ch, ast.ExceptHandler) and not any(isinstance(s, ast.Raise) for s in ch.body):
                key = nf or "<module>"
                out[key] = out.get(key, 0) + 1
            walk(ch, nf)

    walk(tree, None)
    return out


def _swallowing_handlers(source: str) -> int:
    """吞没处理器总数（保留旧函数名：调用处按"有几个"判）。"""
    return sum(_swallow_sites(source).values())


def _suppress_sites(source: str) -> dict[str, int]:
    """`with suppress(...)`／`with contextlib.suppress(...)`／两者的 `async with` 形（按最内层函数归属）。

    这种写法**天生**不 re-raise（它就是为此而被 import 的），所以旧尺一条都数不到它。

    R2-F10（复核第二轮）：改前只匹配 `ast.With` ⇒ `async with contextlib.suppress(...)` 在**异步**
    的 `main.py` 里（`stream`／`lifespan` 那几十条 `async def` 路径）完全隐形——普查报「零 suppress 落点」
    而实际有人用异步形吞掉异常。现在两形一起数（正对照见
    `test_suppress_ruler_detects_both_alias_and_async_shapes`：别名/限定名 × 同步/异步 四形各数得出，
    且 `async with` 别的上下文管理器**不**被误数）。
    """
    tree = ast.parse(source)
    out: dict[str, int] = {}

    def qual(n):
        if isinstance(n, ast.Name):
            return n.id
        if isinstance(n, ast.Attribute):
            return n.attr
        return ""

    def walk(node, fname):
        for ch in ast.iter_child_nodes(node):
            nf = fname
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nf = ch.name
            if isinstance(ch, (ast.With, ast.AsyncWith)):
                for item in ch.items:
                    ctx = item.context_expr
                    if isinstance(ctx, ast.Call) and qual(ctx.func) == "suppress":
                        key = nf or "<module>"
                        out[key] = out.get(key, 0) + 1
            walk(ch, nf)

    walk(tree, None)
    return out


def _call_sites_outside_own_def(source: str, fn_name: str) -> list[int]:
    """`fn_name(...)` 的**调用**落点行号，排除它自己 def 体内的那一处。

    R2-F4（复核第二轮）：「`image_failure` 有读者」这句话，旧判据数的是**属性读取**
    （`x.image_failure` 出现在 Load 位），而那个读取就写在 `_note_empty_image_description` **自己身上**
    （`main.py:541`）——读者读自己的字段也算「有读者」。结果把路由层那行**调用**
    （`main.py:771`）整行删掉，全树仍然绿：函数定义了却没人调，降级读数一次也不会落。
    现在钉的是调用点：必须在它自己 def **之外**真有一处把它接进请求路径。
    """
    tree = ast.parse(source)
    inside = set()
    for d in ast.walk(tree):
        if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef)) and d.name == fn_name:
            inside |= {id(n) for n in ast.walk(d)}
    return [
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn_name and id(n) not in inside
    ]


# 作用域（票 W7-B10）：`multimodal`／`request_bootstrap`／`main`／`mcp_server` 四个文件一起扫。
# `mcp_server.py` 不能 import（本机没装 `mcp` 包），所以一律按**源文件文本**读——
# 尺量的是文本，与被测模块能不能装载无关。
_CENSUS_FILES = ("multimodal.py", "request_bootstrap.py", "main.py", "mcp_server.py")

# 存量登记在册（W7-FIX 只把尺子**扩**到这些文件，逐条改造清理路径超出本票面）：
# 数字与键（函数名）任一变化都红 ⇒ 新增一处吞没必红，改掉一处也得同步把这条读数往下改。
_KNOWN_SWALLOW_SITES = {
    "multimodal.py": {},
    "mcp_server.py": {},
    "request_bootstrap.py": {"cleanup_persisted_images": 2, "bootstrap_request": 3},
    "main.py": {
        "__call__": 1,
        "lifespan": 1,
        "healthz": 3,
        "_best_effort_log_agent_gate_failure": 1,
        "_observe_agent_gate": 4,
        "_run_agent_gate_shadow": 1,
        "_pre": 1,
        "_record_actual_agent_route": 2,
        "_join_owned_task": 2,
        "run_and_record": 1,
        "watch_disconnect": 1,
        "_execute_agent_observing_disconnect": 1,
        "_record_analysis": 1,
        "finalize_verified_agent_answer": 1,
        "_safe_pick": 1,
        "_embed_question": 1,
        "_similar_cache_hit": 1,
        "_ainvoke_cancel_safe": 2,
        "_light_buffered_locked": 1,
        "_do": 2,
        "_acquire_chat_turn": 1,
        "_serialized_chat": 1,
        "stream": 16,
        "compensate_unstarted": 1,
    },
}
_KNOWN_SUPPRESS_SITES = {
    "multimodal.py": {},
    "mcp_server.py": {},
    "request_bootstrap.py": {},
    "main.py": {"_execute_agent_observing_disconnect": 1},
}


def _file_source(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8")


def test_multimodal_has_no_swallowing_handler_left():
    """甲之后 `multimodal`／`mcp_server` 里不该再有吞异常的处理器；其余两个文件按存量在册（AST 普查）。

    为什么用普查而不是逐条 `pytest.raises`：逐条判据只覆盖**想到了的那几种**异常与**那两条**出口，
    而"哪天有人给 multipart 腿补一句 except 返回空串"是新增出口——普查对整只文件生效。
    watch-it-fail（正对照）见下面那条 `_swallow_sites` 形状判据，五种漏项各一条合成正对照。
    """
    assert _swallowing_handlers(inspect.getsource(multimodal)) == 0, "multimodal 里又出现了吞异常的处理器"
    assert _swallowing_handlers(inspect.getsource(multimodal.transcribe_audio)) == 0

    for name in _CENSUS_FILES:
        assert _swallow_sites(_file_source(name)) == _KNOWN_SWALLOW_SITES[name], (
            f"{name} 的吞异常面与在册读数不符：{_swallow_sites(_file_source(name))}"
        )
        assert _suppress_sites(_file_source(name)) == _KNOWN_SUPPRESS_SITES[name], (
            f"{name} 的 contextlib.suppress 落点与在册读数不符：{_suppress_sites(_file_source(name))}"
        )

    swallowed = "\n".join(
        [
            "def f(x):",
            "    try:",
            "        return x()",
            "    except Exception:",
            "        return ''",
        ]
    )
    assert _swallowing_handlers(swallowed) == 1, "尺子失灵：明显的吞没被数出来"
    converted = "\n".join(
        [
            "def g(x):",
            "    try:",
            "        return x()",
            "    except KeyError as e:",
            "        raise ValueError('bad') from e",
        ]
    )
    assert _swallowing_handlers(converted) == 0, "换类型上抛被误判成吞 ⇒ 判据会把合法代码也钉红"


@pytest.mark.parametrize(
    "shape,expected",
    [
        # ① 处理器里 pass，try 之后才 return（旧尺：处理器内没有 Return ⇒ 数不出来）
        (
            "\n".join(
                [
                    "def f(x):",
                    "    try:",
                    "        x()",
                    "    except Exception:",
                    "        pass",
                    "    return 'ok'",
                ]
            ),
            1,
        ),
        # ② 条件 re-raise ＋ return：`if not isinstance(e, X): raise` ⇒ **只继续吞某一类**那种回退
        (
            "\n".join(
                [
                    "def f(x):",
                    "    try:",
                    "        return x()",
                    "    except Exception as e:",
                    "        if not isinstance(e, TimeoutError):",
                    "            raise",
                    "        return ''",
                ]
            ),
            1,
        ),
        # ③ 赋值后返回（处理器内无 Return 语句，返回的是刚赋的值）
        (
            "\n".join(
                [
                    "def f(x):",
                    "    try:",
                    "        out = x()",
                    "    except Exception:",
                    "        out = ''",
                    "    return out",
                ]
            ),
            1,
        ),
        # ④ 委托 helper（返回值来自被调函数，旧尺数得到 Return 但形状判不出"顶层不抛"）
        (
            "\n".join(
                [
                    "def f(x, fallback):",
                    "    try:",
                    "        return x()",
                    "    except Exception as e:",
                    "        return fallback(e)",
                ]
            ),
            1,
        ),
        # 正对照：顶层 bare raise ⇒ 不是吞
        (
            "\n".join(
                [
                    "def f(x):",
                    "    try:",
                    "        return x()",
                    "    except Exception:",
                    "        raise",
                ]
            ),
            0,
        ),
    ],
    ids=["pass-then-return", "conditional-reraise", "assign-then-return", "delegated-helper", "bare-raise"],
)
def test_swallow_ruler_detects_each_previously_missed_shape(shape, expected):
    """W7-B10 的 watch-it-fail：四种漏项各被数出 1，合法的那条仍是 0（否则这条尺是恒真的）。"""
    assert sum(_swallow_sites(shape).values()) == expected, _swallow_sites(shape)


def test_suppress_ruler_detects_contextlib_suppress():
    """`contextlib.suppress`（`main.py` 早就 import 了它）在旧尺里一条都数不到——这里补上。"""
    src = "\n".join(
        [
            "from contextlib import suppress",
            "def f(x):",
            "    with suppress(ValueError):",
            "        x()",
        ]
    )
    assert _suppress_sites(src) == {"f": 1}
    assert _suppress_sites("def f(x):\n    return x()\n") == {}


@pytest.mark.parametrize(
    "src,expected",
    [
        # 别名形（`from contextlib import suppress`）＋同步
        (
            "\n".join(
                [
                    "from contextlib import suppress",
                    "def f(x):",
                    "    with suppress(ValueError):",
                    "        x()",
                ]
            ),
            {"f": 1},
        ),
        # 限定名形（`contextlib.suppress`）＋同步
        (
            "\n".join(
                [
                    "import contextlib",
                    "def f(x):",
                    "    with contextlib.suppress(ValueError):",
                    "        x()",
                ]
            ),
            {"f": 1},
        ),
        # R2-F10：别名形＋**异步**——改前只匹配 `ast.With`，这一发整条隐形
        (
            "\n".join(
                [
                    "from contextlib import suppress",
                    "async def f(x):",
                    "    async with suppress(ValueError):",
                    "        await x()",
                ]
            ),
            {"f": 1},
        ),
        # 限定名形＋异步
        (
            "\n".join(
                [
                    "import contextlib",
                    "async def f(x):",
                    "    async with contextlib.suppress(ValueError):",
                    "        await x()",
                ]
            ),
            {"f": 1},
        ),
        # 反对照：`async with` 用的不是 suppress ⇒ 一条都不该数（否则这把尺是恒真的）
        (
            "\n".join(
                [
                    "async def f(lock, x):",
                    "    async with lock:",
                    "        await x()",
                ]
            ),
            {},
        ),
    ],
    ids=["sync-alias", "sync-qualified", "async-alias", "async-qualified", "async-other-context"],
)
def test_suppress_ruler_detects_both_alias_and_async_shapes(src, expected):
    """R2-F10 的 watch-it-fail：别名/限定名 × 同步/异步 四形各数得出 1，异步的**别的**上下文数出 0。

    异步那两形为什么算吞没落点：`with suppress(...)` 的形状天生不 re-raise，`async with` 只是把它
    搬到 `main.py` 里那些 `async def`（`stream`／`lifespan`）路径上——普查看不见它，就等于
    「异步面零吞没」这条读数是假的。
    """
    assert _suppress_sites(src) == expected, _suppress_sites(src)


# ---------------------------------------------------------------- §3 第 2 条：分键亮灭


def test_injected_exception_lights_key_a_only(store):
    """§3 第 2 条（异常腿）：亮的是 `image_describe_failed`，**不是** `image_content_empty`。

    这一轮不得留下半截轮次（用户消息不落库），否则「明确失败」与「答了一半」在库里同形。
    """
    boom = _BoomLlm(RuntimeError("识图炸了"))
    with _Capture(logging.getLogger("legal.chat")) as records:
        with pytest.raises(RuntimeError):
            bootstrap_request(
                store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store, describe_image=_boom_describer(boom))
            )
    assert records.lit("image_describe_failed") is True
    assert records.lit("image_content_empty") is False
    assert boom.calls == 1

    db = store.sessions()
    assert db.query(Message).count() == 0
    db.close()


def test_empty_content_lights_key_b_only(store):
    """§3 第 2 条（空内容腿）：亮的是 `image_content_empty`，**不是** `image_describe_failed`。"""
    with _Capture(logging.getLogger("legal.chat")) as records:
        got = bootstrap_request(
            store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store, describe_image=lambda image, text: "")
        )
    assert records.lit("image_content_empty") is True
    assert records.lit("image_describe_failed") is False
    assert _failure_bit(got) == "content_empty"
    assert got.image_description == ""
    assert got.image is not None, "pre 里还带着图 ⇒ 下游仍按「有图」走，只是描述是空的"
    assert got.raw_query == _QUESTION, "空描述仍继续整轮（甲只要求可分，不要求把「没字」当失败）"


def test_normal_description_lights_neither_key(store):
    """正对照：图正常读出内容时两个键都不亮，失败位是 None。

    没有这条，上面两条会因为「无论发生什么都末尾亮键 B」而假绿。
    """
    with _Capture(logging.getLogger("legal.chat")) as records:
        got = bootstrap_request(store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store))
    assert records.items == []
    assert _failure_bit(got) is None
    assert _DESCRIPTION in got.raw_query


def test_text_only_turn_lights_neither_key(store):
    """反向守卫：本轮没图就不许亮任何识图归因键（否则读数会把纯文本轮算进失败面）。"""
    with _Capture(logging.getLogger("legal.chat")) as records:
        got = bootstrap_request(store.user_id, None, _QUESTION, None, False, _deps=_deps(store))
    assert records.items == []
    assert _failure_bit(got) is None


# ---------------------------------------------------------------- §1 ⑦：契约里的失败位


def test_request_bootstrap_contract_gained_a_failure_bit():
    """§2 末：`RequestBootstrap` 现在有一位能表达「这一轮的图没被读出来」。

    改前的字段面里没有任何失败位（那只闭集判据是唯一现量，已在 `test_image_failure_visibility.py`
    改写成新闭集）。本条只钉**新增位存在且缺省 None**——缺省必须是 None，
    否则 `main._resume_bootstrap` 这类不涉图的构造点会被迫填值。
    """
    fields = {f.name for f in dataclasses.fields(RequestBootstrap)}
    assert "image_failure" in fields, sorted(fields)
    field = next(f for f in dataclasses.fields(RequestBootstrap) if f.name == "image_failure")
    assert field.default is None, repr(field.default)


def test_failure_bit_is_not_repudicated_by_the_empty_description_path(store):
    """失败位落到实例上才是「位」：空描述那一轮读得到 `content_empty`，正常轮读到 None。"""
    empty = bootstrap_request(
        store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store, describe_image=lambda image, text: "")
    )
    ok = bootstrap_request(store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store))
    assert (_failure_bit(empty), _failure_bit(ok)) == ("content_empty", None)


def _image_failure_reads() -> dict[str, int]:
    """`x.image_failure` 的**属性读取**（AST，Load 位）按文件归集；不含 request_bootstrap 自己那份写。"""
    out: dict[str, int] = {}
    for path in sorted(BACKEND.glob("*.py")):
        if path.name == "request_bootstrap.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        n = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "image_failure" and isinstance(node.ctx, ast.Load)
        )
        if n:
            out[path.name] = n
    return out


def test_empty_content_leg_has_a_reader_and_counts_as_degraded(store):
    """V-B3（W7-B3）：空内容腿**有读者＋有降级计数**——甲那句「失败可见」在这一腿上至此才成立。

    改前 `image_failure` 是只写字段（全树除测试无人读），空内容那一轮继续拿原图作答且没有任何声明。
    三条一起钉：
    ① 静态面：除 `request_bootstrap` 外必须真有属性**读取**（注释里提一句不算，所以走 AST）；
    ② 行为面：空内容轮落一条 `image_desc_empty_degraded`（连同既有 `kind`/`degraded`）；
    ③ 反对照：正常轮不落（否则这条计数会把所有带图轮都算成降级）。
    """
    import main

    # 原钉 `_image_failure_reads().get("main.py", 0) >= 1`（数属性**读取**）⇒ 现钉「def 之外有调用点」。
    # 理由（R2-F4，复核第二轮）：旧那半条被读者**自己**满足——`_note_empty_image_description` 函数体里
    # 那句 `bootstrap.image_failure != "content_empty"` 就是一次 Load，删掉 `main.py:771` 那行**调用**
    # （于是没有请求路径会走到这里，计数一次也不落）判据照样绿。读取计数留作辅助读数，真判据换成调用点。
    assert _image_failure_reads().get("main.py", 0) >= 1, _image_failure_reads()
    call_sites = _call_sites_outside_own_def(_file_source("main.py"), "_note_empty_image_description")
    assert call_sites, "没有**请求路径上**的调用点 ⇒ 读者定义了却没人叫它（V-B3 的接线没钉住）"
    # 接线要在 bootstrap 那一步之后：早于 bootstrap 拿到 `image_failure` 就没东西可读
    assert (
        _file_source("main.py").splitlines()[call_sites[0] - 1].strip().startswith("_note_empty_image_description(")
    ), f"调用点形状变了：{call_sites}"

    empty = bootstrap_request(
        store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store, describe_image=lambda image, text: "")
    )
    ok = bootstrap_request(store.user_id, None, _QUESTION, _PNG, False, _deps=_deps(store))
    assert empty.image_failure == "content_empty" and ok.image_failure is None

    with _Capture(logging.getLogger("legal.chat"), logging.INFO) as recs:
        main._note_empty_image_description(empty)
    assert recs.lit("image_desc_empty_degraded") is True, [r.getMessage() for r in recs.items]
    assert [getattr(r, "kind", None) for r in recs.items] == ["image_desc_empty_degraded"]
    assert all(getattr(r, "degraded", False) is True for r in recs.items)

    with _Capture(logging.getLogger("legal.chat"), logging.INFO) as clean:
        main._note_empty_image_description(ok)
    assert clean.items == [], [r.getMessage() for r in clean.items]


def test_r2_empty_content_leg_is_a_log_counter_not_a_frame_path():
    """R2-F5（cosmetic，但要落地）：`b06af58` 的提交信息把这一腿写成「计数**＋声明帧路径**」——
    复核判它 unsupported：`main.py` 这一段只是个日志计数器，没有任何 NOTE/SSE 帧
    （新增一帧要动 gate-exit 登记表，本就不在上一票面内）。

    历史提交不能改（本票红线：只新增提交、不 amend），所以这一格落成**判据**而不是删字：
    把「只有日志、没有帧」钉住 ⇒ 那句话要么由后来者真的实现一帧（并同步登记表与本条），
    要么就只能继续是错的。回执 §5 里那句措辞已按现量撤回。
    """
    import main

    src = inspect.getsource(main._note_empty_image_description)
    tree = ast.parse(textwrap.dedent(src))
    assert not any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(tree)), (
        "空内容腿出现了 yield ⇒ 它不再只是计数器，gate-exit 登记表与本条要一起改"
    )
    emitted = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert emitted <= {"log_account"}, f"这一段除了日志还做了别的事（措得当核对现量）：{sorted(emitted)}"
    for frame_token in ("NOTE", "StreamingResponse", "EventSource", "Response("):
        assert frame_token not in src, f"出现帧词汇 {frame_token} ⇒ 「声明帧路径」这句话需要重新核实"
    # 现量侧的正对照：这一腿的**读数**确实存在（否则上面那堆"没有帧"就只是函数被删空的假话）
    assert "image_desc_empty_degraded" in src


# ---------------------------------------------------------------- §3 第 1 条：HTTP 一层


def _wire_image_chat(monkeypatch, describer):
    """把 /api/chat 的图片腿接上假识图，并把检索/生成整段换成记账桩（零外发）。

    刻意**不**替换 `main._describe_image_for_bootstrap`：那条 502 映射本身就是被测对象。
    """
    import main

    entered: list[str] = []
    monkeypatch.setattr(main.registry, "has_modality", lambda modality: modality == "vision")
    monkeypatch.setattr(main.registry, "pick", lambda modality, tier, **kw: ("vision_flag", SimpleNamespace()))
    monkeypatch.setattr(main, "validate_image", lambda image: image)
    monkeypatch.setattr(main, "persist_image", lambda image: ("media/x.png", "media/x_thumb.jpg"))
    monkeypatch.setattr(main, "describe_image", describer)

    def _stub_prepared(bootstrap, *_args, **_kwargs):
        entered.append("prepare_fast_path")
        return {}

    monkeypatch.setattr(main, "prepare_fast_path", _stub_prepared)
    return entered


def test_failed_image_turn_returns_explicit_http_failure_and_never_answers(monkeypatch):
    """§3 第 1 条（甲）＋V-B5/V-B6：带图问答识图失败 ⇒ HTTP 502 ＋ **结构化信号**，且不进入检索/生成。

    「不能是正常答案」用两条腿一起钉：状态码不是 2xx 且响应体没有 content/answer，
    外加 `prepare_fast_path` 一次都没被调用。
    信号本身（B5/B6）：那只响应头＋逐字相符的 detail——前端认的就是这两样，
    「TestClient 端到端拿到 502」这条判据把"尺子按函数名数、不绑路由"那个漏洞补上
    （往 `chat()` 函数体里再加一个 502，光数函数名的判据照样绿，而这里会红在 detail/头上）。
    """
    from fastapi.testclient import TestClient

    import main
    from auth import get_current_user

    def boom(_llm, _image, _text):
        raise RuntimeError("401 Unauthorized")

    entered = _wire_image_chat(monkeypatch, boom)
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with (
            TestClient(main.app, raise_server_exceptions=False) as client,
            _Capture(logging.getLogger("legal.chat")) as records,
        ):
            resp = client.post("/api/chat", json={"content": _QUESTION, "image": _PNG})
    finally:
        main.app.dependency_overrides.clear()

    assert entered == [], "识图失败还走进了检索/生成阶段 ⇒ 用户拿到的仍是「正常答案」"
    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body.get("detail"), body
    assert "content" not in body and "answer" not in body
    # 结构化信号（前端唯一的认定依据）：头 + detail 逐字
    assert resp.headers.get(main.IMAGE_FAILURE_HEADER) == main.IMAGE_FAILURE_HEADER_VALUE, dict(resp.headers)
    assert body["detail"] == main.IMAGE_DESCRIBE_FAILED_DETAIL, body
    # 生产链路（不是只桩出来的 dep）也要亮键 A：main 把异常换成 502 之后，
    # bootstrap 那一道 `except Exception` 收到的仍是同一发 ⇒ 一次失败一个读数。
    assert records.lit("image_describe_failed") is True
    assert records.lit("image_content_empty") is False


def test_transcribe_route_502_carries_no_image_signal_and_logs_only_the_exception_class(monkeypatch):
    """B5 的反例＋B9 的读数面：语音那条路由的 502 **不是**识图失败信号，日志里也不许有异常正文。

    为什么要这条：`/api/chat/transcribe` 也回 502（不同语义），如果前端只看状态码，
    一轮带图的请求撞上语音故障就会被标成「图片识别失败」。这里量的是后端**没有**给那条 502
    发识图信号（头缺失＋detail 不同字），所以前端据信号判是安全的。
    B9：改前那行 `logging.warning("transcribe failed: %s", e)` 把 SDK 异常正文无条件写进 `msg`
    （`_JsonFormatter` 永远输出 `msg`）⇒ 现在只许出现**异常类名**。
    「上游是否回显请求字节」这一问没有真 key 测不了 ⇒ 标 NOT TESTABLE，本条只钉我们这一侧。
    """
    from fastapi.testclient import TestClient

    import main
    from auth import get_current_user

    monkeypatch.setattr(main.settings, "feature_transcribe", True)
    monkeypatch.setattr(main.registry, "has_modality", lambda modality: modality == "voice")
    monkeypatch.setattr(main.registry, "pick", lambda modality, tier, **kw: ("voice_flag", SimpleNamespace()))

    def boom(*_a, **_kw):
        raise RuntimeError("上游把请求内容回显出来的那种异常 zzz-marker-不能进日志")

    monkeypatch.setattr(main, "transcribe_audio", boom)
    main.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    try:
        with (
            TestClient(main.app, raise_server_exceptions=False) as client,
            _Capture(logging.getLogger("legal.chat")) as records,
        ):
            resp = client.post(
                "/api/chat/transcribe",
                files={"file": ("a.wav", b"RIIFFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE" * 40, "audio/wav")},
            )
    finally:
        main.app.dependency_overrides.clear()

    assert resp.status_code == 502, resp.text
    assert main.IMAGE_FAILURE_HEADER not in resp.headers, dict(resp.headers)
    assert resp.json()["detail"] != main.IMAGE_DESCRIBE_FAILED_DETAIL, resp.json()
    hits = [getattr(r, "llm_error_class", None) for r in records.items if getattr(r, "llm_error_class", None)]
    assert hits == ["RuntimeError"], hits
    text = "\n".join(_JsonFormatter().format(r) for r in records.items)
    assert "zzz-marker" not in text, f"异常正文进了日志：{text[:300]}"


def test_empty_image_description_does_not_become_an_http_failure(monkeypatch):
    """甲的边界（F13 改写）：空内容腿**确实跑了识图调用**，且**没有**被变成 HTTP 失败。

    原钉 `records.lit("image_content_empty") is False` ⇒ 现钉「调用计数 1 ＋ 返回值是空串 ＋ 没抛 HTTPException」。
    理由（票 F13）：`_describe_image_for_bootstrap` 这条路径**根本不调** `bootstrap_request`，
    那个键在这一段永远不会亮 ⇒ 断它的"灭"近恒真。空内容腿的读数由另外两条真的走到那一层的判据量：
    `test_empty_content_lights_key_b_only`（bootstrap 层的分键）与
    `test_empty_content_leg_has_a_reader_and_counts_as_degraded`（路由层的降级计数，V-B3）。
    """
    from fastapi import HTTPException

    import main

    picks: list[str] = []

    def pick(modality, tier, **kw):
        picks.append(modality)
        return "vision_flag", SimpleNamespace()

    monkeypatch.setattr(main.registry, "pick", pick)
    monkeypatch.setattr(main, "describe_image", lambda _llm, _image, _text: "")

    try:
        out = main._describe_image_for_bootstrap(_PNG, _QUESTION)
    except HTTPException as exc:  # 空内容被升级成 HTTP 失败 ⇒ 甲的边界被击穿
        pytest.fail(f"空内容腿被变成 HTTP {exc.status_code}：甲只把**调用失败**那一支变成 502")
    assert out == "", repr(out)
    assert picks == ["vision"], f"这条腿根本没发过识图请求 ⇒ 判据在空转：{picks}"


def test_vision_quota_shortage_stays_503_and_is_not_counted_as_describe_failure(monkeypatch):
    """能力/配额出口的档位不许被甲的新 502 吞掉：QuotaExhausted 仍是 503，且**不发**识图请求。"""
    from fastapi import HTTPException

    import main
    from llm_registry import QuotaExhausted

    calls: list[int] = []

    def exhausted(modality, tier, **kw):
        raise QuotaExhausted("no vision quota")

    monkeypatch.setattr(main.registry, "pick", exhausted)
    monkeypatch.setattr(main, "describe_image", lambda *a: calls.append(1) or "")

    with _Capture(logging.getLogger("legal.chat")) as records:
        with pytest.raises(HTTPException) as ei:
            main._describe_image_for_bootstrap(_PNG, _QUESTION)
    assert ei.value.status_code == 503
    assert calls == []
    assert records.lit("image_describe_failed") is False


def _http_exception_sites(source: str) -> dict[int, set[str]]:
    """按状态码归集「在哪个函数里 raise 了 HTTPException」——**两种写法都收**（票 F12）。

    改前的尺只匹配关键字形式 `HTTPException(status_code=502, ...)`；`HTTPException(502, ...)`
    这种**位置参数**写法会漏（今天的树里 0 处，所以尺子暂时不瞎，但没被合成对照钉住）。
    """
    by_status: dict[int, set[str]] = {}

    def visit(node, fname):
        for ch in ast.iter_child_nodes(node):
            fn = fname
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = ch.name
            if isinstance(ch, ast.Call) and getattr(ch.func, "id", "") == "HTTPException":
                status = None
                for kw in ch.keywords:
                    if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
                        status = kw.value.value
                if status is None and ch.args and isinstance(ch.args[0], ast.Constant):
                    status = ch.args[0].value
                if isinstance(status, int):
                    by_status.setdefault(status, set()).add(fn or "<module>")
            visit(ch, fn)

    visit(ast.parse(source), None)
    return by_status


def test_502_on_the_chat_route_has_exactly_one_source():
    """识图失败是 `/api/chat` **这条路由上** 502 的唯一出处（尺子两种写法都收，各配合成正对照）。

    判据是 AST 计数（不是 grep 印象）：`main.py` 里 raise 502 的函数集合恰好等于
    {识图失败出口, 语音转写出口}，后者住在另一条路由 `/api/chat/transcribe` 上——
    所以措辞里的限定词是「该路由上」，不是「全仓只有一个 502」。
    正对照：同一条尺量 501 得到**多个**函数 ⇒ 尺不是打空；
    F12 的合成正对照：关键字式与位置式各造一条，两样都要被数出来。
    """
    import main

    source = Path(main.__file__).read_text(encoding="utf-8")
    by_status = _http_exception_sites(source)
    assert by_status.get(502) == {"_describe_image_for_bootstrap", "chat_transcribe"}, by_status.get(502)
    assert len(by_status.get(501, set())) > 1, f"尺子打空：501 只数出 {by_status.get(501)}"

    keyword_shape = "\n".join(
        [
            "def f_a():",
            "    raise HTTPException(status_code=502, detail='x')",
        ]
    )
    positional_shape = "\n".join(
        [
            "def f_b():",
            "    raise HTTPException(502, 'x')",
        ]
    )
    assert _http_exception_sites(keyword_shape) == {502: {"f_a"}}, _http_exception_sites(keyword_shape)
    assert _http_exception_sites(positional_shape) == {502: {"f_b"}}, _http_exception_sites(positional_shape)
    both = keyword_shape + "\n" + positional_shape
    assert _http_exception_sites(both) == {502: {"f_a", "f_b"}}, "两种写法必须被同一把尺一起数"


# ---------------------------------------------------------------- 归因键与 formatter


def test_both_attribution_keys_are_registered():
    """上一票的漏格：新键不登记进 `observability._ACCOUNT_FIELDS` 就会被 JSON formatter 丢掉。

    W07-FIX 起的读数面（V-B3 的降级计数、B1 的 entry 跳过归因）与识图两键同一条规矩，
    所以一起钉在这里——漏一个就是"键白写"。
    """
    for key in (
        "image_describe_failed",
        "image_content_empty",
        "image_desc_empty_degraded",
        "llm_cfg_unknown_keys",
        "llm_cfg_entry_rejected",
    ):
        assert key in _ACCOUNT_FIELDS, f"{key} 未登记 ⇒ 结构化日志里读不到"


def test_json_formatter_keeps_both_keys_and_drops_an_unregistered_one():
    """formatter 本体的成对判据：登记过的两个键进 JSON，没登记的那个（正对照）确实被静默丢掉。"""
    fmt = _JsonFormatter()

    def _payload(key: str) -> dict:
        record = logging.LogRecord("legal.chat", logging.WARNING, __file__, 1, "归因", None, None)
        setattr(record, key, True)
        return json.loads(fmt.format(record))

    assert _payload("image_describe_failed").get("image_describe_failed") is True
    assert _payload("image_content_empty").get("image_content_empty") is True
    assert "deliberately_unregistered_w07_key" not in _payload("deliberately_unregistered_w07_key")


def test_attribution_records_carry_no_prompt_no_image_bytes(store):
    """§2：日志只落归因键——不落题干、不落图片内容、不落 base64（AUTH-3 同一口径）。"""
    question = "对方叫张三，合同金额 88 万"
    data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg"

    with _Capture(logging.getLogger("legal.chat")) as failed:
        with pytest.raises(RuntimeError):
            bootstrap_request(
                store.user_id,
                None,
                question,
                data_url,
                False,
                _deps=_deps(store, describe_image=_boom_describer(_BoomLlm(RuntimeError("识图失败")))),
            )
    with _Capture(logging.getLogger("legal.chat")) as empty:
        bootstrap_request(
            store.user_id, None, question, data_url, False, _deps=_deps(store, describe_image=lambda image, text: "")
        )

    fmt = _JsonFormatter()
    for record in failed.items + empty.items:
        text = fmt.format(record)
        assert "张三" not in text and "88 万" not in text, text
        assert "iVBORw0KGgo" not in text and "base64" not in text, text
    assert failed.lit("image_describe_failed") and empty.lit("image_content_empty")


# ---------------------------------------------------------------- 跨面：前端一条错误文案


def test_frontend_has_one_dedicated_image_failure_message():
    """甲要求「HTTP/SSE 一层＋前端一条错误文案」——这条把那句文案钉成判据（先例：recorder MIME 跨面钉）。

    skip 只在整只 `frontend/` 不在场时发生；在场而读不到一律**红**（不许拿「扫不到当通过」）。
    """
    if not FRONTEND_DIR.is_dir():
        pytest.skip(f"整只 frontend 不在场（{FRONTEND_DIR}）⇒ 这条跨面判据无对象")
    constants = (FRONTEND_DIR / "lib" / "constants.ts").read_text(encoding="utf-8")
    # 只数**定义**、再单独取值：prettier 会把长行折成「等号换行再缩进放字符串」，
    # 所以两条正则都必须与格式化无关——第一版按单行字面量匹配，prettier 一折行这条就假红，
    # 跨面判据不该指望别人怎么换行。
    definitions = re.findall(r"^export const IMAGE_DESCRIBE_FAILED_MESSAGE", constants, re.M)
    assert len(definitions) == 1, f"前端图片失败文案应当只有一条，实际 {len(definitions)} 条"
    value = re.search(r'IMAGE_DESCRIBE_FAILED_MESSAGE\s*=\s*"([^"]+)"', constants, re.S)
    assert value, "定义了却读不到它的值"
    text = value.group(1)
    assert "图片" in text and ("识别" in text or "识图" in text), text
    assert len(text) <= 60, f"一条用户可见文案不该写成长篇：{text}"

    # 文案的**使用点**住在 lib/api.ts 的流式错误映射里——那正是 401 那条前端文案的同一处
    # （`onError("登录已过期，请重新登录")`），映射规则的邻居就该待在一起。
    api = (FRONTEND_DIR / "lib" / "api.ts").read_text(encoding="utf-8")
    assert "IMAGE_DESCRIBE_FAILED_MESSAGE" in api, "定义了却没被使用 ⇒ 用户仍看不到这条文案"
    # 502 只在**本轮带图**时才是识图失败；条件写成一条正则判据，免得「文件里有个 502」就蒙过去。
    assert re.search(r"status\s*===\s*502[\s\S]{0,120}payload\.image", api), "502 没和「本轮带图」绑在一起"
    assert "登录已过期" in api, "正对照：这条判据量的确实是同一段流式错误映射"

    # V-B5（票 W7-FIX B5）：光「502 ＋ 本轮带图」不够——反代合成的 502 会把基建故障标成图片失败。
    # 前端必须**另**认一个结构化信号（响应头，或逐字相符的 detail），三者一起才算数。
    assert re.search(r"headers\s*\.\s*get\s*\(\s*IMAGE_FAILURE_HEADER", api), "前端没读那只结构化响应头"
    assert re.search(r"detail\s*===\s*IMAGE_DESCRIBE_FAILED_DETAIL", api), "detail 那条退路没了"
    assert re.search(r"payload\.image[\s\S]{0,80}imageFailureSignal", api), "502 认定没和结构化信号绑在一起"

    # 跨面同值（先例：recorder 的 MIME 尺）：前端那两个契约值必须与后端逐字相同，否则"信号"各自漂移。
    # 与格式化无关的两条正则（prettier 会把长行折成「等号换行再缩进放字符串」）：
    # 一条只要求常量**存在**，另一条取值出来与后端对字面。
    header_name = re.search(r"^export const IMAGE_FAILURE_HEADER\s*=\s*\"([^\"]+)\"", constants, re.M)
    header_value = re.search(r"^export const IMAGE_FAILURE_HEADER_VALUE\s*=\s*\"([^\"]+)\"", constants, re.M)
    detail_pair = re.search(r'IMAGE_DESCRIBE_FAILED_DETAIL\s*=\s*\s*"([^"]+)"', constants, re.S)
    assert header_name and header_value and detail_pair, (
        f"前端缺识图信号常量：header={bool(header_name)} value={bool(header_value)} detail={bool(detail_pair)}"
    )
    import main

    assert header_name.group(1) == main.IMAGE_FAILURE_HEADER, header_name.group(1)
    assert header_value.group(1) == main.IMAGE_FAILURE_HEADER_VALUE, header_value.group(1)
    assert detail_pair.group(1) == main.IMAGE_DESCRIBE_FAILED_DETAIL, detail_pair.group(1)
