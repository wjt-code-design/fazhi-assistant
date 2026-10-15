"""公开历史查询：默认可用；显式关闭时拒绝；所选日期写入结构化审计。"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import sys
from datetime import date

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import main  # noqa: E402
import settings as settings_mod  # noqa: E402
from tests._sse_harness import chat_frames, login, sse_client  # noqa: E402

PRE_WATERSHED = "2019-01-01"
QUESTION = "试用期最长多久"
MAIN_SRC = pathlib.Path(__file__).resolve().parent.parent / "main.py"


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


def test_default_allows_client_law_as_of_at_endpoint(monkeypatch):
    assert settings_mod.Settings.model_fields["allow_client_law_as_of"].default is True
    captured: dict = {}
    with sse_client(monkeypatch, route="light_buffered") as c:
        _reset_shared_state()
        _wire_fast_path_spy(monkeypatch, captured)
        monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", True)
        token = login(c)
        chat_frames(c, token, QUESTION, extra={"law_as_of": PRE_WATERSHED})

    assert captured.get("client_value") is not None, "请求里的 law_as_of 没到达端点（夹具问题）"
    assert captured.get("effective") == date(2019, 1, 1)


def test_public_date_reaches_fast_retrieval(monkeypatch):
    seen_cutoffs = []
    with sse_client(monkeypatch, route="light_buffered") as c:
        _reset_shared_state()
        monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", True)
        monkeypatch.setattr(main, "retrieve", lambda query, k, cutoff=None: seen_cutoffs.append(cutoff) or [])
        token = login(c)
        chat_frames(c, token, QUESTION, extra={"law_as_of": PRE_WATERSHED})
    assert seen_cutoffs == [PRE_WATERSHED]


def test_explicit_date_disables_shared_answer_cache():
    pre = {
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "sources": [{"source": "旧法", "article": "第一条"}],
        "law_as_of": date(2019, 1, 1),
    }
    assert main._cacheable(pre) is False


def test_disabled_historical_query_returns_503(monkeypatch):
    with sse_client(monkeypatch, route="light_buffered") as c:
        monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", False)
        token = login(c)
        response = c.post(
            "/api/chat",
            json={"content": QUESTION, "law_as_of": PRE_WATERSHED},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 503
    assert "历史查询" in response.json()["detail"]


def test_historical_query_audit_has_ids_and_date_without_question(monkeypatch):
    from observability import _JsonFormatter

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("legal.chat")
    handler = Capture()
    with sse_client(monkeypatch, route="light_buffered") as c:
        logger.addHandler(handler)
        try:
            _reset_shared_state()
            monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", True)
            token = login(c)
            frames = chat_frames(c, token, QUESTION, extra={"law_as_of": PRE_WATERSHED})
        finally:
            logger.removeHandler(handler)

    audit = [record for record in records if getattr(record, "kind", None) == "historical_law_query"]
    assert len(audit) == 1
    payload = json.loads(_JsonFormatter().format(audit[0]))
    response_conv_id = next(
        json.loads(frame[6:])["conversation_id"]
        for frame in frames
        if frame.startswith("data: {") and "conversation_id" in frame
    )
    assert payload["user_id"] > 0
    assert payload["conv_id"] == response_conv_id
    assert payload["law_as_of"] == PRE_WATERSHED
    assert QUESTION not in json.dumps(payload, ensure_ascii=False)


def test_control_absent_value_stays_none(monkeypatch):
    monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", False)
    assert main._client_law_as_of(_Body(None)) is None


def test_fast_path_uses_same_gate(monkeypatch):
    monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", False)
    with pytest.raises(HTTPException) as exc:
        main._fast_path_law_as_of(_Body(date(2019, 1, 1)))
    assert exc.value.status_code == 503
    assert main._fast_path_law_as_of(_Body(None)) == date.today()
    monkeypatch.setattr(settings_mod.settings, "allow_client_law_as_of", True)
    assert main._fast_path_law_as_of(_Body(date(2019, 1, 1))) == date(2019, 1, 1)
    assert main._fast_path_law_as_of(_Body(None)) == date.today()


def test_no_ungated_client_read_of_law_as_of_in_main():
    """回归守卫：`body.law_as_of` 只允许出现在 `_client_law_as_of` 内（与 `case_domain` 同款）。

    该闸口现在还是 503 的唯一发出处 ⇒ 任何闸外直读都不只是"绕过评测通道"，
    而是让一个部署已关闭历史查询的实例重新变成静默改用当日。
    """
    src = MAIN_SRC.read_text(encoding="utf-8")
    hits = [m.start() for m in re.finditer(r"body\.law_as_of", src)]
    assert hits, "主源码里找不到 `body.law_as_of`（改名了？本守卫需同步更新）"

    accessor = re.search(r"def _client_law_as_of\(.*?\n(?=\ndef |\nclass )", src, re.S)
    assert accessor is not None, "找不到 `_client_law_as_of` 定义（闸不存在？）"
    lo, hi = accessor.span()
    outside = [h for h in hits if not (lo <= h < hi)]
    assert not outside, "存在**闸外**的 `body.law_as_of` 直读（行号={}）——必须改为 `_client_law_as_of(body)`".format(
        [src[:h].count("\n") + 1 for h in outside]
    )


def test_exit_law_as_of_prefers_the_baseline_the_request_retrieved_with():
    """降级出口的基准日必须来自**本次取数所用**的日期，而不是拿 body 重算。

    恢复分支技术性降级时日期在 run 上、body 里没有 ⇒ 重算得今日，于是版本绊线
    用现行法去判历史证据、日志也把 `law_as_of` 记成今日。
    """
    historical = date(2019, 1, 1)
    assert main._exit_law_as_of({"law_as_of": historical}, _Body(None)) == historical
    # 未指定历史时逐字不变：body 无日期 ⇒ 当日；body 有日期 ⇒ 该日期
    assert main._exit_law_as_of({}, _Body(None)) == date.today()
    assert main._exit_law_as_of({}, _Body(historical)) == historical


def test_no_fast_path_exit_recomputes_the_baseline_from_body_only():
    """回归守卫：`_fast_path_law_as_of(body)` 只允许出现在 `_exit_law_as_of` 内（与闸口守卫同款）。

    四个出口（QA 直返 / 轻量缓冲 / 流式版本绊线两条腿）各自重算 ⇒ 降级路径上
    `pre["law_as_of"]` 与出口拿到的值可以不同，而这个差异没有任何用例会红。
    """
    src = MAIN_SRC.read_text(encoding="utf-8")
    hits = [m.start() for m in re.finditer(r"(?<!def )_fast_path_law_as_of\(body\)", src)]
    assert hits, "主源码里找不到 `_fast_path_law_as_of(body)` 调用（改名了？本守卫需同步更新）"

    accessor = re.search(r"def _exit_law_as_of\(.*?\n(?=\ndef |\nclass )", src, re.S)
    assert accessor is not None, "找不到 `_exit_law_as_of` ⇒ 出口没有统一取基准日，降级路径必然各算各的"
    lo, hi = accessor.span()
    outside = [h for h in hits if not (lo <= h < hi)]
    assert not outside, "存在 `_exit_law_as_of` 之外的按 body 重算（行号={}）".format(
        [src[:h].count("\n") + 1 for h in outside]
    )
