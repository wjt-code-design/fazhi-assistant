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
