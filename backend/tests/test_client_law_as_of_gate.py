"""R15 安全观察整改：客户端 `law_as_of` 的**评测通道闸**（Owner 2026-09-21 裁定 A）。

背景：`/api/chat` 的普通认证请求原本就能传 `law_as_of`（直接改变"用哪天的法"与证据 cutoff，
也进票 I-2(a) 护栏）——「生产前端不传」不是信任边界。裁定：定位为**评测通道**，
`settings.allow_client_law_as_of=False`（默认）⇒ 客户端传值被忽略。

判据（4 条 = 1 先红 + 3 控制）：
  ① 先红（端点级）：开关默认关 + 请求带分水岭前的 `law_as_of` ⇒ light 路径**实际生效**的
     基准日必须是**当日**（改前是 2019-01-01，透传锁先红）；
  ② 控制（端点级）：开关开 ⇒ 生效基准日 = 2019-01-01（评测通道可用）；
  ③ 控制：开关关 + 未传 ⇒ `_client_law_as_of` 返回 None（与"没传"一致）；
  ④ 快路径：`_fast_path_law_as_of` 同口径（关 ⇒ 当日；开 ⇒ 原值）。

⚠️ 透传锁钉在**真正的消费点**上：light 路径的 `law_as_of` 消费者是
`_fast_path_law_as_of(body)`（分支1 直接调用），而 `_bootstrap_only` 在 light 路由下
**只收 5 个参数、根本不传 law_as_of**（实测 bindings：user_id/conversation_id/text/image/
client_truncated）——第一版把锁钉在 `_bootstrap_only` 上 ⇒ 控制腿假红。
端点级锁 = monkeypatch `main._fast_path_law_as_of` 包一层"记录返回值再转发"。
"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402
import settings as settings_mod  # noqa: E402
from tests._sse_harness import chat_frames, login, sse_client  # noqa: E402

PRE_WATERSHED = "2019-01-01"
QUESTION = "试用期最长多久"


class _Body:
    """`_client_law_as_of` / `_fast_path_law_as_of` 只读 `body.law_as_of` ⇒ 最小替身即可。"""

    def __init__(self, law_as_of):
        self.law_as_of = law_as_of


def _reset_shared_state() -> None:
    """清掉进程级 `answer_cache`（与 test_flagship_quality 同款卫生）。

    ⚠️ 不清的后果（ticket J 已踩过一次，本文件又踩一次）：同问题的缓存条目会让请求在
    分支0（缓存命中）直接返回 ⇒ 后面的分支与透传锁根本不会被调用 ⇒ 端点级断言测了个寂寞。
    """
    import answer_cache

    answer_cache.clear()


def _wire_fast_path_spy(monkeypatch, captured: dict) -> None:
    """把 `main._fast_path_law_as_of` 包一层"记录**生效基准日**再转发"的透传锁。"""
    real = main._fast_path_law_as_of

    def _spy(body):
        effective = real(body)
        captured["effective"] = effective
        captured["client_value"] = body.law_as_of
        return effective

    monkeypatch.setattr(main, "_fast_path_law_as_of", _spy)


def test_default_ignores_client_law_as_of_at_endpoint(monkeypatch):
    """先红（端点级）：开关默认关 + 请求带 2019-01-01 ⇒ 生效基准日必须是**当日**。

    改前形态：`_fast_path_law_as_of` 直接 `body.law_as_of or date.today()` ⇒ 生效日 = 2019-01-01
    （即"任何用户都能让系统用 2019 年的法/触发护栏回落"）。
    """
    captured: dict = {}
    with sse_client(monkeypatch, route="light_buffered") as c:
        _reset_shared_state()
        _wire_fast_path_spy(monkeypatch, captured)
        monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", False)
        token = login(c)
        chat_frames(c, token, QUESTION, extra={"law_as_of": PRE_WATERSHED})

    assert captured.get("client_value") is not None, "请求里的 law_as_of 没到达端点（夹具问题）"
    assert captured.get("effective") == date.today(), (
        f"开关默认关时生效基准日必须落当日（忽略客户端值），实得 {captured.get('effective')!r}"
    )


def test_control_switch_on_allows_eval_value(monkeypatch):
    """控制腿（端点级）：开关开 ⇒ 生效基准日 = 客户端原值（评测通道可用）。"""
    captured: dict = {}
    with sse_client(monkeypatch, route="light_buffered") as c:
        _reset_shared_state()
        _wire_fast_path_spy(monkeypatch, captured)
        monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", True)
        token = login(c)
        chat_frames(c, token, QUESTION, extra={"law_as_of": PRE_WATERSHED})

    assert captured.get("effective") == date(2019, 1, 1), f"评测通道应原值放行，实得 {captured.get('effective')!r}"


def test_control_absent_value_stays_none(monkeypatch):
    """控制腿：开关关 + 客户端没传 ⇒ `_client_law_as_of` 返回 None（与"没传"一致）。"""
    assert main._client_law_as_of(_Body(None)) is None


def test_fast_path_uses_same_gate(monkeypatch):
    """快路径同口径（单元级）：关 ⇒ 当日（生产默认路径不变）；开 ⇒ 原值；未传 ⇒ 当日。"""
    monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", False)
    assert main._fast_path_law_as_of(_Body(date(2019, 1, 1))) == date.today()
    assert main._fast_path_law_as_of(_Body(None)) == date.today()
    monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", True)
    assert main._fast_path_law_as_of(_Body(date(2019, 1, 1))) == date(2019, 1, 1)
    assert main._fast_path_law_as_of(_Body(None)) == date.today()
