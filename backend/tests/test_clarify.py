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
    assert not clarify.detect_underspecified("我朋友开公司欠我货款不还，我已经起诉到法院了，他还转移财产，我该怎么办？")


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
    # 真实回归：保险诈骗罪考题里「无法」「非法」、遗产继承「法定」曾是假法名导致误拒答
    assert clarify.extract_source_names("自己作为被保险人就无法从保险公司获得赔偿") == []
    assert clarify.extract_source_names("因欠缺非法占有目的") == []
    assert clarify.extract_source_names("遗产的法定继承顺序是什么？") == []  # 基准发现：法定误抽致误拒答
    assert clarify.extract_source_names("根据法定继承规定，第一顺序继承人是谁？") == []  # 根据法误抽
    # 真法名仍正常抽出
    assert clarify.extract_source_names("保险法第一百七十四条") == ["保险法"]


def test_source_alias():
    # 简称 → 全称归一：库里存全称，短名直查会误判「不在库」→ 误拒答（code-review 发现）
    assert clarify.extract_source_names("民诉法第一百二十条") == ["民事诉讼法"]
    assert clarify.extract_source_names("刑诉法第八十三条") == ["刑事诉讼法"]
    assert clarify.extract_source_names("消保法第五十五条") == ["消费者权益保护法"]
    # 归一后在库 → 不因短名误拒答
    assert clarify.decide("legal_query", "民诉法第一百二十条是什么", True) == "direct"


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
    """库外裸名法名的诚实拒答：仅在**无据**（检索未命中）时触发（2026-08-04 根治）。

    根治：有据（检索命中相近条文）时裸名不在库不再拒答——检索有据还答"未收录"正是
    误拒答（伤害体验），宁可基于库内相近条文尽力回答；书引《X法》确凿点名不受此限。
    """
    # 无据 → 裸名可信法名不在库 → 诚实拒答
    assert clarify.decide("legal_query", "工伤保险条例里规定的工伤认定标准是什么？", False) == "refuse"
    assert clarify.decide("legal_query", "根据合同法第五十二条，合同无效的情形有哪些？", False) == "refuse"
    assert clarify.decide("legal_query", "婚姻法规定的夫妻共同财产怎么分割？", False) == "refuse"
    # 有据 → 不因裸名不在库拒答（根治：有据尽力回答，杜绝误拒答）
    assert clarify.decide("legal_query", "工伤保险条例里规定的工伤认定标准是什么？", True) == "direct"
    # 书引《X法》：**2026-10-13 口径①裁定后此行已改**——旧版"即使有据也不硬答"作废；
    # 现状＝有据时不再整题拒答，缺的依据由 missing_sources 交调用方声明（无据时仍拒，见下一条用例）。
    assert clarify.decide("legal_query", "《工伤保险条例》里的认定标准", True) == "direct"


def test_decide_no_false_refuse_from_mis_extracted_law():
    """误抽法名不触发拒答（2026-08-04 修复，用户实测正当防卫法考题）。

    真实 case：「不管何种刑法学说」被裸名正则整段误抽成法名 → source_in_kb 判
    不在库 → 误拒答（知识库有刑法20条且检索命中，却答"未收录"）。修复：不在库的
    裸名须通过 _plausible_law 可信度判定（含连接/疑问词、泛称法名 → 丢弃不拒答）。
    """
    exam = (
        "甲乙二人对丙素有仇怨，伺机报复。丙掏出铁棍击打乙，乙掏出小刀回击，最后二人都负轻伤，"
        "如何评价甲乙丙？A.如果乙成立正当防卫，甲也成立正当防卫 "
        "B.乙不因为一开始有伤害意图，而影响正当防卫的构成 "
        "C.乙有过错，所以成立防卫过当 "
        "D.不管何种刑法学说，丙都不构成正当防卫"
    )
    assert clarify.decide("legal_query", exam, True) == "direct"  # 检索命中 → 正常回答
    # 误抽形态：连接词/泛称/疑问 → 不拒答
    assert clarify.decide("legal_query", "这种合同纠纷适用合同法还是民法？", True) == "direct"


