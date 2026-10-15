"""票 R15-A 先红用例（Owner 2026-09-21 批准开票）：

**R15-5**（日期格式）：`_DATE_RE` 只认「2019年3月5日」，ISO `2019-03-05` 与斜杠 `2019/3/5`
静默 fail-open ⇒ 版本门漏判。修法（票面明令）：**只补 ISO 与斜杠两种明确格式**，
不上通用自然语言日期解析器；同时为"支持/不支持的输入形状"建立契约测试。

**R15-4**（快车道分段）：`law_version_crosses_watershed` 把**整段答案**当 claim——
答案里任何位置出现劳动关键词就整段跳过民事检查 ⇒ 混合答案里的民事错答绕过版本门。
修法（票面明令）：按**确定性句段拆分**后逐段应用同一判据（不加第二套版本门）；
劳动排除只作用于**实际命中劳动关键词的句段**。
"""

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from agent.limitation_calc import (  # noqa: E402
    CIVIL_CODE_EFFECTIVE,
    accrual_anchor_dates,
    extract_dates,
    law_version_crosses_watershed,
)

FACT_2019 = ["借款到期日为2019年3月5日，权利人当日知道权利受损。"]
AS_OF_2026 = date(2026, 9, 21)


# ───────────────────────── R15-5：日期格式 ─────────────────────────


def test_r15a_iso_date_is_parsed():
    """先红：ISO 日期（2019-03-05）此前不被解析 ⇒ extract_dates 返回 []。"""
    assert extract_dates(["借款到期日为2019-03-05，权利人当日知道权利受损。"]) == [date(2019, 3, 5)]


def test_r15a_slash_date_is_parsed():
    """先红：斜杠日期（2019/3/5）此前不被解析。"""
    assert extract_dates(["借款到期日为2019/3/5，权利人当日知道权利受损。"]) == [date(2019, 3, 5)]


def test_r15a_contract_chinese_numerals_still_unparsed():
    """契约（支持/不支持形状）：中文数字日期**刻意不解析**（fail-open，不引入口径分叉）——保持不变。"""
    assert extract_dates(["借款到期日为二〇一九年三月五日。"]) == []


def test_r15a_contract_digit_run_not_misread_as_date():
    """契约：更长的数字串（如编号 12021-01-01）不得被截成 2021-01-01 误读。"""
    assert extract_dates(["合同编号12021-01-01-XYZ，本案与日期无关。"]) == []


def test_r15a_iso_date_feeds_the_gate():
    """端到端：ISO 事实日期此前让版本门**漏判**（无日期不拦）；修复后应命中。"""
    claim = "根据《民法典》第188条，诉讼时效为三年，自权利人知道权利受损之日起算。"
    facts = ["借款到期日为2019-03-05。"]
    assert law_version_crosses_watershed(claim, facts, AS_OF_2026) is True


# ───────────────────────── R15-4：分段判定 ─────────────────────────


def test_r15a_labor_sentence_elsewhere_no_longer_shields_civil_error():
    """先红：民事错答句 + 别处的劳动句 ⇒ 此前整段被劳动关键词放过（返回 False）；修复后应命中。"""
    claim = "本案借款适用《民法典》第188条，诉讼时效为三年。另外，劳动仲裁时效为一年。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is True


def test_r15a_control_pure_labor_claim_still_passes_through():
    """控制腿：纯劳动口径的 claim（**含劳动关键词**）⇒ 仍不拦（劳调法 27 条与分水岭无关）。

    ⚠️ 另一发现（超出本票射程，记为 R15-B 的输入）：「劳动争议**申请仲裁**的时效期间为一年」
    **不含**任何 `_LABOR_KEYWORDS`（仲裁时效/劳动仲裁/劳动争议仲裁）⇒ 现行判据把它当民事误拦。
    这是关键词脆性，属 R15-1（过触发）家族，不在 R15-A（分段判定）的修复范围。
    """
    claim = "本案应适用劳动仲裁时效一年的规定，从当事人知道权利被侵害之日起算。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


