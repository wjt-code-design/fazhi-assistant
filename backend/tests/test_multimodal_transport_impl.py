"""W07-IMPL 新契约（票 §1 四段接缝 ＋ §3 第 3、4、5 条负控 ＋ §5 单源红线）。

与 `test_multimodal_transport_contract.py`（特征化轮，钉的是**改前现量**）的分工：
那只文件把「语音只有一条传输路、未知 cfg 键无声消失」钉成现量；本文件钉的是**改后**应有的行为——
transport 从 entry 输入经 cfg 白名单到调用处一路不丢，且分派点与真源各只有一处。

零外发约定（票 §5）：
- multipart 腿走 `httpx.MockTransport`——它不建 socket，只在内存里交出**真实请求字节**，
  所以本文件校的是请求形状（multipart 里有 `file`＋`model`），不是调用计数；
- 缺省客户端腿把 base_url 指 `http://127.0.0.1:9`（discard 端口，回环立即拒连），
  唯一目的是证明「不注入客户端时走的仍是 entry 自己的根客户端」。
"""

import ast
import base64
import inspect
import json
import logging
import os
import sys
from types import SimpleNamespace

import httpx
import openai
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import llm_registry  # noqa: E402
import multimodal  # noqa: E402
import quota_store  # noqa: E402

# 假值：base_url 指回环死端口，任何一条腿都打不出去
_FAKE_CFG = {"api_key": "fake-value-not-a-secret", "base_url": "http://127.0.0.1:9/v1"}
_FAKE_B64 = base64.b64encode(b"hello").decode()


