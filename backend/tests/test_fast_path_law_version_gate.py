"""S5：快车道缓冲轻量出口的法律版本绊线门（settings.fast_path_law_version_check）。

票面：docs/handoff-s5-fastpath-version-gate-20260919.md

期望值来源（§6-② 独立性）：`dispatch-output/s5-independent-expectations-20260919/expected.json`。
那张表由一个**未被允许读 `limitation_calc.py` / `verifier.py` / `main.py`** 的独立会话按规则文本
手算，本会话只引用其结论、未参与生成，样本 id 与期望逐条对应。

显式排除、不进断言的样本（连手算者自己判为歧义 —— 拿它们当判据等于替歧义选边）：
  S08  事实晚于分水岭 + 基准日早于分水岭（真源实测是双向 XOR，规则文本读起来像单向）
  S10  只有年份没有月日（"可解析的具体日期"粒度未定义）
  S13  民事与劳动语境并存、两读结论相反
  S16  纯法条陈述无时效结论（关键词表判法 vs "断言结论"判法相反）
这四条本票**无权**定：判定真源在 `backend/agent/limitation_calc.py`，票面 §11 禁止改它，
所以只能登记成残余风险（见收口报告），不能用测试把它焊成"正确"。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest  # noqa: E402

import llm_registry  # noqa: E402
import main  # noqa: E402
import quality  # noqa: E402
from tests._sse_harness import chat_frames, login, sse_client  # noqa: E402

# ---------------- 样本（文本原样取自独立表，未做任何"迁就实现"的改写） ----------------

FACT_W01_2019 = [
    "2019年3月5日对方向我借款10万元，约定当日归还，此后我一直没催过，也没还过钱。我现在起诉还能胜诉吗？",
    "借款发生于2019年3月5日；约定还款日就是当天；此后没有任何催收记录。",
]
FACT_W02_2023 = ["2023年8月1日对方向我借款10万元，约定当日归还，此后我一直没催过，也没还过钱。我现在起诉还能胜诉吗？"]
FACT_EARLY_AND_LATE = [
    "2019年11月11日他借了我8万元没还，后来2022年5月20日重新打了借条，我现在起诉还行吗？",
    "第一次借款发生于2019年11月11日；2022年5月20日他补写借条并承诺还款。",
]
FACT_ON_WATERSHED = ["2021年1月1日到期的一笔货款对方分文未付，约定付款日就是当天。"]
FACT_2020 = ["2020年6月15日他向我借款5万元，约定当天归还，之后一直没还。"]
FACT_NO_DATE = ["朋友前些年借了我一笔钱一直没还，我现在去起诉还来得及吗？"]
FACT_LABOR = ["我在2019年4月1日从公司离职，公司还压着两个月工资没结，我当时就没再联系过公司。"]

CLAIM_S01_WRONG_CURRENT_LAW = (
    "依据《民法典》第一百八十八条，向人民法院请求保护民事权利的诉讼时效期间为三年，"
    "自2019年3月5日约定还款日起算至2022年3月5日届满，你现在起诉已经超过诉讼时效，对方提出时效抗辩法院就会驳回。"
)
# S02 是法律上**正确**的形状（按行为时法作答），独立手算仍判命中：判定只看时效表述与日期，
# 不看引了哪部法。本条断的是这道门的**假阳性面**，不是在说"这是错答"。留在这里是为了让
# 将来把开关打开的人先看到代价（收口报告同款登记）。
CLAIM_S02_CORRECT_OLD_LAW = (
    "本案借款发生在2019年3月5日，适用行为发生时的法律：依《民法通则》第一百三十五条诉讼时效期间为二年，"
    "自2019年3月5日起至2021年3月5日已届满，《民法典》第一百八十八条的三年时效对这笔债权不溯及适用。"
)
CLAIM_S03_IN_PERIOD = (
    "依据《民法典》第一百八十八条，诉讼时效期间为三年，自2023年8月1日起算至2026年8月1日届满，"
    "你现在起诉仍在三年诉讼时效之内。"
)
CLAIM_S04_OLD_LAW_ON_NEW_FACT = (
    "你这笔借款属于《民法典》施行前的情形，依《民法通则》第一百三十五条诉讼时效期间为二年，"
    "从2023年8月1日起算到2025年8月1日就已经届满了。"
)
CLAIM_S15_RECALC_AFTER_INTERRUPTION = (
    "对方2022年5月20日补写了借条并承诺还款，诉讼时效应自该日起重新计算三年，现在尚未届满。"
)
CLAIM_S06_ON_WATERSHED = (
    "依《民法典》第一百八十八条，诉讼时效期间为三年，自2021年1月1日起算至2024年1月1日届满，现在起诉还在时效内。"
)
CLAIM_S07_EVE = "依《民法通则》第一百三十五条，诉讼时效期间为二年，自2020年6月15日起算至2022年6月15日届满。"
CLAIM_S09_NO_DATE = "依《民法典》第一百八十八条，诉讼时效期间为三年，你现在起诉仍在诉讼时效内。"
CLAIM_S12_LABOR = (
    "你与公司解除劳动关系后申请劳动仲裁的仲裁时效为一年，依《劳动争议调解仲裁法》第二十七条，"
    "从2019年4月1日离职之日起算已经超过一年，仲裁委不会再支持你的欠薪请求。"
)
NEUTRAL_ANSWER = "该问题需要结合合同约定与履行情况综合判断，建议核对条文原文。"

AS_OF_2026 = date(2026, 9, 18)
AS_OF_2020_EVE = date(2020, 12, 31)

# (id, 答案, 事实文本, 基准日, 期望是否命中)
EXPECTATIONS = [
    ("S01", CLAIM_S01_WRONG_CURRENT_LAW, FACT_W01_2019, AS_OF_2026, True),
    ("S02", CLAIM_S02_CORRECT_OLD_LAW, FACT_W01_2019, AS_OF_2026, True),
    ("S03", CLAIM_S03_IN_PERIOD, FACT_W02_2023, AS_OF_2026, False),
    ("S04", CLAIM_S04_OLD_LAW_ON_NEW_FACT, FACT_W02_2023, AS_OF_2026, False),
    ("S06", CLAIM_S06_ON_WATERSHED, FACT_ON_WATERSHED, AS_OF_2026, False),
    ("S07", CLAIM_S07_EVE, FACT_2020, AS_OF_2020_EVE, False),
    ("S09", CLAIM_S09_NO_DATE, FACT_NO_DATE, AS_OF_2026, False),
    ("S12", CLAIM_S12_LABOR, FACT_LABOR, AS_OF_2026, False),
    ("S15", CLAIM_S15_RECALC_AFTER_INTERRUPTION, FACT_EARLY_AND_LATE, AS_OF_2026, True),
]


class _NoAsOf:
    """哨兵：表示"按现网两参数形状调用"，即根本不传基准日。"""


NO_AS_OF = _NoAsOf()


class FakeLLM:
    def __init__(self, content, tokens=10):
        self._content = content
        self._tokens = tokens

    def invoke(self, messages):
        return SimpleNamespace(content=self._content, usage_metadata={"total_tokens": self._tokens})


def make_pre(fact_texts, context=None, sources=None):
    """事实只经**生产 `pre` 真有的键**流入：`user_text` / `rewritten` / `recent` 里的用户消息。
    （`pre` 的形状被 `tests/test_request_bootstrap.py` 的 `LEGACY_KEYS` 钉死，里面**没有** `facts` 键 ——
    自造一个键让测试通过，就是 `[PL#14]` 假接线的形状。）
    `context`/`sources` 是**法条文本**，刻意不进事实集 —— 见 test_law_text_dates_are_not_facts。"""
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [{"role": "user", "content": t} for t in fact_texts[1:]],
        "rewritten": fact_texts[0],
        "user_text": fact_texts[0],
        "summary": "",
        "qa_hit": None,
        "context": context if context is not None else "民法典 第一百八十八条 ...",
        "sources": sources if sources is not None else [{"source": "民法典", "article": "第一百八十八条"}],
        "image_rel": None,
        "thumb_rel": None,
        "is_exam": False,
        "has_options": False,
        "contract_data": None,
    }


def install_fakes(monkeypatch, light_content, flag_content=None, shape="ok-light", verdicts=None):
    light = FakeLLM(light_content)
    flag = FakeLLM(flag_content or light_content)

    def fake_pick(modality, tier, *, exclude=None):
        if tier == "light":
            return ("L", light)
        if shape == "quota":
            raise llm_registry.QuotaExhausted("x")
        if shape == "same-key":
            return ("L", light)  # 轻量即旗舰，无更强者可升
        return ("F", flag)

    seq = iter(list(verdicts or [(True, "")]))

    def fake_self_check(answer, ctx, in_kb=None):
        ok, reason = next(seq)
        return quality.Verdict(ok, reason)

    monkeypatch.setattr(llm_registry.registry, "pick", fake_pick)
    monkeypatch.setattr(llm_registry.registry, "model_of", lambda k: {"L": "m-light", "F": "m-flag"}.get(k, ""))
    monkeypatch.setattr(llm_registry.registry, "deduct", lambda k, t: None)
    monkeypatch.setattr(quality, "self_check", fake_self_check)


def run_light(monkeypatch, pre, answer, law_as_of=NO_AS_OF, shape="ok-light", verdicts=None, flag_content=None):
    install_fakes(monkeypatch, answer, flag_content=flag_content, shape=shape, verdicts=verdicts)
    if isinstance(law_as_of, _NoAsOf):
        return main._light_buffered(pre, [])  # 现网调用形状（§4-Q2 之所以要带默认值尾参）
    return main._light_buffered(pre, [], law_as_of)


# ---------------- ① 先红：两参数调用，未实现时红在断言本身而不是签名报错 ----------------


def test_failclosed_when_switch_on_but_law_as_of_missing(monkeypatch):
    """§4-Q3：开关开 + 拿不到基准日 = 判定不可信 ⇒ 走保守分支。
    **不许**写成"缺就当作不拦"（照抄 agent 路径 verifier.py:296-297 的 fail-closed）。
    用两参数调用 ⇒ 生产码未改时这道题红在断言上，可作 §6-① 的干净红。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    res = run_light(monkeypatch, make_pre(FACT_W01_2019), CLAIM_S01_WRONG_CURRENT_LAW)
    assert getattr(res, "law_version_hit", None) is True, (
        "要么这道门不存在（返回结构没有 law_version_hit 字段），"
        f"要么门存在但未按 fail-closed 处理缺基准日（实得 {getattr(res, 'law_version_hit', None)!r}）：{res!r}"
    )
    assert "版本" in res.answer and "注：" in res.answer