def test_r15_4_comma_joined_labor_no_longer_shields_civil_error():
    """先红（R15-4）：劳动句与民事错答句**用逗号连在同一句里** ⇒ 现行分段只按 `。！？；\\n` 切，
    整句含劳动关键词 ⇒ 民事错答被一起放过（返回 False）。这是"缩小劳动排除范围"要闭的形状。

    快车道把**整段答案**传进本函数（`main._law_version_gate`），所以这个形状在启用后可触发。
    """
    claim = "劳动仲裁时效为一年，本案借款适用《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is True


def test_r15_4_control_pure_labor_with_comma_still_passes_through():
    """控制腿（防过度分段把纯劳动答案变成误拦）：逗号连接的**纯劳动**口径 ⇒ 仍不拦。

    分段后每一段要么含劳动关键词（跳过）、要么没有新法引用标记（不满足判据 1）⇒ False。
    """
    claim = "劳动仲裁时效为一年，仲裁申请应从当事人知道权利被侵害之日起一年内提出。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


def test_r15_4_control_comma_joined_same_side_stays_no_conflict():
    """控制腿：同一形状但事实与基准日同侧 ⇒ 不拦（证明修复没有把命中面扩大到无关请求）。"""
    claim = "劳动仲裁时效为一年，本案借款适用《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, ["借款到期日为2023年8月1日。"], AS_OF_2026) is False


def test_r15_4_control_sentence_shape_unchanged():
    """控制腿：原本已能拦的"两句"形状在改动后行为不变（防修一个形状碰坏另一个）。"""
    claim = "劳动仲裁时效为一年。本案借款适用《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is True


def test_r15_4_control_comma_split_does_not_create_new_false_positive():
    """对照腿（本改动**新打开**的风险面）：逗号入段后，劳动口径里那句
    "《民法典》的诉讼时效规定不适用于仲裁申请"会单独成段——它同时含民事关键词与新法标记，
    若衔接说明不再被同段的劳动关键词掩护，就会被误拦。本腿钉住"这种仍不拦"。

    写这条的理由：修复漏拦时，同一处改动完全可能把过触发面扩大；不测这一侧就等于只看一半。
    """
    claim = "本案为劳动争议，劳动仲裁时效为一年，《民法典》的诉讼时效规定并不直接适用于仲裁申请。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


# ───────────────────────── R15-2：起算锚的相关性 ─────────────────────────

BIRTH_AND_DUE = ["甲1980年3月5日出生", "2023年4月1日借款到期并知损"]


@pytest.mark.parametrize(
    "fact",
    [
        "甲1980年1月1日出生并于2023年3月5日借款到期，债务人未还款。",
        "2023-03-05借款到期的债权人出生于1980-01-01。",
        "借款于2019/3/5到期或于2023/3/5到期，具体日期不明。",
    ],
)
def test_r15_2_ambiguous_dates_in_one_clause_do_not_trigger_conflict(fact):
    claim = "根据《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, [fact], AS_OF_2026) is False
    assert accrual_anchor_dates([fact]) == []


def test_r15_2_ambiguous_clause_does_not_hide_another_clear_anchor():
    facts = ["甲1980年1月1日出生并于2023年3月5日借款到期，另一笔借款于2019年3月5日到期。"]
    assert accrual_anchor_dates(facts) == [date(2019, 3, 5)]
    assert law_version_crosses_watershed("根据《民法典》第188条，诉讼时效为三年。", facts, AS_OF_2026) is True


def test_r15_2_repeated_same_date_is_not_ambiguous():
    facts = ["2019年3月5日借款到期且2019-03-05知悉权利受损。"]
    assert accrual_anchor_dates(facts) == [date(2019, 3, 5)]
    assert law_version_crosses_watershed("根据《民法典》第188条，诉讼时效为三年。", facts, AS_OF_2026) is True


def test_r15_2_birth_date_no_longer_impersonates_the_accrual_date():
    """先红（R15-2）：现行判据取 `extract_dates` 的**全局最早日**，与 claim 句段无绑定
    ⇒ 出生日期（与本案请求权起算无关）会被当成事实日。

    本案事实里的起算锚是 2023 年到期并知损（分水岭后），基准日 2026 也在分水岭后 ⇒ 同侧，
    不该拦。改动前返回 True（因为 1980 更早）。
    """
    claim = "诉讼时效适用《民法典》第188条，为三年。"
    assert law_version_crosses_watershed(claim, BIRTH_AND_DUE, AS_OF_2026) is False


