"""票 J：轻量缓冲出口（登记表 E7）的闸门对齐 —— 多选完整性 / 确定性写闸 / 降级信号（2026-09-20）。

为什么**只能**是端点级（票面 J-3 第二条硬提醒）：本票改的三处（多选症状检测、写缓存闸条件集、
降级信号）都在 `stream()` 的**调用点**上，而单元级直调 `_light_buffered` 看不见调用点 ——
上一轮 `capture_light_baseline.py` 就是这么给过一次"平凡相同"的 sha。⇒ 一律走
`sse_client(route="light_buffered")`（登记表里那条叫 **E7**）。

⚠️ 本票**线上效果为零**（J-3：`llm_registry` 实配只有 `('text','flag')` ⇒ `use_light` 恒假）。
所以本文件的读数**不是**"线上已生效"，只是"两条出口的闸门形状已对称"。别拿它当评测收益的证据。

判据口径（票面 §0 第 1/2 条）：每条新断言都先看过它为**正确的原因**红（功能缺失，不是 TypeError）；
声称"拦住了"的用例必须配一条"该放行时确实放行"的控制腿。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from llm_registry import QuotaExhausted
from tests._sse_harness import LIGHT_ANSWER, chat_frames, login, sse_client
from tests.test_quality import _ANS_FULL, _ANS_SINGLE, _MULTI_Q

PLAIN_QUESTION = "试用期最长多久"
CITED_IN_KB = "根据《劳动合同法》第十九条，试用期最长六个月。"
CITED_FOREIGN = "根据《民法典》第五百七十七条，违约方应承担违约责任。"
DEGRADED_RAW = "本案应结合具体情形判断。"


def _light_client(monkeypatch, **kw):
    return sse_client(monkeypatch, route="light_buffered", **kw)


def _payloads(frames: list[str]) -> list[dict]:
    """原始帧序列 → 已解析的 JSON 载荷（状态帧/空行/`[DONE]`/非 dict 一律跳过）。"""
    out: list[dict] = []
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
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _contents(frames: list[str]) -> list[str]:
    return [p["content"] for p in _payloads(frames) if "content" in p]


def _put_spy(monkeypatch) -> list[dict]:
    """把 `answer_cache.put` 换成记录器（同票 H：桩点必须是 `answer_cache.put`）。"""
    import answer_cache

    sink: list[dict] = []

    def _put(key, answer, sources, **kw):
        sink.append({"key": key, "answer": answer, "model": kw.get("model", "")})

    monkeypatch.setattr(answer_cache, "put", _put)
    return sink


def _multi_note() -> str:
    """取多选注记文本（**唯一真源** = `main.NOTE_MULTI_INCOMPLETE`，见票 J §J-2「不许重写规则」）。

    刻意用**显式断言**而不是 `getattr(..., "")` 兜底：
    - 常量缺失时这里给出 `AssertionError: main 里没有 NOTE_MULTI_INCOMPLETE 常量`——
      是"功能缺失"的干净红因，而不是 `AttributeError`（票面 §0 判据 1 要求红因不是 TypeError/笔误）；
    - 反过来也不给"默认空串"留路：若有人日后删了常量，`"" in joined` 会恒真 ⇒ 那才是空枪。
    """
    import main

    assert hasattr(main, "NOTE_MULTI_INCOMPLETE"), "main 里没有 NOTE_MULTI_INCOMPLETE 常量（注记无唯一真源）"
    return main.NOTE_MULTI_INCOMPLETE


def _log_spy(monkeypatch) -> list[dict]:
    import main

    recs: list[dict] = []
    monkeypatch.setattr(main, "log_account", lambda **kw: recs.append(kw))
    return recs


def _focus_route(monkeypatch) -> None:
    """把请求钉死在分支1（轻量）上：合同分支与相似缓存都得让路，否则判据会串到别的出口。

    ⚠️ 这些桩必须写在 `with sse_client(...)` **块内**：夹具内部对 `main.citation_verify` /
    `main._safe_pick` 有默认桩，写在块外会被它覆盖（票 H 红错过一次）。
    """
    import main

    monkeypatch.setattr(main, "is_contract_review", lambda t: False)
    monkeypatch.setattr(main, "_similar_cache_hit", lambda pre: None)


def _study_aid_route_with_one_hit(monkeypatch) -> None:
    """把请求钉成 study_aid，**并且保证检索有命中**。

    ⚠️ 只改 `classify_intent` 不够（第一版就是这么造出一条**恒真的空枪**）：`prepare_fast_path`
    对 study_aid 走 `feature_study_retrieval` 那一支，该开关为假时 `docs` 被硬置为 `[]`
    ⇒ `sources` 为空 ⇒ `_cacheable` 判假 ⇒ **`cache_key` 为 None** ⇒ 写缓存闸根本不会被求值，
    `assert sink == []` 于是恒真（为错的原因绿）。必须先让 `sources` 非空，判据才有分辨率。
    """
    from langchain_core.documents import Document

    import main

    def _one_hit(q):  # noqa: ARG001 - 形参由 retrieve_exam 决定
        return [Document(page_content="第十九条 试用期…", metadata={"source": "劳动合同法", "article": "第十九条"})]

    monkeypatch.setattr(main, "classify_intent", lambda t: "study_aid")
    monkeypatch.setattr(main.settings, "feature_study_cache", True)
    monkeypatch.setattr(main.settings, "feature_study_retrieval", True)
    monkeypatch.setattr(main, "scenario_supplement_docs", lambda t: [])
    monkeypatch.setattr(main, "retrieve_exam", _one_hit)


# ───────────────────── J-2(a)：多选漏答的症状检测 + 注记 + 拦缓存 ─────────────────────


def test_light_path_flags_multi_incomplete_and_blocks_cache(monkeypatch):
    """先红：轻量出口对"多选题只给一个正确项"必须追加注记帧且**不写缓存**。

    改前形态：`quality.multi_incomplete` 全仓只有流式分支一处调用点（票面 J-1 的读数）
    ⇒ 轻量路径的多选漏答零防护，而法考多选题恰恰最可能被路由到轻量档。
    """

    with _light_client(monkeypatch, light_text=_ANS_SINGLE) as c:
        _focus_route(monkeypatch)
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, _MULTI_Q)

    joined = "".join(_contents(frames))
    assert joined.startswith(_ANS_SINGLE), "整答应原样下发"
    # 主判据放**最前**：改前树上这一条先红，红因就是"错答进了缓存"这个缺陷本身，
    # 而不是后面那句"常量缺失"（间接形状）—— 判据要红在为它存在的那件事上。
    assert sink == [], f"多选漏答的答复进了缓存：{sink}"
    assert _multi_note() in joined, "多选漏答必须显式注记（不静默）"


def test_control_light_path_does_not_flag_full_multi_answer(monkeypatch):
    """控制腿：三个正确项都给了（同一道多选题）⇒ 不得出现注记，且必须**照常写一次缓存**。

    没有这条腿，「把多选检测写成恒真」也能让上一条全绿。
    "注记没被误发"由 `joined == _ANS_FULL` **等价覆盖**（注记是追加在 answer 尾部的，误发必然改变它），
    所以这里刻意**不**去读注记常量 —— 否则这条控制腿会在改前树上死于"常量不存在"，
    失去"两侧都绿"这条控制腿该有的性质。
    """

    with _light_client(monkeypatch, light_text=_ANS_FULL) as c:
        _focus_route(monkeypatch)
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, _MULTI_Q)

    assert "".join(_contents(frames)) == _ANS_FULL
    assert len(sink) == 1, f"完整答案应恰好写一次缓存，实得 {len(sink)}"


def test_control_light_path_plain_question_still_cached(monkeypatch):
    """控制腿：非多选题 ⇒ 不注记且照常写缓存（防"把缓存写没了却报成修好了"）。同上，用等值断言覆盖。"""

    with _light_client(monkeypatch) as c:
        _focus_route(monkeypatch)
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, PLAIN_QUESTION)

    assert "".join(_contents(frames)) == LIGHT_ANSWER
    assert len(sink) == 1, f"普通问答应恰好写一次缓存，实得 {len(sink)}"


# ───────────────────── J-2(b)：`_cache_write_ok` 对轻量路径同样生效 ─────────────────────


def test_light_path_cache_write_ok_blocks_foreign_citation(monkeypatch):
    """先红：study_aid 的引用若不在本轮检索条文里，轻量出口**不得**写缓存。

    改前形态：轻量那条闸只有 `cache_key` / `verdict` / `law_version_hit`，
    对 `_cache_write_ok` **无任何对应物**（票面 J-1 原文）。
    """

    with _light_client(monkeypatch, light_text=CITED_FOREIGN) as c:
        _focus_route(monkeypatch)
        _study_aid_route_with_one_hit(monkeypatch)
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, PLAIN_QUESTION)

    assert CITED_FOREIGN in "".join(_contents(frames))
    assert sink == [], f"引用不在检索条文内的答案进了缓存：{sink}"


def test_control_light_path_cache_write_ok_allows_retrieved_citation(monkeypatch):
    """控制腿：引用 ⊆ 本轮检索条文时，`_cache_write_ok` 必须放行（仍写一次）。

    这条腿同时是上一条的**分辨率证明**：同一个请求形状（同 question / 同 study_aid / 同检索）
    在本控制腿里确实写出了缓存 ⇒ 上一条的 `sink == []` 是**被闸拦下**，不是"压根没有 cache_key"。
    """

    with _light_client(monkeypatch, light_text=CITED_IN_KB) as c:
        _focus_route(monkeypatch)
        _study_aid_route_with_one_hit(monkeypatch)
        sink = _put_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, PLAIN_QUESTION)

    assert CITED_IN_KB in "".join(_contents(frames))
    assert len(sink) == 1, f"引用 ⊆ 检索条文的答案应写一次缓存，实得 {len(sink)}"


# ───────────────────── J-2(c)：独立降级信号（不复用 verdict） ─────────────────────


def test_light_path_degraded_signal_is_independent_from_verdict(monkeypatch):
    """先红：升级旗舰时配额耗尽 ⇒ 独立降级信号点亮，且与 verdict **同现于一张日志**。

    改前形态：`_LightResult` 没有降级字段，降级只能从 `verdict` 里那个 "low_quota" 字符串反推
    ⇒ 与自检归因挤在同一个字段里（票面 J-1 说的"归因粒度比流式粗"）。
    """
    import main
    import quality

    with _light_client(monkeypatch, light_text=DEGRADED_RAW) as c:
        _focus_route(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(False, "vague"))

        def _pick_exhausted(modality, tier, **kw):
            raise QuotaExhausted()

        monkeypatch.setattr(main.registry, "pick", _pick_exhausted)
        sink = _put_spy(monkeypatch)
        recs = _log_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, PLAIN_QUESTION)

    joined = "".join(_contents(frames))
    assert main.NOTE_QUOTA in joined, "降级产出必须明说（NOTE_QUOTA）"
    light_logs = [r for r in recs if r.get("tier") == "light"]
    assert light_logs, f"轻量分支应落一条 account 日志，实得 {[r.get('tier') for r in recs]}"
    rec = light_logs[-1]
    assert rec.get("degraded") is True, f"降级信号未独立落盘：{rec}"
    assert rec.get("verdict") != "pass", "两条降级原因必须能同时读出（verdict + degraded）"
    assert sink == [], "降级产物不得进缓存（复播时会掉免责注）"


def test_control_light_path_non_degraded_records_false_and_caches(monkeypatch):
    """控制腿：同一请求形状（legal_query + 自检 PASS）⇒ **照常写一次缓存**。

    这条腿是降级那条的**分辨率证明**：形状相同却能写出缓存 ⇒ 降级那条的 `sink == []`
    是被 `verdict` / `not res.degraded` 拦下的，不是"压根没有 cache_key"。
    （其中 `degraded is False` 那半句是**新字段**的取值断言：改前源码里根本没有这个键，
    所以它在改前是红的——它不算"两侧都绿"的控制项，真正的控制项是 `len(sink) == 1`。）
    """

    with _light_client(monkeypatch) as c:
        _focus_route(monkeypatch)
        sink = _put_spy(monkeypatch)
        recs = _log_spy(monkeypatch)
        token = login(c)
        frames = chat_frames(c, token, PLAIN_QUESTION)

    assert "".join(_contents(frames)) == LIGHT_ANSWER
    light_logs = [r for r in recs if r.get("tier") == "light"]
    assert light_logs, f"轻量分支应落一条 account 日志，实得 {[r.get('tier') for r in recs]}"
    assert light_logs[-1].get("degraded") is False
    assert len(sink) == 1, f"未降级的普通问答应写一次缓存，实得 {len(sink)}"
