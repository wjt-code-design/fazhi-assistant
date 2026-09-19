"""S5 §6-③：缓冲轻量出口 5 个 return 点的逐字基线采集。

改前跑一次存 baseline，改后再跑一次比对，差异条数必须为 0（默认关 ⇒ 行为逐字不变）。

用法（cwd 必须是 backend/）：
    ./venv/Scripts/python.exe ../dispatch-output/s5-fastpath-gate-20260919/capture_light_baseline.py baseline
    ./venv/Scripts/python.exe ../dispatch-output/s5-fastpath-gate-20260919/capture_light_baseline.py on
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(str(BACKEND / ".env"))

import llm_registry  # noqa: E402
import main  # noqa: E402
import quality  # noqa: E402

# 答案文本：一组"会跨分水岭"（引用民法典三年时效），一组中性（不含时效表述）。
CIVIL_TODAY = "依据《民法典》第一百八十八条，诉讼时效期间为三年，自权利人知道或者应当知道权利受到损害之日起计算。"
NEUTRAL = "该问题需要结合合同约定与履行情况综合判断，建议核对条文原文。"

# 事实来自用户自述（与 agent 路径 _fact_texts 同语义：事实文本，不是法条文本）。
FACT_Q_2019 = "2019年3月5日对方向我借款10万元，约定当日归还，此后我一直没催过。我现在起诉还能胜诉吗？"
FACT_Q_2022 = "2022年6月1日对方向我借款10万元，约定当日归还，此后我一直没催过。我现在起诉还能胜诉吗？"


class FakeLLM:
    def __init__(self, content: str, key: str, tokens: int = 10) -> None:
        self._content = content
        self._key = key
        self._tokens = tokens

    def invoke(self, messages):
        return SimpleNamespace(content=self._content, usage_metadata={"total_tokens": self._tokens})


def make_pre(user_text: str) -> dict:
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": user_text,
        "user_text": user_text,
        "sources": [{"source": "民法典", "article": "第一百八十八条"}],
        "context": "民法典 第一百八十八条 ...",
    }


def case_defs() -> list[dict]:
    """每个 return 点两个变体（会命中 / 中性）；return 点行号按 2026-09-19 采集时实测标注。"""
    pts = [
        ("R1_1171_pass", "ok-light"),
        ("R2_1176_quota", "quota"),
        ("R3_1180_no_stronger", "same-key"),
        ("R4_1186_escalate_pass", "escalate-pass"),
        ("R5_1187_escalate_fail", "escalate-fail"),
    ]
    out = []
    for pid, shape in pts:
        for flavor, light_text, flag_text in (
            ("civil2019", CIVIL_TODAY, CIVIL_TODAY),
            ("neutral", NEUTRAL, NEUTRAL),
        ):
            out.append(
                {
                    "id": f"{pid}__{flavor}",
                    "return_point": pid,
                    "shape": shape,
                    "user_text": FACT_Q_2019 if flavor == "civil2019" else FACT_Q_2022,
                    "light_text": light_text,
                    "flag_text": flag_text,
                }
            )
    return out


def install_fakes(case: dict) -> None:
    light = FakeLLM(case["light_text"], "L")
    flag = FakeLLM(case["flag_text"], "F")
    shape = case["shape"]

    def fake_pick(modality, tier, *, exclude=None):
        if tier == "light":
            return ("L", light)
        if shape == "quota":
            raise llm_registry.QuotaExhausted("x")
        if shape == "same-key":
            return ("L", light)  # 轻量即旗舰
        return ("F", flag)

    llm_registry.registry.pick = fake_pick  # 进程内替身，不落盘
    llm_registry.registry.model_of = lambda k: {"L": "m-light", "F": "m-flag"}.get(k, "")
    llm_registry.registry.deduct = lambda k, t: None

    seq: list = {
        "ok-light": [(True, "")],
        "quota": [(False, "vague")],
        "same-key": [(False, "vague")],
        "escalate-pass": [(False, "no_citation_while_hit"), (True, "")],
        "escalate-fail": [(False, "vague"), (False, "vague")],
    }[shape]
    it = iter(seq)

    def fake_self_check(answer, ctx, in_kb=None):
        ok, reason = next(it)
        return quality.Verdict(ok, reason)

    quality.self_check = fake_self_check


def run_case(case: dict, as_of=None) -> dict:
    install_fakes(case)
    if as_of is None:
        res = main._light_buffered(make_pre(case["user_text"]), [])  # 现网两参数形状
    else:
        res = main._light_buffered(make_pre(case["user_text"]), [], as_of)
    return {
        "answer": res.answer,
        "key": res.key,
        "modality": res.modality,
        "tier": res.tier,
        "usage": res.usage,
        "escalated": res.escalated,
        "verdict": res.verdict,
    }


def main_run(mode: str) -> int:
    if mode not in ("baseline", "on", "on_asof"):
        print(f"unknown mode: {mode}", flush=True)
        return 2
    # on      = 开关开、按现网两参数形状调用（拿不到基准日）⇒ 只可能触发 fail-closed
    # on_asof = 开关开、显式给基准日 ⇒ 触发的是**版本判定本身**（与 on 对照才能把两者分开证）
    if hasattr(main.settings, "fast_path_law_version_check"):
        setattr(main.settings, "fast_path_law_version_check", mode != "baseline")
        effective = getattr(main.settings, "fast_path_law_version_check")
    else:
        effective = None  # 改前：该开关尚不存在
    as_of = date(2026, 9, 18) if mode == "on_asof" else None

    records = []
    nondeterministic = 0
    for case in case_defs():
        a = run_case(case, as_of)
        b = run_case(case, as_of)
        if a != b:
            nondeterministic += 1
        records.append({"input": case, "run1": a, "run2": b, "stable": a == b})

    dump = json.dumps(records, ensure_ascii=False, sort_keys=True)
    payload = {
        "mode": mode,
        "switch_present_in_settings": effective is not None,
        "switch_effective_value": effective,
        "call_signature_arity": 2,
        "nondeterministic_cases": nondeterministic,
        "case_count": len(records),
        "records": records,
        "dump_sha256": hashlib.sha256(dump.encode("utf-8")).hexdigest(),
    }
    out_dir = Path(__file__).resolve().parent
    out_path = out_dir / f"light-baseline-{mode}.json"
    # 坑①：core.autocrlf + Windows 文本模式会把 \n 写成 \r\n ⇒ 写字节
    out_path.write_bytes(json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8"))
    print(f"mode={mode} cases={len(records)} nondeterministic={nondeterministic}", flush=True)
    print(f"dump_sha256={payload['dump_sha256']}", flush=True)
    print(f"wrote={out_path}", flush=True)
    print("rc=0", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main_run(sys.argv[1] if len(sys.argv) > 1 else "baseline"))
