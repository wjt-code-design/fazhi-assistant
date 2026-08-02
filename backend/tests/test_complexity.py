"""复杂度分级路由（M1）测试：纯函数。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import complexity as C  # noqa: E402


# ---------------- assess ----------------
def test_assess_cheating_light():
    assert C.assess("帮我做考试题", False, "cheating_request", []) == ("text", "light")


def test_assess_study_flag():
    assert C.assess("这个选项为什么对", False, "study_aid", []) == ("text", "flag")


def test_assess_legal_short_light():
    assert C.assess("试用期最长多久", False, "legal_query", []) == ("text", "light")


def test_assess_legal_long_flag():
    long_q = "我想了解一下关于劳动合同解除后的经济补偿金计算方式以及需要注意的事项和风险" * 3
    assert C.assess(long_q, False, "legal_query", []) == ("text", "flag")


def test_assess_legal_keyword_flag():
    assert C.assess("公司违法解除劳动合同，赔偿金怎么算", False, "legal_query", []) == ("text", "flag")


def test_assess_multi_turn_flag():
    assert C.assess("那赔偿金呢", False, "legal_query", [{"role": "user"}]) == ("text", "flag")


def test_assess_image_vision_undecided():
    modality, tier = C.assess("这图片里是什么", True, "legal_query", [])
    assert modality == "vision" and tier is None


# ---------------- admit_light ----------------
def test_admit_light_all_ok():
    assert C.admit_light("试用期最长多久", False, "legal_query", [], context_hit=True) is True


def test_admit_light_reject_intent():
    assert C.admit_light("帮我做题", False, "study_aid", [], context_hit=True) is False


def test_admit_light_reject_image():
    assert C.admit_light("看图", True, "legal_query", [], context_hit=True) is False


def test_admit_light_reject_no_hit():
    # 检索未命中 → 不给轻量（防凭空编造）
    assert C.admit_light("试用期最长多久", False, "legal_query", [], context_hit=False) is False


def test_admit_light_reject_multi_turn():
    assert C.admit_light("那赔偿金呢", False, "legal_query", [{"role": "user"}], context_hit=True) is False


def test_admit_light_reject_long():
    long_q = "我想了解一下关于劳动合同解除后的经济补偿金计算方式以及需要注意的事项" * 2
    assert C.admit_light(long_q, False, "legal_query", [], context_hit=True) is False


def test_admit_light_reject_keyword():
    assert C.admit_light("工伤赔偿怎么算", False, "legal_query", [], context_hit=True) is False
