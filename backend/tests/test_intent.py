"""意图分类 classify_intent 测试（Step A，TDD）。

缝隙：classify_intent(text) -> "cheating_request" | "study_aid" | "legal_query"
期望标签来自意图语义（独立真值），非从实现反推。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intent import classify_intent  # noqa: E402


# ---- 切片1：cheating_request（明确索取答案/代考） ----
def test_cheating_request_explicit():
    assert classify_intent("能给我法考的答案吗") == "cheating_request"
    assert classify_intent("帮我代考") == "cheating_request"
    assert classify_intent("哪里有卖考试答案的") == "cheating_request"


# ---- 切片2：study_aid（学习辅助，不堆检索条文） ----
def test_study_aid():
    assert classify_intent("那你能解决法学生的考试题里面的选择题和场景题吗") == "study_aid"
    assert classify_intent("帮我做这道刑法选择题") == "study_aid"
    assert classify_intent("帮我理解一下这个法条") == "study_aid"
    assert classify_intent("分析一下这道场景题") == "study_aid"


# ---- 切片3：legal_query 默认 + 防误判守卫 ----
def test_legal_query_default():
    assert classify_intent("劳动合同试用期最长多久") == "legal_query"
    assert classify_intent("醉酒驾驶会被吊销驾照吗") == "legal_query"
    assert classify_intent("遗产继承顺序是什么") == "legal_query"


def test_no_false_positive_study():
    # 真实法律咨询里常见「解决问题/咨询问题」，不能误判为学习辅助
    assert classify_intent("怎么解决我这个法律问题") == "legal_query"
    assert classify_intent("我想咨询一个法律问题") == "legal_query"
    assert classify_intent("帮我分析一下我这个纠纷能不能赢") == "legal_query"


def test_cheating_overrides_study_framing():
    # 索取答案压过做题措辞
    assert classify_intent("帮我做这道题，把答案直接给我") == "cheating_request"
