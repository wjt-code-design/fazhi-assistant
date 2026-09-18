"""确定性时效计算（R11，2026-09-18）。外部 harness 方案差距分析（
docs/external-harness-plan-gap-analysis-20260918.md）P0-1：方案 §2.5.4 表2 要求
「时效/金额/管辖等高频期限做成确定性工具 + 硬编码常量，禁止 LLM 心算」。
grep 全仓证实：此前「诉讼时效三年」只存在于题库文本与语料正文——知识是让模型
从语料里"读"出来的，不是程序算出来的（跨 2021-01-01 场景必然错，方案 T1）。

数据真源 = 本模块**代码级常量**：
- 普通民事诉讼时效 **3 年** ——《民法典》第 188 条（自权利人知道或应当知道权利受损
  及义务人之日起算）；
- 最长权利保护 **20 年** ——《民法典》第 188 条第 2 款（自权利受损之日起算，
  **不适用中止、中断**；普通时效经中断重新起算后亦不得突破该上限）；
- 劳动争议仲裁时效 **1 年** ——《劳动争议调解仲裁法》第 27 条（劳动报酬争议在
  劳动关系存续期间不受 1 年限制；劳动关系终止的，自终止之日起 1 年内提出）；
- 民法典分水岭 **2021-01-01** ——《民法典》第 1260 条废止九部法律；分水岭前普通
  时效按《民法通则》第 135 条为 2 年。

纯函数、无 IO、无模型调用；缺日期/无法判型 → 返回 None/空集（fail-open，
同 fee_calc 先例）。受控 token 消费口径与 fee_calc 相同：writer/verifier 在
`settings.numeric_matching_v2` 开启时并入数字白名单（默认关 = 行为逐字不变）。

刻意保守的边界（自审记录）：
1. **时效衔接不猜测**：跨 2021-01-01 事实存在"旧法已届满不复活 / 施行日尚未届满
   适用民法典三年"的衔接规则（《民法典》时间效力规定），需个案事实判断 ⇒
   `calc_limitation` 对分水岭前事实标注 `needs_case_review=True`（仍给出旧法
   2 年口径供参考），而**白名单函数对分水岭前事实一律返回空集**——不把衔接期
   判断固化为常量，宁可放行原校验（fail-open）也不放错 token。
2. **中止（暂停）暂不支持**：只实现中断（民法典 195 条，自中断之日起重新计算）。
   中止需"最后 6 个月内 + 不可抗力/其他障碍"的定性判断，硬编码反而制造伪确定性。
3. **事实日代理**：用户陈述里通常无法区分「权利受损日」与「知道或应当知道日」，
   白名单口径取事实文本中**最早**日期为起算锚（更保守）；起算日语义由调用方
   （未来的确定性工具/追问环节）显式传入 `knowledge_date` 时才可精确。
4. 本模块只产出**年数 token**（duration:N:年），不产出日期 token——届满日依赖
   起算日语义（见边界 3），放行具体日期 token 的误放风险大于收益。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import date

CIVIL_GENERAL_YEARS = 3  # 《民法典》第188条第1款
CIVIL_MAXIMUM_YEARS = 20  # 《民法典》第188条第2款（不适用中止、中断）
CIVIL_PRE_CODE_YEARS = 2  # 《民法通则》第135条（分水岭前口径）
LABOR_ARBITRATION_YEARS = 1  # 《劳动争议调解仲裁法》第27条
CIVIL_CODE_EFFECTIVE = date(2021, 1, 1)  # 《民法典》第1260条：九部法律同日废止

_CLAIM_TYPES = ("civil", "labor_arbitration", "labor_remuneration")

# 仅认 NFKC 归一后的阿拉伯数字日期（2021年1月1日 / ２０２１年０１月０１日）。
# 中文数字日期（二〇二一年…）刻意不解析 → fail-open，不引入口径分叉。
_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

# 白名单触发关键词：claim 文本必须**断言时效结论**才允许放行年数 token，
# 防止把年份常量泄漏给无关 claim（如"借款 3 年后到期"不含时效关键词则不触发）。
_LABOR_KEYWORDS = ("仲裁时效", "劳动仲裁", "劳动争议仲裁")
_CIVIL_KEYWORDS = ("诉讼时效", "时效期间", "时效")

# 与 writer.numeric_tokens 的 token 契约对齐：duration:{N}:{单位}，N 经
# _canonical_number 归一（阿拉伯数字字符串）。此处只产出整数年，格式恒定。
_DURATION_TOKEN = "duration:{n}:年"


def extract_dates(texts: Iterable[str]) -> list[date]:
    """一组文本中的全部可解析日期（升序去重）；无可解析日期 → 空列表。"""
    found: set[date] = set()
    for text in texts or []:
        normalized = unicodedata.normalize("NFKC", text or "")
        for match in _DATE_RE.finditer(normalized):
            try:
                found.add(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
            except ValueError:
                continue  # 非法日期（2021年2月30日）→ 逐个跳过，不整体放弃
    return sorted(found)


def _add_years(day: date, years: int) -> date:
    """date + N 年（2月29日 → 平年落 2月28日，不静默报错）。"""
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 2/29 → 平年
        return day.replace(year=day.year + years, day=28)


def calc_limitation(
    claim_type: str,
    *,
    fact_date: date,
    knowledge_date: date | None = None,
    interruption_dates: Sequence[date] = (),
    labor_termination_date: date | None = None,
    as_of: date | None = None,
) -> dict | None:
    """确定性计算时效届满日；claim_type 非法 → None。

    返回 dict（含 law_basis/general_years/start_date/expiry_date/notes 等）；
    `needs_case_review=True` 表示结果落在时间效力衔接区，只能作参考不能直接当结论。
    `as_of` 传入时才计算 `expired_as_of`（缺省 None → 不判定，保持纯函数确定性）。
    """
    if claim_type not in _CLAIM_TYPES:
        return None
    notes: list[str] = []
    if claim_type == "labor_remuneration" and labor_termination_date is None:
        # 《劳动争议调解仲裁法》第27条第4款：劳动关系存续期间拖欠劳动报酬的争议
        # 不受 1 年仲裁时效限制（终止后方起算）。
        return {
            "claim_type": claim_type,
            "law_basis": "《劳动争议调解仲裁法》第27条第4款",
            "general_years": None,
            "start_date": None,
            "expiry_date": None,
            "max_protection_expiry": None,
            "expired_as_of": None,
            "needs_case_review": False,
            "not_limited_within_relationship": True,
            "notes": [
                "劳动关系存续期间因拖欠劳动报酬发生争议的，申请仲裁不受一年时效期间的限制；"
                "劳动关系终止的，应当自劳动关系终止之日起一年内提出。"
            ],
        }
    if claim_type.startswith("labor"):
        # 第27条第1款：自知道或应当知道权利被侵害之日起 1 年；劳动报酬争议以
        # 劳动关系终止日为起算点（第4款后段）。remuneration 且无终止日的情形
        # 已在上方 not_limited 分支返回 → 此处必有终止日。
        if claim_type == "labor_remuneration":
            assert labor_termination_date is not None
            start: date = labor_termination_date
        else:
            start = knowledge_date or fact_date
        return {
            "claim_type": claim_type,
            "law_basis": "《劳动争议调解仲裁法》第27条",
            "general_years": LABOR_ARBITRATION_YEARS,
            "start_date": start,
            "expiry_date": _add_years(start, LABOR_ARBITRATION_YEARS),
            "max_protection_expiry": None,
            "expired_as_of": (as_of > _add_years(start, LABOR_ARBITRATION_YEARS)) if as_of else None,
            "needs_case_review": False,
            "not_limited_within_relationship": False,
            "notes": notes,
        }
    # ---- civil ----
    pre_code = fact_date < CIVIL_CODE_EFFECTIVE
    years = CIVIL_PRE_CODE_YEARS if pre_code else CIVIL_GENERAL_YEARS
    if pre_code:
        notes.append(
            "事实发生于《民法典》施行（2021-01-01）前，普通时效按《民法通则》二年口径给出；"
            "施行日尚未届满时是否衔接适用《民法典》三年（时间效力规定）需个案复核。"
        )
    start = knowledge_date or fact_date
    expiry = _add_years(start, years)
    # 中断（民法典195条）：自中断、有关程序终结之日起重新计算。仅接纳落在
    # [start, expiry] 区间内的中断日——区间外的日期对当前起算无意义。
    for interruption in sorted(set(interruption_dates)):
        if start <= interruption <= expiry:
            expiry = _add_years(interruption, years)
    # 最长保护期（188条第2款）：自权利受损之日起 20 年，不适用中止、中断——
    # 同时构成普通时效（含中断重新起算）的客观上限。
    max_protection_expiry = _add_years(fact_date, CIVIL_MAXIMUM_YEARS)
    if expiry > max_protection_expiry:
        expiry = max_protection_expiry
        notes.append("普通时效经中断重新起算后仍受最长权利保护期间（20年）约束，已按上限截断。")
    return {
        "claim_type": claim_type,
        "law_basis": "《民法典》第188条" if not pre_code else "《民法通则》第135条（衔接期，需个案复核）",
        "general_years": years,
        "start_date": start,
        "expiry_date": expiry,
        "max_protection_expiry": max_protection_expiry,
        "expired_as_of": (as_of > expiry) if as_of else None,
        "needs_case_review": pre_code,
        "not_limited_within_relationship": False,
        "notes": notes,
    }


def controlled_limitation_tokens(claim_text: str, fact_texts: Iterable[str]) -> set[str]:
    """受控放行集：时效类 claim 可引用的年数 token（duration:N:年）。

    与 fee_calc.controlled_fee_tokens 同一消费口径（writer/verifier 在
    numeric_matching_v2 开启时并入数字白名单；单一真源拆两防线）。触发条件全部
    确定性可判，任一不满足 → 空集（fail-open，不改既有校验行为）：
    1. claim 文本断言时效结论（命中时效关键词）；
    2. 类型可判（劳动/仲裁 → 1年；否则民事）；
    3. 民事：事实文本含可解析日期且最早日期 ≥ 2021-01-01（分水岭前 → 空集，
       见模块 docstring 边界 1）。

    刻意**不**放行裸数字 token（number:N）与日期 token（见模块 docstring 边界 4）。
    """
    text = unicodedata.normalize("NFKC", claim_text or "")
    is_labor = any(keyword in text for keyword in _LABOR_KEYWORDS)
    if not is_labor and not any(keyword in text for keyword in _CIVIL_KEYWORDS):
        return set()
    if is_labor:
        return {_DURATION_TOKEN.format(n=LABOR_ARBITRATION_YEARS)}
    dates = extract_dates(fact_texts)
    if not dates:
        return set()
    if dates[0] < CIVIL_CODE_EFFECTIVE:
        return set()
    return {
        _DURATION_TOKEN.format(n=CIVIL_GENERAL_YEARS),
        _DURATION_TOKEN.format(n=CIVIL_MAXIMUM_YEARS),
    }


def law_version_crosses_watershed(
    claim_text: str,
    fact_texts: Iterable[str],
    law_as_of: date | None,
) -> bool:
    """True = 「按 law_as_of 版本的法回答分水岭前事实」的版本适用冲突（R15，2026-09-18）。

    判据全确定性，任一不满足 → False（不拦，调用方行为逐字不变）：
    1. claim 断言**民事**时效结论（命中 _CIVIL_KEYWORDS）；劳动仲裁走劳调法 27 条
       （2008 年生效，与民法典分水岭无关）→ 一律 False；
    2. `law_as_of` 已给定（None = 调用方没给基准日，无从判定）；
    3. 事实文本含可解析日期（无日期不拦：「没日期就不许谈时效」会误伤纯法条陈述）；
    4. 最早事实日（本模块边界 3 的起算锚）与 `law_as_of` **分跨** CIVIL_CODE_EFFECTIVE 两侧。

    与 `controlled_limitation_tokens` 的分工（不是重复）：后者只在**数字白名单**维度
    收回放行（fail-open，边界 1 刻意保守），本函数在**版本适用**维度终止作答
    （fail-closed）。它覆盖的是既有门看不见的一类：claim 不带年数 token（仅引用
    《民法典》某条）时，numeric 门无 token 可算、citation 门只验"条文是否在证据池"
    ——而证据池本身就是按 law_as_of 做 cutoff 捞的，必然只捞得到分水岭后的法。
    """
    text = unicodedata.normalize("NFKC", claim_text or "")
    if any(keyword in text for keyword in _LABOR_KEYWORDS):
        return False
    if not any(keyword in text for keyword in _CIVIL_KEYWORDS):
        return False
    if law_as_of is None:
        return False
    dates = extract_dates(fact_texts)
    if not dates:
        return False
    return (dates[0] < CIVIL_CODE_EFFECTIVE) != (law_as_of < CIVIL_CODE_EFFECTIVE)


__all__ = [
    "CIVIL_CODE_EFFECTIVE",
    "CIVIL_GENERAL_YEARS",
    "CIVIL_MAXIMUM_YEARS",
    "CIVIL_PRE_CODE_YEARS",
    "LABOR_ARBITRATION_YEARS",
    "calc_limitation",
    "controlled_limitation_tokens",
    "extract_dates",
    "law_version_crosses_watershed",
]
