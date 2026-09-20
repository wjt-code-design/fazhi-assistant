"""票 C/S6：旗舰流式出口（登记表 E8/E9）的法律版本绊线门。

票面：`docs/handoff-s6-stream-exit-version-gate-20260920.md`
开关：复用 S5 的 `settings.fast_path_law_version_check`（票 C §4-Q4 裁定），默认值必须仍是 `False`。

**为什么是这条出口**：S5（`dec7a95`）把门接在缓冲轻量出口上，而 `llm_registry` 实配里没有
`('text','light')` 角色 ⇒ `use_light` 恒假 ⇒ 那条门今天零流量；默认配置下三种法律问句形态
**全部**走本文件的 `stream()` 分支2。⇒ 本文件每条用例都在端点级打那条真承接流量的出口。

**为什么全部是端点级（SSE）而不是单元级**：
1. 本票改的东西有三处在"调用点/端点里"而不是被测函数里 —— 两个答案来源各过一次门（§5-3）、
   写缓存闸从四条件变五条件（§5-6）、基准日传 `_fast_path_law_as_of(body)`（§5-4）。
   直接调 `_law_version_gate` 的仪器对这三处**完全不可见**（S5 的 `capture_light_baseline.py`
   就是这么给出过一个平凡相同的 sha，见主会话自审 §九-B）。
2. `dispatch-output/s5-followup-20260920` 实测：删掉"命中不进缓存"那道闸后**定向零反应**，
   全量才有读数 ⇒ 闸必须在端点上测才杀得动。

期望值来源（§6-② 独立性）：**逐条复用** `tests/test_fast_path_law_version_gate.py` 里的
`EXPECTATIONS` 常量表 —— 那张表由一个未被允许读 `limitation_calc.py`/`verifier.py`/`main.py`
的独立会话按规则文本手算（原始产物
`dispatch-output/s5-independent-expectations-20260919/expected.json`），本会话只引用其结论。
在此**另抄一份样本**就是 `[PL#13]`：两张表会各自漂移，然后互相不一致。
S08 / S10 / S13 / S16 四条不在该表里（手算者自判歧义，真源在 `agent/` 不许改 ⇒ 只能登记不能焊死）。

⚠️ 本文件不写 `main.py:NNNN`：ADR-018/R4 定的是只用符号锚点（行号在本仓已漂过五次）。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import pytest  # noqa: E402

import main  # noqa: E402
from tests._sse_harness import chat_frames, login, sse_client  # noqa: E402
from tests.test_fast_path_law_version_gate import (  # noqa: E402
    AS_OF_2020_EVE,
    AS_OF_2026,
    CLAIM_S01_WRONG_CURRENT_LAW,
    CLAIM_S03_IN_PERIOD,
    EXPECTATIONS,
    FACT_NO_DATE,
    FACT_ON_WATERSHED,
    FACT_W01_2019,
    FACT_W02_2023,
    NEUTRAL_ANSWER,
    NOTE_MARKER,
)

# 流式出口的分片：把整答拆成两块吐出，才能证明"帧已发出之后追加注记"这件事（票 C §2b）。
STREAM_PARTS_HIT = (CLAIM_S01_WRONG_CURRENT_LAW[:40], CLAIM_S01_WRONG_CURRENT_LAW[40:])
STREAM_PARTS_MISS = (CLAIM_S03_IN_PERIOD[:30], CLAIM_S03_IN_PERIOD[30:])


def _normalise_frames(frames: list[str]) -> list[Any]:
    """SSE 原始行 → 可比对的对象序列（`conversation_id` 每次新建会话都变，与本票判据无关）。"""
    norm: list[Any] = []
    for f in frames:
        if f.startswith("data: ") and f.strip() != "data: [DONE]":
            obj = json.loads(f[len("data: ") :])
            obj.pop("conversation_id", None)
            norm.append(obj)
        else:
            norm.append(f)
    return norm


class Run:
    """一次端点级请求的全部可观测面。"""

    def __init__(self, frames: list[str], puts: list, gate_calls: list[dict], warnings: list) -> None:
        self.raw = frames
        self.frames = _normalise_frames(frames)
        self.body = "".join(frames)
        self.puts = puts
        self.gate_calls = gate_calls
        self.warnings = warnings
        self.reasons = [str((kw.get("extra") or {}).get("fast_path_law_version_reason", "")) for _a, kw in warnings]
        self.labels = [" ".join(str(a) for a in args) for args, _kw in warnings]

    @property
    def judged(self) -> list[str]:
        return [c["judged"] for c in self.gate_calls]

    @property
    def noted(self) -> bool:
        return NOTE_MARKER in self.body

    @property
    def content_frames(self) -> list[str]:
        return [f["content"] for f in self.frames if isinstance(f, dict) and "content" in f]


def run_stream_exit(
    monkeypatch,
    *,
    on: bool,
    question: str,
    parts: tuple[str, ...] = STREAM_PARTS_HIT,
    fallback_text: str | None = None,
    law_as_of: date | None = None,
    chain: Any = None,
) -> Run:
    """在端点级打一次旗舰流式出口，返回 (帧序列, 写缓存次数, 门调用记录, 命中日志)。

    `parts=()` ⇒ 流式返回空 ⇒ 走 `_invoke_llm`（登记表 E9，票 C §5-3 的第二个答案来源）；
    此时 `fallback_text` 是那份兜底整答（`_sse_harness` 的 `fallback_text` 参数负责让
    `flag_llm` 真的可 `invoke` —— 否则 `_invoke_llm` 必抛、E9 在测试里恒等于"兜底也失败"）。

    `quality.self_check` 固定替成 PASS 是**为了鉴别力**：不桩的话命中样本会同时触发
    E12 自检注记 + 整块 `put` 不执行，"ON 时 puts==0" 就可能只是因为这条路径根本不写缓存
    （= 空枪，S5 的 `test_empty_answer_still_returns_empty` 第一代就是这个形状）。
    于是 ON/OFF 两腿之间唯一的变化就是门本身。
    """
    import answer_cache
    import quality

    answer_cache.clear()
    puts: list = []
    gate_calls: list[dict] = []
    warnings: list = []

    monkeypatch.setattr(main.settings, "fast_path_law_version_check", on)
    monkeypatch.setattr(quality, "self_check", lambda answer, context_present: quality.Verdict(True))

    real_gate = main._law_version_gate

    def spy_gate(answer: str, fact_texts: list[str], as_of: date | None, *, exit_label: str):
        delivered, hit = real_gate(answer, fact_texts, as_of, exit_label=exit_label)
        gate_calls.append(
            {
                "judged": answer,
                "delivered": delivered,
                "hit": hit,
                "exit_label": exit_label,
                "fact_texts": list(fact_texts),
                "law_as_of": as_of,
            }
        )
        return delivered, hit

    # 门**必须仍被真实执行**（只记录不代跑 ⇒ 本文件全部结论退化成"我桩了一个恒过的门"）。
    monkeypatch.setattr(main, "_law_version_gate", spy_gate)
    monkeypatch.setattr(main.logging.getLogger("legal.chat"), "warning", lambda *a, **k: warnings.append((a, k)))

    payload = {"law_as_of": law_as_of.isoformat()} if law_as_of else None
    with sse_client(
        monkeypatch,
        route="flagship_stream",
        flagship_parts=parts,
        fallback_text=fallback_text,
        cache_put=lambda *a, **k: puts.append(a),
    ) as c:
        if chain is not None:
            # 必须在 `sse_client` **之内**再打一次：夹具自己把 `main.make_chain` 换成了
            # `_FakeChain`，在它之前 patch 会被静默覆盖（"桩没生效而测试照样绿"的形状）。
            monkeypatch.setattr(main, "make_chain", lambda _llm: chain)
        frames = chat_frames(c, login(c), question, payload)
    return Run(frames, puts, gate_calls, warnings)


# ---------------- ① 先红：两条答案来源各自一条（改前红在断言本身，不是 TypeError） ----------------


def test_streaming_join_hits_gate_and_appends_note_frame(monkeypatch):
    """来源 1/2（流式 join，登记表 E8）：分水岭前事实 + 分水岭后法的答复 ⇒ 追加一帧版本注记。

    改前 RED：本出口根本没有门 ⇒ 帧序列里没有 NOTE ⇒ 红在断言本身。
    """
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        parts=STREAM_PARTS_HIT,
        law_as_of=AS_OF_2026,
    )
    assert run.noted, f"开关开 + 跨分水岭却没加版本注记 ⇒ E8 没接到门：{run.body[:240]}"
    assert run.content_frames[-1] == main.NOTE_LAW_VERSION, "注记必须是**单独一帧**追加在流式分片之后"
    assert len(run.gate_calls) == 1, f"门被调了 {len(run.gate_calls)} 次：{run.judged}"
    assert run.gate_calls[0]["hit"] is True


def test_fallback_answer_also_passes_the_gate(monkeypatch):
    """来源 2/2（`_invoke_llm` 兜底，登记表 E9）：流式返回空时门**不能消失**。

    票 C §2c：兜底产物与流式 join 是两个不同来源，只接流式 = 空答兜底时门整体失效。
    改前 RED：E9 那条分支上没有门（且旧夹具下 `_invoke_llm` 根本抛错、到不了这里）。
    """
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        parts=(),  # 流式空答 ⇒ 走 _invoke_llm
        fallback_text=CLAIM_S01_WRONG_CURRENT_LAW,
        law_as_of=AS_OF_2026,
    )
    assert run.noted, f"兜底整答没过门 ⇒ 流式一空答门就消失：{run.body[:240]}"
    assert len(run.gate_calls) == 1, f"兜底路径的门调用记录不符：{run.judged}"
    assert run.gate_calls[0]["judged"] == CLAIM_S01_WRONG_CURRENT_LAW
    # 注记帧必须在**整答帧之后**（帧已吐出不收回、不重放 ⇒ 追加一帧，票 C §2b）。
    assert run.content_frames[0] == CLAIM_S01_WRONG_CURRENT_LAW
    assert run.content_frames[-1] != run.content_frames[0]


# ---------------- ② §5-6 命中必须进那条写缓存闸（四条件 → 五条件），带控制腿 ----------------


def test_hit_answer_does_not_enter_cache(monkeypatch):
    """命中答复不进缓存：分支0（缓存直返）早于本门，一旦落缓存就被后续同题零 token 固化。"""
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        parts=STREAM_PARTS_HIT,
        law_as_of=AS_OF_2026,
    )
    assert run.noted
    assert run.puts == [], f"被拦答复仍写缓存 ⇒ 同题后续请求会零 token 直返错版答案：{run.puts!r}"


def test_control_leg_writes_cache_when_switch_off(monkeypatch):
    """控制腿：同一请求在开关**关**时确实写了一次缓存且无注记。

    没有这条，上面那句 `puts == []` 可能只是因为这条路径根本不写缓存（= 空枪）。
    """
    run = run_stream_exit(
        monkeypatch,
        on=False,
        question=FACT_W01_2019[0],
        parts=STREAM_PARTS_HIT,
        law_as_of=AS_OF_2026,
    )
    assert len(run.puts) == 1, f"开关关时这条路径本应写缓存一次，实际 {len(run.puts)} 次 ⇒ 控制腿失效"
    assert not run.noted, "开关关却加注记 ⇒ 默认行为被改（Owner 纪律：默认关 ⇒ 线上一字不变）"


def test_control_leg_writes_cache_on_fallback_path_when_switch_off(monkeypatch):
    """E9 那条路径的控制腿（与上一条同理，防兜底路径成为空枪）。"""
    run = run_stream_exit(
        monkeypatch,
        on=False,
        question=FACT_W01_2019[0],
        parts=(),
        fallback_text=CLAIM_S01_WRONG_CURRENT_LAW,
        law_as_of=AS_OF_2026,
    )
    assert len(run.puts) == 1, f"兜底路径开关关时应写缓存一次，实际 {len(run.puts)} 次 ⇒ E9 的结论不可信"
    assert not run.noted


# ---------------- ③ §6-② 独立期望表：九条样本全部经**流式出口**复算 ----------------


def test_independent_expectation_table_on_streaming_exit(monkeypatch):
    """独立手算表的九条（S01/S02/S03/S04/S06/S07/S09/S12/S15）逐条经 E8 复算。

    与 S5 那份的差别只有一个：同一样本、同一期望，走的出口从"缓冲轻量"换成"旗舰流式"。
    每条额外断三件"真的走到了门"的事，缺一条这条用例就会**假过**（中途从 E1/E2/E3 出口
    return 掉同样表现为"没有注记"，S5 那份不需要防这个，换了出口就得防）：
      · 门被调用恰好一次；
      · 被判定文本 == 该行答案（不是别的东西）；
      · 用户实际收到的正文 == 该行答案 (+ 命中时的注记)。
    """
    bad: list[str] = []
    for sid, claim, facts, as_of, expect_hit in EXPECTATIONS:
        run = run_stream_exit(monkeypatch, on=True, question=facts[0], parts=(claim[:40], claim[40:]), law_as_of=as_of)
        delivered = "".join(run.content_frames)  # 正文帧按序拼接（流式是分片的，不能拿整行 body 去 in 判断）
        want = claim + (main.NOTE_LAW_VERSION if expect_hit else "")
        if len(run.gate_calls) != 1:
            bad.append(f"{sid}: 门被调用 {len(run.gate_calls)} 次（期望 1 次）⇒ 本条根本没走到 E8")
        elif run.judged[0] != claim:
            bad.append(f"{sid}: 被判定文本不是本行答案（{run.judged[0][:30]}…）")
        elif run.gate_calls[0]["hit"] is not expect_hit:
            bad.append(f"{sid}: 期望命中={expect_hit} 实得={run.gate_calls[0]['hit']}")
        elif delivered != want:
            bad.append(f"{sid}: 交付文本不符（命中注记没落地或被别的注记混进来）实得 {delivered[-60:]!r}")
    assert not bad, "；".join(bad)


# ---------------- ④ §2d 判定输入只含用户自述，不含法条文本 ----------------


def test_law_text_dates_are_not_facts_on_stream_exit(monkeypatch):
    """检索到的**法条文本**里带分水岭前的年份，不得被当成本案事实点亮判定。

    鉴别方式（与 S5 那条同形状，但这里在端点级）：事实无任何可解析日期 + 答案写成
    "按现行法给三年结论"的 S01 形状 ⇒ 正确取法不命中；把 `pre['context']` 当事实喂进去就命中。
    库内条文换成《民法通则》（含 1986/2021 两个日期），让错取法必然点亮。
    """
    from langchain_core.documents import Document

    def old_law_retrieval(q: str, k: int = 4) -> list[Document]:  # noqa: ARG001
        return [
            Document(
                page_content=(
                    "第一百三十五条 向人民法院请求保护民事权利的诉讼时效期间为二年。"
                    "（《民法通则》1986年4月12日通过，2021年1月1日废止）"
                ),
                metadata={"source": "民法通则", "article": "第一百三十五条"},
            )
        ]

    monkeypatch.setattr(main, "retrieve", old_law_retrieval)
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_NO_DATE[0],  # 事实里没有任何可解析日期
        parts=(CLAIM_S01_WRONG_CURRENT_LAW[:40], CLAIM_S01_WRONG_CURRENT_LAW[40:]),
        law_as_of=AS_OF_2026,
    )
    assert run.gate_calls, "门没被调用 ⇒ 本条没测到东西"
    facts = run.gate_calls[0]["fact_texts"]
    assert facts and all("1986" not in t and "1986年" not in t for t in facts), f"法条文本漏进了事实集：{facts}"
    assert run.gate_calls[0]["hit"] is False, "无事实日期却命中 ⇒ 把检索条文当事实了（票 C §2d）"
    assert not run.noted


# ---------------- ⑤ §5-4/§5-5 基准日口径：正常路径不得出现 LAW_TRIPWIRE_NOT_WIRED ----------------


def test_default_client_shape_never_reports_tripwire_not_wired(monkeypatch):
    """生产客户端不传 `law_as_of` ⇒ 服务端落 `date.today()`（`_fast_path_law_as_of`），
    分水岭后事实 + 分水岭后法 ⇒ **不命中**、不停写缓存。

    改前 RED 面：这条在旧代码上是绿的（那时根本没有门 ⇒ 也没 NOT_WIRED）；它钉的是
    "接线没漏"这件事，与 §5-4 那条一票两面：漏传就变成**每条答复都命中**。
    与 `test_hit_reason_is_version_rule_not_missing_baseline_date` 配对才完整：
    只断"不命中"会把"门是哑的"也一起放过。
    """
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W02_2023[0],  # 分水岭**后**事实
        parts=STREAM_PARTS_MISS,
        law_as_of=None,  # 客户端不传 —— 现网形状
    )
    assert run.reasons == [], f"正常路径出现了命中日志（说明基准日仍可能是 None）：{run.reasons!r}"
    assert "LAW_TRIPWIRE_NOT_WIRED" not in run.body
    assert not run.noted, "客户端不传基准日 ⇒ 每条答复都被加注记 ⇒ R15-lite 第①半在这条出口仍缺"
    assert len(run.puts) == 1, "不该命中却仍停写缓存 ⇒ 门在生产形态下是恒命中"
    assert run.gate_calls and run.gate_calls[0]["law_as_of"] == date.today()


def test_hit_reason_is_version_rule_not_missing_baseline_date(monkeypatch):
    """命中必须**是按版本判定**命中（reason=LAW_VERSION_WATERSHED_MISMATCH），
    且日志要说是哪条出口命中的（票 C 之后这道门有两个消费者，写死出口名 = 假归因）。"""
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        parts=STREAM_PARTS_HIT,
        law_as_of=None,  # 不传 ⇒ 由服务端落当日；今天与 2019 分处两侧 ⇒ 该命中
    )
    assert run.reasons == ["LAW_VERSION_WATERSHED_MISMATCH"], f"命中原因不是版本判定：{run.reasons!r}"
    assert run.labels and main.EXIT_STREAM in run.labels[0], f"日志没说是哪条出口：{run.labels!r}"
    assert run.noted


def test_gate_uses_the_single_truth_source_and_not_a_copy(monkeypatch):
    """§5-1：判定必须委托 `limitation_calc`，main.py 里不许有第二份规则。恒真/恒假替身各一次。"""
    monkeypatch.setattr(main.limitation_calc, "law_version_crosses_watershed", lambda *a, **k: True)
    hit = run_stream_exit(
        monkeypatch, on=True, question=FACT_W02_2023[0], parts=STREAM_PARTS_MISS, law_as_of=AS_OF_2026
    )
    assert hit.noted, "恒 True 替身下仍不命中 ⇒ 流式出口自己藏了一份判定"

    monkeypatch.setattr(main.limitation_calc, "law_version_crosses_watershed", lambda *a, **k: False)
    miss = run_stream_exit(
        monkeypatch, on=True, question=FACT_W01_2019[0], parts=STREAM_PARTS_HIT, law_as_of=AS_OF_2026
    )
    assert not miss.noted, "恒 False 替身下仍命中 ⇒ 门没在调真源"


# ---------------- ⑥ §2c 空答：门不得把"没答上来"伪装成"答了但仅供参考" ----------------


def test_empty_answer_yields_error_frame_and_no_version_note(monkeypatch):
    """流式与兜底**都**空 ⇒ 只有 error 帧，没有正文、没有版本注记。

    恒 True 真源替身 ⇒ 只要门拿到非空文本就一定命中；于是"没注记"这条断言测的确实是
    空答豁免，而不是"样本刚好触发不了"（S5 第一代那条就是后者，票 G F6）。
    """
    monkeypatch.setattr(main.limitation_calc, "law_version_crosses_watershed", lambda *a, **k: True)
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        parts=(),
        fallback_text="",  # 兜底也空
        law_as_of=AS_OF_2026,
    )
    assert run.gate_calls == [], f"空答却过了门（会被加注记）：{run.judged!r}"
    assert not run.noted
    assert any("error" in json.dumps(f, ensure_ascii=False) for f in run.frames), f"空答却没有 error 帧：{run.frames}"


def test_empty_stream_but_nonempty_fallback_is_judged_once(monkeypatch):
    """流式空、兜底有整答 ⇒ 门判的是**兜底那份**，且只判一次（不是对流式空串判一次再对兜底判一次）。"""
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        parts=(),
        fallback_text=CLAIM_S01_WRONG_CURRENT_LAW,
        law_as_of=AS_OF_2026,
    )
    assert len(run.gate_calls) == 1, f"门调用次数不符：{run.judged!r}"
    assert run.judged[0] == CLAIM_S01_WRONG_CURRENT_LAW


# ---------------- ⑦ 票 §8 必答留白：重答环里判哪一份（用执行回答，不读码推断） ----------------


def test_gate_judges_final_answer_once_across_model_restart(monkeypatch):
    """`_restart_pending` 那条重答环里，门判的是**最终 chunks 拼出来的那一份**、只判一次。

    票 §8 要求用执行回答。做法：第一条链先吐半截再抛错（触发 `on_model_failure` ⇒
    `chunks` 清空 + 前端收 `restart` 帧），第二条链吐完整答案。若门是"每次重答后各判一次"，
    这里会看到 ≥2 次调用、且其中一次的被判定文本含被丢弃的半截。
    """

    class _RestartOnceChain:
        def __init__(self, parts: tuple[str, ...]) -> None:
            self._parts = parts
            self.n = 0

        async def astream(self, messages):  # noqa: ARG002
            self.n += 1
            if self.n == 1:
                yield CLAIM_S03_IN_PERIOD[:20]  # 半截：会被 chunks 清空丢弃
                raise RuntimeError("模拟模型侧失败：触发零重答")  # 非瞬时 ⇒ 走 mark_depleted 分支
            for p in self._parts:
                yield p

    shared = _RestartOnceChain(STREAM_PARTS_HIT)
    run = run_stream_exit(
        monkeypatch,
        on=True,
        question=FACT_W01_2019[0],
        law_as_of=AS_OF_2026,
        chain=shared,
    )
    assert shared.n >= 2, f"链只被调用 {shared.n} 次 ⇒ 根本没触发重答，本条是空枪"
    assert any(isinstance(f, dict) and f.get("type") == "restart" for f in run.frames), "没出现 restart 帧"
    assert len(run.gate_calls) == 1, f"重答环里门被判了 {len(run.gate_calls)} 次：{run.judged}"
    assert run.judged[0] == CLAIM_S01_WRONG_CURRENT_LAW, "判的不是最终那一份"
    assert all(CLAIM_S03_IN_PERIOD[:20] not in j for j in run.judged), "被丢弃的半截进了判定"
    assert run.noted


# ---------------- ⑧ §6-③ 端点级逐帧零变化：采集口（开关 OFF，改前/改后比 sha256） ----------------


def test_dump_stream_frames_for_zero_change_diff(monkeypatch):
    """票 C §6-③ 的真仪器：默认关（**不动默认值**）下把两条答案来源的 SSE 帧序列落盘。

    只在设了 `S6_DUMP_FRAMES` 时执行（平时 skip，不给套件加时长）。改前侧在
    `b40076b` 的副本树里跑、改后侧在 live 树里跑，两份 `sha256` 必须相同。
    ⚠️ 不能用 `capture_light_baseline.py` 那套替代：它直接调被测函数，凡改在**调用点/端点里**
    的东西（本票三处改动全在这一层）对它完全不可见。
    """
    out = os.environ.get("S6_DUMP_FRAMES")
    if not out:
        pytest.skip("未设 S6_DUMP_FRAMES：本用例是票 C 改前/改后逐帧比对的采集口")
    assert main.settings.fast_path_law_version_check is False, "开关默认值被改过 ⇒ 这份基线不再是默认态"
    samples = {
        "stream_join": {
            "question": FACT_W01_2019[0],
            "parts": STREAM_PARTS_HIT,
            "fallback_text": None,
            "law_as_of": AS_OF_2026,
        },
        "fallback_invoke_llm": {
            "question": FACT_W01_2019[0],
            "parts": (),
            "fallback_text": CLAIM_S01_WRONG_CURRENT_LAW,
            "law_as_of": AS_OF_2026,
        },
        "no_baseline_date_sent": {
            "question": FACT_ON_WATERSHED[0],
            "parts": STREAM_PARTS_MISS,
            "fallback_text": None,
            "law_as_of": None,
        },
        "neutral_answer": {
            "question": FACT_W02_2023[0],
            "parts": (NEUTRAL_ANSWER,),
            "fallback_text": None,
            "law_as_of": AS_OF_2020_EVE,
        },
    }
    dumps = {}
    for name, kw in samples.items():
        run = run_stream_exit(monkeypatch, on=False, **kw)
        dumps[name] = _normalise_frames(run.raw)
    payload = json.dumps(dumps, ensure_ascii=False, sort_keys=True, indent=1)
    with open(out, "wb") as fh:
        fh.write(
            json.dumps(
                {
                    "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                    "n_samples": len(dumps),
                    "samples": dumps,
                },
                ensure_ascii=False,
                indent=1,
            ).encode("utf-8")
        )
