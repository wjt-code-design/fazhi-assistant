"""票 H：合同出口（登记表 E5/E6）的两道闸 —— 写缓存闸与配额降级注记（2026-09-20）。

为什么必须是**端点级**：两道闸都长在 `stream()` 的分支0.3 里，单元层直调合同分支看不到调用点
（票 J 已踩过一次同形状的坑，见 §0.5.2 与 `_sse_harness` docstring）。本文件一律走
`sse_client(route="contract_review")`。

判据口径（票 H §0 第 1/2 条）：
- **先红**：每条断言都先看过它为**正确的原因**红（功能缺失，不是 TypeError/笔误）。
- **控制腿**：声称"拦住了错答"的用例，必须配一条"该放行时确实放行"的用例——否则改坏了也报绿。
- 断言只写**符号 + 唯一形状**，不写行号（本仓行号已漂过五次）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest

from tests._sse_harness import CONTRACT_ANSWER, CONTRACT_PARTS, chat_frames, login, sse_client

CONTRACT_QUESTION = "帮我审一下这份租赁合同"


def _contract_client(monkeypatch, **kw):
    return sse_client(monkeypatch, route="contract_review", flagship_parts=CONTRACT_PARTS, **kw)


def _contents(frames: list[str]) -> list[str]:
    """从原始帧序列里取出所有正文帧的 `content`（非正文帧/状态帧/空行一律跳过）。"""
    out: list[str] = []
    for f in frames:
        if not f.startswith("data: "):
            continue
        payload = f[len("data: ") :].strip()
        if payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except ValueError:
            continue
        if isinstance(obj, dict) and "content" in obj:
            out.append(obj["content"])
    return out


def _errors(frames: list[str]) -> list[str]:
    out: list[str] = []
    for f in frames:
        if not f.startswith("data: "):
            continue
        try:
            obj = json.loads(f[len("data: ") :].strip())
        except ValueError:
            continue
        if isinstance(obj, dict) and "error" in obj:
            out.append(obj["error"])
    return out


@pytest.fixture
def client(monkeypatch):
    with _contract_client(monkeypatch) as c:
        yield c


# ───────────────────────── H-2 取证：合同分支的 failover 收场有几种 ─────────────────────────


def test_contract_failover_endings_are_characterized(client, monkeypatch, tmp_path):
    """把"failover 全灭"的收场逐个数出来（打桩计数，不推断），读数落盘成证据文件。

    三种收场各自构造：
    ① 正常产出（既有 `client` 夹具）→ 报告正文帧；
    ② **三次尝试全部"空内容、无异常"** → `stream_with_retry` 正常返回、`answer == ""`；
    ③ **末次尝试抛异常** → `stream_with_retry` 上抛 → 外层 `except Exception`。
    """
    import answer_cache
    import main

    token = login(client)

    # ① 正常
    answer_cache.clear()
    normal = chat_frames(client, token, CONTRACT_QUESTION)

    # ② 全空内容：`flagship_parts=()` ⇒ `_FakeChain.astream` 一个非空块都不产
    monkeypatch.setattr(main, "make_chain", lambda llm: _FakeChainEmpty())
    answer_cache.clear()
    empty = chat_frames(client, token, CONTRACT_QUESTION)

    # ③ 末次尝试抛异常：三次都抛 ⇒ 只有 i == len(configs)-1 那一次会上抛
    calls = {"n": 0}

    class _Boom:
        async def astream(self, messages):  # noqa: ARG002
            calls["n"] += 1
            raise RuntimeError("boom")
            yield  # pragma: no cover - 让它成为异步生成器

    monkeypatch.setattr(main, "make_chain", lambda llm: _Boom())
    answer_cache.clear()
    raised = chat_frames(client, token, CONTRACT_QUESTION)

    readings = {
        "normal_contents": _contents(normal),
        "normal_errors": _errors(normal),
        "empty_contents": _contents(empty),
        "empty_errors": _errors(empty),
        "raised_contents": _contents(raised),
        "raised_errors": _errors(raised),
        "boom_astream_calls": calls["n"],
    }
    (tmp_path / "contract-failover-endings.json").write_text(
        json.dumps(readings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(readings, ensure_ascii=False, indent=2))

    # ① 正常收场：报告正文可达（且引用校验替身恒返回空 ⇒ 无告警注记）
    assert "".join(_contents(normal)) == CONTRACT_ANSWER
    assert _errors(normal) == []
    # ② 全空收场：**静默**——没有 error 帧（票面 H-2 假设的"落到外层 error 帧"在"全空内容"这一支不成立）
    assert _contents(empty) == []
    assert _errors(empty) == []
    # ③ 异常上抛收场：外层 error 帧（票面 H-2 描述的那一支）
    assert _errors(raised) == ["服务暂时无响应，请稍后重试"]
    assert calls["n"] == 3, "三次 config 都应被尝试过（否则 on_model_failure 的推进语义变了）"


class _FakeChainEmpty:
    """`astream` 一个非空块都不产（对比 `_sse_harness._FakeChain` 的"产两块"）。"""

    async def astream(self, messages):  # noqa: ARG002
        for p in ():
            yield p  # pragma: no cover - 迭代空元组
        return


# ───────────────────────── H-1：引用未收录的合同报告不得进缓存 ─────────────────────────


def _put_spy(monkeypatch) -> list[dict]:
    """把 `answer_cache.put` 换成记录器。

    桩点必须是 `answer_cache.put`（main 是以模块属性调用的），不是 `main.answer_cache`——
    两者都行，但认前者更贴近真实调用形状。
    """
    import answer_cache

    sink: list[dict] = []

    def _put(key, answer, sources, **kw):
        sink.append({"key": key, "answer": answer, "sources": sources, "model": kw.get("model", "")})

    monkeypatch.setattr(answer_cache, "put", _put)
    return sink


def test_bad_citation_report_is_not_cached(monkeypatch):
    """先红：合同报告的引用未收录时，缓存里**一次写入都不能有**。

    改前形状：`bad = citation_verify(answer)` 的**下一行**就是 `if cache_key:`，没看 `bad`
    ⇒ 一条"引用未收录"的报告以「无告警」形态进缓存，被零 token 复播时丢掉那条告警。
    """
    import main

    with _contract_client(monkeypatch) as c:
        # ⚠️ 两个替身都必须在 **sse_client 进入之后**打：夹具内部对 `main.citation_verify`
        # 与 `main._safe_pick` 各有一份默认桩，先打会被它覆盖（本用例第一版就这么红错的）。
        monkeypatch.setattr(main, "citation_verify", lambda a, in_kb=None: ["《民法典》第九百九十九条"])
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, CONTRACT_QUESTION)

    # 报告本身照常下发 + 告警注记帧仍在（本票不删告警，只拦缓存）
    joined = "".join(_contents(frames))
    assert joined.startswith(CONTRACT_ANSWER)
    assert "未在知识库中检索到" in joined
    assert sink == [], f"引用未收录的合同报告进了缓存：{sink}"


def test_control_good_report_is_still_cached_once(monkeypatch):
    """控制腿：`bad` 为空时**必须**仍写缓存一次，且写进去的就是不带注记的报告正文。

    没有这条腿，「把特性改没了却报成修好了」也能全绿。
    """
    import main

    with _contract_client(monkeypatch) as c:
        monkeypatch.setattr(main, "citation_verify", lambda a, in_kb=None: [])
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, CONTRACT_QUESTION)

    assert "".join(_contents(frames)) == CONTRACT_ANSWER
    assert len(sink) == 1, f"干净报告应恰好写一次缓存，实得 {len(sink)}"
    assert sink[0]["answer"] == CONTRACT_ANSWER
    assert sink[0]["model"] == "contract_review"


# ───────────────────────── H-2：合同报告的配额降级必须明说 ─────────────────────────


def test_degraded_contract_report_carries_quota_note(monkeypatch):
    """先红：`flag_degraded`（回退模型本身不可用）时合同报告必须追加 NOTE_QUOTA 注记帧。

    流式出口（登记表 E13）早就这么做了；合同分支此前**没有任何降级出口** ⇒ 用户看到一份
    "看起来正常"的报告，却不知道它是耗尽模型后硬出的。
    """
    import main

    with _contract_client(monkeypatch) as c:
        sink = _put_spy(monkeypatch)
        monkeypatch.setattr(main, "_safe_pick", lambda modality, tier, **kw: ("flag-test", object(), True))
        token = login(c)
        frames = chat_frames(c, token, CONTRACT_QUESTION)

    joined = "".join(_contents(frames))
    assert main.NOTE_QUOTA in joined, "降级产出未明说（应追加 NOTE_QUOTA 注记帧）"
    assert sink == [], "降级报告不得进缓存（否则复播时掉免责注）"


def test_control_non_degraded_report_has_no_quota_note(monkeypatch):
    """控制腿：未降级时**不得**出现 NOTE_QUOTA（否则注记变成噪音、且这条断言恒真）。"""
    import main

    with _contract_client(monkeypatch) as c:
        monkeypatch.setattr(main, "citation_verify", lambda a, in_kb=None: [])
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, CONTRACT_QUESTION)

    joined = "".join(_contents(frames))
    assert main.NOTE_QUOTA not in joined
    assert joined == CONTRACT_ANSWER
    assert len(sink) == 1
