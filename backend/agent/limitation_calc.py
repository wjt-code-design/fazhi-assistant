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
- 普通时效自 **2017-10-01** 起为 3 年（《民法总则》第188条）；此前为2年，
  尚未届满的按法释〔2018〕12号衔接，已经届满的不复活。

纯函数、无 IO、无模型调用；缺日期/无法判型 → 返回 None/空集（fail-open，
同 fee_calc 先例）。受控 token 消费口径与 fee_calc 相同：writer/verifier 在
`settings.numeric_matching_v2` 开启时并入数字白名单（默认关 = 行为逐字不变）。

刻意保守的边界（自审记录）：
1. **特殊衔接不猜测**：普通二年/三年按2017年分界及未届满规则计算，特殊期间、
   中止等仍需个案事实判断。`calc_limitation` 对2021年前事实保留
   `needs_case_review=True`（给出历史普通时效口径供参考），而**白名单函数对分水岭前事实一律返回空集**——不把衔接期
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
CIVIL_PRE_CODE_YEARS = 2  # 《民法通则》第135条（2017-10-01前，保留旧导出名兼容调用方）
LABOR_ARBITRATION_YEARS = 1  # 《劳动争议调解仲裁法》第27条
CIVIL_CODE_EFFECTIVE = date(2021, 1, 1)  # 《民法典》第1260条：九部法律同日废止
CIVIL_GENERAL_PROVISIONS_EFFECTIVE = date(2017, 10, 1)

_CLAIM_TYPES = ("civil", "labor_arbitration", "labor_remuneration")

# 仅认 NFKC 归一后的明确日期格式（R15-5，2026-09-21 扩两种，Owner 批准的票 R15-A）：
#   ① 2021年1月1日 / ２０２１年０１月０１日（NFKC 归一后即阿拉伯数字）；
#   ② ISO：2021-01-01；③ 斜杠：2021/1/1。
# ISO/斜杠带 (?<!\d)(?!\d) 边界：编号串（12021-01-01-XYZ）不得被截成 2021-01-01 误读。
# 中文数字日期（二〇二一年…）**仍刻意不解析** → fail-open，不引入口径分叉（契约测试锁定）。
_DATE_RE = re.compile(
    r"(?:(?P<ymd_y>\d{4})年(?P<ymd_m>\d{1,2})月(?P<ymd_d>\d{1,2})日"
    r"|(?<!\d)(?P<iso_y>\d{4})[-/](?P<iso_m>\d{1,2})[-/](?P<iso_d>\d{1,2})(?!\d))"
)

# 白名单触发关键词：claim 文本必须**断言时效结论**才允许放行年数 token，
# 防止把年份常量泄漏给无关 claim（如"借款 3 年后到期"不含时效关键词则不触发）。
# 命名注意（Standards 轴评审 2026-09-21）：domain_rules.py 另有一个同名的 `_LABOR_KEYWORDS`
# （合同劳动条款关键词，语义不同）。这里改叫 `_LABOR_TIMING_KEYWORDS` 以示区别——
# 两处是**不同规则**，不能合并，但同名会让单一真源检索误报。
_LABOR_TIMING_KEYWORDS = ("仲裁时效", "劳动仲裁", "劳动争议仲裁")
_CIVIL_KEYWORDS = ("诉讼时效", "时效期间", "时效")

# R15-B（2026-09-21）：判"版本冲突"必须先看 claim **引用的是哪部法**与**是否作衔接说明**，
# 不能仅凭两个日期直接判错（需求真源 `evals/watershed-cases-r15.json`：critical 只有
# 「对2019年事实直接按《民法典》第188条给出三年时效结论**而不作新旧法衔接说明**」）。
#   · 未明确引用新法（民法典）⇒ 适用法**不确定** ⇒ 不拦（fail-open，宁可不拦也不错拦）；
#   · 引用了新法但作了衔接/旧法说明 ⇒ 需求上不是 critical ⇒ 不拦；
#   · 只有"明确按新法答 + 无衔接说明"才进入分水岭日期比较。
# 全确定性（不引入模型判定器，票面明令）。
_NEW_LAW_MARKERS = ("民法典",)
_TRANSITION_MARKERS = ("衔接", "法释〔2018〕12号", "不直接适用", "当时有效", "旧法")

# 起算锚词面（R15-2）：日期只有出现在含这些词的分句里，才有资格充当"时效从哪天起算"的锚。
# 刻意是**词面相关性**而不是日期推理——票面明令不为本判据造起算日解析框架。
_ACCRUAL_ANCHOR_TOKENS = (
    "到期",
    "履行期",
    "清偿",
    "偿还",
    "还款",
    "归还",
    "借款",
    "欠款",
    "拖欠",
    "未付",
    "拒付",
    "催告",
    "催收",
    "起诉",
    "知道",
    "得知",
    "应当知道",
    "受损",
    "被侵害",
    "侵害",
    "起算",
)

# 与 writer.numeric_tokens 的 token 契约对齐：duration:{N}:{单位}，N 经
# _canonical_number 归一（阿拉伯数字字符串）。此处只产出整数年，格式恒定。
_DURATION_TOKEN = "duration:{n}:年"


