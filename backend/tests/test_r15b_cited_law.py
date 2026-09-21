"""票 R15-B 先红用例：版本门必须能**区分**"正确引用旧法/说明衔接"与"用新法错答旧事实"。

需求真源（`evals/watershed-cases-r15.json:32`）：critical 只有一条——
「对2019年事实**直接按《民法典》第188条给出三年时效结论而不作新旧法衔接说明**」。

⇒ 现行判据（"含时效关键词 + 两个日期分跨分水岭 ⇒ 冲突"）把判定范围扩大了一圈：
   ①正确引用《民法总则》；②明确说不直接适用《民法典》；③仅提示需结合衔接规则 —— 都被判 True。
修复方向（票面明令，确定性实现、不引入模型判定器）：
   先判 claim **引用的是哪部法**（新法/旧法）与**是否作衔接说明**；
   判不了（无明确新法引用）⇒ 不确定 ⇒ **不拦**；只有"明确按新法答 + 无衔接说明"才判冲突。
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from agent.limitation_calc import law_version_crosses_watershed  # noqa: E402

FACT_2019 = ["借款到期日为2019年3月5日，权利人当日知道权利受损。"]
FACT_2023 = ["借款到期日为2023年8月1日，权利人当日知道权利受损。"]
AS_OF_2026 = date(2026, 9, 21)


# ─────────────── 先红：应当**放行**的三种正确/半正确表述 ───────────────


def test_r15b_correct_old_law_citation_is_not_a_conflict():
    """先红：正确引用《民法总则》第188条 ⇒ 需求上不是 critical（现返回 True）。"""
    claim = "本案权利人于2019年知道权利受损，应适用当时有效的《民法总则》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


def test_r15b_explicit_non_application_of_new_law_is_not_a_conflict():
    """先红：明确说明"不直接适用《民法典》" ⇒ 不是 critical（现返回 True）。"""
    claim = "本案事实发生于民法典施行之前，不直接适用《民法典》第188条，应按当时有效的《民法总则》第188条处理，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


def test_r15b_transition_note_only_is_not_a_conflict():
    """先红：仅提示"需结合新旧法衔接规则判断" ⇒ 不是 critical（现返回 True）。"""
    claim = "本案时效应结合新旧法衔接规则判断，本回答仅供参考。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


# ─────────────── 控制腿：该拦的必须仍拦，其余语义不变 ───────────────


def test_r15b_control_new_law_without_transition_still_conflict():
    """控制腿：直接按《民法典》答且不衔接 ⇒ **必须拦**（需求里唯一的 critical；修复后保持）。"""
    claim = "根据《民法典》第188条，诉讼时效为三年，自权利人知道权利受损之日起算。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is True


def test_r15b_control_same_side_not_conflict():
    """控制腿：事实与基准日同侧 ⇒ 不命中（既有语义）。"""
    claim = "根据《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, FACT_2023, AS_OF_2026) is False


def test_r15b_control_no_dates_no_conflict():
    """控制腿：无日期 ⇒ 不拦（"没日期就不许谈时效"会误伤纯法条陈述）。"""
    claim = "根据《民法典》第188条，诉讼时效为三年。"
    assert law_version_crosses_watershed(claim, ["本案与具体日期无关。"], AS_OF_2026) is False


def test_r15b_control_no_civil_keyword_no_conflict():
    """控制腿：不含时效关键词 ⇒ 不拦（白名单触发）。"""
    claim = "本案借款合同成立并生效，双方应按约定履行。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False


def test_r15b_known_limitation_generic_transition_word_can_be_abused():
    """已知局限（**钉住形状**，非缺陷修复——Spec 轴评审 2026-09-21 指出）：

    `_TRANSITION_MARKERS` 里的通用词（当时有效/旧法）偏宽——一个**真错答**只要顺带提一句
    「旧法规定为二年」就能绕过版本门（它确实按《民法典》答了三年，却没有任何真实衔接说明）。
    这与票面「宁可不拦也不错拦」的取向一致，属确定性启发式的固有代价；
    守它的正解是**评测集反例**（`evals/` 为冻结资产，不在本票动）。
    本用例把该形状钉住：将来若有人收紧标记集，这里的行为变化会被看见（而非静默发生）。
    """
    claim = "根据《民法典》第188条，诉讼时效为三年（旧法规定为二年）。"
    assert law_version_crosses_watershed(claim, FACT_2019, AS_OF_2026) is False
