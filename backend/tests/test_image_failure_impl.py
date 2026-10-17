"""W07-IMPL 新契约（C04＝甲 已裁）：识图失败**可见**——异常不再收敛成空串，两个出口分得开。

与 `test_image_failure_visibility.py`（特征化轮，钉的是「失败与空内容同形、契约里没有失败位」）的分工：
那只文件量改前的现量，本文件量改后应有的行为。票 §3 第 1、2 条在这里成对：

1. 带图问答在识图失败时 ⇒ 用户看到明确失败（HTTP 502），**不是**「正常答案」，也不许进入检索/生成阶段；
2. 注入异常亮键 A（`image_describe_failed`）、返回空内容亮键 B（`image_content_empty`）
   ⇒ 断言**是哪个键亮了**（两个键各自单独判，不只断言「有键亮」）。

外加两条本票特有的：`RequestBootstrap` 的失败位（§1 ⑦ 穷举证明改前没有），
以及两个归因键在 `observability._ACCOUNT_FIELDS` 里真的登记过（上一票就是漏这格被全量门打回）。

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


def _swallowing_handlers(source: str) -> int:
    """数「捕获之后不把异常抛出去、而是返回一个值」的 except 处理器——那才是吞。

    只看 `Return` 不看 `Raise` 会把 `except KeyError: raise ValueError(...)` 这种**换类型上抛**
    误判成吞（票 §1 ④ 的分派表里正好有一条），所以两个都要查。
    """
    total = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ExceptHandler):
            # 必须是 list：生成器被上面那次 any() 消费完，下面再迭代就永远为空 ⇒
            # 尺子会数出 0，第一条断言于是变成恒绿假象（本轮就是这么被正对照打回来的）
            body = list(ast.walk(node))
            if any(isinstance(x, ast.Raise) for x in body):
                continue
            if any(isinstance(x, ast.Return) for x in body):
                total += 1
    return total


def test_multimodal_has_no_swallowing_handler_left():
    """甲之后 `multimodal` 里不该再有「捕获→返回一个值」的处理器（AST 普查，两侧一起管）。

    为什么用普查而不是逐条 `pytest.raises`：逐条判据只覆盖**想到了的那几种**异常与**那两条**出口，
    而"哪天有人给 multipart 腿补一句 except 返回空串"是新增出口——普查对整只文件生效。
    watch-it-fail（正对照）：合成一份 `except Exception: return ""` 的源码必须数出 1，
    同一段合成源码里 `except KeyError: raise ValueError` 必须数出 0 ⇒ 尺子量的是「吞」而不是「有 try」。
    """
    assert _swallowing_handlers(inspect.getsource(multimodal)) == 0, "multimodal 里又出现了吞异常的处理器"
    assert _swallowing_handlers(inspect.getsource(multimodal.transcribe_audio)) == 0

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
    """§3 第 1 条（甲）：带图问答识图失败 ⇒ HTTP 502 明确失败，且**没有**进入检索/生成阶段。

    「不能是正常答案」用两条腿一起钉：状态码不是 2xx 且响应体没有 content/answer，
    外加 `prepare_fast_path` 一次都没被调用。
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
    # 生产链路（不是只桩出来的 dep）也要亮键 A：main 把异常换成 502 之后，
    # bootstrap 那一道 `except Exception` 收到的仍是同一发 ⇒ 一次失败一个读数。
    assert records.lit("image_describe_failed") is True
    assert records.lit("image_content_empty") is False


def test_empty_image_description_does_not_become_an_http_failure(monkeypatch):
    """甲的边界：「图里没字」不是失败——识图出口不许把它变成 HTTP 异常。

    反向钉 §3 第 2 条的另一半：实现若把两种出口混成一个异常，这条就红。
    同时钉住「空内容的读数只落在 bootstrap 那一处」，不留两份账。
    """
    import main

    monkeypatch.setattr(main.registry, "pick", lambda modality, tier, **kw: ("vision_flag", SimpleNamespace()))
    monkeypatch.setattr(main, "describe_image", lambda _llm, _image, _text: "")

    with _Capture(logging.getLogger("legal.chat")) as records:
        assert main._describe_image_for_bootstrap(_PNG, _QUESTION) == ""
    assert records.lit("image_content_empty") is False


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


def test_502_on_the_chat_route_has_exactly_one_source():
    """前端按「状态码 502 ＋ 本轮带图」判图片失败，所以后端这条路由上 502 只能有一个出处。

    判据是 AST 计数（不是 grep 印象）：`main.py` 里 raise 502 的函数集合恰好等于
    {识图失败出口, 语音转写出口}，后者住在另一条路由 `/api/chat/transcribe` 上。
    正对照：同一条尺量 501 得到**多个**函数 ⇒ 尺子不是打空。
    """
    import main

    source = Path(main.__file__).read_text(encoding="utf-8")
    by_status: dict[int, set[str]] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and getattr(sub.func, "id", "") == "HTTPException":
                    for kw in sub.keywords:
                        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
                            by_status.setdefault(kw.value.value, set()).add(node.name)
    assert by_status.get(502) == {"_describe_image_for_bootstrap", "chat_transcribe"}, by_status.get(502)
    assert len(by_status.get(501, set())) > 1, f"尺子打空：501 只数出 {by_status.get(501)}"


# ---------------------------------------------------------------- 归因键与 formatter


def test_both_attribution_keys_are_registered():
    """上一票的漏格：新键不登记进 `observability._ACCOUNT_FIELDS` 就会被 JSON formatter 丢掉。"""
    for key in ("image_describe_failed", "image_content_empty", "llm_cfg_unknown_keys"):
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