def test_decide_no_false_refuse_from_org_abbrev():
    """机构简称「最高法」不被误抽成法名致误拒答（2026-08-04 同类第 3 次）。

    真实 case：死刑复核法考题选项「直接寄送最高法」——「最高法」以"法"结尾、长度合规，
    被 _plausible_law 判为可信法名，source_in_kb 判不在库 → 误拒答"未收录"，尽管刑诉法
    246-252（死刑复核全章）已在库且检索命中。修复：机构简称显式免疫。
    """
    exam = (
        "刘某因故意杀人被判处死立执，同案钱某因涉其他案件被另案处理。关于死刑复核程序："
        "A.刘某辩护律师可讲辩护意见直接寄送最高法 B.报请死刑复核的案件报告中应包括钱某处理情况 "
        "C.如最高检经复核认为刘某可死缓并限制减刑，可直接改判 "
        "D.如死刑复核期间最高检提出意见，最高法应当面听取并制作笔录"
    )
    assert clarify.decide("legal_query", exam, True) == "direct"  # 检索命中 → 正常回答
    # 机构简称本身不是法律：不应被当作"不在库的可信法名"触发拒答
    assert clarify._plausible_law("最高法") is False
    assert clarify._plausible_law("最高检") is False
    assert clarify._plausible_law("人民法院") is False
    assert clarify.decide("legal_query", "刑事法怎么规定的？", True) == "direct"
    assert clarify.decide("legal_query", "行政法规定的行政处罚种类", True) == "direct"


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


# ---------------- 口径①（2026-10-13 裁定）：书名号只触发法源核查，不整题拒答 ----------------
def test_quoted_contract_name_is_not_a_named_law():
    """书名号里是合同/文书名（《房屋租赁合同》《解除通知》）时，它不是"点名某部法"，不触发任何拒答。"""
    assert clarify.decide("legal_query", "《房屋租赁合同》第五条把维修义务全给了乙方，怎么破？", True) == "direct"


def test_quoted_missing_law_no_longer_refuses_the_whole_answer():
    """真点名、确实不在库：有检索依据时不再整题拒答——缺的依据交调用方声明（missing_sources）。"""
    text = "《工伤保险条例》里的认定标准是什么？"
    assert clarify.decide("legal_query", text, True) == "direct"
    assert clarify.missing_sources(text) == ["工伤保险条例"]


def test_quoted_missing_law_still_refuses_without_any_sources():
    """零检索命中时才维持诚实拒答——那才是"确实缺少必要依据"。"""
    assert clarify.decide("legal_query", "《工伤保险条例》里的认定标准是什么？", False) == "refuse"


def test_missing_sources_ignores_non_law_quotes():
    assert clarify.missing_sources("《房屋买卖合同》和《解除通知》都在附件里，争议怎么写？") == []


def test_missing_sources_flags_official_full_name_and_judicial_interpretation():
    """口径①：官方全称（12 字）与司法解释名（带（一）后缀）都算"点名了法源"——
    裸名判据 `_plausible_law` 限长 2–8 且只认 法/条例/法典，套到书引上会把这两种静默放过。"""
    assert clarify.missing_sources("《中华人民共和国合同法》还有效吗？") == ["中华人民共和国合同法"]
    assert clarify.missing_sources(
        "按《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》处理，《工伤保险条例》也有规定。"
    ) == ["最高人民法院关于审理民间借贷案件适用法律若干问题的规定", "工伤保险条例"]


def test_missing_sources_lists_each_spelling_separately_documented_limit():
    """已知边界（不是断言"应该如此"）：`canon_source` 不去"中华人民共和国"前缀，
    所以同一部法的全称与简称会各报一次。对"缺依据声明"只是措辞重复，不影响判定；
    若将来要让声明去重，改的是 canon（共享函数，改前先查全部消费面）。"""
    assert clarify.missing_sources("《中华人民共和国合同法》第二百零六条与《合同法》第一百零七条冲突吗？") == [
        "中华人民共和国合同法",
        "合同法",
    ]
