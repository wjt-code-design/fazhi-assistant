"""W07 特征化判据（票面 `:360-362`）——**2026-10-17 由 W07-IMPL 逐条改写**：语音曾只有一种传输形状，
而 cfg 白名单会把新键静默丢掉。

本轮 C04/C09 已裁（C04＝形状甲），transport 四段接缝落地 ⇒ 本文件按仓规「**改写旧尺，不许删**」
逐条转义。改前的现量字节在 head `15e6820`，改前/改后的读数在
`reports/execution-runs/fazhi-full-closeout-20261016-*/evidence/W07-IMPL-*-{before,after}.log`；
逐条「原钉 ⇒ 现钉 ⇒ 理由」记在派发票 §6 的回执里。新契约的行为判据住在
`test_multimodal_transport_impl.py`，本文件留的是**形状与闭集**那几把尺：

① 语音的**缺省**传输仍是 chat 形状：`multimodal.transcribe_audio` 用
   `HumanMessage(content=[input_audio, text])` 调 `invoke()`，且 chat 腿的请求里仍不带端点概念
   （multimodal.py 的 `_transcribe_chat`）——甲的回归腿，防改造打穿现役 Qwen livetranslate 路径。
② cfg 白名单：`translation_options` 落 extra_body、`transport` 落进分派但**不落请求体**，
   而白名单外的键（`transpor` 拼错）现在**构造期就 ValueError**——改前那一格是「不报错也不生效」，
   本条改成两个出口分开的闭集。
③ `_build` 读的 cfg 键按 **AST 穷举**钉成新闭集（多出 `transport` 那一个）；
   这条与第 2 条一起仍是「未知键静默丢」的唯一现量测量器具，所以只许改写不许删。
④ 前端产出的音频 MIME 必须落在后端白名单里（跨面判据，本轮一字未动）。

真端点/真音频样本腿（票面 `:363`）不在本轮：本机进程没有凭据，且没有既定中文音频样本 ⇒
按票面记 **BLOCKED**，不许用"形状兼容"冒充"转写正确"。
"""

import ast
import inspect
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import llm_registry  # noqa: E402
import multimodal  # noqa: E402

# 跨面契约：前端录出来的音频 MIME 必须是后端白名单里的成员
RECORDER_TS = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "recorder.ts"
FRONTEND_DIR = RECORDER_TS.parents[1]

# 假值：不写成任何像真凭据的形状（base_url 指回环死端口，绝不打出去）
_FAKE_CFG = {"api_key": "fake-value-not-a-secret", "base_url": "http://127.0.0.1:9/v1"}