def test_switch_off_leaves_hitting_answer_untouched(monkeypatch):
    """§5-4：开关关 ⇒ 同一条会命中的输入也必须逐字不变。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", False)
    res = run_light(
        monkeypatch,
        make_pre(FACT_W01_2019),
        CLAIM_S01_WRONG_CURRENT_LAW,
        law_as_of=AS_OF_2026,
    )
    assert getattr(res, "law_version_hit", False) is False
    assert res.answer == CLAIM_S01_WRONG_CURRENT_LAW
    assert res.verdict == "pass"


# ---------------- ② 独立期望值表：逐条按那张表的期望断言 ----------------


def test_independent_expectation_table(monkeypatch):
    """九条样本（S01/S02/S03/S04/S06/S07/S09/S12/S15），期望值抄自独立手算表。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    bad = []
    for sid, claim, facts, as_of, expect_hit in EXPECTATIONS:
        res = run_light(monkeypatch, make_pre(facts), claim, law_as_of=as_of)
        got = getattr(res, "law_version_hit", None)
        if got is None:
            bad.append(f"{sid}: 返回结构没有 law_version_hit 字段（门未实现）")
        elif got is not expect_hit:
            bad.append(f"{sid}: 期望命中={expect_hit} 实得={got}")
        elif got and (claim not in res.answer or "注：" not in res.answer):
            bad.append(f"{sid}: 命中却没给用户可见的版本注记（静默替换=票面禁止项）")
    assert not bad, "；".join(bad)


