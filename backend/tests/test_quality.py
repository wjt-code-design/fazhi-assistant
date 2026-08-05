"""回答自检（M2）测试：纯函数，in_kb 注入控制，零 LLM、零真实库。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import quality as Q  # noqa: E402


def _kb_true(name, art):
    return True


def _kb_false(name, art):
    return False


# ---------------- detect_vague ----------------
def test_detect_vague_no_citation_marks():
    assert Q.detect_vague("这个要看相关规定处理。") is True
    assert Q.detect_vague("具体需咨询律师。") is True


def test_detect_vague_with_citation_not_vague():
    # 有引用 → 不算含糊（哪怕含"相关规定"字样）
    assert Q.detect_vague("根据《劳动合同法》第八十七条，相关规定需要结合案情。") is False


def test_detect_vague_normal_answer():
    assert Q.detect_vague("根据《劳动合同法》第四十七条，经济补偿按工作年限计算。") is False


# ---------------- self_check ----------------
def test_self_check_empty():
    assert Q.self_check("", True).ok is False


def test_self_check_too_short():
    assert Q.self_check("好的", True).ok is False


def test_self_check_cite_bad_fails():
    # 引用不在库 → 判失败
    v = Q.self_check("依据《刑法》第九百九十九条处理此事，需要承担相应法律后果与责任。", True, in_kb=_kb_false)
    assert v.ok is False and v.reason.startswith("cite_bad")


def test_self_check_hit_no_citation_fails():
    # 检索命中却无引用 → 判失败（轻量最常见掉链子）
    v = Q.self_check("根据法律规定，需要结合具体案情进行分析和判断，不能一概而论。", True, in_kb=_kb_true)
    assert v.ok is False and v.reason == "no_citation_while_hit"


def test_self_check_hit_with_citation_pass():
    v = Q.self_check("根据《劳动合同法》第八十七条，用人单位违法解除应支付赔偿金。", True, in_kb=_kb_true)
    assert v.ok is True


def test_self_check_no_hit_honest_refusal_pass():
    v = Q.self_check("根据现有资料无法完整回答，未检索到相关条文。", False, in_kb=_kb_true)
    assert v.ok is True


def test_self_check_no_hit_answered_fail():
    # 无命中却回答（无诚实拒答）→ 无据胡答
    v = Q.self_check("你可以去法院起诉，收集好证据材料，向有管辖权的人民法院提起诉讼。", False, in_kb=_kb_true)
    assert v.ok is False and v.reason == "no_ground_but_answered"


def test_self_check_vague_fails():
    v = Q.self_check("这个要看相关规定处理，具体需要咨询专业人士给出法律意见。", True, in_kb=_kb_true)
    assert v.ok is False and v.reason == "vague"


# ---------------- 多选完整性（决策 8，query rewrite v3 后续） ----------------
_MULTI_Q = (
    "根据《劳动合同法》，下列关于试用期的说法正确的有："
    "A. 试用期最长不得超过六个月 "
    "B. 同一用人单位与同一劳动者只能约定一次试用期 "
    "C. 试用期包含在劳动合同期限内 "
    "D. 试用期可以单独签订"
)

_ANS_SINGLE = (
    "**A. 试用期最长不得超过六个月**【判断】正确\n"
    "**B. 同一用人单位与同一劳动者只能约定一次试用期**【判断】错误\n"
    "**C. 试用期包含在劳动合同期限内**【判断】错误\n"
    "**D. 试用期可以单独签订**【判断】错误\n"
    "本题正确答案为 A。"
)

_ANS_FULL = (
    "**A. 试用期最长不得超过六个月**【判断】正确\n"
    "**B. 同一用人单位与同一劳动者只能约定一次试用期**【判断】正确\n"
    "**C. 试用期包含在劳动合同期限内**【判断】正确\n"
    "**D. 试用期可以单独签订**【判断】错误\n"
    "本题正确答案为 A、B、C。"
)


def test_answer_declared_correct_extracts():
    assert Q._answer_declared_correct(_ANS_FULL) == {"A", "B", "C"}
    assert Q._answer_declared_correct(_ANS_SINGLE) == {"A"}
    assert Q._answer_declared_correct("") == set()
    assert Q._answer_declared_correct("无结构化逐项判断") == set()


def test_answer_declared_correct_item_format():
    """实际模型输出格式「X项判断：正确」也识别（2026-08-05 eval 实测）。"""
    ans = (
        "**A项判断：正确。**根据《民法典》第一千一百二十七条……\n"
        "**B项判断：正确。**……\n"
        "**C项判断：错误。**……\n"
        "**D项判断：错误。**……\n"
    )
    assert Q._answer_declared_correct(ans) == {"A", "B"}


def test_answer_declared_correct_dash_format():
    """qa_cache 的 glm 答案格式「X. 内容 —— 正确」识别（2026-08-05 实测）。"""
    ans = (
        "**A. 消费者定作的商品不适用七天无理由退货 —— 正确**\n"
        "**B. 鲜活易腐的商品不适用七天无理由退货 —— 正确**\n"
        "**C. 在线下载的数字商品不适用七天无理由退货 —— 正确**\n"
        "**D. 所有网购商品都适用七天无理由退货 —— 错误**\n"
    )
    assert Q._answer_declared_correct(ans) == {"A", "B", "C"}


def test_answer_declared_correct_dash_hedge_and_neutral():
    """hedge（法理正确）算正确；无法判断 → 中性（不计数）。"""
    ans = (
        "**A. 应当遵循合法正当必要诚信原则 —— 依据不足（但法理正确）**\n"
        "**B. 应当遵循最小必要原则 —— 正确**\n"
        "**C. 处理敏感个人信息应当取得个人单独同意 —— 错误（表述不严谨）**\n"
        "**D. 无需公开处理规则 —— 无法判断**\n"
    )
    assert Q._answer_declared_correct(ans) == {"A", "B"}


def test_answer_declared_correct_conclusion():
    """结论段抽取：'正确的是 A、B、C'（独立判断行格式的答案靠结论兜底）。"""
    ans = (
        "**A. 向人民法院请求保护民事权利的诉讼时效期间为三年**\n"
        "**判断：正确。**依据《民法典》第一百八十八条……\n"
        "**B. 诉讼时效期间自权利人知道或应当知道权利受损害及义务人之日起计算**\n"
        "**判断：正确。**……\n"
        "**C. 诉讼时效期间届满后，义务人同意履行的不得以诉讼时效届满抗辩**\n"
        "**判断：正确。**……\n"
        "**D. 诉讼时效届满后权利人丧失实体权利**\n"
        "**判断：错误。**……\n"
        "**结论：**本题中说法正确的选项为 **A、B、C**。\n"
    )
    assert Q._answer_declared_correct(ans) == {"A", "B", "C"}


def test_multi_incomplete_single_option_flagged():
    """多选题型 + 回答只声明 1 个正确选项 → 疑似漏答。"""
    assert Q.multi_incomplete(_MULTI_Q, _ANS_SINGLE) is True


def test_multi_incomplete_full_not_flagged():
    assert Q.multi_incomplete(_MULTI_Q, _ANS_FULL) is False


def test_multi_incomplete_single_select_not_flagged():
    """单选/unknown 题型（'下列说法正确的是'）→ 不触发。"""
    q = "关于劳动合同试用期，下列说法正确的是：A. 六个月 B. 三个月 C. 一年 D. 两年"
    assert Q.multi_incomplete(q, _ANS_SINGLE) is False


def test_multi_incomplete_indeterminate_not_flagged():
    """不定项可合法只有 1 个正确项 → 不触发。"""
    q = "关于下列情形，属于不定项选择的是：A. 甲 B. 乙 C. 丙 D. 丁"
    assert Q.multi_incomplete(q, _ANS_SINGLE) is False
