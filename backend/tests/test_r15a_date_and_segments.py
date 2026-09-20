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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from agent.limitation_calc import (  # noqa: E402
    CIVIL_CODE_EFFECTIVE,
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
