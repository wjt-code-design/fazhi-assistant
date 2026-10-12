"""合同评估触发/切分/标签/rubric 单测（纯逻辑——domain_rules 合同函数只依赖 re，秒级不停后端）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import domain_rules as D  # noqa: E402


# ---------------- is_contract_review 触发 ----------------
def test_trigger_long_contract_text():
    t = "租赁合同。甲方将房屋出租给乙方，租金每月三千元。" * 20
    assert D.is_contract_review(t) is True


def test_trigger_review_request_short():
    assert D.is_contract_review("帮我审一下这份租赁合同") is True


def test_no_trigger_short_question():
    assert D.is_contract_review("违约金怎么算？") is False
    assert D.is_contract_review("租赁合同到期怎么办") is False


def test_no_trigger_bare_review_word():
    assert D.is_contract_review("审查起诉阶段，被告人有哪些权利？") is False


# ---------------- 争议分析题不得被误路由进合同审查 ----------------
# 缺陷形状（2026-10-12 抓到，2026-10-13 复现并收窄）。`is_contract_review` 的第二分支是
#     len>=80 and ( "甲方" in t or "乙方" in t or ("条" in t and 合同名词命中>=3) )
# 争议分析题常要复述合同条款，于是两支都可能被咬住：引条款编号走后者，
# 用"甲方／乙方"称呼当事人走前者。**只堵一支的修法是错修。**
# 边界更正（2026-10-13）：先前记录说"对任何争议分析题恒成立"过强——不复述条款编号
# 也不写甲乙双方的争议题本就不触发（劳动争议／借款担保／房屋租赁三型实测均 False）。
# 夹具是出题人原题的压缩改写（内联 445 字；原题 952 字、另一份完整改写 1128 字，
# 三者在本判据下同判 True），保留的是触发要素而非逐字原文。
_DISPUTE_CASE = """2024年8月1日，A市甲公司与乙公司签订《设备采购及安装合同》，总价1200万元，付款分四期：签约付20%（240万）、到货付50%（600万）、验收合格后30日内付25%（300万）、质保期满付5%（60万）。合同第18条约定：“因本合同发生的一切争议，提交A仲裁委员会仲裁。”
同日配套两份担保：丁公司向甲出具《连带责任保证函》，未附股东会决议（丁公司章程规定对外担保须经股东会决议）；丙（甲法定代表人张某之妻）签署《抵押承诺书》，以其个人名下商铺为乙的付款义务设定抵押，未办理抵押登记。
甲的诉讼请求：①戊支付余款460万及违约金（日万分之五）；②丁承担连带保证责任；③丙在商铺价值范围内承担担保责任。
各被告抗辩：戊在首次开庭前提交仲裁协议；丁主张保证未经决议对其不生效、且保证期间已过；丙主张抵押未登记不生效。
请回答：主管与管辖——法院应否受理？转让的效力——乙能否免责？证据——100万现金付款的举证责任如何分配？实务——如果你是甲的代理人，起诉时被告与管辖策略应如何设计？"""


def test_no_trigger_dispute_analysis_case():
    """已起诉的争议分析题：禁入合同审查通道（本条在现役判据下应为红）。"""
    assert len(_DISPUTE_CASE) >= 80
    assert D.is_contract_review(_DISPUTE_CASE) is False


def test_no_trigger_dispute_case_clause_numbering():
    """形状 A：靠『出现"条"＋≥3 合同名词』这一析取支被误触发。"""
    t = (
        "2023年5月，甲公司与乙公司签订《设备买卖合同》，合同第六条约定货款分两期支付，"
        "第十二条约定违约金按日万分之五计算，另约定争议提交B仲裁委员会仲裁。乙公司未按期"
        "交货，甲公司起诉要求解除合同并赔偿损失；乙公司抗辩标的物质量不合格且违约金过高，"
        "丙公司作为保证人主张保证期间已过。请回答：法院应否受理？举证责任如何分配？"
        "违约金是否应予酌减？如果你是甲公司的代理人，应如何设计诉讼请求与被告范围？"
    )
    assert len(t) >= 80
    assert D.is_contract_review(t) is False


def test_no_trigger_dispute_case_party_labels():
    """形状 B：全文不含"条"字，仅靠『甲方／乙方』那一支被误触发——只堵一支会漏这条。"""
    t = (
        "甲方（供货方）与乙方（收货方）因《货物买卖合同》的付款义务发生纠纷，已诉至法院。"
        "乙方抗辩甲方交付的货物存在质量瑕疵并主张拒付尾款，甲方则要求乙方支付欠款并承担违约责任。"
        "请回答：本案举证责任如何在甲乙双方之间分配？法院应否支持甲方的违约责任请求？"
    )
    assert len(t) >= 80
    assert "条" not in t
    assert D.is_contract_review(t) is False


def test_no_trigger_dispute_case_single_litigation_marker():
    """形状 C：案情叙述只命中**一个**诉讼语汇、法条写成行内引文——`litigation < 2` 压不住它。

    2026-10-13 拿出题人 Q8 全文（752 字，`git archive` 纯树实测）打出来：现役判据仍判 True，
    于是"已废止条文陷阱题"被端进合同审查模板。夹具保留的是触发要素而非逐字原文：
    合同／违约金／借款三个名词齐、"条"只出现在行内引文与"借条"里、全文没有"甲方／乙方"字样、
    诉讼语汇只有"起诉"一个。
    """
    t = (
        "2021-05-01 甲借给乙50万元，借条约定借期至2021-12-31，借期内年利率12%，"
        "逾期按年利率24%计收逾期利息，未约定逾期利息与违约金并存。乙已支付借期内利息40000元，"
        "本金未还。2022-06-10 与 2023-01-15 甲两次微信催告有聊天记录，2025-10-08 的电话催告无证据。"
        "甲于2026-03-05起诉，认为《中华人民共和国合同法》第二百零六条规定借款人应当按照约定期限返还借款，"
        "又担心《中华人民共和国民法通则》第一百三十五条的二年诉讼时效已经过了。"
        "请回答：本案诉讼时效是否届满？逾期利息的上限如何确定？已付利息能否抵扣本金？"
    )
    assert len(t) >= 80
    assert not ("甲方" in t or "乙方" in t)
    assert sum(1 for m in D._LITIGATION_MARKERS if m in t) <= 1
    assert D.is_contract_review(t) is False


def test_trigger_contract_without_party_labels():
    """反回归钉（改前也是绿的）：真合同草稿常写"出租人／承租人"而不写"甲方／乙方"。

    这条现在靠『出现"条"＋≥3 合同名词』接住。收紧长文本支时它最容易被顺手剪掉，
    而 8 题校准批里两只 H 题都带"甲方／乙方"、根本覆盖不到它——所以先钉住再改判据。
    """
    t = (
        "房屋租赁合同\n"
        "第一条 出租人将坐落于B市C路200平方米房屋出租给承租人，用途为商业经营。\n"
        "第二条 租金每月三万元，承租人应于每月5日前支付，逾期按日承担违约金。\n"
        "第三条 租赁期自2026年3月1日起至2051年2月28日止，共计25年。\n"
        "第四条 承租人可以将房屋转租第三人，无需出租人同意。"
    )
    assert len(t) >= 80
    assert not ("甲方" in t or "乙方" in t)
    assert D.is_contract_review(t) is True


def test_trigger_contract_one_line_without_party_labels():
    """先红用例（2026-10-13 夜间复核抓到）：整份合同挤成**一行**且只写"出租人／承租人"。

    聊天框粘贴、PDF 抽取、移动端输入都会把换行吃掉，这时"行首"锚点根本不存在。
    上一笔把条款支收成"必须落在行首的 第X条"，这类合同从"能进合同审查"退回"进不去"——
    代价不只是一条 system 提示词：`request_bootstrap.py` 里合同态还决定
    `contract_split` 的**逐条证据集**与上一轮合同文本回捞，漏判＝整条链路都不走。
    判别轴换成"第X条 **且不是紧跟在 》 之后**"：合同自指条款满足，
    行内引法条（《合同法》第二百零六条）被 》 挡住，于是 Q8 那一型仍然不进合同审查。
    """
    t = (
        "房屋租赁合同 第一条 租赁期限：自2026年1月1日起至2027年12月31日止。"
        "第二条 租金与付款方式：每月租金三千元，于每月5日前付款至账户。"
        "第三条 押金：押金六千元，租赁期满无违约则退还。"
        "第四条 违约责任：逾期付款按日承担违约金，任何一方可解除本条款约定。 出租人（签章）： 承租人（签章）："
    )
    assert len(t) >= 80
    assert "\n" not in t
    assert not ("甲方" in t or "乙方" in t)
    assert D.is_contract_review(t) is True


def test_trigger_explicit_review_survives_litigation_vocab():
    """防误杀：显式审查请求里出现诉讼词汇，仍必须进合同审查（治标不能把通道一起堵死）。"""
    t = "帮我审查这份采购合同的风险，这单后面可能要打官司，需要看违约金条款站不站得住。"
    assert D.is_contract_review(t) is True


def test_trigger_contract_with_agent_and_venue_clauses():
    """防误杀：真合同正文本来就写"委托代理人""管辖法院"，不得被任务形态轴误判成非合同。"""
    t = (
        "本供货合同由甲方委托代理人与乙方签署，第二条 价款与付款，第三条 违约责任与违约金，"
        "第四条 争议解决及管辖法院，合同项下保证金为总价百分之五。"
    ) * 3
    assert len(t) >= 80
    assert D.is_contract_review(t) is True


# ---------------- contract_split 切分 ----------------
def test_split_by_articles():
    t = "第一条 甲方义务。\n第二条 乙方义务。\n第三条 违约责任。"
    segs = D.contract_split(t)
    assert len(segs) == 3
    assert segs[0][0] == "第一条"
    assert "违约责任" in segs[2][1]


def test_split_no_marker_whole():
    t = "这是一个没有条号的合同文本内容。" * 10
    segs = D.contract_split(t)
    assert len(segs) == 1
    assert segs[0][0] == "全文"


# ---------------- 风险标签 / rubric ----------------
def test_clause_risk_tags():
    assert "违约金" in D.clause_risk_tags("违约金为合同金额的20%")
    assert "免责" in D.clause_risk_tags("任何情况下均免责")
    assert D.clause_risk_tags("本合同自双方签字之日起生效") == []


def test_rubric_high_risk():
    clauses = [("一、", "违约金20%，定金双倍，任何情况下概不负责"), ("二、", "最终解释权归甲方")]
    level, _ = D.rubric_risk_level(clauses)
    assert level == "极高"  # 双 high 词（概不+最终解释权）触发极高


def test_rubric_low_risk():
    clauses = [("一、", "本合同一式两份，双方各执一份")]
    level, _ = D.rubric_risk_level(clauses)
    assert level == "低"


def test_contract_split_keeps_preamble():
    """首条标记前的引言/首段必须保留（2026-08-06 diagnosing-bugs：当前被丢弃，结构性漏条款）。"""
    t = (
        "本合同由甲方与乙方于2026年签订，双方本着自愿原则达成如下协议。\n"
        "第一条 甲方将房屋出租给乙方。\n"
        "第二条 租金每月3000元。"
    )
    segs = D.contract_split(t)
    texts = [c for _, c in segs]
    assert any("本合同由甲方与乙方" in c for c in texts), "引言/首段被丢弃"


# ---------------- 劳动法域隔离（is_labor_clause） ----------------
def test_is_labor_clause_boundary_words():
    """code-review 边界盲区（2026-08-06）：纯"试用期"条款此前未判为劳动 → 含"解除"会错绑民法典563。"""
    assert D.is_labor_clause("试用期三个月，试用期工资按转正工资的80%支付") is True
    assert D.is_labor_clause("甲方为乙方缴纳社会保险及住房公积金") is True
    assert D.is_labor_clause("乙方提前三十日解除劳动合同，应支付赔偿金") is True


def test_is_labor_clause_not_misclassify_services():
    """ "培训"不进特征词：培训服务合同（消费场景）不得判为劳动，保留格式条款映射。"""
    assert D.is_labor_clause("本合同约定培训课程费用一经收取概不退款") is False
    assert D.is_labor_clause("甲方将房屋出租给乙方，租金每月三千元") is False
