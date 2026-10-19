"""W06-B SSE 逐帧端到端补测（B11–B16 的 K16 证据缺口）。

用既有 `tests/_sse_harness.sse_client`（真 `/api/chat` + 真 `stream()` + 内存库）逐帧断言；
撤回时点由**缝替身**（`_qa_direct_return`/`_light_buffered`/`make_chain` 的链）在确定位置触发，
**不 sleep 赌时序**。阴性控制先证旧内容确实在待发产物里（防「本来就没引用」假绿）。

QA 命中由 `main.ks.search_eligible_qa` 替身返回合成 `QaHit`（score 0.8 ⇒ 只注入不直返；
score 0.95 ⇒ 触发直返），SQL 侧在内存库里合成一条可服务候选行（approved + human + 链闭合）。
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from langchain_core.documents import Document  # noqa: E402

import answer_cache  # noqa: E402
import database  # noqa: E402
import main  # noqa: E402
import qa_eligibility as qe  # noqa: E402
import quality  # noqa: E402
import retrieval  # noqa: E402
from models import QaCandidate  # noqa: E402
from tests import _sse_harness as harness  # noqa: E402

ANSWER = "G-OLD-ANSWER-旧产物"
EVIDENCE = json.dumps([{"source": "中华人民共和国劳动合同法", "article": "第十九条"}], ensure_ascii=False)
BASIS = "2026-08-23"
Q = "B-SSE 合成问题甲"


@pytest.fixture(autouse=True)
def _clean_cache():
    """`answer_cache` 是模块级共享 LRU，`sse_client` 不隔离它 ⇒ 逐用例清空，防跨用例串味假绿/假红。"""
    answer_cache.clear()
    yield
    answer_cache.clear()


def _kb(monkeypatch):
    """把「条文还在库」钉成给定读数（provenance/citation 两道判据的输入）。"""
    docs = [Document(page_content="第十九条 试用期……", metadata={"source": "劳动合同法", "article": "第十九条"})]
    monkeypatch.setattr(retrieval, "exact_article_lookup", lambda src, art, cutoff=None: docs)
    monkeypatch.setattr(main, "exact_article_lookup", lambda src, art, cutoff=None: docs)


def _seed(sm, doc_id="doc-g"):
    with sm() as s:
        row = QaCandidate(
            question=Q,
            answer=ANSWER,
            grounded_score=0.8,
            evidence=EVIDENCE,
            status="approved",
            approval_source="human",
            vector_doc_id=doc_id,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _revoke(sm, cand_id):
    with sm() as s:
        row = s.get(QaCandidate, cand_id)
        row.eligibility = "revoked"
        s.commit()


def _hit(cand_id, doc_id, score):
    h = qe.QaHit(
        {
            "question": Q,
            "answer": ANSWER,
            "score": score,
            "evidence": EVIDENCE,
            "law_as_of_basis": BASIS,
            "fingerprint": "",
            "qa_candidate_id": cand_id,
        }
    )
    h.doc_id = doc_id
    return h


def _unlinked_hit(score=0.8):
    h = qe.QaHit(
        {
            "question": Q,
            "answer": ANSWER,
            "score": score,
            "evidence": EVIDENCE,
            "law_as_of_basis": BASIS,
            "fingerprint": "",
            "qa_candidate_id": None,
        }
    )
    h.doc_id = None
    return h


def _prompt_text(messages) -> str:
    out = []
    for m in messages:
        c = getattr(m, "content", m)
        out.append(c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
    return "\n".join(out)


def _count_type(frames, kind) -> int:
    return sum(1 for p in harness.payload_frames(frames) if p.get("type") == kind)


def _count_done(frames) -> int:
    return sum(1 for f in frames if f.strip() == "data: [DONE]")


class _HookChain:
    """逐块产出 + 在指定块前后执行 hook（控制撤回时点，不 sleep）。"""

    def __init__(self, parts, *, sink=None, before=None, after=None):
        self._parts = parts
        self._sink = sink
        self._before = before  # 每块 yield 前调用
        self._after = after
        self.records = []

    def astream(self, messages):
        if self._sink is not None:
            self._sink.append(_prompt_text(messages))
        self.records.append(messages)

        async def generate():
            for index, piece in enumerate(self._parts):
                if self._before is not None:
                    self._before(index, piece)
                yield piece
                if self._after is not None:
                    self._after(index, piece)

        return generate()


class _EchoLLM:
    """轻量模型替身：按输入 messages 里有没有 G 回不同整答（用于分辨旧产物 vs 重建产物）。"""

    def invoke(self, messages):
        return harness._FakeResp("OLD-G-ANSWER" if "此前已确认的问答" in _prompt_text(messages) else "NEW-CLEAN")

    async def ainvoke(self, messages):
        return self.invoke(messages)


def _recorders(monkeypatch):
    posted, placeholders = [], []

    def _post(pre, answer, curate=True, **kwargs):  # 同步：产品经 run_in_threadpool 调用它（async 会不被 await）
        posted.append((pre, answer, curate))

    def _post_placeholder(pre, reason="no_response"):
        placeholders.append((pre, reason))

    monkeypatch.setattr(main, "_post", _post)
    monkeypatch.setattr(main, "_post_placeholder", _post_placeholder)
    return posted, placeholders


# ==================== B12：撤回在模型调用前提交 ⇒ 新模型输入不含 G ====================


def _b12_run(monkeypatch, *, revoke_before_model: bool):
    """共用心跳：seeding + QA 命中（注入用 score 0.8）；返回 (frames, captured_messages)。"""
    sm_ref = {}
    captured: list[str] = []
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        sm = database.SessionLocal
        sm_ref["sm"] = sm
        cand = _seed(sm, "doc-b12")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b12", 0.8))
        if revoke_before_model:

            def hooked_direct(pre, law_as_of=None):
                _revoke(sm, cand)
                return None

            monkeypatch.setattr(main, "_qa_direct_return", hooked_direct)
        monkeypatch.setattr(main, "make_chain", lambda llm: _HookChain(harness.FLAGSHIP_PARTS, sink=captured))
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")
    return frames, captured


def test_b12_target_revocation_before_model_removes_g_from_input(monkeypatch):
    """B12 目标：撤回在模型调用前提交 ⇒ 送进模型的新输入不含 G（重建生效）。"""
    frames, captured = _b12_run(monkeypatch, revoke_before_model=True)
    assert harness.content_of(frames), f"本条没有正文 ⇒ 判据对象不存在：{frames}"
    assert captured, "链没拿到 messages ⇒ 判据失去对象"
    assert "此前已确认的问答" not in captured[-1], "撤回后仍把 G 递进模型 ⇒ B12 未闭合"
    assert ANSWER not in captured[-1]


def test_b12_control_without_revocation_input_still_has_g(monkeypatch):
    """B12 阴性控制：不撤回时旧内容**确实**在待发 messages 里（防「本来就没引用」假绿）。"""
    frames, captured = _b12_run(monkeypatch, revoke_before_model=False)
    assert harness.content_of(frames)
    assert captured and "此前已确认的问答" in captured[-1] and ANSWER in captured[-1], (
        "控制腿没证明 G 在输入里 ⇒ 目标腿的「不含 G」可能只是本来就没引用"
    )


# ==================== B13：status 已发、content 未发；O 读前撤回 ⇒ 不发旧答案 ====================


def test_b13_direct_return_revoked_before_o_is_not_sent(monkeypatch):
    """B13（QA 直返）：准备完成后、O 读前撤回 ⇒ 不发旧直返答案；status 不算正文已开始；DONE/_post 各一次。"""
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        posted, _ = _recorders(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b13")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b13", 0.95))
        real_direct = main._qa_direct_return

        def direct_then_revoke(pre, law_as_of=None):
            ans = real_direct(pre, law_as_of)
            _revoke(sm, cand)  # 直返「准备完成」后、O 新鲜读之前提交撤回
            return ans

        monkeypatch.setattr(main, "_qa_direct_return", direct_then_revoke)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert frames and json.loads(frames[0][6:])["type"] == "status", f"首个帧不是 status：{frames[:2]}"
    assert ANSWER not in "".join(harness.content_of(frames)), "撤回后仍发旧直返答案 ⇒ B13 未闭合"
    assert harness.content_of(frames), "回退后应有正常生成正文"
    assert _count_done(frames) == 1, f"DONE 次数不为 1：{frames}"
    assert len(posted) == 1, f"_post 次数不为 1：{len(posted)}"


def test_b13_cache_entry_revoked_before_o_is_not_served(monkeypatch):
    """B13（精确缓存）：命中条目已取到、O 读前撤回 ⇒ miss、不发旧缓存答案；正常回退。"""
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        posted, _ = _recorders(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b13c")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: None)  # 本次请求无 QA
        dep = qe.capture_dependency(_hit(cand, "doc-b13c", 0.8))
        assert dep is not None
        stale = {"answer": ANSWER, "sources": [], "qa_dependencies": (dep,)}

        def get_then_revoke(key):
            _revoke(sm, cand)
            return stale

        monkeypatch.setattr(answer_cache, "get", get_then_revoke)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert ANSWER not in "".join(harness.content_of(frames)), "撤回后仍发旧缓存答案 ⇒ B13 缓存腿未闭合"
    assert harness.content_of(frames), "回退后应有正常生成正文"


def test_b13_control_cache_entry_without_revocation_is_served(monkeypatch):
    """B13 缓存腿阴性控制：不撤回时该条目**确实**会被零 token 直返（防假绿）。"""
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b13cc")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: None)
        dep = qe.capture_dependency(_hit(cand, "doc-b13cc", 0.8))
        stale = {"answer": ANSWER, "sources": [], "qa_dependencies": (dep,)}
        monkeypatch.setattr(answer_cache, "get", lambda key: stale)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert ANSWER in harness.content_of(frames), "控制腿没命中 ⇒ 目标腿的 miss 可能只是条目本身送不出去"


# ==================== B14：丢弃旧产物 + 重建 + 最多重做 1 次 ====================


def test_b14_light_buffered_discarded_and_redo_once(monkeypatch):
    """B14（轻量）：已缓冲整答含 G，撤回后 O 放行 ⇒ 丢弃旧产物、重建、重做恰好 1 次、只发重建产物。"""
    calls: list[str] = []
    with harness.sse_client(monkeypatch, route="light_buffered") as client:
        _kb(monkeypatch)
        posted, _ = _recorders(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b14l")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b14l", 0.8))
        monkeypatch.setattr(main, "_safe_pick", lambda modality, tier, **kw: ("light-test", _EchoLLM(), False))
        real_light = main._light_buffered

        async def light_then_revoke(pre, messages, law_as_of=None):
            calls.append(_prompt_text(messages))
            if len(calls) == 1:
                _revoke(sm, cand)
            return await real_light(pre, messages, law_as_of)

        monkeypatch.setattr(main, "_light_buffered", light_then_revoke)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    content = harness.content_of(frames)
    assert content == ["NEW-CLEAN"], f"旧产物未被丢弃/重建失效：{content}"
    assert len(calls) == 2, f"重做次数不为 1（调用 {len(calls)} 次）⇒ 无界重做风险"
    assert "此前已确认的问答" in calls[0] and "此前已确认的问答" not in calls[1], "重建输入仍含 G"
    assert len(posted) == 1 and posted[0][1] == "NEW-CLEAN", "成功 _post 的不是重建产物"


def test_b14_flagship_first_block_discarded_and_redo_once(monkeypatch):
    """B14（旗舰）：首块已取得未发 content，撤回后 O 放行 ⇒ 关闭旧生成器、丢弃、重做 1 次、只发重建产物。"""
    calls = {"n": 0}
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        posted, _ = _recorders(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b14f")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b14f", 0.8))

        def make_chain(llm):
            index = calls["n"]
            calls["n"] += 1

            def before(_i, _piece):
                if index == 0:
                    _revoke(sm, cand)

            parts = ("OLD-G-ANSWER",) if index == 0 else ("NEW-CLEAN",)
            return _HookChain(parts, before=before)

        monkeypatch.setattr(main, "make_chain", make_chain)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    content = harness.content_of(frames)
    assert content and "NEW-CLEAN" in content and "OLD-G-ANSWER" not in content, f"旧首块被发出：{content}"
    assert calls["n"] == 2, f"链工厂调用 {calls['n']} 次 ⇒ 重做不为 1"
    assert len(posted) == 1 and posted[0][1].startswith("NEW-CLEAN"), "成功 _post 的不是重建产物"


# ==================== B15：首条非空 content 已发 ⇒ 允许原流完成；W 拒绝写缓存 ====================


def test_b15_after_first_content_stream_completes_and_cache_write_rejected(monkeypatch):
    """B15：先消费首条非空 content，再撤回，继续消费 ⇒ 原流完成、不打断；W 拒写失效依赖缓存。"""
    puts: list[dict] = []
    with harness.sse_client(
        monkeypatch, route="flagship_stream", cache_put=lambda key, answer, sources, **kw: puts.append(kw)
    ) as client:
        _kb(monkeypatch)
        posted, _ = _recorders(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(True))
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b15")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b15", 0.8))

        def make_chain(llm):
            def after(index, _piece):
                if index == 0:
                    _revoke(sm, cand)  # 首条非空 content 已产出/发送之后

            return _HookChain(("P1", "P2"), after=after)

        monkeypatch.setattr(main, "make_chain", make_chain)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert harness.content_of(frames) == ["P1", "P2"], f"首正文后不给原流完成/被主动打断：{harness.content_of(frames)}"
    assert _count_type(frames, "restart") == 0, "首正文后不应再发 restart"
    assert _count_done(frames) == 1 and len(posted) == 1
    assert puts == [], f"W 未拒绝写失效依赖缓存：{puts}"


def test_b15_control_cache_write_happens_when_dependency_valid(monkeypatch):
    """B15 阴性控制：不撤回时同一路径**确实**会写缓存（防「本来就写不进」假绿）。"""
    puts: list[dict] = []
    with harness.sse_client(
        monkeypatch, route="flagship_stream", cache_put=lambda key, answer, sources, **kw: puts.append(kw)
    ) as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(True))
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b15c")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b15c", 0.8))
        monkeypatch.setattr(main, "make_chain", lambda llm: _HookChain(("P1", "P2")))
        token = harness.login(client)
        harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert len(puts) == 1, f"控制腿没写缓存 ⇒ 目标腿的「不写」不可信：{puts}"
    deps = puts[0].get("qa_dependencies")
    assert isinstance(deps, tuple) and len(deps) == 1, f"写点没显式传实际输入依赖：{deps}"


# ==================== B16：空 chunk 不算开始；重做失败明确结束 ====================


def test_b16_empty_chunk_is_not_a_content_start(monkeypatch):
    """B16：空 chunk 不算正文已开始 ⇒ 空块之后撤回，仍应在首个**非空**块处判失效并丢弃重做。"""
    calls = {"n": 0}
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b16e")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b16e", 0.8))

        def make_chain(llm):
            index = calls["n"]
            calls["n"] += 1

            def before(i, _piece):
                if index == 0 and i == 1:  # 空块(i=0)已发之后、首个非空块(i=1)之前撤回
                    _revoke(sm, cand)

            parts = ("", "OLD-G-ANSWER") if index == 0 else ("NEW-CLEAN",)
            return _HookChain(parts, before=before)

        monkeypatch.setattr(main, "make_chain", make_chain)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    content = harness.content_of(frames)
    assert "OLD-G-ANSWER" not in content, f"空块之后撤回没被当作未开始：{content}"
    assert "NEW-CLEAN" in content and calls["n"] == 2


def test_b16_redo_failure_ends_explicitly_without_cache_write(monkeypatch):
    """B16：重建后重做仍失败（空产物）⇒ 明确结束（error 帧）、不写缓存、不成功 _post。"""
    puts: list[dict] = []
    calls = {"n": 0}
    with harness.sse_client(
        monkeypatch, route="flagship_stream", cache_put=lambda key, answer, sources, **kw: puts.append(kw)
    ) as client:
        _kb(monkeypatch)
        posted, placeholders = _recorders(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(True))
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b16f")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b16f", 0.8))

        def make_chain(llm):
            index = calls["n"]
            calls["n"] += 1

            def before(_i, _piece):
                if index == 0:
                    _revoke(sm, cand)

            return _HookChain(("OLD-G-ANSWER",), before=before) if index == 0 else _HookChain(())

        monkeypatch.setattr(main, "make_chain", make_chain)
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert harness.error_of(frames), f"重做失败没有明确 error 帧：{frames}"
    assert "OLD-G-ANSWER" not in harness.content_of(frames)
    assert posted == [], f"重做失败却成功 _post 了旧产物：{posted}"
    assert puts == [], f"重做失败却写了缓存：{puts}"
    assert len(placeholders) == 1, f"未给出恰好一条占位：{len(placeholders)}"


# ==================== B11：3 处 put 端到端观察元数据（含无 QA / 有 QA 控制） ====================


def _capture_put(monkeypatch):
    puts: list[dict] = []
    monkeypatch.setattr(answer_cache, "put", lambda key, answer, sources, **kw: puts.append(kw))
    return puts


def test_b11_flagship_put_passes_actual_dependency(monkeypatch):
    """B11（旗舰/有 QA 控制）：写点显式传实际输入依赖（非空元组）。"""
    puts: list[dict] = []
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(True))
        puts = _capture_put(monkeypatch)
        sm = database.SessionLocal
        cand = _seed(sm, "doc-b11f")
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _hit(cand, "doc-b11f", 0.8))
        monkeypatch.setattr(main, "make_chain", lambda llm: _HookChain(harness.FLAGSHIP_PARTS))
        token = harness.login(client)
        harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert len(puts) == 1, f"旗舰有 QA 控制没写缓存：{puts}"
    deps = puts[0].get("qa_dependencies")
    assert isinstance(deps, tuple) and len(deps) == 1 and deps[0].candidate_id == cand


def test_b11_flagship_put_with_no_qa_signs_empty_tuple(monkeypatch):
    """B11（旗舰/无 QA 控制）：无 QA 的合法路径写点时显式签空 tuple。"""
    puts: list[dict] = []
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(True))
        puts = _capture_put(monkeypatch)
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: None)
        monkeypatch.setattr(main, "make_chain", lambda llm: _HookChain(harness.FLAGSHIP_PARTS))
        token = harness.login(client)
        harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert len(puts) == 1, f"旗舰无 QA 没写缓存：{puts}"
    assert puts[0].get("qa_dependencies") == (), f"无 QA 未签空 tuple：{puts[0].get('qa_dependencies')!r}"


def test_b11_light_put_with_no_qa_signs_empty_tuple(monkeypatch):
    """B11（轻量/无 QA 控制）：轻量写点同样显式签空 tuple。"""
    puts: list[dict] = []
    with harness.sse_client(monkeypatch, route="light_buffered") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        puts = _capture_put(monkeypatch)
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: None)
        token = harness.login(client)
        harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert len(puts) == 1 and puts[0].get("qa_dependencies") == (), f"轻量无 QA 未签空 tuple：{puts}"


def test_b11_contract_put_with_no_qa_signs_empty_tuple(monkeypatch):
    """B11（合同/无 QA 控制）：合同写点显式签空 tuple。"""
    puts: list[dict] = []
    with harness.sse_client(monkeypatch, route="contract_review", flagship_parts=harness.CONTRACT_PARTS) as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        puts = _capture_put(monkeypatch)
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: None)
        token = harness.login(client)
        harness.chat_frames(client, token, "请审查这份合同的风险")

    assert len(puts) == 1 and puts[0].get("qa_dependencies") == (), f"合同无 QA 未签空 tuple：{puts}"


def test_b11_unlinked_qa_put_omitted_because_dependency_unknown(monkeypatch):
    """B11（有 QA 但身份不可靠 ⇒ 漏传 None ⇒ 不缓存）：无链 QA 参与生成，答案不进缓存。"""
    puts: list[dict] = []
    with harness.sse_client(monkeypatch, route="flagship_stream") as client:
        _kb(monkeypatch)
        _recorders(monkeypatch)
        monkeypatch.setattr(quality, "self_check", lambda answer, ctx: quality.Verdict(True))
        puts = _capture_put(monkeypatch)
        monkeypatch.setattr(main.ks, "search_eligible_qa", lambda query: _unlinked_hit(0.8))
        monkeypatch.setattr(main, "make_chain", lambda llm: _HookChain(harness.FLAGSHIP_PARTS))
        token = harness.login(client)
        frames = harness.chat_frames(client, token, "请说明这件劳动争议的处理原则")

    assert harness.content_of(frames), "无链 QA 生成应继续（直接读取资格不变，B08）"
    assert puts == [], f"依赖未知(None)却仍写缓存：{puts}"