def test_hit_appends_note_instead_of_replacing_answer(monkeypatch):
    """Q1：命中必须**明说降级**（同 NOTE_QUOTA/NOTE_COMPLEX 惯用法），不许静默替换答案。
    原答案文本必须仍在，注记追加在后面。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    res = run_light(monkeypatch, make_pre(FACT_W01_2019), CLAIM_S01_WRONG_CURRENT_LAW, law_as_of=AS_OF_2026)
    assert res.law_version_hit is True
    assert res.answer.startswith(CLAIM_S01_WRONG_CURRENT_LAW)
    assert len(res.answer) > len(CLAIM_S01_WRONG_CURRENT_LAW)


def test_law_text_dates_are_not_facts(monkeypatch):
    """事实集只许来自用户自述。检索命中的**法条文本**里带分水岭前的年份，
    不得被当成本案事实去触发判定（否则每条引用的旧法都会把门点亮）。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    res = run_light(
        monkeypatch,
        make_pre(
            ["我借出去的钱对方一直没还，现在起诉还来得及吗？"],  # 事实：无任何可解析日期
            context="《民法通则》第一百三十五条（1986年4月12日通过，2021年1月1日废止）：向人民法院请求保护民事权利的诉讼时效期间为二年。",
            sources=[{"source": "民法通则", "article": "第一百三十五条"}],
        ),
        CLAIM_S01_WRONG_CURRENT_LAW,
        law_as_of=AS_OF_2026,
    )
    assert res.law_version_hit is False  # 无事实日期 ⇒ 条款3不成立 ⇒ 不拦