def test_r15_2_control_irrelevant_date_alone_does_not_intercept():
    """先红（同族）：事实里**只有**出生日期 ⇒ 认不出任何起算锚 ⇒ 不拦。

    改动前：1980 与 2026 分跨分水岭 ⇒ 拦。这是一次实打实的误拦（把一个无从判定时效起算的
    请求判成版本冲突）。
    """
    claim = "诉讼时效适用《民法典》第188条，为三年。"
    assert law_version_crosses_watershed(claim, ["甲1980年3月5日出生。"], AS_OF_2026) is False


def test_r15_2_control_real_pre_watershed_accrual_still_intercepts():
    """控制腿（防把修复做成"只测放行"）：起算锚确实在分水岭前 ⇒ 仍必须拦。"""
    claim = "诉讼时效适用《民法典》第188条，为三年。"
    assert law_version_crosses_watershed(claim, ["甲于2019年5月1日借款到期并知道权利受损。"], AS_OF_2026) is True


def test_r15_2_control_unrelated_date_after_relevant_one_does_not_flip_the_result():
    """控制腿：起算锚 2019 前，另有一句无关的 2023 日期 ⇒ 仍按起算锚拦。

    钉住"取相关日期里最早的那个"而不是"取最后出现的"或"取全局最晚"，否则修 A 会破 B。
    """
    claim = "诉讼时效适用《民法典》第188条，为三年。"
    facts = ["双方于2023年1月1日签订新的合作协议。", "本案借款2019年3月5日到期，权利人当日知道受损。"]
    assert law_version_crosses_watershed(claim, facts, AS_OF_2026) is True


def test_r15_2_known_limitation_unlisted_phrasing_fails_open():
    """明示边界（不是断言正确，是钉住"我们知道这里漏"）：起算锚词表**之外**的表达
    ⇒ 认不出锚 ⇒ 不拦。

    这条腿存在的理由：`accrual_anchor_dates` 是词面相关性，不是日期推理（票面明令不造解析框架），
    所以它的覆盖面=词表。把"漏在哪一侧"写成用例，比在注释里说"可能漏"更可查——
    将来有人扩词表时，这条会告诉他当前形状的行为是什么。
    """
    claim = "诉讼时效适用《民法典》第188条，为三年。"
    assert law_version_crosses_watershed(claim, ["双方于2019年3月5日当面商谈了此事。"], AS_OF_2026) is False


def test_r15_2_multiple_anchors_use_the_earliest():
    """钉住"多个锚日里取**最早**"这个方向：最早的相关事实日最可能落在分水岭前 ⇒ 判定偏保守。

    配这条的理由：`accrual_anchor_dates` 返回升序，取 `[0]` 还是 `[-1]` 是一个真实的口径选择，
    而它上面三条腿都只有**一个**锚日——没有这条腿，"取最晚"这种改法可以全绿通过。
    """
    claim = "诉讼时效适用《民法典》第188条，为三年。"
    facts = ["本案一笔借款于2023年4月1日到期。", "另一笔借款于2019年3月5日到期未还。"]
    assert law_version_crosses_watershed(claim, facts, AS_OF_2026) is True


def test_r15a_control_single_civil_sentence_unchanged():
    """控制腿：单句民事错答（无劳动句）⇒ 行为与修复前一致（命中）。"""
    claim = "根据《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is True


def test_r15a_control_same_side_no_conflict():
    """控制腿：事实与基准日同侧 ⇒ 不命中（既有语义保持）。"""
    claim = "根据《民法典》第188条，诉讼时效为三年。另外，劳动仲裁时效为一年。"
    facts = ["借款到期日为2023年8月1日。"]
    assert law_version_crosses_watershed(claim, facts, AS_OF_2026) is False


def test_r15a_control_watershed_constant_unchanged():
    """控制腿：分水岭常量仍是 2021-01-01（不另立第二个分水岭）。"""
    assert CIVIL_CODE_EFFECTIVE == date(2021, 1, 1)