def _mentions(text: str, keywords: tuple[str, ...]) -> bool:
    """Standards 轴（Repeated Switches）：segment/text × 关键词表的命中判断只此一份。"""
    return any(keyword in text for keyword in keywords)


def extract_dates(texts: Iterable[str]) -> list[date]:
    """一组文本中的全部可解析日期（升序去重）；无可解析日期 → 空列表。

    R15-5：同时认「年月日」与「ISO/斜杠」两种数字形态（组布局不同 ⇒ 按命中的分支取组）。
    """
    found: set[date] = set()
    for text in texts or []:
        normalized = unicodedata.normalize("NFKC", text or "")
        for match in _DATE_RE.finditer(normalized):
            g = match.groupdict()  # 命名组（Standards 轴：去魔数下标）
            y = g["ymd_y"] or g["iso_y"]
            m = g["ymd_m"] or g["iso_m"]
            d = g["ymd_d"] or g["iso_d"]
            try:
                found.add(date(int(y), int(m), int(d)))
            except ValueError:
                continue  # 非法日期（2021年2月30日 / 2021-02-30）→ 逐个跳过，不整体放弃
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
        expiry = _add_years(start, LABOR_ARBITRATION_YEARS)
        for interruption in sorted(set(interruption_dates)):
            if start <= interruption <= expiry and (as_of is None or interruption <= as_of):
                expiry = _add_years(interruption, LABOR_ARBITRATION_YEARS)
        return {
            "claim_type": claim_type,
            "law_basis": "《劳动争议调解仲裁法》第27条",
            "general_years": LABOR_ARBITRATION_YEARS,
            "start_date": start,
            "expiry_date": expiry,
            "max_protection_expiry": None,
            "expired_as_of": (as_of > expiry) if as_of else None,
            "needs_case_review": False,
            "not_limited_within_relationship": False,
            "notes": notes,
        }
    # ---- civil ----
    pre_code = fact_date < CIVIL_CODE_EFFECTIVE
    start = knowledge_date or fact_date
    years = CIVIL_PRE_CODE_YEARS if start < CIVIL_GENERAL_PROVISIONS_EFFECTIVE else CIVIL_GENERAL_YEARS
    if pre_code:
        notes.append(
            "事实发生于《民法典》施行前；2017-10-01起普通时效为三年，"
            "此前已届满不复活、尚未届满按民法总则衔接；特殊时效及中止仍需个案复核。"
        )
    expiry = _add_years(start, years)
    # 中断（民法典195条）：自中断、有关程序终结之日起重新计算。仅接纳落在
    # [start, expiry] 区间内的中断日——区间外的日期对当前起算无意义。
    anchor = start
    for interruption in sorted(set(interruption_dates)):
        if as_of is not None and interruption > as_of:
            continue
        if interruption >= CIVIL_GENERAL_PROVISIONS_EFFECTIVE and expiry >= CIVIL_GENERAL_PROVISIONS_EFFECTIVE:
            if years == CIVIL_PRE_CODE_YEARS:
                years = CIVIL_GENERAL_YEARS
                expiry = _add_years(anchor, years)
        if start <= interruption <= expiry:
            anchor = interruption
            expiry = _add_years(interruption, years)
    if years == CIVIL_PRE_CODE_YEARS and expiry >= CIVIL_GENERAL_PROVISIONS_EFFECTIVE:
        if as_of is None or as_of >= CIVIL_GENERAL_PROVISIONS_EFFECTIVE:
            years = CIVIL_GENERAL_YEARS
            expiry = _add_years(anchor, years)
    # 最长保护期（188条第2款）：自权利受损之日起 20 年，不适用中止、中断——
    # 同时构成普通时效（含中断重新起算）的客观上限。
    max_protection_expiry = _add_years(fact_date, CIVIL_MAXIMUM_YEARS)
    if expiry > max_protection_expiry:
        expiry = max_protection_expiry
        notes.append("普通时效经中断重新起算后仍受最长权利保护期间（20年）约束，已按上限截断。")
    return {
        "claim_type": claim_type,
        "law_basis": (
            "《民法典》第188条"
            if start >= CIVIL_CODE_EFFECTIVE
            else "《民法总则》第188条（法释〔2018〕12号衔接）"
            if years == 3
            else "《民法通则》第135条"
        ),
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
    is_labor = _mentions(text, _LABOR_TIMING_KEYWORDS)
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


def accrual_anchor_dates(texts: Iterable[str]) -> list[date]:
    """从事实文本里挑"可能承担时效起算"的日期，升序返回（R15-2，2026-09-25）。

    为什么需要这一层：`law_version_crosses_watershed` 原先取 `extract_dates` 的**全局最早日**，
    与 claim 句段没有任何绑定 ⇒ "甲1980年出生"这类与请求权起算无关的日期会被当成事实日，
    把一个本不该拦的请求判成版本冲突（《民法典》第188条看的是权利受损与知悉，不是出生）。

    认不出锚时返回空表，调用方按"不拦"处理——fail-open，与本模块边界 3 的既有口径一致：
    宁可对无关日期放行，也不凭一个词面猜不出的日期去终止作答。
    """
    found: set[date] = set()
    for text in texts:
        normalized = unicodedata.normalize("NFKC", text or "")
        # 分隔符用**半角** `,`：NFKC 已把全角 `，` 折过来（见 law_version_crosses_watershed 内约束 ①）
        for segment in re.split(r"[。！？；,\n]", normalized):
            if not any(token in segment for token in _ACCRUAL_ANCHOR_TOKENS):
                continue
            found.update(extract_dates([segment]))
    return sorted(found)


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
    3. 事实文本里**认得出起算锚日期**（`accrual_anchor_dates`：既要有可解析日期，该日期还要出现在
       含起算锚词的分句里 ⇒ 否则不拦。「没日期就不许谈时效」会误伤纯法条陈述；R15-2 把同一口径
       扩到「有日期但与起算无关」，如出生日期）；
    4. 最早的**起算锚日**（R15-2 之前这里是"全局最早事实日"）与 `law_as_of` **分跨** CIVIL_CODE_EFFECTIVE 两侧。

    与 `controlled_limitation_tokens` 的分工（不是重复）：后者只在**数字白名单**维度
    收回放行（fail-open，边界 1 刻意保守），本函数在**版本适用**维度终止作答
    （fail-closed）。它覆盖的是既有门看不见的一类：claim 不带年数 token（仅引用
    《民法典》某条）时，numeric 门无 token 可算、citation 门只验"条文是否在证据池"
    ——而证据池本身就是按 law_as_of 做 cutoff 捞的，必然只捞得到分水岭后的法。
    """
    text = unicodedata.normalize("NFKC", claim_text or "")
    if law_as_of is None:
        return False
    dates = accrual_anchor_dates(fact_texts)
    if not dates:
        return False  # 事实里认不出起算锚（含"一个日期都没有"）⇒ 不拦，见 `accrual_anchor_dates`
    # R15-4（2026-09-21，票 R15-A）：按**确定性句段**拆分后逐段应用同一判据。
    # 修复的缺陷：此前把整段答案当 claim，任何位置出现劳动关键词就整段跳过民事检查
    # ⇒ 混合答案（民事错答句 + 别处的劳动句）里的民事错答绕过版本门。
    # 劳动排除现在只作用于**实际命中劳动关键词的句段**；不加第二套版本门（票面明令）。
    #
    # R15-4 第二轮（2026-09-25）：把"排除的范围"从**句**缩到**子句**，但共现判定仍留在句级。
    # 两个都是实测出来的约束，不是设计偏好：
    # ① 逗号必须按**半角** `,` 匹配——`text` 上面已过 `NFKC` 归一，全角 `，` 早被折成 `,`；
    #    按 `，` 写分隔符是"看起来对、一次都切不到"的假修复（本会话第一版就犯了这个）。
    # ② 不能直接把逗号加进 ① 的分隔符表：`根据《民法典》第188条，诉讼时效为三年` 这类最常见的
    #    答复里，新法标记与时效结论**分居两个子句**，切成子句后共现消失 ⇒ 8 条既有用例转红，
    #    等于修一个漏拦制造一批漏拦。
    # 所以本函数的单位是"句"，而劳动排除的单位是"子句"：先摘掉命中劳动关键词的子句，
    # 剩下的部分**仍按整句**做民事/新法/衔接判定。这样只有"含劳动子句的句子"行为改变，
    # 其余形状逐字不变。
    for sentence in re.split(r"[。！？；\n]", text):
        # NFKC 之后中文逗号已是 `,`（见上方约束 ①）
        segments = [c for c in sentence.split(",") if not _mentions(c, _LABOR_TIMING_KEYWORDS)]
        if not segments:
            continue  # 整句都是劳动口径 ⇒ 与民法典分水岭无关
        segment = ",".join(segments)
        if not _mentions(segment, _CIVIL_KEYWORDS):
            continue  # 该段不是民事时效结论
        # R15-B：先看引用了哪部法 / 是否衔接，再谈日期（顺序不可颠倒——否则又回到"仅凭两个日期判错"）
        if not any(marker in segment for marker in _NEW_LAW_MARKERS):
            continue  # 未明确引用新法 ⇒ 适用法不确定 ⇒ 不拦
        if any(marker in segment for marker in _TRANSITION_MARKERS):
            continue  # 已作新旧法衔接说明 ⇒ 需求上不是 critical
        if (dates[0] < CIVIL_CODE_EFFECTIVE) != (law_as_of < CIVIL_CODE_EFFECTIVE):
            return True
    return False


__all__ = [
    "CIVIL_CODE_EFFECTIVE",
    "CIVIL_GENERAL_YEARS",
    "CIVIL_MAXIMUM_YEARS",
    "CIVIL_PRE_CODE_YEARS",
    "LABOR_ARBITRATION_YEARS",
    "accrual_anchor_dates",
    "calc_limitation",
    "controlled_limitation_tokens",
    "extract_dates",
    "law_version_crosses_watershed",
]