# ---------------- ③ §5-2：五个 return 点必须全过同一道门 ----------------
# 坐标按 2026-09-19 22:3x 实测：1171 / 1176-1178 / 1180 / 1186 / 1187。开工时重数，别信注释。

# 每个 shape 必须让**最终交付给用户的那段文本**可触发，否则本测试分不清"没接门"与"样本触发不了"
# —— 那正是 M3（只接一个 return 点）要抓的区分，写成不可触发的样本就等于给 M3 放行。
_JUNK_LIGHT = "看相关规定吧"  # 无时效表述：自检不过、且门正确地不命中
RETURN_POINT_SHAPES = [
    # (shape, 自检序列, 轻量文本, 旗舰文本, 该 shape 落在哪个 return)
    ("ok-light", [(True, "")], CLAIM_S01_WRONG_CURRENT_LAW, None, "自检通过直接返回"),
    ("quota", [(False, "vague")], CLAIM_S01_WRONG_CURRENT_LAW, None, "配额耗尽不升级"),
    ("same-key", [(False, "vague")], CLAIM_S01_WRONG_CURRENT_LAW, None, "轻量即旗舰，无更强者"),
    (
        "escalate-pass",
        [(False, "no_citation_while_hit"), (True, "")],
        _JUNK_LIGHT,
        CLAIM_S01_WRONG_CURRENT_LAW,
        "升级后自检通过",
    ),
    ("escalate-fail", [(False, "vague"), (False, "vague")], _JUNK_LIGHT, CLAIM_S01_WRONG_CURRENT_LAW, "升级后仍不过"),
]


