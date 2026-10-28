"""`case_domain` 的**评测通道闸**（与 `law_as_of` 同款；Owner 2026-09-21 裁定的另一半）。

背景：`/api/chat` 的普通认证请求原本就能传 `case_domain`（决定 R1-OB 判域），
「生产前端不传」不是信任边界（前端实测确实不传，但任何人都能传）。
裁定：与 `law_as_of` 同款处理——定位为**评测/灰度输入**，`settings.allow_client_case_domain=False`
（默认）⇒ 客户端传值被忽略。当前 Agent Path 零流量 ⇒ 默认关在生产**零行为变化**。

**判据分两层（诚实标注可达层级）**：
  ① **单元级**：`main._client_case_domain(body)` —— 关 ⇒ None；开 ⇒ 原值。
  ② **回归守卫**：`main.py` 里**不得存在闸外的客户端直读**（`body.case_domain` 只允许出现在
     `_client_case_domain` 内）——防将来有人新增一处未过闸的读取（law_as_of 那轮的评审正是
     以"是否覆盖全部消费点"为核心问题）。
  ❌ **本文件没有端点级用例**：`case_domain` 的唯一消费点在** agent 启用分支**内
     （`main.py` 的 `if not settings.agent_enabled:` 之后），而 `tests/_sse_harness.py` 只提供
     `flagship_stream` / `light_buffered` / `contract_review` 三条 route，**没有 agent 路由** ⇒
     端点级暂时不可达。agent 路径启用并补上其 harness 后，应在此文件补端点级用例（见文末 TODO）。
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402
import settings as settings_mod  # noqa: E402

MAIN_SRC = pathlib.Path(__file__).resolve().parent.parent / "main.py"


class _Body:
    """`_client_case_domain` 只读 `body.case_domain` ⇒ 最小替身即可。"""

    def __init__(self, case_domain):
        self.case_domain = case_domain


def test_gate_ignores_client_value_when_off(monkeypatch):
    """① 先红：开关默认关 ⇒ 客户端传的 case_domain 必须被忽略（返回 None）。"""
    monkeypatch.setattr(settings_mod.settings, "allow_client_case_domain", False)
    got = main._client_case_domain(_Body("labor"))
    assert got is None, f"默认关时必须忽略客户端值，实得 {got!r}"


def test_gate_passes_value_when_on(monkeypatch):
    """① 控制腿：开关开 ⇒ 原值透传（评测通道可用）。"""
    monkeypatch.setattr(settings_mod.settings, "allow_client_case_domain", True)
    assert main._client_case_domain(_Body("labor")) == "labor"


def test_gate_none_stays_none_when_on(monkeypatch):
    """① 控制腿：没传（None）在开关开时仍是 None（不编造默认域）。"""
    monkeypatch.setattr(settings_mod.settings, "allow_client_case_domain", True)
    assert main._client_case_domain(_Body(None)) is None


def test_no_ungated_client_read_of_case_domain_in_main():
    """② 回归守卫：`body.case_domain` 只允许出现在 `_client_case_domain` 内。

    将来若有人新增一处直读（绕过闸），本用例变红——这正是 law_as_of 那轮评审
    最关心的"是否覆盖全部消费点"。
    """
    src = MAIN_SRC.read_text(encoding="utf-8")
    hits = [m.start() for m in re.finditer(r"body\.case_domain", src)]
    assert hits, "主源码里找不到 `body.case_domain`（改名了？本守卫需同步更新）"

    accessor = re.search(r"def _client_case_domain\(.*?\n(?=\ndef |\nclass )", src, re.S)
    assert accessor is not None, "找不到 `_client_case_domain` 定义（闸不存在？）"
    lo, hi = accessor.span()
    outside = [h for h in hits if not (lo <= h < hi)]
    assert not outside, (
        "存在**闸外**的 `body.case_domain` 直读（行号={}）——必须改为 `_client_case_domain(body)`".format(
            [src[:h].count("\n") + 1 for h in outside]
        )
    )


# TODO（agent 路径启用时补）：端点级用例——harness 增 agent route 后，
# 断言默认关时 `_bootstrap_only` 收到的 case_domain 实参为 None（透传锁）。