class _RecordingLlm:
    """只记账的假语音模型：`invoke` 记录入参，返回固定转写文本。"""

    def __init__(self, content="转写结果"):
        self.calls = []
        self._content = content

    def invoke(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return SimpleNamespace(content=self._content)


def test_the_default_voice_transport_still_emits_chat_shaped_input_audio():
    """①（甲的回归腿）缺省 transport＝chat：那条 chat/completions 形状逐字不变。

    原钉「语音只有这一条传输路」⇒ 现钉「这一条仍是缺省那条，且 chat 腿的请求里不带端点概念」，
    理由：票 §1 ④ 加了第二条传输路（multipart），"唯一"这个词今天不成立了；但票 §3 第 5 条
    要求不给 transport 的旧条目行为逐字不变 ⇒ 形状断言一条都不许松。
    """
    llm = _RecordingLlm()
    out = multimodal.transcribe_audio(llm, "aGVsbG8=", "wav")
    assert out == "转写结果"
    assert len(llm.calls) == 1, f"语音调用应当一发，实际 {len(llm.calls)} 发"
    messages, kwargs = llm.calls[0]

    assert len(messages) == 1 and type(messages[0]).__name__ == "HumanMessage"
    parts = messages[0].content
    assert isinstance(parts, list) and [p["type"] for p in parts] == ["input_audio", "text"]
    # 空 MIME 前缀是实测合同（裸 base64 返回空），这里钉住它不会被哪天"顺手清理"掉
    assert parts[0]["input_audio"]["data"] == "data:;base64,aGVsbG8="
    assert parts[0]["input_audio"]["format"] == "wav"
    assert parts[1]["text"] == multimodal.AUDIO_PROMPT
    # 原钉：`kwargs == {}` 证「入参里根本没有端点/传输这个概念」。
    # 现钉：缺省腿仍然不带任何端点概念（transport 是**函数参数**，不会被转进聊天抽象）。
    assert kwargs == {}, sorted(kwargs)
    assert multimodal.CHAT_TRANSPORT == "chat", "缺省传输不再是 chat ⇒ 旧条目行为不再逐字不变"


def test_whitelisted_cfg_keys_take_effect_while_unknown_keys_are_rejected():
    """②（改写）：已知键生效且不落请求体；白名单外的键**构造期显式失败**。

    原钉「`transport` 在 cfg 里无声消失、构造期不报错」⇒ 现钉「`transport` 是白名单内的键
    （进分派但不进请求体），拼成 `transpor` 才 raise」，理由：票 §1 ② 与 §3 第 4 条要的正是
    「把配置写了但没人读从静默变成会红」；而请求体那个闭集仍是「别的东西一点都没漏进去」的尺，
    一条没删（复核轮把它从装饰性的 `getattr(llm, "transport", None)` 换成闭集，本轮继续背）。
    """
    llm = llm_registry._build(
        {
            **_FAKE_CFG,
            "model": "Fake/Model",
            "translation_options": {"source_lang": "zh", "target_lang": "zh"},
            "transport": "audio_transcriptions",
        }
    )
    # 新 SDK 把 `model_kwargs` 里的 extra_body **搬到独立字段**（构造时那条 UserWarning 就在说这件事）
    # ⇒ 只读 model_kwargs 会得到空 dict，这条判据就会绿在错的地方。两处都取一次，把搬家这件事也钉住。
    assert "extra_body" not in (llm.model_kwargs or {}), llm.model_kwargs or {}
    body = getattr(llm, "extra_body", None) or {}
    assert body.get("translation_options") == {"source_lang": "zh", "target_lang": "zh"}
    # 请求体键集仍是闭集：transport 只做分派，绝不被塞进聊天请求体
    assert set(body) == {"translation_options"}, sorted(body)
    assert type(llm).__name__ == "ChatOpenAI"

    with pytest.raises(ValueError, match="transpor"):
        llm_registry._build({**_FAKE_CFG, "model": "Fake/Model", "transpor": "audio_transcriptions"})


def test_build_reads_exactly_this_closed_set_of_cfg_keys():
    """③ `_build` 读的 cfg 键按 **AST 穷举**，不是按我读了三遍源码的印象。

    为什么穷举而不是列举：票面要的是「transport 标记从 entry 输入经过 cfg 白名单一路不丢」。
    改前这条链上根本没有 transport 这个键——要用"没有 X"的形状钉住，就必须把 X 可能出现的位置
    穷举完，并同时钉住**已有键确实在集合里**（否则正则打空也会得到空集，判据恒真）。
    本轮（W07-IMPL）把闭集**改写成含 transport 的新集合**，没删：它同时仍是
    「未知键静默丢」的唯一现量测量器具——集合少一个键会红，多一个键也会红。
    """
    tree = ast.parse(inspect.getsource(llm_registry._build))
    reads = set()
    for node in ast.walk(tree):
        # 两种读法都要收：`cfg.get("x")` 是 Call，`cfg["x"]` 是 Subscript。
        # 第一版我只收 Call ⇒ api_key/base_url/model 这三个下标读法全漏。
        # 集合变小不是"判据更严"，是量错了对象——这条靠下面的非空/成员正对照守住。
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr != "get" or not isinstance(node.func.value, ast.Name) or node.func.value.id != "cfg":
                continue
            if not node.args:
                continue
            key = node.args[0]
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "cfg":
            key = node.slice
        else:
            continue
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            reads.add(key.value)
    expected = {
        "api_key",
        "base_url",
        "model",
        "translation_options",
        "disable_thinking",
        "timeout",
        "transport",
    }
    assert reads == expected, sorted(reads)
    # 原钉 `"transport" not in reads` ⇒ 现钉它在集合里；`endpoint` 那半**保留**：
    # 本票裁的是 transport 分派，端点这个概念仍然不许出现在 cfg 读取里（两处各存一份的入口）。
    assert "transport" in reads and "endpoint" not in reads
    # 正对照：白名单里**有**一个真正会改变请求体的键（第 2 条已行为证过它落到 extra_body）。
    # 没有这条，"集合恰好等于我抄的这七个"会因为抄错而一直红，或因为打空而一直绿。
    assert "translation_options" in reads
    # 已知未覆盖点（写清楚，不留给下一轮猜）：share 分支里 `cfg.get(k)` 的 k 是
    # ("base_url", "api_key", "timeout") 循环里的**变量**，AST 收不到常量；
    # 那三个键已在集合内，所以覆盖面对得上，但本条穷举不覆盖"将来新增变量键循环"。
    # 另一处已知差集：`CFG_KEYS` 比本集合多一个 `capabilities`——它写进 cfg 给 ModelEntry 用，
    # `_build` 不读它，这是设计而不是漏项（见 llm_registry.CFG_KEYS 上方注释）。


def test_frontend_audio_mime_is_inside_the_backend_whitelist():
    """④ 跨面契约钉子（复核指出我"推迟给 W11"没有理由之后补的）。

    后端只收 `wav/mp3/m4a/flac/ogg`（`multimodal.AUDIO_EXTS`，chat_transcribe 里不在白名单直接 400），
    而前端 `lib/recorder.ts` 自己抓 PCM 编码成 `audio/wav`（文件头注释就写着这层原因）。
    两边各有一句注释 ⇒ 今天对得上，**但没有任何判据**：前端一旦换回 MediaRecorder 默认产物（webm/opus），
    后端会 400 而全部门禁仍绿。这里把"注释里的约定"变成判据。

    skip 只在整只 `frontend/` 不在场时发生（快照 lane 的树形状）；
    **在场而读不到 recorder 一律算红**——"扫不到就当通过"是我这一轮反复钉的假阴性机器，不能自己再造一台。
    """
    if not FRONTEND_DIR.is_dir():
        pytest.skip(f"整只 frontend 不在场（{FRONTEND_DIR}）⇒ 这条跨面判据无对象，跳；在场时不会跳")
    src = RECORDER_TS.read_text(encoding="utf-8")
    mimes = set(re.findall(r'type:\s*"audio/([A-Za-z0-9+\-.]+)"', src))
    assert mimes, "recorder.ts 里读不到任何 audio MIME 字面量 ⇒ 判据打空，不许当成通过"
    unsupported = {m for m in mimes if m not in multimodal.AUDIO_EXTS}
    assert not unsupported, f"前端产出 {sorted(unsupported)} 不在后端白名单 {list(multimodal.AUDIO_EXTS)} 内 ⇒ 真机 400"