def test_every_return_point_passes_the_gate(monkeypatch):
    """漏一个 return 点就是"门在但走不到"（§9-1 `[PL#14]` 假接线的直接教训）。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    missed = []
    for shape, verdicts, light_text, flag_text, label in RETURN_POINT_SHAPES:
        res = run_light(
            monkeypatch,
            make_pre(FACT_W01_2019),
            light_text,
            law_as_of=AS_OF_2026,
            shape=shape,
            verdicts=verdicts,
            flag_content=flag_text,
        )
        if getattr(res, "law_version_hit", None) is not True:
            missed.append(f"{label}（shape={shape}）未过门：law_version_hit={getattr(res, 'law_version_hit', None)!r}")
        elif "注：" not in res.answer:
            missed.append(f"{label}（shape={shape}）过了门但没给用户可见注记")
    assert not missed, "；".join(missed)


def test_escalated_answer_is_judged_not_the_light_one(monkeypatch):
    """升级到旗舰后，被判定的是**最终交付给用户的那段文本**（fraw），不是被替换掉的轻量稿。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    res = run_light(
        monkeypatch,
        make_pre(FACT_W01_2019),
        "看相关规定吧",
        law_as_of=AS_OF_2026,
        shape="escalate-pass",
        verdicts=[(False, "no_citation_while_hit"), (True, "")],
        flag_content=CLAIM_S01_WRONG_CURRENT_LAW,
    )
    assert res.tier == "flag" and res.escalated is True
    assert res.law_version_hit is True
    assert res.answer.startswith(CLAIM_S01_WRONG_CURRENT_LAW)


def test_empty_answer_still_returns_empty(monkeypatch):
    """上游空答时不得给空串追加注记 —— 否则会把调用方的"空答走 error 帧"兜底
    （`_light_buffered` 调用点之后那个 `else`）变成一条假装有内容的降级回答。

    ⚠️ 本条重写过一次（票 G F6）：旧写法喂的是"真源根本不会命中"的空文本
    （空 claim 在 `_CIVIL_KEYWORDS` 那关就返回 False）⇒ 门永不触发，断言实际测的是
    "没命中时答案没变"，是一把**空枪**。现在用恒 True 替身**强制命中**，才真的钉住 carve-out：
    把门改成"空答也追加注记"，本条必须变红。
    """
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    monkeypatch.setattr(main.limitation_calc, "law_version_crosses_watershed", lambda *a, **k: True)
    res = run_light(
        monkeypatch,
        make_pre(FACT_W01_2019),
        "",
        law_as_of=AS_OF_2026,
        shape="escalate-fail",
        verdicts=[(False, "empty"), (False, "empty")],
        flag_content="",
    )
    assert res.law_version_hit is True, "恒 True 替身下却没命中 ⇒ 本条又退化成空枪"
    assert res.answer == "", f"命中却给空答案加了注记 ⇒ 造出一条有字没内容的假降级回答：{res.answer!r}"


# ---------------- ④ 判定必须委托真源，不在 main.py 重写规则（§5-1） ----------------


def test_gate_uses_the_single_truth_source_and_not_a_copy(monkeypatch):
    """真源被换成恒 True / 恒 False 时，门必须跟着变 ⇒ 证明 main.py 里没有第二份规则。
    只 patch 读，不改 agent/ 任何一行。"""
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    pre = make_pre(FACT_W01_2019)

    monkeypatch.setattr(main.limitation_calc, "law_version_crosses_watershed", lambda *a, **k: True)
    hit = run_light(monkeypatch, pre, NEUTRAL_ANSWER, law_as_of=AS_OF_2026)
    assert hit.law_version_hit is True, "恒 True 替身下仍不命中 ⇒ main.py 里藏了第二份判定"

    monkeypatch.setattr(main.limitation_calc, "law_version_crosses_watershed", lambda *a, **k: False)
    miss = run_light(monkeypatch, pre, CLAIM_S01_WRONG_CURRENT_LAW, law_as_of=AS_OF_2026)
    assert miss.law_version_hit is False, "恒 False 替身下仍命中 ⇒ 门没在调真源"


