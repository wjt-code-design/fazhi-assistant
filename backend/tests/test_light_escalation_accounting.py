"""R20：轻量 L 自检失败升级旗舰 F 重答后，**两个模型各记各的账**。

改前 `_LightResult(fraw, fkey, ..., usage + fusage, ...)`：结果 key=F、用量=L+F，
而调用点只有 `registry.deduct(res.key, res.usage)` ⇒ L 的用量被一并扣在 F 头上，
L 的配额账**从不被扣**（看门狗对 L 的剩余量永远乐观）。

端点级而非单元级：改的是"调用点怎么记账"，直调 `_light_buffered_locked` 看不到那一步。
⚠️ 默认角色表没有 `('text','light')` 角色（票面已标注"默认不可达"）⇒ 本文件走
`sse_client(route="light_buffered")`（该 route 把四个合取项逐个造真）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402
import quality  # noqa: E402
from llm_registry import estimate_tokens  # noqa: E402
from tests._sse_harness import (  # noqa: E402
    LIGHT_ANSWER,
    _FakeInvokableLLM,
    chat_frames,
    login,
    sse_client,
)

FLAG_ANSWER = "旗舰重答正文，用于区分 L 与 F 的账。"


def test_light_escalation_charges_each_model_its_own_tokens(monkeypatch):
    deducted: list[tuple[str, int]] = []
    verdicts = {
        "n": 0,
    }

    def fake_self_check(answer, context_present):
        verdicts["n"] += 1
        # 第一次（轻量 L）判 FAIL → 触发升级；第二次（旗舰 F）判 PASS → 采用 F 的正文
        return quality.Verdict(False, reason="vague") if verdicts["n"] == 1 else quality.Verdict(True)

    with sse_client(monkeypatch, route="light_buffered", light_text=LIGHT_ANSWER) as c:
        # 桩必须在夹具**之内**再打一次：夹具已把这些名字换成自己的替身。
        monkeypatch.setattr(quality, "self_check", fake_self_check)
        monkeypatch.setattr(
            main.registry, "pick", lambda modality, tier, **kw: ("flag-other", _FakeInvokableLLM(FLAG_ANSWER))
        )
        monkeypatch.setattr(main.registry, "deduct", lambda key, tokens: deducted.append((key, tokens)))
        frames = chat_frames(c, login(c), "租赁合同押金不退怎么办")

    texts = "".join(f for f in frames if f.startswith("data: "))
    assert FLAG_ANSWER in texts, f"没走到升级后的旗舰正文（本条是空枪）：{frames}"
    assert deducted == [
        ("light-test", estimate_tokens(LIGHT_ANSWER)),
        ("flag-other", estimate_tokens(FLAG_ANSWER)),
    ], f"记账不是逐调用各记各的：{deducted}"
