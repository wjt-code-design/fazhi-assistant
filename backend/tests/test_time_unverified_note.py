"""S0-c：显式历史基准日 + 证据时效未核验 ⇒ 答案层注记，**逐出口点名**。

票面：`docs/h1-law-version-collision-tickets-20260926.md` §S0-c（Q2/Q4/Q5 裁决）
判据本体：`main._time_unverified_hit`（全仓唯一一份）· 措辞真源：`main.NOTE_TIME_UNVERIFIED`
登记表列：`gate_exit_registry.COLUMNS` 的「时效未核验注记」

为什么必须逐出口、且清单必须绑登记表（而不是"抽一条代表"）：Owner 裁决原文是"判据不许写成
『确认各出口都加了注记』"——本仓已在"所有出口都挡了"这句话上漏过平行入口两次（票 C §2c 的 E9、
票 H 的 E6）。所以本文件：
  ① 出口清单来自 `gate_exit_registry.EXITS`（**手写那份会在下一次加出口时悄悄失效**）；
  ② 每格断言的是**注记文本出现在该出口产出的答案/帧里**（不是"函数被调用过"）；
  ③ 判"不适用"的出口也要留一条取证腿（NA 不是免检，见 E2）。

期望值来源（§6-② 独立性）：版本绊线那条用例**复用** `tests/test_fast_path_law_version_gate.py`
的样本表，不在这里另抄一份法条结论（两张表会各自漂移）。

⚠️ 本文件不写 `main.py:NNNN`（ADR-018/R4：行号在本仓已漂过五次）。
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from datetime import date
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from langchain_core.documents import Document  # noqa: E402

import clarify
import main  # noqa: E402
from gate_exit_registry import COLUMNS, EXITS  # noqa: E402
from tests._sse_harness import (  # noqa: E402
    CONTRACT_PARTS,
    FLAGSHIP_PARTS,
    LIGHT_ANSWER,
    chat_frames,
    login,
    sse_client,
)
from tests.test_fast_path_law_version_gate import (  # noqa: E402
    CLAIM_S01_WRONG_CURRENT_LAW,
    FACT_W01_2019,
)

NOTE = main.NOTE_TIME_UNVERIFIED
CELL = "时效未核验注记"

AS_OF = date(2026, 9, 1)  # 分水岭之后的显式历史基准日（本文件不测分水岭，只测"用了历史基准日"）
QUESTION = "试用期最长可以约定多久？"

# 现网形状：既无 `status` 也无日期 ⇒ `time_validity_state` = unknown
# （E7 清点读数：真实库 10266 条全是这一类，见 docs/e7-legacy-undated-corpus-inventory-20260926.md）
UNDATED: tuple[Document, ...] = (
    Document(page_content="第十九条 试用期…", metadata={"source": "劳动合同法", "article": "第十九条"}),
)
# 对照组：日期齐 + 显式现行 ⇒ verified ⇒ 不该注记（防"注记只跟基准日走"这种半截判据）
DATED: tuple[Document, ...] = (
    Document(
        page_content="第十九条 试用期…",
        metadata={
            "source": "劳动合同法",
            "article": "第十九条",
            "status": "现行",
            "effective_from": "2008-01-01",
            "effective_to": "",
        },
    ),
)


# ════════ 出口清单绑登记表（元测试见文件末） ════════
# 值 = 覆盖该出口的**本文件**用例名；空元组 = 该出口按结构不产注记（理由必须写在登记表那一格里）。
S0C_CASES: dict[str, tuple[str, ...]] = {
    "E1": ("test_e1_annotated_answers_never_enter_the_shared_cache",),
    "E2": ("test_e2_has_no_note_timing_under_explicit_basis",),
    "E3": ("test_e3_clarify_template_carries_no_note",),
    "E4": ("test_e4_contract_clarify_template_carries_no_note",),
    "E19": ("test_e19_contract_intent_confirm_template_carries_no_note",),
    "E20": ("test_e20_missing_source_note_declares_the_gap",),
    "E5": ("test_e5_contract_report_answer_carries_the_note",),
    "E6": (),
    "E7": ("test_e7_light_buffered_answer_carries_the_note_inline",),
    "E8": ("test_e8_streaming_answer_carries_the_note",),
    "E9": ("test_e9_fallback_answer_carries_the_note",),
    "E10": (),
    "E11": (),
    "E12": (),
    "E13": (),
    "E14": ("test_e17_frame_precedes_the_version_note",),
    "E15": (),
    "E16": (),
    "E17": ("test_e8_streaming_answer_carries_the_note", "test_e17_frame_precedes_the_version_note"),
    "E18": ("test_e5_contract_report_answer_carries_the_note",),
}


def contents_of(frames: list[str]) -> list[str]:
    """SSE 原始帧 → 正文帧的 `content` 列表（顺序即语义；非正文帧跳过）。"""
    out: list[str] = []
    for f in frames:
        if not f.startswith("data: ") or f.strip() == "data: [DONE]":
            continue
        try:
            obj = json.loads(f[len("data: ") :])
        except ValueError:
            continue
        if isinstance(obj, dict) and "content" in obj:
            out.append(obj["content"])
    return out


def _ask(
    monkeypatch,
    *,
    route: str = "flagship_stream",
    parts: tuple[str, ...] = FLAGSHIP_PARTS,
    light_text: str = LIGHT_ANSWER,
    fallback_text: str | None = None,
    as_of: date | None = AS_OF,
    docs: tuple[Document, ...] = UNDATED,
    tune: Callable[[Any], None] | None = None,
    question: str = QUESTION,
) -> list[str]:
    """端点级打一次 `/api/chat`，返回原始帧。

    `main.retrieve` 的再桩**必须在 `sse_client` 之内**：夹具自己已经把 `retrieve` 换成
    `_one_hit_retrieval`，在它之前 patch 会被静默覆盖（`test_stream_exit_law_version_gate.py`
    对 `make_chain` 记过同一条仪器事实）。

    `quality.self_check` 默认替成 PASS，理由与那份文件同款：**为了鉴别力**。不桩的话样本答复
    会同时触发 E12（自检 FAIL），`cs[-1] == NOTE` 就可能红在别的注记上 —— 那测的不是本票。
    """
    previous_allow_client_law_as_of = main.settings.allow_client_law_as_of
    main.settings.allow_client_law_as_of = True
    import answer_cache
    import quality

    try:
        answer_cache.clear()
        with sse_client(
            monkeypatch,
            route=route,
            flagship_parts=parts,
            light_text=light_text,
            fallback_text=fallback_text,
        ) as c:
            monkeypatch.setattr(main, "retrieve", lambda q, k=4, cutoff=None: list(docs))
            monkeypatch.setattr(quality, "self_check", lambda a, cp: quality.Verdict(True))
            if tune is not None:
                tune(monkeypatch)
            payload = {"law_as_of": as_of.isoformat()} if as_of else None
            return chat_frames(c, login(c), question, payload)
    finally:
        main.settings.allow_client_law_as_of = previous_allow_client_law_as_of


# ════════ ① 判据本体（单元腿：两个条件缺一不可） ════════


def test_judgement_requires_both_conditions():
    """只有基准日 / 只有未核验证据 / 两者都在 ⇒ 只有第三种才注记。"""
    hit = main._time_unverified_hit
    assert hit({"law_as_of": AS_OF, "sources": [dict(m.metadata) for m in UNDATED]}) is True
    assert hit({"sources": [dict(m.metadata) for m in UNDATED]}) is False, "无显式基准日却注记 ⇒ 现行业务被改"
    assert hit({"law_as_of": AS_OF, "sources": [dict(m.metadata) for m in DATED]}) is False, "证据可核验仍注记"
    assert hit({"law_as_of": AS_OF, "sources": []}) is False


def test_request_helper_restores_client_date_setting(monkeypatch):
    monkeypatch.setattr(main.settings, "allow_client_law_as_of", False)
    _ask(monkeypatch)
    assert main.settings.allow_client_law_as_of is False


def test_note_wording_does_not_collide_with_self_check_markers():
    """注记会进 `quality.self_check` 的输入 ⇒ 措辞撞上 `_HONEST_REFUSE_MARKS` 等于给每条注记答复发免死牌。

    不是洁癖：`self_check` 用 `any(m in text)` 判"诚实拒答"，注记里出现"未收录"三字就会把
    "无据硬答"洗成通过；撞上 `VAGUE_PHRASES` 则反向把正常答复判成含糊。
    """
    import quality
    from domain_rules import VAGUE_PHRASES

    assert not [m for m in quality._HONEST_REFUSE_MARKS if m in NOTE], NOTE
    assert not [p for p in VAGUE_PHRASES if p in NOTE], NOTE


# ════════ ② 承流量生成出口：E8 / E9 / E7 / E5（正向，逐帧断言） ════════


def test_e8_streaming_answer_carries_the_note(monkeypatch):
    """E8（旗舰流式增量，主承流量）+ E17：注记是**单独一帧**，追加在流式分片之后。"""
    cs = contents_of(_ask(monkeypatch))
    assert cs[: len(FLAGSHIP_PARTS)] == list(FLAGSHIP_PARTS), f"分片被改写：{cs}"
    assert cs[-1] == NOTE, f"流式出口没产注记帧 ⇒ E17 没接上：{cs}"


def test_e9_fallback_answer_carries_the_note(monkeypatch):
    """E9（`_invoke_llm` 兜底整答）：流式返空时注记不能一起消失（票 C §2c 那个"漏 return 点"的形状）。

    判据写在两条答案来源**合流之后** ⇒ 本条同时证明"合流点没有只覆盖流式那一支"。
    """
    cs = contents_of(_ask(monkeypatch, parts=(), fallback_text="试用期最长六个月。"))
    assert cs[0] == "试用期最长六个月。", f"兜底整答帧不符：{cs}"
    assert cs[-1] == NOTE, f"兜底来源没被注记覆盖 ⇒ 流式一空答注记就整体消失：{cs}"


def test_e7_light_buffered_answer_carries_the_note_inline(monkeypatch):
    """E7（缓冲轻量整答）：整答还没吐出 ⇒ 注记**并进同一帧**（同 `NOTE_LAW_VERSION` 的形状，不另开帧）。"""
    cs = contents_of(_ask(monkeypatch, route="light_buffered"))
    assert cs and cs[0] == LIGHT_ANSWER + NOTE, f"E7 整答帧应带着注记：{cs}"


def test_e5_contract_report_answer_carries_the_note(monkeypatch):
    """E5 + E18：报告分片之后追加注记；显式历史请求不进入共享缓存。"""
    cs = contents_of(_ask(monkeypatch, route="contract_review", parts=CONTRACT_PARTS))
    assert "".join(cs).startswith("".join(CONTRACT_PARTS)), f"注记改写了已吐出的报告正文：{cs}"
    assert NOTE in cs, f"合同出口没产注记帧 ⇒ E18 没接上：{cs}"


def test_e17_frame_precedes_the_version_note(monkeypatch):
    """两条注记同时命中时，版本绊线那句压在最后（它断言"版本可能错"，比"时效没核"更强）。

    顺带把顺序写成判据：`test_stream_exit_law_version_gate.py` 有一条断言
    `content_frames[-1] == NOTE_LAW_VERSION`，靠本条兜住而不是靠运气。
    ⚠️ 这条只管 E17/E14 那一支。E7 是**反的**，见 `test_e7_note_order_is_the_reverse_of_e17`。
    """
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    parts = (CLAIM_S01_WRONG_CURRENT_LAW[:40], CLAIM_S01_WRONG_CURRENT_LAW[40:])
    cs = contents_of(_ask(monkeypatch, parts=parts, question=FACT_W01_2019[0]))
    assert main.NOTE_LAW_VERSION in cs, f"版本绊线未命中（夹具问题，不是判据）：{cs}"
    assert cs[-1] == main.NOTE_LAW_VERSION and cs[-2] == NOTE, f"E17 与 E14 的先后不符：{cs}"


def test_e7_note_order_is_the_reverse_of_e17(monkeypatch):
    """E7 与 E17 的注记先后**相反**，这是载体差异不是笔误：流式只能追加帧，缓冲整答只能往后贴字符串。

    `_light_buffered` 内部已把 `NOTE_LAW_VERSION` 贴进 answer ⇒ 时效注记落在它后面。
    本条存在的理由：上一版的票面把"时效在前、版本在后"当成全局判据，那是只看了合流点那一支。
    """
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    cs = contents_of(
        _ask(
            monkeypatch,
            route="light_buffered",
            light_text=CLAIM_S01_WRONG_CURRENT_LAW,
            question=FACT_W01_2019[0],
        )
    )
    assert cs and cs[0] == CLAIM_S01_WRONG_CURRENT_LAW + main.NOTE_LAW_VERSION + NOTE, (
        f"E7 的先后不是「版本在前、时效在后」：{cs}"
    )


# ════════ ③ 控制腿：两个条件各自单独不成立时，一条注记都不该出现 ════════


def test_control_no_explicit_basis_produces_no_note(monkeypatch):
    """现网多数请求（客户端不传 `law_as_of`）⇒ 行为逐字不变。没有这条，上面的红可能只因"总会加注"。"""
    cs = contents_of(_ask(monkeypatch, as_of=None))
    assert all(NOTE not in c for c in cs), f"未指定历史基准日却注记 ⇒ 默认行为被改：{cs}"


def test_control_verified_evidence_produces_no_note(monkeypatch):
    """日期齐的证据 ⇒ 不注记。钉住"注记不是只跟基准日走"（否则它就成了历史查询的固定尾巴）。"""
    cs = contents_of(_ask(monkeypatch, docs=DATED))
    assert all(NOTE not in c for c in cs), f"证据可核验仍注记：{cs}"


def test_e3_clarify_template_carries_no_note(monkeypatch):
    """E3（低置信反问 / 诚实拒答，零 LLM 模板）：模板不下法律结论 ⇒ 没有"所引条文时效"可披露。"""

    def tune(mp):
        mp.setattr(main.clarify, "decide", lambda *a, **k: "clarify")

    cs = contents_of(_ask(monkeypatch, tune=tune))
    assert cs == [main.clarify.CLARIFY_PROMPT], f"没走到 E3 反问出口（夹具问题）：{cs}"


def test_e4_contract_clarify_template_carries_no_note(monkeypatch):
    """E4（合同信息确认闸，零 LLM 模板）：同 E3 —— 还没引用任何条文，谈不上时效。"""

    def tune(mp):
        mp.setattr(
            main,
            "build_contract_data",
            lambda text, cutoff=None: {"need_clarify": True, "docs": [], "blocks": [], "level": "中"},
        )

    cs = contents_of(_ask(monkeypatch, route="contract_review", parts=CONTRACT_PARTS, tune=tune))
    assert cs == [main.CONTRACT_CLARIFY_PROMPT], f"没走到 E4 合同澄清出口（夹具问题）：{cs}"


def test_e2_has_no_note_timing_under_explicit_basis(monkeypatch):
    """E2 的"不适用"是**算出来的**，不是免责话术：显式基准日的请求根本不会走到 QA 语料直返。

    `request_bootstrap.prepare_fast_path`：`qa_hit = None if cutoff else deps.search_qa(...)`
    ⇒ 有 `law_as_of` 就没有 `qa_hit`，`_qa_direct_return` 恒 None ⇒ 本出口拿不到注记时机。
    所以本票**不**给 E2 接注记（接了就是登记表里那种"恒不命中的空门"，E3/E4 的版本绊线格前科）。
    """
    calls: list[str] = []

    def fake_search_qa(q):
        calls.append(q)
        return {
            "score": 0.95,
            "answer": "不该被直返",
            "evidence": "劳动合同法|第十九条",
            "law_as_of_basis": "2026-08-23",
        }

    _ask(monkeypatch, tune=lambda mp: mp.setattr(main.ks, "search_eligible_qa", fake_search_qa))
    assert calls == [], f"带显式基准日的请求仍去取 QA 语料 ⇒ E2 的 NA 判定不成立：{calls}"

    calls.clear()
    _ask(monkeypatch, as_of=None, tune=lambda mp: mp.setattr(main.ks, "search_eligible_qa", fake_search_qa))
    assert calls, "对照组失效：不传基准日时也不取语料 ⇒ 上面那条 `calls == []` 是空枪"


def test_e1_annotated_answers_never_enter_the_shared_cache(monkeypatch):
    """E1 的"不适用"是被 `_cacheable` 钉死的，不是我推的：`not pre.get("law_as_of")` 是它的合取项
    （函数注释原文「显式历史日期不进共享答案缓存」）⇒ **带注记的答复永不进缓存，历史请求也读不到缓存**。

    所以这一格不存在"复播丢注记"，也不存在"把未核验的答复固化 6 小时"。
    四条腿各钉一件事：
    ① 无基准日 ⇒ 写缓存一次，且那份**没有**注记（对照组，防"根本没写"让 ②③ 变空枪）；
    ② 有基准日 ⇒ 一次都不写；
    ③ 有基准日的请求**重新生成**（帧数 = 分片 + 注记），不是零 token 直返；
    ④ 同一题先无基准日后有基准日 ⇒ 第二问不走 E1。
    """
    import answer_cache

    puts: list[tuple] = []
    monkeypatch.setattr(answer_cache, "put", lambda *a, **k: puts.append(a))

    cs_now = contents_of(_ask(monkeypatch, as_of=None))
    assert len(puts) == 1, f"无基准日的答复本该写缓存一次（对照组失效）：{len(puts)}"
    assert NOTE not in puts[0][1], "无基准日却把注记写进了缓存 ⇒ `_cacheable` 的排除项没起作用"
    assert all(NOTE not in c for c in cs_now)

    puts.clear()
    cs_hist = contents_of(_ask(monkeypatch))
    assert puts == [], f"带显式基准日的答复进了缓存 ⇒ E1 的 NA 判定不成立：{puts!r}"
    assert cs_hist[-1] == NOTE, f"带基准日的请求没重新生成（走了直返？）：{cs_hist}"


# ════════ ④ 元测试：清单绑登记表（加出口却不填这一列 ⇒ 红） ════════


def test_every_registry_exit_has_an_s0c_row():
    ids = {e["id"] for e in EXITS}
    extra = sorted(set(S0C_CASES) - ids)
    assert ids == set(S0C_CASES), f"出口清单与登记表不吻合：登记表缺{sorted(ids - set(S0C_CASES))} 本文件多{extra}"


def test_column_exists_in_registry_columns():
    assert CELL in COLUMNS, f"登记表没有「{CELL}」这一列 ⇒ 出口 × 闸门矩阵不闭合"


def test_pass_cells_are_backed_by_a_case_here():
    """登记表把某出口这一格判成 PASS ⇒ 本文件必须有真跑得动的用例指着它（防"表上绿、码里没有"）。"""
    missing = [e["id"] for e in EXITS if e["cells"][CELL][0] == "PASS" and not S0C_CASES.get(e["id"])]
    assert not missing, f"登记表格子写 PASS 却没有对应用例：{missing}"


def test_named_cases_exist():
    mod = sys.modules[__name__]
    named = {n for rows in S0C_CASES.values() for n in rows}
    ghost = [n for n in sorted(named) if not hasattr(mod, n)]
    assert not ghost, f"S0C_CASES 指向不存在的用例（假指针）：{ghost}"


def test_rows_without_cases_explain_themselves_in_the_registry():
    """不给用例的出口必须在登记表那一格写清为什么不适用：状态在词表里、理由非空、GAP-TODO 还得上票。

    长度门槛量不出"理由够不够"，所以这里只钉两件可判定的事：状态合法 + 缺口必须挂票号
    （沿用哨兵 `TICKET_RE` 的口径，不另造一套"什么算挂了票"）。
    """
    silent = []
    for e in EXITS:
        if S0C_CASES.get(e["id"]):
            continue
        status, evidence = e["cells"][CELL]
        if status not in {"NA", "GAP-ACCEPTED", "GAP-TODO", "DISABLED", "BLOCKED"}:
            silent.append(f"{e['id']}={status}（既没有用例，状态又不是「不适用/缺口」类）")
        elif not evidence.strip():
            silent.append(f"{e['id']} 的理由是空的")
        elif status == "GAP-TODO" and not re.search(r"待开票|票\s*[A-Z]|\bS\d{1,2}\b", evidence):
            silent.append(f"{e['id']} 记 GAP-TODO 却没挂票号")
    assert not silent, f"这些出口既没有用例也没有可核的理由：{silent}"


def test_e19_contract_intent_confirm_template_carries_no_note(monkeypatch):
    """E19（合同审查意图确认闸，零 LLM 模板）：同 E3／E4 —— 还没引用任何条文，谈不上时效。"""

    def tune(mp):
        mp.setattr(
            main,
            "build_contract_data",
            lambda text, cutoff=None: {"confirm_intent": True, "docs": [], "blocks": [], "level": "中"},
        )

    cs = contents_of(_ask(monkeypatch, route="contract_review", parts=CONTRACT_PARTS, tune=tune))
    assert cs == [main.CONTRACT_INTENT_CONFIRM_PROMPT], f"没走到 E19 审查意图确认出口（夹具问题）：{cs}"


def test_e20_missing_source_note_declares_the_gap(monkeypatch):
    """E20（缺依据声明帧，口径①）：点名了、像法源、但不在库 ⇒ 只声明"这部分缺依据"，不整题拒答。"""
    monkeypatch.setattr(main, "_time_unverified_hit", lambda pre: False)  # 隔离 E17，免得顺序纠缠
    # 自足化：本用例只验"声明帧"，不该依赖知识库的真实内容，更不该被别处泄漏的 vectorstore 替身牵动
    monkeypatch.setattr(clarify.R, "source_in_kb", lambda name: False)
    q = "《工伤保险条例》里规定的工伤认定标准是什么？"
    cs = contents_of(_ask(monkeypatch, question=q))
    hits = [c for c in cs if "不在本库收录范围" in c]
    assert hits and "工伤保险条例" in hits[0], f"没产缺依据声明帧（夹具/判据问题）：{cs}"