# ---------------- ⑤ 命中必须可归因（§5-3）：落日志带被判定原文 + 基准日 ----------------


def test_hit_is_logged_with_judged_text_and_baseline_date(monkeypatch):
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    captured = []
    monkeypatch.setattr(main.logging.getLogger("legal.chat"), "warning", lambda *a, **k: captured.append((a, k)))
    res = run_light(monkeypatch, make_pre(FACT_W01_2019), CLAIM_S01_WRONG_CURRENT_LAW, law_as_of=AS_OF_2026)
    assert res.law_version_hit is True
    assert captured, "命中却没落任何日志 ⇒ 线上只能看见注记，分不清按哪版法拦了哪句"
    extras = [kw.get("extra", {}) for _, kw in captured]
    joined = {k: v for e in extras for k, v in e.items()}
    assert joined, f"日志未带 extra：{captured!r}"
    assert any(CLAIM_S01_WRONG_CURRENT_LAW[:20] in str(v) for v in joined.values()), "缺被判定原文"
    assert any("2026" in str(v) for v in joined.values()), "缺基准日 law_as_of"


# ---------------- ⑥ 端点级（SSE）：闸在 stream() 里，不在 _light_buffered 里 ----------------
#
# 这一节为什么必须存在（票 G F5/F6 + 本计划 §九-B）：
#   1. `main.py:1921` 的 `not res.law_version_hit` 是 S5 提交信息里写明"否则门再也走不到"的
#      load-bearing 闸，但 S5 的四个变异**每个只跑了本文件** ⇒ 删掉它全量 21→21 零反应（G-M1 存活）。
#      本节的 `test_e6_hit_...` 就是能杀它的那条。
#   2. 复审 §6 自陈"缓存全部停写是推的不是看到的" ⇒ 本节把它从推断变成读数。
#   3. 1a 那行改动在 `main.py:1914`（调用点）。`capture_light_baseline.py` 直接调 `_light_buffered`，
#      不经该行 ⇒ 对它不可见；唯一能证 1a 零变化的仪器是**端点级逐帧比对**（见 dump 采集口）。

E6_QUESTION = FACT_W01_2019[0]  # 分水岭**前**事实（2019年3月5日）
E6_ANSWER = CLAIM_S01_WRONG_CURRENT_LAW  # 分水岭**后**法的民事时效结论
NOTE_MARKER = "注：本回答所适用的法律版本"  # NOTE_LAW_VERSION 去换行后的稳定子串


def test_e6_hit_does_not_enter_cache(monkeypatch):
    """开关开 + 跨分水岭 ⇒ 答复被加注记，且**一次缓存写入都没有**。

    期望值独立于实现：命中形状取自独立手算表 S01（`EXPECTATIONS[0]`），
    "不进缓存"取自 S5 提交信息对该闸的明示要求，不是从 `:1921` 那行反推的。
    """
    import answer_cache

    answer_cache.clear()
    puts = []
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    with sse_client(
        monkeypatch,
        route="light_buffered",
        light_text=E6_ANSWER,
        cache_put=lambda *a, **k: puts.append(a),
    ) as c:
        frames = chat_frames(c, login(c), E6_QUESTION)
    body = "".join(frames)
    assert NOTE_MARKER in body, f"开关开 + 事实跨分水岭却未加注记 ⇒ E6 没走到门：{body[:200]}"
    assert puts == [], f"被拦答复仍写缓存 ⇒ 同题后续请求会零 token 直返错版答案：{puts!r}"