class _RecordingLlm:
    """只记账的假语音模型：记录 `invoke` 入参（chat 抽象有没有被走，就看这里）。"""

    def __init__(self, content="转写结果", model_name="Fake/ASR-V3.2"):
        self.calls = []
        self._content = content
        self.model_name = model_name
        self.request_timeout = 120

    def invoke(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return SimpleNamespace(content=self._content)


class _MultipartSink:
    """`httpx.MockTransport` 的处理器：把真实请求字节收下来，回一条固定转写。"""

    def __init__(self, status=200, payload=None):
        self.requests = []
        self._status = status
        self._payload = {"text": "转写好的中文"} if payload is None else payload

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._status >= 400:
            return httpx.Response(self._status, json={"error": {"message": "端点拒了这一发"}})
        return httpx.Response(200, json=self._payload)


def _sdk_client(sink: _MultipartSink) -> openai.OpenAI:
    """真 OpenAI SDK 客户端 ＋ 假传输：交出的是**真请求字节**，但没有一个字节出机器。"""
    return openai.OpenAI(
        api_key="fake-value-not-a-secret",
        base_url="http://127.0.0.1:9/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(sink)),
        max_retries=0,
    )


def _require(obj, *names: str) -> None:
    """契约位存在性守卫：缺位时红在断言上，而不是红在 AttributeError 上（票 §6 要「断言级红」）。"""
    missing = [n for n in names if not hasattr(obj, n)]
    label = getattr(obj, "__name__", type(obj).__name__)
    assert not missing, f"{label} 还缺这些契约位：{missing}"


def _transcribe(voice_llm, b64: str, fmt: str, **kwargs):
    """带前置形状断言的调用：参数不存在时先红在断言上，而不是红在 TypeError 上。"""
    params = inspect.signature(multimodal.transcribe_audio).parameters
    missing = sorted(k for k in kwargs if k not in params)
    assert not missing, f"transcribe_audio 不接受这些参数：{missing}——票 §1 ④ 要求调用处按 transport 分派"
    return multimodal.transcribe_audio(voice_llm, b64, fmt, **kwargs)


def _chat_leg_shape(llm: _RecordingLlm) -> tuple[list, dict]:
    """取出 chat 腿那一发的 (messages, kwargs)，形状判据与特征化轮逐字同形。"""
    assert len(llm.calls) == 1, f"chat 腿应当恰好一发，实际 {len(llm.calls)} 发"
    messages, kwargs = llm.calls[0]
    assert len(messages) == 1 and type(messages[0]).__name__ == "HumanMessage"
    parts = messages[0].content
    assert isinstance(parts, list) and [p["type"] for p in parts] == ["input_audio", "text"]
    assert parts[0]["input_audio"]["data"] == f"data:;base64,{_FAKE_B64}"
    assert parts[0]["input_audio"]["format"] == "wav"
    assert parts[1]["text"] == multimodal.AUDIO_PROMPT
    return messages, kwargs


def _registry_from(monkeypatch, roles) -> llm_registry.LLMRegistry:
    """按给定 roles 造一只真 registry（形状同 `test_capability_gates._registry_from`）。"""
    import settings as _s

    monkeypatch.setattr(_s.settings, "llm_models_json", json.dumps(roles))
    monkeypatch.setattr(quota_store, "get_used", lambda key: 0)
    monkeypatch.setattr(quota_store, "record_delta", lambda key, delta: 0)
    monkeypatch.setattr(quota_store, "initial_override", lambda key: None)
    return llm_registry.LLMRegistry()


def _role(key: str, **extra) -> dict:
    base = {
        "key": key,
        "model": f"Fake/{key}",
        "modality": "voice",
        "tier": "flag",
        "priority": 0,
        "capabilities": ["speech", "asr"],
        **_FAKE_CFG,
    }
    base.update(extra)
    return base


class _Capture:
    """直挂 logger 抓记录，不用 caplog（`setup_logging` 把 propagate 关了，caplog 收不到）。"""

    def __init__(self, logger: logging.Logger, level: int):
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


def _capture(logger: logging.Logger, level: int) -> _Capture:
    return _Capture(logger, level)


# ---------------------------------------------------------------- ① entry 输入 ＋ ⑤ 默认兼容


def test_shipped_voice_roles_still_resolve_to_the_chat_transport():
    """§3 第 5 条：不给 `transport` 的既有 entry ⇒ 走的仍是今天那条 chat 路。

    现役 `DEFAULT_ROLES` 一条都没写 transport，所以这条是「老模型没被新字段拖进另一条路」的回归腿。
    """
    _require(llm_registry, "TRANSPORTS", "DEFAULT_TRANSPORT", "CFG_KEYS")
    _require(multimodal, "CHAT_TRANSPORT", "MULTIPART_TRANSPORT", "NO_TRANSPORT", "VOICE_TRANSPORTS")
    for role in llm_registry.DEFAULT_ROLES:
        value = role.get("transport", llm_registry.DEFAULT_TRANSPORT)
        assert value == "chat", f"entry {role['key']} 的 transport 变成 {value} 了"
    assert llm_registry.DEFAULT_TRANSPORT == "chat"
    assert multimodal.CHAT_TRANSPORT == llm_registry.DEFAULT_TRANSPORT


def test_default_chat_transport_keeps_the_chat_request_verbatim(monkeypatch):
    """①＋④：transport 缺省＝chat，请求形状与特征化轮钉的那一条逐字相同。"""
    reg = _registry_from(monkeypatch, [_role("voice_lt")])
    _require(reg, "transport_of")
    assert reg.transport_of("voice_lt") == "chat"

    llm = _RecordingLlm()
    out = _transcribe(llm, _FAKE_B64, "wav")
    assert out == "转写结果"
    _chat_leg_shape(llm)


# ---------------------------------------------------------------- ④ 调用处分派（§3 第 3 条）


def test_audio_transcriptions_entry_hits_multipart_with_file_and_model():
    """§3 第 3 条（正腿）：`audio_transcriptions` ⇒ multipart `POST {base}/audio/transcriptions`。

    校的是**请求形状**而不是计数：multipart 边界、`file` 部件（带文件名与 MIME 的真字节）、
    `model` 表单字段，以及「这不是 chat 请求体」（`messages`/`input_audio` 一律不许出现）。
    """
    sink = _MultipartSink()
    llm = _RecordingLlm()
    out = _transcribe(llm, _FAKE_B64, "wav", transport="audio_transcriptions", client=_sdk_client(sink))

    assert out == "转写好的中文"
    assert llm.calls == [], "multipart 腿不该再走 ChatOpenAI 的 invoke"
    assert len(sink.requests) == 1, f"应当一发 HTTP 请求，实际 {len(sink.requests)} 发"
    request = sink.requests[0]
    assert request.method == "POST"
    assert request.url.path == "/v1/audio/transcriptions"
    assert request.headers["content-type"].startswith("multipart/form-data")
    body = request.read()
    assert b'name="file"' in body, body[:400]
    assert b"filename=" in body and b"audio/wav" in body
    assert b"hello" in body, "base64 应当被还原成音频字节再放进 file 部件"
    assert b'name="model"' in body and b"Fake/ASR-V3.2" in body
    assert b"input_audio" not in body and b"messages" not in body


def test_multipart_leg_never_touches_the_chat_abstraction_even_for_ogg():
    """④：`不经过 ChatOpenAI 抽象`——格式映射表覆盖白名单，且始终零 `invoke`。"""
    for fmt, mime in (("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("ogg", "audio/ogg")):
        sink = _MultipartSink()
        llm = _RecordingLlm()
        _transcribe(llm, _FAKE_B64, fmt, transport="audio_transcriptions", client=_sdk_client(sink))
        assert len(sink.requests) == 1 and llm.calls == []
        assert mime.encode() in sink.requests[0].read()


def test_multipart_leg_failures_propagate_instead_of_degrading():
    """卡 §2 末：ASR 分支的异常**向上抛**，与语音侧现有纪律一致（不许换个地方复现静默）。"""
    sink = _MultipartSink(status=500)
    with pytest.raises(openai.APIStatusError):
        _transcribe(_RecordingLlm(), _FAKE_B64, "wav", transport="audio_transcriptions", client=_sdk_client(sink))
    assert len(sink.requests) == 1


def test_multipart_leg_uses_the_entry_root_client_when_none_is_injected():
    """缺省客户端腿：不注入 client 时走的是 entry 自己那只根客户端（不新建连接池）。

    base_url 是回环死端口 ⇒ 必然连接被拒，一个字节都出不去；这条只证「默认取的是根客户端」，
    所以红的形状是「没抛出连接类错误」而不是「抛了别的」。
    """
    llm = llm_registry._build({**_FAKE_CFG, "model": "Fake/ASR", "transport": "audio_transcriptions"})
    with pytest.raises(openai.APIConnectionError):
        _transcribe(llm, _FAKE_B64, "wav", transport="audio_transcriptions")


def test_none_transport_refuses_the_call_and_unknown_value_fails_loudly():
    """④ 的两条负腿：`none`＝显式拒答（不发请求、不静默回退 chat），拼错的值＝当场报错。"""
    llm = _RecordingLlm()
    with pytest.raises(Exception) as ei:
        _transcribe(llm, _FAKE_B64, "wav", transport="none")
    assert llm.calls == []
    assert "none" in str(ei.value)

    with pytest.raises(ValueError, match="whisper"):
        _transcribe(llm, _FAKE_B64, "wav", transport="whisper")
    assert llm.calls == []


# ---------------------------------------------------------------- ② cfg 白名单（§3 第 4 条）


def test_unknown_cfg_key_raises_instead_of_vanishing():
    """§3 第 4 条：白名单外的键（拼错 `transpor`）必须显式失败——今天它是无声消失的。

    正对照：同一个 cfg 写对 `transport` 就不报错，且构造出来的仍是 ChatOpenAI。
    """
    with pytest.raises(ValueError, match="transpor"):
        llm_registry._build({**_FAKE_CFG, "model": "Fake/Model", "transpor": "audio_transcriptions"})

    llm = llm_registry._build(
        {
            **_FAKE_CFG,
            "model": "Fake/Model",
            "translation_options": {"source_lang": "zh", "target_lang": "zh"},
            "transport": "audio_transcriptions",
        }
    )
    assert type(llm).__name__ == "ChatOpenAI"


def test_transport_never_leaks_into_the_request_body():
    """②：transport 是**分派标记**，不是请求体参数——它既不在 extra_body 也不在 model_kwargs。

    判据形式沿用特征化轮的闭集断言（复核指出「属性上不存在」是装饰性的）：
    白名单内的 `translation_options` 确实落进请求体，正证这条闭集不是打空。
    """
    llm = llm_registry._build(
        {
            **_FAKE_CFG,
            "model": "Fake/Model",
            "translation_options": {"source_lang": "zh", "target_lang": "zh"},
            "transport": "audio_transcriptions",
        }
    )
    assert "extra_body" not in (llm.model_kwargs or {}), llm.model_kwargs or {}
    body = getattr(llm, "extra_body", None) or {}
    assert body.get("translation_options") == {"source_lang": "zh", "target_lang": "zh"}
    assert set(body) == {"translation_options"}, sorted(body)


def test_build_rejects_a_transport_value_outside_the_closed_set():
    """②：值也要过白名单——`TRANSPORTS` 之外的值不许当成 chat 静默跑掉。"""
    _require(llm_registry, "TRANSPORTS")
    assert set(llm_registry.TRANSPORTS) == {"chat", "audio_transcriptions", "none"}
    with pytest.raises(ValueError, match="transport"):
        llm_registry._build({**_FAKE_CFG, "model": "Fake/Model", "transport": "transcription"})


def test_unknown_role_entry_key_is_logged_not_dropped(monkeypatch):
    """① 的入口面：`LLM_MODELS_JSON` 里拼错的键今天走到 `_load` 就没了 ⇒ 必须落日志留痕。

    刻意不在 entry 层 raise：现役 `.env` 里的条目本轮不可读也不可变，启动期炸整只 registry
    超出本票授权；「显式失败或落日志」里选落日志那半，cfg 层（第 2 段）仍按 raise 办。
    """
    records = _capture(logging.getLogger("legal.llm"), logging.WARNING)
    roles = [_role("voice_lt"), _role("voice_typo", transpor="audio_transcriptions")]
    with records:
        reg = _registry_from(monkeypatch, roles)
    _require(reg, "transport_of")
    assert reg.transport_of("voice_typo") == "chat", "拼错的键不许被当成 transport 生效"

    hits = [r for r in records.items if getattr(r, "llm_cfg_unknown_keys", None)]
    assert len(hits) == 1, f"未知 entry 键没有留痕：{[getattr(r, 'llm_cfg_unknown_keys', None) for r in records.items]}"
    assert hits[0].llm_cfg_unknown_keys == ["transpor"]
    assert "transpor" in json.dumps({k: v for k, v in vars(hits[0]).items() if k == "llm_cfg_unknown_keys"})
    # 正对照：干净条目不许每次都陪跑一条 warning
    assert len([r for r in records.items if getattr(r, "llm_cfg_unknown_keys", None)]) == 1


# ---------------------------------------------------------------- §5 单源与一处判据


def _cfg_key_reads_in(source: str, key: str) -> int:
    """数一段源码里 `cfg.get(key)`／`cfg[key]` 的**读法**次数（两种写法都要收）。"""
    total = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "cfg"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == key
            ):
                total += 1
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "cfg"
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == key
        ):
            total += 1
    return total


def _functions_reading_cfg_key(module_source: str, key: str) -> dict[str, int]:
    """按函数归属统计 cfg 读法（找「两处各存一份」这类漂移要用归属，不能只给总数）。"""
    out: dict[str, int] = {}
    for node in ast.walk(ast.parse(module_source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n = _cfg_key_reads_in(ast.unparse(node), key)
            if n:
                out[node.name] = n
    return out


def test_transport_is_read_from_cfg_in_exactly_one_place():
    """§5：`transport` 的 cfg 读取只许一处（第②段＝`_build`）。

    正对照：同一把尺量 `translation_options` 得到非空 ⇒ 尺本身没打空。
    反向对照（watch-it-fail）：手造一份「两处各读一次」的源码，同一函数必须报 2 个函数名——
    否则这条守卫就是恒真的装饰。
    """
    source = inspect.getsource(llm_registry)
    readers = _functions_reading_cfg_key(source, "transport")
    assert readers == {"_build": 1}, f"transport 的 cfg 读取散在了多处：{readers}"
    assert _cfg_key_reads_in(inspect.getsource(llm_registry._build), "transport") == 1

    assert _functions_reading_cfg_key(source, "translation_options"), "尺子打空：连已知键都数不出来"

    two_places = "\n".join(
        [
            "def a(cfg):",
            "    return cfg.get('transport')",
            "",
            "def b(cfg):",
            "    return cfg['transport']",
        ]
    )
    assert _functions_reading_cfg_key(two_places, "transport") == {"a": 1, "b": 1}

    # multimodal 不许回头去读 cfg／transport（那才是第二处真源：它的 transport 只从调用处拿参数）
    assert _cfg_key_reads_in(inspect.getsource(multimodal), "transport") == 0
    assert ".cfg" not in inspect.getsource(multimodal), "multimodal 回头读 entry.cfg ⇒ 出现第二处真源"


def test_multimodal_dispatch_is_a_single_point():
    """§5：分派点只一处——`transcribe_audio` 里不许出现第二条按 transport 值分岔的支路。

    判据是 AST 计数而非「我读了两遍觉得只有一处」；正对照是同一条尺在合成源码上数出 2。
    """
    _require(multimodal, "VOICE_TRANSPORTS")
    body = inspect.getsource(multimodal.transcribe_audio)
    tree = ast.parse(body)
    transport_compares = 0
    dispatch_lookups = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            constants = [n.value for n in [node.left, *node.comparators] if isinstance(n, ast.Constant)]
            if any(isinstance(c, str) and c in multimodal.VOICE_TRANSPORTS for c in constants):
                transport_compares += 1
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "_VOICE_DISPATCH":
            dispatch_lookups += 1
    assert transport_compares == 0, f"transcribe_audio 里出现 {transport_compares} 处分岔比较 ⇒ 分派点不止一处"
    assert dispatch_lookups == 1, f"分派表查了 {dispatch_lookups} 次"

    # 语音的两条传输路各只有一个落点：chat 腿只 `invoke` 一次、multipart 腿只引用 ASR 资源一次；
    # 且 multipart 那条绝不碰聊天抽象。（视觉的 `invoke` 在 describe_image 里，不属于本条作用面。）
    module = inspect.getsource(multimodal)
    chat_leg = inspect.getsource(multimodal._transcribe_chat)
    multipart_leg = inspect.getsource(multimodal._transcribe_multipart)
    assert chat_leg.count(".invoke(") == 1, "chat 腿的聊天抽象不止一处"
    assert multipart_leg.count(".invoke(") == 0, "multipart 腿又绕回了聊天抽象"
    assert module.count("audio.transcriptions") == 1, "multipart 端点出现了第二处"

    synthetic = "\n".join(
        [
            "def f(transport):",
            "    if transport == 'chat':",
            "        return 1",
            "    if transport == 'none':",
            "        return 2",
        ]
    )
    counts = sum(
        1
        for node in ast.walk(ast.parse(synthetic))
        if isinstance(node, ast.Compare)
        and any(
            isinstance(c.value, str) and c.value in multimodal.VOICE_TRANSPORTS
            for c in [node.left, *node.comparators]
            if isinstance(c, ast.Constant)
        )
    )
    assert counts == 2, "同一把尺在合成源码上数不出两处 ⇒ 判据是恒真的"


def test_registry_entry_is_the_only_store_of_transport(monkeypatch):
    """③：transport 挂在 entry 上、由调用方读；`pick()` 的公共返回形状不变。"""
    roles = [_role("voice_multipart", transport="audio_transcriptions"), _role("voice_plain")]
    reg = _registry_from(monkeypatch, roles)

    _require(reg, "transport_of")
    entry = reg._entries["voice_multipart"]
    _require(entry, "transport")
    assert entry.transport == "audio_transcriptions"
    assert entry.cfg["transport"] == entry.transport, "entry 与 cfg 两份真源漂移了"
    assert reg.transport_of("voice_plain") == "chat"
    assert reg.transport_of("没有这个 key") == "chat", "未知 key 不许把调用方拖进另一条路"

    key, llm = reg.pick("voice", "flag")
    assert (key, type(llm).__name__) == ("voice_multipart", "ChatOpenAI")
    assert reg.transport_of(key) == "audio_transcriptions"


def test_transport_names_are_the_same_words_on_both_sides():
    """②↔④：cfg 白名单与调用处分派表用的是同一套词（两处字面量，由本条钉住不许漂移）。"""
    _require(llm_registry, "TRANSPORTS")
    _require(multimodal, "VOICE_TRANSPORTS")
    assert set(llm_registry.TRANSPORTS) == set(multimodal.VOICE_TRANSPORTS)
    assert len(multimodal.VOICE_TRANSPORTS) == 3
