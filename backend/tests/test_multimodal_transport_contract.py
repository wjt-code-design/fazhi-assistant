"""W07 特征化（零外发半，票面 `:360-362`）：语音**只有一种传输形状**，而 cfg 白名单会把新键**静默丢掉**。

C04（图片失败可见性）与 C09（非文本能力额度）都还没裁，所以本文件**不改任何行为**，只把四件事钉成现量：

① 语音→文字在产品里只有一条路：`multimodal.transcribe_audio` 用 `HumanMessage(content=[input_audio, text])`
   调 `invoke()`（multimodal.py:115-130）——也就是 **chat/completions 形状**。
   Owner 指定的 `XingChenAGI/XingChenASR-V3.2-Ultra` 需要 multipart `/v1/audio/transcriptions`
   （该外部证据由另一会话的端点探测给出，**不是本文件测的**）；本文件能测的是：
   产品发出的请求形状与"端点/传输"这个概念**完全无关**，所以任何需要另一种端点的模型都只能在供应商侧吃 400。
   票面 `:361` 说「不要把 ASR 强塞进 ChatOpenAI 的聊天抽象」——今天就是那个形状。
② `_build` 只读它认识的 cfg 键（AST 穷举见第 3 条），**未知键不报错也不生效**
   ⇒ 将来加 `transport` 标记时，"配置写了但没人读"这件事**不会有任何信号**（正是票面 `:361`
   「设置不丢」要防的失效）。同一条 cfg 里 `translation_options` 确实会落到 extra_body，
   所以这条断言不是"我传了个空 dict"造成的空转。
④ 前端产出的音频 MIME 必须落在后端白名单里（第 4 条）——这条是复核指出我「推迟给 W11 却没有 C 格理由」之后补的跨面判据。
   ③ 语音条目建出来的对象类型就是 `ChatOpenAI`（llm_registry.py:376-414 唯一出口）——
   传输层的**唯一**可变点是 extra_body 与 client 复用，没有端点分派。

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


def test_the_only_voice_transport_is_chat_shaped_input_audio():
    """① 语音出口今天只发 chat 形状，端点/传输这个概念在入参里根本不存在。"""
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
    # 没有第二个参数携带端点/传输 ⇒ 想换 /audio/transcriptions 只能改代码，改配置换不掉
    assert kwargs == {}, sorted(kwargs)


def test_unknown_cfg_keys_are_dropped_without_any_signal():
    """② 同一份 cfg：白名单内的键落到请求体，白名单外的键**无声消失**。"""
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
    # 请求体键集也钉成闭集：只断言 `getattr(llm,"transport",None) is None` 是装饰性的
    # （这个属性本来就不可能出现在 ChatOpenAI 上），"body 里没有它"才是要害。
    assert set(body) == {"translation_options"}, sorted(body)
    # 构造期也不报错——所以"配置写了但没人读"这条没有任何失败信号，只能靠判据拦
    assert type(llm).__name__ == "ChatOpenAI"


def test_build_reads_exactly_this_closed_set_of_cfg_keys():
    """③ `_build` 读的 cfg 键按 **AST 穷举**，不是按我读了三遍源码的印象。

    为什么穷举而不是列举：票面要的是「transport 标记从 entry 输入经过 cfg 白名单一路不丢」。
    今天这条链上根本没有 transport 这个键——要用"没有 X"的形状钉住，就必须把 X 可能出现的位置
    穷举完，并同时钉住**已有键确实在集合里**（否则正则打空也会得到空集，判据恒真）。
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
    expected = {"api_key", "base_url", "model", "translation_options", "disable_thinking", "timeout"}
    assert reads == expected, sorted(reads)
    assert "transport" not in reads and "endpoint" not in reads
    # 正对照：白名单里**有**一个真正会改变请求体的键（第 2 条已行为证过它落到 extra_body）。
    # 没有这条，"集合恰好等于我抄的这六个"会因为抄错而一直红，或因为打空而一直绿。
    assert "translation_options" in reads
    # 已知未覆盖点（写清楚，不留给下一轮猜）：share 分支里 `cfg.get(k)` 的 k 是
    # ("base_url", "api_key", "timeout") 循环里的**变量**，AST 收不到常量；
    # 那三个键已在集合内，所以覆盖面对得上，但本条穷举不覆盖"将来新增变量键循环"。


def test_frontend_audio_mime_is_inside_the_backend_whitelist():
    """④ 跨面契约钉子（复核指出我"推迟给 W11"没有理由之后补的）。

    后端只收 `wav/mp3/m4a/flac/ogg`（multimodal.py:112，`main.py:1722-1723` 处直接 400），
    而前端 `lib/recorder.ts:72` 自己抓 PCM 编码成 `audio/wav`（:2 的注释就写着这层原因）。
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