def test_e6_control_leg_writes_cache_when_switch_off(monkeypatch):
    """控制腿：同一请求在开关**关**时确实写了一次缓存、且没有注记。

    没有这条，上面那句 `puts == []` 可能只是因为这条路径根本不写缓存（= 空枪）。
    S5 已经因为"样本喂的是不可触发文本"让一条全 return 点测试失去鉴别力，这里补齐。
    """
    import answer_cache

    answer_cache.clear()
    puts = []
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", False)
    with sse_client(
        monkeypatch,
        route="light_buffered",
        light_text=E6_ANSWER,
        cache_put=lambda *a, **k: puts.append(a),
    ) as c:
        frames = chat_frames(c, login(c), E6_QUESTION)
    body = "".join(frames)
    assert len(puts) == 1, f"开关关时这条路径本应写缓存一次，实际 {len(puts)} 次 ⇒ 控制腿失效，⑥ 全部结论不可信"
    assert NOTE_MARKER not in body, "开关关却加注记 ⇒ 默认行为被改（Owner 纪律：默认关 ⇒ 线上一字不变）"


def test_e6_dump_frames_for_zero_change_diff(monkeypatch):
    """1a 的零变化证据采集口：开关 OFF 下把 E6 的 SSE 帧序列落盘，改前/改后比 sha256。

    只在设了 `FZ_DUMP_FRAMES` 时执行（平时 skip，不给套件加时长）。
    `conversation_id` 是每次新建会话的自增主键，与"答复有没有变"无关 ⇒ 归一化时剔除。
    """
    import answer_cache

    out = os.environ.get("FZ_DUMP_FRAMES")
    if not out:
        pytest.skip("未设 FZ_DUMP_FRAMES：本用例是 1a 改前/改后逐帧比对的采集口")
    assert main.settings.fast_path_law_version_check is False, "开关默认值被改过 ⇒ 这份基线不再是默认态"
    answer_cache.clear()
    with sse_client(monkeypatch, route="light_buffered", light_text=E6_ANSWER) as c:
        frames = chat_frames(c, login(c), E6_QUESTION)
    norm = []
    for f in frames:
        if f.startswith("data: ") and f.strip() != "data: [DONE]":
            obj = json.loads(f[len("data: ") :])
            obj.pop("conversation_id", None)
            norm.append(obj)
        else:
            norm.append(f)
    dump = json.dumps(norm, ensure_ascii=False, sort_keys=True)
    payload = {"sha256": hashlib.sha256(dump.encode("utf-8")).hexdigest(), "n_frames": len(norm), "frames": norm}
    with open(out, "wb") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))


# ---- 1a：R15-lite 契约的第①半（缺省基准日由服务端落当日）在快车道调用点补上 ----
#
# 为什么这两条是**先红**的（本计划 §一 R1 + 票 G F3）：`agent/repository.py` 的 `create_run` docstring
# 把契约写成两半 —— ①缺省时服务端落 `date.today()` ②错版答复由绊线拦。快车道路线**不经过**
# `create_run`，`:1914` 直接把 `body.law_as_of`（生产客户端不传 ⇒ `None`）递给门 ⇒ 开关一开，
# 每条答复都在 `LAW_TRIPWIRE_NOT_WIRED` 那支命中（与答案写了什么无关）。
# 判据形状取自独立手算表：S03（2023 事实 + 分水岭后基准日 ⇒ 不命中）、S01（2019 事实 ⇒ 命中）。
# 今天（2026-09-20）与 `AS_OF_2026`（2026-09-18）在分水岭同侧 ⇒ 可直接沿用该表结论，无需我另算。


def _capture_gate_reasons(monkeypatch) -> list[str]:
    """抓 `_law_version_gate` 落的 reason —— 钉"按哪支命中"，不钉"命中没命中"。

    只断"命中"会让 S01 那条在修复前也是绿的（`None` 走 NOT_WIRED 同样命中）⇒ 失去鉴别力。
    """
    captured: list[str] = []

    def fake_warning(*args, **kwargs):
        captured.append(str(kwargs.get("extra", {}).get("fast_path_law_version_reason", "")))

    monkeypatch.setattr(main.logging.getLogger("legal.chat"), "warning", fake_warning)
    return captured


