"""clarify 策略层测试：信息不足检测 / 源名抽取 / 4 档决策 / chitchat 意图 / 拒答模板过自检。

对照 data/eval_negative.json 的 underspecified / chitchat / out_of_kb / abolished 用例，
保证「该反问时反问、该拒答时拒答、该聊时聊」的确定性行为（零 LLM，纯函数）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import clarify  # noqa: E402
import intent  # noqa: E402
import quality  # noqa: E402


# ---------------- detect_underspecified：信息不足信号 ----------------
def test_underspecified_eval_cases():
    # eval_negative 的 3 例 underspecified
    assert clarify.detect_underspecified("这个合法吗？")
    assert clarify.detect_underspecified("我想咨询一下法律问题。")
    assert clarify.detect_underspecified("他这样做法违反第几条？")


def test_underspecified_boundaries():
    # 有具体场景 → 不模糊
    assert not clarify.detect_underspecified("我被人打了，怎么要求赔偿？")
    assert not clarify.detect_underspecified("根据劳动法第三十九条解除劳动合同合法吗？")
    assert not clarify.detect_underspecified("欠钱不还怎么办？")
    # 库外硬信号 → 不算模糊（走拒答路径）
    assert not clarify.detect_underspecified("民间借贷司法解释对利率上限怎么规定？")
    # 长问 → 默认有信息量
    assert not clarify.detect_underspecified(
        "我朋友开公司欠我货款不还，我已经起诉到法院了，他还转移财产，我该怎么办？"
    )


# ---------------- extract_source_names：法名抽取 ----------------
def test_extract_source_names():
    assert clarify.extract_source_names("《工伤保险条例》里的认定标准") == ["工伤保险条例"]
    assert clarify.extract_source_names("根据劳动合同法实施条例办理") == ["劳动合同法实施条例"]
    assert clarify.extract_source_names("婚姻法规定的夫妻共同财产怎么分") == ["婚姻法"]
    # 泛词不误抽
    assert clarify.extract_source_names("交通事故的处理办法是什么？") == []
    assert clarify.extract_source_names("我这样做违法吗？") == []
    assert clarify.extract_source_names("这个合法吗？") == []
    assert clarify.extract_source_names("他这样做法违反第几条？") == []  # "做法"误抽曾导致误拒答


# ---------------- decide：4 档策略 ----------------
def test_decide_chitchat():
    assert clarify.decide("chitchat", "你好！", False) == "chat"


def test_decide_non_legal_passthrough():
    assert clarify.decide("study_aid", "帮我分析这道题", False) == "direct"
    assert clarify.decide("cheating_request", "把答案给我", False) == "direct"


def test_decide_hit_direct():
    assert clarify.decide("legal_query", "高空抛物致人损害谁负责", True) == "direct"


def test_decide_refuse_marks():
    assert clarify.decide("legal_query", "民间借贷司法解释怎么规定", False) == "refuse"


def test_decide_refuse_out_of_kb_source():
    # 问题指名的来源不在库 → 拒答（即使检索到相近条文）
    assert clarify.decide("legal_query", "工伤保险条例里规定的工伤认定标准是什么？", True) == "refuse"
    assert clarify.decide("legal_query", "根据合同法第五十二条，合同无效的情形有哪些？", True) == "refuse"
    assert clarify.decide("legal_query", "婚姻法规定的夫妻共同财产怎么分割？", True) == "refuse"


def test_decide_source_in_kb_direct():
    # 指名来源在库 → 不因来源拒答
    assert clarify.decide("legal_query", "民法典第一千二百五十四条是什么", True) == "direct"
    assert clarify.decide("legal_query", "劳动法怎么规定试用期？", False) == "refuse"  # 无命中 → 拒答


def test_decide_underspecified_clarify():
    # 信息不足 → 反问（有命中也反问：没事实没法答准）
    assert clarify.decide("legal_query", "这个合法吗？", True) == "clarify"
    assert clarify.decide("legal_query", "我想咨询一下法律问题。", False) == "clarify"


def test_decide_clarified_once_no_loop():
    # 已反问过：不再反问——有据直接答，无据拒答（防死循环）
    assert clarify.decide("legal_query", "这个合法吗？", True, clarified_once=True) == "direct"
    assert clarify.decide("legal_query", "我想咨询一下法律问题。", False, clarified_once=True) == "refuse"


def test_decide_no_hit_specific_refuse():
    assert clarify.decide("legal_query", "网络借贷信息中介机构业务活动的部门规章有哪些要求？", False) == "refuse"


# ---------------- chitchat 意图 ----------------
def test_intent_chitchat():
    assert intent.classify_intent("你好！") == "chitchat"
    assert intent.classify_intent("今天天气怎么样？") == "chitchat"
    assert intent.classify_intent("谢谢你的解答") == "chitchat"


def test_intent_chitchat_not_steal_legal():
    # 闲聊词 + 法律实体 → 仍按法律咨询
    assert intent.classify_intent("你好，我被人打了怎么办？") == "legal_query"
    assert intent.classify_intent("您好，借钱不还怎么办") == "legal_query"
    # 既有意图优先级不受影响
    assert intent.classify_intent("帮我做这道刑法选择题") == "study_aid"
    assert intent.classify_intent("能直接把法考的答案给我吗") == "cheating_request"


# ---------------- 拒答模板必须过 self_check ----------------
def test_refuse_prompt_passes_self_check():
    # 若编排路径意外触发 self_check，拒答模板措辞必须命中诚实拒答标记
    v = quality.self_check(clarify.REFUSE_PROMPT, context_present=False)
    assert v.ok, v.reason