def test_e6_missing_client_date_does_not_degrade_every_answer(monkeypatch):
    """S03 形状（分水岭后事实 + 民事时效结论）：客户端不传基准日 ⇒ **不该**被加注记。

    修复前 RED：`law_as_of=None` ⇒ `LAW_TRIPWIRE_NOT_WIRED` ⇒ 恒命中 ⇒ 注记出现、缓存停写。
    修复后 GREEN：服务端落 `date.today()` ⇒ 事实与基准日同在分水岭后 ⇒ 判定 False ⇒ 原样交付。
    """
    import answer_cache

    answer_cache.clear()
    puts = []
    reasons = _capture_gate_reasons(monkeypatch)
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    with sse_client(
        monkeypatch,
        route="light_buffered",
        light_text=CLAIM_S03_IN_PERIOD,
        cache_put=lambda *a, **k: puts.append(a),
    ) as c:
        frames = chat_frames(c, login(c), FACT_W02_2023[0])
    body = "".join(frames)
    assert NOTE_MARKER not in body, f"每条答复都被加注记 ⇒ 第①半仍缺：{body[:200]}"
    assert reasons == [], f"不该命中的形状落了命中日志：{reasons!r}"
    assert len(puts) == 1, "不该命中却仍停写缓存 ⇒ 门在生产形态下仍是恒命中"


def test_e6_pre_watershed_fact_hits_by_version_rule_not_by_missing_date(monkeypatch):
    """S01 形状（分水岭前事实）：仍要命中，但**必须**是按版本判定命中，不是 `LAW_TRIPWIRE_NOT_WIRED`。

    这条同时防两个方向：修坏了（门变哑 ⇒ 断言不绿）、修成"靠缺省日常量兜着"（reason 不是 WATERSHED_MISMATCH）。
    修复前 RED：reason 是 `LAW_TRIPWIRE_NOT_WIRED`（根本没进真源）。
    """
    reasons = _capture_gate_reasons(monkeypatch)
    monkeypatch.setattr(main.settings, "fast_path_law_version_check", True)
    with sse_client(monkeypatch, route="light_buffered", light_text=CLAIM_S01_WRONG_CURRENT_LAW) as c:
        frames = chat_frames(c, login(c), FACT_W01_2019[0])
    body = "".join(frames)
    assert NOTE_MARKER in body, "分水岭前事实 + 分水岭后法却没加注记 ⇒ 门没在 E6 上生效"
    assert reasons == ["LAW_VERSION_WATERSHED_MISMATCH"], (
        f"命中原因不是版本判定 ⇒ 第①半仍未补上（`None` 被当成接线丢失）：{reasons!r}"
    )


def test_fast_path_law_as_of_uses_server_today_not_a_constant(monkeypatch):
    """函数自身：不传 ⇒ 落**当日**；显式传 ⇒ 原样透传（第①半的字面口径）。

    与上面两条端点级用例的分工：端点级钉"调用点确实用了它"，本条钉"它算的是哪天"。
    把 `main.date` 冻成分水岭**前**的一天再断言，既让判据不随墙钟漂移，也排掉"写死一个分水岭后的
    常量"这类伪实现 —— 不冻的话，硬编码当天日期的实现要等到隔天才会露馅。
    """

    class _FrozenDay(date):
        @classmethod
        def today(cls):
            return date(2019, 7, 1)  # 分水岭前的"当日"：若实现写死后一半日期，这里就会露馅

    monkeypatch.setattr(main, "date", _FrozenDay)
    assert main._fast_path_law_as_of(SimpleNamespace(law_as_of=None)) == date(2019, 7, 1)
    assert main._fast_path_law_as_of(SimpleNamespace(law_as_of=date(2021, 1, 1))) == date(2021, 1, 1)
