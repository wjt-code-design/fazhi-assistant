"""领域规则集中地（single source of truth）。

硬编码的条文映射、场景关键词、提示词规则统一放这里，避免散落在 main.py：
- 条文映射（作弊 / 格式条款 / 引用选择）只改这里，main.py 不感知细节
- 提示词规则从这里导入，main.py 只负责拼接

复用 retrieval.exact_article_lookup 做精确条号命中（函数内局部 import，解开
domain_rules ↔ retrieval 循环依赖——retrieval 需要本模块的 canon_source 等常量）。
"""

import json
import os
import re

from settings import settings


def _lookup_all(specs: list[tuple[str, str]], cutoff: str | None = None):
    """按 (source, article) 精确查找，返回 Document 列表（顺序 = 传入顺序）。

    `cutoff`：历史查询基准日（ISO 串），透传给 `exact_article_lookup` 的时效判定；
    缺省 None ⇒ 落当日，与历史行为逐字一致。
    """
    from retrieval import exact_article_lookup  # noqa: PLC0415

    docs = []
    for source, article in specs:
        docs += exact_article_lookup(source, article, cutoff=cutoff)
    return docs


# ==================== 作弊 / 考试场景条文 ====================
# 作弊路径定向检索考试作弊相关条文，使释法引用有据（避免通用检索召回无关条文）。
CHEATING_DOCS_SPEC = [
    ("刑法", "第二百八十四条之一"),  # 组织考试作弊罪
    ("治安管理处罚法", "第二十七条"),  # 冒名顶替 / 伪造证件等
]


def cheating_docs(cutoff: str | None = None):
    return _lookup_all(CHEATING_DOCS_SPEC, cutoff=cutoff)


# ==================== 消费者格式条款场景 ====================
# 商家单方限制消费者权利的关键词（命中即补充格式条款条文到检索上下文）
CC_KEYWORDS = ("拆封不退", "概不退款", "不予退款", "最终解释权", "格式条款", "概不退换", "拒退", "概不负责")


def is_consumer_clause_scenario(text: str) -> bool:
    """检测「商家单方限制消费者权利 / 格式条款」场景，命中则补充格式条款条文到检索上下文。

    注意：组合条件必须要求「退货/退款 + 条款效力措辞」同时出现，不能只靠「退」字——
    「退货流程怎么走」「退款到账时间」这类普通问题不应触发格式条款增强（曾因
    `"退" in t` 与「退货/退款」必然同真导致条件退化，误判所有含「退」的问题）。
    """
    t = text or ""
    if any(k in t for k in CC_KEYWORDS):
        return True
    return ("退货" in t or "退款" in t) and ("条款" in t or "免责" in t or "无效" in t)


# 格式条款 / 消费者权利兜底条文：民法典496/497（格式条款）、消保法26（限制消费者权利条款无效）。
CONSUMER_CLAUSE_DOCS_SPEC = [
    ("民法典", "第四百九十六条"),  # 格式条款定义
    ("民法典", "第四百九十七条"),  # 格式条款无效情形
    ("消费者权益保护法", "第二十六条"),  # 排除限制消费者权利条款无效
]


def consumer_clause_docs(cutoff: str | None = None):
    return _lookup_all(CONSUMER_CLAUSE_DOCS_SPEC, cutoff=cutoff)


# ==================== 消费欺诈 / 退一赔三场景 ====================
# 复合问题里检索 top-k 常被电商法占满，漏掉消保法55条（退一赔三），故定向补充。
FRAUD_KEYWORDS = (
    "欺诈",
    "退一赔三",
    "退一赔十",
    "假一赔",
    "假货",
    "假冒伪劣",
    "以假充真",
    "以次充好",
    "虚假宣传",
    "三倍赔偿",
    "赔偿三倍",
    "假货赔偿",
)


def is_consumer_fraud_scenario(text: str) -> bool:
    """检测「消费欺诈 / 退一赔三」场景，命中则补充消保法55条到检索上下文。"""
    t = text or ""
    return any(k in t for k in FRAUD_KEYWORDS)


# 消费欺诈惩罚性赔偿：消保法55条（退一赔三，食品等另有食安法148 假一赔十，按需扩展）。
CONSUMER_FRAUD_DOCS_SPEC = [
    ("消费者权益保护法", "第五十五条"),  # 欺诈退一赔三 / 惩罚性赔偿
]


def consumer_fraud_docs(cutoff: str | None = None):
    return _lookup_all(CONSUMER_FRAUD_DOCS_SPEC, cutoff=cutoff)


# ==================== 要件法条确定性补充（writer 轴立项，2026-09-10）【暂存未接线】 ====================
# ⚠️ **当前未接线**（tools/legal_retrieval.retrieve_laws 的注入已按预登记回退）——
#   首轮双集验收未过：可靠性守卫恶化（评测集 completed 6/10→5/10 + 两个新错误码；留出集 1/5）
#   且留出集 HIT 21% < 评测集 37%−10pp ⇒ 判过拟合。详见
#   dispatch-output/t2-persistence-20260910/writer-axis-verification.txt 与 legal_retrieval.py 的回退注释。
# **重做前必须先解决**：(a) 每 issue 注入上限（证据池 4→8–23 条膨胀是首要嫌疑）；
#   (b) 补充文档在 map_document 的存活问题（留出题 H03/H05 的映射条文 EVIDENCE_MISS，疑似未存活）；
#   (c) 重复轮次排除随机性。接线 = 恢复 retrieve_laws 的注入并重跑双集验收。
# 依据：独立审计（dispatch-output/t2-persistence-20260910/writer-axis-audit.txt）——57 个评测
# required 法条实例中 **68%（39 条）根本未进入证据**（检索盲区），而 writer 对证据内法条的
# 渲染为 0 失误 ⇒ "终稿缺要件法条"的根因是**必需法条未被检索进证据**，不在 writer。
# 本表按**法律领域知识**声明「场景 → 该领域论证必需的核心法条」。
# ⚠️ 防过拟合红线：本表依据与评测题集（frozen-cases-v1.json）**独立**；泛化由留出集
# holdout-cases-v1.json（SHA256 734f0f11…44cd7d2，冻结于实现之前）验收——
# 判据：留出题 HIT 率 ≥ 评测题集 HIT 率 − 10pp，否则判过拟合。**禁止照题集抄 required_laws。**
# ⚠️ 关键词必须限定（先例见 is_consumer_clause_scenario 的防退化注释）：
#    禁止用「退」「合同」「租」这类单字/泛词做触发，避免条件退化为"全部命中"。
_STATUTE_SUPPLEMENT_TABLE: list[tuple[tuple[str, ...], list[tuple[str, str]]]] = [
    # ⚠️ 跨块重复是有意的：如 劳动合同法46/47 同时属于「解除」与「社保」两个场景的核心要件，
    #    民法典577 同时属于「租赁」与「合同违约」。注入侧由 statute_supplement_docs 的
    #    seen 去重保证同一法条只注入一次；各块保持自洽（单关键词命中即得该场景完整要件）。
    # 劳动·解除与补偿（违法解除 vs 合理解除 vs 补偿标准）
    (
        ("解除劳动合同", "辞退", "开除", "裁员", "试用期", "被迫离职"),
        [
            ("劳动合同法", "第二十一条"),  # 试用期解除须说明理由
            ("劳动合同法", "第四十条"),  # 无过失性解除
            ("劳动合同法", "第四十六条"),  # 应当支付经济补偿的情形
            ("劳动合同法", "第四十七条"),  # 经济补偿计算标准
            ("劳动合同法", "第八十七条"),
        ],
    ),  # 违法解除 = 二倍经济补偿
    # 劳动·未签书面合同（二倍工资）
    (
        ("没签合同", "未签合同", "没有签劳动合同", "二倍工资"),
        [
            ("劳动合同法", "第十条"),  # 应订立书面劳动合同
            ("劳动合同法", "第八十二条"),
        ],
    ),  # 二倍工资
    # 劳动·工时与加班费
    (
        ("加班", "加班费", "工时", "工作时长"),
        [
            ("劳动法", "第三十六条"),  # 工时上限
            ("劳动法", "第四十四条"),
        ],
    ),  # 加班工资标准
    # 劳动·社会保险
    (
        ("社保", "五险", "缴纳社会保险"),
        [
            ("劳动合同法", "第三十八条"),  # 未依法缴纳社保 → 劳动者可解除
            ("劳动合同法", "第四十六条"),  # 被迫解除的经济补偿
            ("劳动合同法", "第四十七条"),  # 计算标准
            ("社会保险法", "第六十三条"),
        ],
    ),  # 未按时足额缴纳的征缴责任
    # 民事·诉讼时效
    (
        ("诉讼时效", "过时效"),
        [
            ("民法典", "第一百八十八条"),  # 普通诉讼时效期间与起算
            ("民法典", "第一百九十二条"),  # 时效届满后的抗辩权
            ("民法典", "第一百九十五条"),
        ],
    ),  # 诉讼时效中断
    # 民间借贷
    (
        ("借款", "借条", "借钱", "欠款", "欠钱"),
        [
            ("民法典", "第六百六十七条"),  # 借款合同定义
            ("民法典", "第六百七十五条"),  # 借款期限
            ("民法典", "第六百七十六条"),  # 逾期利息
            ("民法典", "第六百八十条"),
        ],
    ),  # 利息约定与禁止高利放贷
    # 担保 / 保证
    (
        ("担保", "保证人", "保证期间"),
        [
            ("民法典", "第六百八十六条"),  # 保证方式
            ("民法典", "第六百九十二条"),  # 保证期间
            ("民法典", "第六百九十三条"),  # 保证期间经过的后果
            ("民法典", "第六百九十五条"),
        ],
    ),  # 主合同变更对保证责任的影响
    # 房屋租赁
    (
        ("租房", "房东", "房租", "押金", "出租", "租赁", "转租"),
        [
            ("民法典", "第七百一十二条"),  # 出租人维修义务
            ("民法典", "第七百一十三条"),  # 承租人代为维修的费用负担
            ("民法典", "第五百七十七条"),
        ],
    ),  # 违约责任
    # 定金 / 订金
    (
        ("定金", "订金"),
        [
            ("民法典", "第五百八十六条"),  # 定金规则
            ("民法典", "第五百八十七条"),  # 定金罚则
            ("民法典", "第五百八十八条"),
        ],
    ),  # 定金与违约金的选择
    # 合同违约（通用）
    (
        ("违约", "毁约", "不履行", "拒绝履行"),
        [
            ("民法典", "第五百七十七条"),  # 违约责任
            ("民法典", "第五百八十二条"),
        ],
    ),  # 质量不符合约定的责任
]


def statute_supplement_docs(text: str):
    """按场景关键词返回**要件法条**补充文档（`tools/legal_retrieval.retrieve_laws` 消费）。

    去重规则：同一 (source, article) 只注入一次；顺序 = 表顺序（稳定，便于测试与追溯）。
    无命中时返回空列表 —— **不注入任何文档**（宁缺勿滥，避免把无关条文灌进证据）。
    """
    t = text or ""
    specs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for keywords, table in _STATUTE_SUPPLEMENT_TABLE:
        if any(k in t for k in keywords):
            for pair in table:
                if pair not in seen:
                    seen.add(pair)
                    specs.append(pair)
    # 复用既有消费欺诈映射（避免同一领域两套真源）
    if is_consumer_fraud_scenario(t):
        for pair in CONSUMER_FRAUD_DOCS_SPEC:
            if pair not in seen:
                seen.add(pair)
                specs.append(pair)
    if not specs:
        return []
    return _lookup_all(specs)


# ==================== 复杂度分级 / 质量自检常量 ====================
# 高利害/多解主题词：命中任一 → 视为复杂问题（走旗舰模型，避免轻量翻车）
COMPLEX_KEYWORDS = (
    "刑事",
    "罪名",
    "拘留",
    "判刑",
    "缓刑",
    "取保候审",
    "自首",
    "立功",
    "劳动仲裁",
    "工伤",
    "解除劳动合同",
    "经济补偿",
    "赔偿金",
    "离婚",
    "抚养",
    "继承",
    "遗嘱",
    "房产",
    "股权",
    "破产",
    "诉讼时效",
    "管辖权",
    "证据",
    "举证",
    "行政复议",
    "行政诉讼",
)

# 含糊填充话（仅当回答"无引用"时才算含糊；有引用不算）
VAGUE_PHRASES = (
    "相关法律",
    "相关法条",
    "相关规定",
    "法律原则",
    "具体需咨询",
    "请咨询律师",
    "具体情况具体分析",
    "视情况而定",
    "依法处理",
)

# 轻量准入：用户问题文本长度上限（超出视为复杂）
LIGHT_SHORT_LEN = 60
# 回答自检：最短答案长度（少于判过短）
MIN_ANSWER_LEN = 20
# token 配额切换阈值：剩余比例 < 该值则路由跳过该模型
QUOTA_THRESHOLD = 0.05


# ==================== 法名简称 → 全称 ====================
# 库内 source 存全称（民事诉讼法）；用户口语/书面常用简称（民诉法）。条号直查
# （exact_article_lookup）、源名存在性（source_in_kb）与引用校验（article_in_kb）共用。
SOURCE_ALIAS = {
    "民诉法": "民事诉讼法",
    "刑诉法": "刑事诉讼法",
    "行诉法": "行政诉讼法",
    "消保法": "消费者权益保护法",
    "电商法": "电子商务法",
    "个保法": "个人信息保护法",
    "网安法": "网络安全法",
    "破产法": "企业破产法",
    # 2026-10-21：司法解释入库。库内 source 一律用**短名**（沿用民法典/民事诉讼法风格），
    # 因为 `retrieval._ART_FULL_RE` 限定书名号内法名 1–24 字且不容内层 `》`：
    # 实测 30 字全称《最高人民法院关于审理民事案件适用诉讼时效制度若干问题的规定》与
    # 含嵌套书名号的《最高人民法院关于适用《民事诉讼法》的解释》**都抽不到引用**
    # ⇒ 引用校验静默漏检（不是误报，是根本看不见）。故短名入库 + 此处把全称/简称统一归一到短名。
    "诉讼时效规定": "诉讼时效规定",
    "诉讼时效司法解释": "诉讼时效规定",
    "诉讼时效制度规定": "诉讼时效规定",
    "最高人民法院关于审理民事案件适用诉讼时效制度若干问题的规定": "诉讼时效规定",
    "民诉法解释": "民诉法解释",
    "民诉解释": "民诉法解释",
    "民事诉讼法解释": "民诉法解释",
    "最高人民法院关于适用《中华人民共和国民事诉讼法》的解释": "民诉法解释",
    # P0 第一批（2026-10-21）：三部民法典配套解释，同样短名入库 + 全称归一。
    "民法典总则编解释": "民法典总则编解释",
    "总则编解释": "民法典总则编解释",
    "最高人民法院关于适用《中华人民共和国民法典》总则编若干问题的解释": "民法典总则编解释",
    "民法典合同编通则解释": "民法典合同编通则解释",
    "合同编通则解释": "民法典合同编通则解释",
    "最高人民法院关于适用《中华人民共和国民法典》合同编通则若干问题的解释": "民法典合同编通则解释",
    "担保制度解释": "担保制度解释",
    "民法典担保制度解释": "担保制度解释",
    "最高人民法院关于适用《中华人民共和国民法典》有关担保制度的解释": "担保制度解释",
    # P0 第二批（2026-10-21）：民间借贷、劳动、证据、人损、道交、婚家、继承
    "民间借贷规定": "民间借贷规定",
    "民间借贷解释": "民间借贷规定",
    "民间借贷司法解释": "民间借贷规定",
    "劳动争议解释一": "劳动争议解释一",
    "劳动争议解释（一）": "劳动争议解释一",
    "劳动争议解释": "劳动争议解释一",
    "民事诉讼证据规定": "民事诉讼证据规定",
    "民诉证据规定": "民事诉讼证据规定",
    "人身损害赔偿解释": "人身损害赔偿解释",
    "人身损害解释": "人身损害赔偿解释",
    "道交损害赔偿解释": "道交损害赔偿解释",
    "道路交通事故损害赔偿解释": "道交损害赔偿解释",
    "婚姻家庭编解释一": "婚姻家庭编解释一",
    "婚姻家庭编解释（一）": "婚姻家庭编解释一",
    "婚姻家庭编解释": "婚姻家庭编解释一",
    "继承编解释一": "继承编解释一",
    "继承编解释（一）": "继承编解释一",
    "继承编解释": "继承编解释一",
}


def canon_source(name: str) -> str:
    return SOURCE_ALIAS.get(name, name)


# ==================== 法名归一（唯一真源，DB-18 / 审查报告 B-49，2026-10-09） ====================
# 库存 `source` 是裸名（`劳动合同法`），而外部权威源与模型输出常写成
# `中华人民共和国劳动合同法(2012修正)`——元典智库返回的法规名**正是这个形状**
# （实测 docs/backend-readonly-audit-20260929.md §12.6：劳动合同法/消费者权益保护法都带
# 半角修正括注）。此前"去前缀 + 剥尾部括注"这条规则有**三份**实现
# （`retrieval._source_key`、`retrieval.parse_article_query` 内联剥前缀、
# `agent.writer._canonical_law_name`）加脚本里一份副本，且**全部只认全角 `（…）`**
# ⇒ 半角版本括注不被容忍，10 个引用校验消费点会把"其实有据可查"的引用判成"库里没有"
# （引用校验假阴性，比拦下更坏）。
# 本函数把**生产读侧那四份**收成一份（`_source_key`、`parse_article_query` 内联、
# `agent.writer._canonical_law_name`、`scripts/smoke_citation_full.norm_law_name`）。
# ⚠️ 射程要说清楚：还有几份**没并进来**，别把这里读成"全仓只剩一份"——
#   写侧 `scripts/import_docs.py:36` + `:53-54`（决定库存 `source` 长什么样）、
#   `scripts/capture_eval.py:56`、`scripts/gen_qwen_cases.py:61`；
#   以及"弱一档那一族"（只剥前缀、不剥括注）的两份 `retrieval._norm_source:438-446` 与
#   `agent/dept_guard.py:42` + `:45-52`——并进来会**变宽**它们的语义，属另两票（报告 DB-20/DB-21）。
# `gate_exit_registry.py:280` 的在册纪律是"不另写第二份去括注正则"——本票是**收口**，未新增第二份。
SOURCE_NAME_PREFIX = "中华人民共和国"
# 尾部版本/年份括注：全角 `（…）` 与半角 `(…)` 都剥（历史只认全角即 B-49 根因）。
# 只剥**尾部**一个，不动中段——与既有 `_source_key` 的行为同界，避免顺手改宽语义。
_SOURCE_TAIL_PAREN_RE = re.compile(r"[（(][^（）()]*[）)][\s]*$")


def norm_law_name(name: str) -> str:
    """法名归一：去「中华人民共和国」前缀 + 剥**尾部**版本/年份括注（全角与半角都剥）。

    空值安全（None/空串 → 空串）。前缀剥离后立即 strip，不留前导空格
    （旧 `_norm_source` 单独用会返回 `" 民法典"`，靠调用方末尾 `.strip()` 兜住）。
    """
    out = (name or "").strip()
    if out.startswith(SOURCE_NAME_PREFIX):
        out = out[len(SOURCE_NAME_PREFIX) :].strip()
    return _SOURCE_TAIL_PAREN_RE.sub("", out).strip()


# ==================== 提示词规则 ====================
# 引用选择规则（所有意图统一，治"选引不准"）：优先引最具体直接的条款，严禁含糊替代。
# 原 FORMAT_CLAUSE_RULE 已并入本规则——涉及商家单方限制消费者权利时，
# 不能只说"格式条款风险"而无条文支撑，须落到民法典496/497条、消保法26条。
CITATION_SELECTION_RULE = (
    "\n\n【引用选择规则】\n"
    "回答必须优先引用与争议焦点最具体、最直接对应的法条；检索结果已含更贴切的条款（如赔偿标准、免责依据、"
    "无效条款依据）时，必须引用之，严禁用“法律基本原则”“相关规定”等含糊表述替代。具体映射："
    "涉及违法解除劳动合同的赔偿金引用《劳动合同法》第八十七条（并引第四十七、四十八条说明计算）；"
    "涉及格式条款或商家单方限制消费者权利（如“拆封不退”“概不退款”“最终解释权归本店”）："
    "先依《民法典》第496条认定该条款属于格式条款，再依第497条及《消费者权益保护法》第26条认定"
    "“排除或限制消费者权利、加重消费者责任的条款无效”，不要只泛泛说“格式条款风险”却不落到具体条文；"
    "涉及交强险/机动车事故赔偿顺位引用《民法典》第一千二百一十三条。"
    # 2026-10-21 民间借贷时效案评审（评审报告 5.1／5.3、四·条文审查）：
    # 病灶不是"不知道三年"，而是"起算与中断混同"——时效尚未起算却称催告中断，
    # 且直接拿第188条从债权成立日起算。根源是正确链条所需的第510/511条（定履行期限）
    # 与司法解释起算特则不在模型可见范围，只能拿188/192/195硬凑。前两条已由
    # scenario_supplements.json 的 private_lending / limitation_period 组定向补入；
    # 此处补"怎么用"的推理纪律，二者缺一不可（只补条文不改纪律，模型仍会照旧套三年）。
    "\n涉及诉讼时效争议时：先排「债权成立—履行期限届满—催告或承诺—起诉」时间轴，再谈时效；"
    "未约定履行期限的，必须先用《民法典》第五百一十条、第五百一十一条确定履行期限，"
    "诉讼时效自该期限届满之日起算（第一百八十八条），不得从债权成立之日直接起算三年；"
    "时效尚未起算的，不得直接表述为「中断」——第一百九十五条以时效已开始计算为前提；"
    # 2026-10-21 三次采样实测：只写"不得表述为中断"时，1/3 的样本仍直接断言"承诺导致中断"
    # （与前句"2026年1月起算"并列，构成硬伤）。原因不是没读懂，是"禁止一条路径却没给合法出口"。
    # 补上带前提的备位写法后，模型有路可走，不必硬憋——实测另 2/3 已自发采用该写法且逻辑成立。
    "如作备位论证，必须显式写明「即使认为时效此前已起算」这一假设，不得与前面的起算认定并列陈述；"
    "起算、届满、中断、中止四个节点分别成句，不得在同一段混用；"
    "引用第一百九十二条时须交代其论证位置：时效届满后义务人同意履行的，不得再以时效届满抗辩。"
    "\n当事人主张某表示「不作数」「随口说的」时，先判断该表示是否具有受法律拘束的意思"
    "（结合语境、交易习惯作意思表示解释），不要直接按欺诈、胁迫、重大误解等可撤销事由处理。"
    "\n法律依据清单中的每一条文都必须在论证中实际承担推理职能；只罗列而不使用者应删除。"
    # 2026-10-21 复验补充：模型把第188条起算写成"第一百八十八条第二款"（起算在第1款，
    # 第2款是20年最长保护期）。写"核对款次"没用——检索给的是整条文本、无款号标记，
    # 模型没有可核对的依据；改成**可执行**的退让规则：不确定就不写款次。
    "\n引用具体到款时，若不能确认是该条第几款，只引到条，不臆写款次。"
    # 2026-10-24 W08 终签 Q5 归因修复（终签报告+归因诊断）：模型引对了条文（劳动合同法
    # 10②/82①/14③ 均在上下文）却算错日期——把用工当日计入期间（违反民法典 201①"开始的
    # 当日不计入"）、以咨询日截断规范上限、11 个月上限算成 5 个月，且错误方向统一指向
    # "让劳动者少要钱"（用户会少主张最多 72000 元）。病根是"引对条文、算错日期"时无纪律可依。
    # 首轮补"逐步列明"后复测：最迟日与"十一个月上限"已稳定正确，但**仍以提问日截断**
    # （问"能主张几个月"答"到 2026-03-01 已约 5 个月"）——程序性表述会被绕过，改禁令+替代式。
    "\n涉及期间、日期、金额计算的结论（如时效起算、二倍工资期间、违约金上限、折算分摊），"
    "先写明规范依据的起算口径（如“开始的当日不计入，自下一日起算”），再给出起算日、截止日、"
    "期间长度与最终数额；不得只给结论数字。"
    "\n问“能主张几个月、多少钱”时，回答的是**规范确定的上限**（自起算日至法定截止日的完整"
    "期间与对应金额），不得以提问日或咨询日截断；提问日早于截止日的，先给上限口径，"
    "再另句说明“截至提问日已发生部分”。"
    # 2026-10-24 W08 终签 Q19 归因修复（终签报告+归因诊断）：模型对考场作弊索取"拒绝外壳
    # 成立、交付实质成立"——先说拒绝，随后以"学术性讲解／法考备考"为名交付 1245 字成体系
    # 论述（总纲+四阶段+理论功能，挂 6 条现行条文逐字引文），结构即法考主观题答卷、可近乎
    # 直接誊抄。现有提示词只有"拒绝作弊"约束、无"拒绝后不得变体交付"约束（路由两轴均判
    # legal_query，未进 cheating 通道 ⇒ 该约束必须挂在通用链路上才能生效）。
    "\n对要求代写、代答、规避监管或违反考试纪律的请求，拒绝之后不得以“学术讲解”“备考指导”"
    "“一般性介绍”等变体交付成体系内容（如分阶段论述提纲、可被直接扩写成答卷的要点清单）；"
    "拒绝是否成立以是否交付了可被利用的成体系内容为准，而非仅看是否说出了拒绝。"
)


# ==================== 合同 / 文书风险评估（确定性骨架，2026-08-06） ====================
# 对抗收敛更优解：不靠 LLM 规划点（12000 字喂入只产出 ≤5 点，已证失败形态），
# 纯函数保证"不漏真实条款"。is_contract_review 触发 + contract_split 切条款 +
# 风险关键词打标签 + rubric 打分。零 LLM、零检索（条款切分层）。
_REVIEW_VERBS = (
    "审查",
    "审核",
    "评估",
    "审一下",
    "帮我审",
    "分析风险",
    "风险点",
    "把关",
    "有没有问题",
    "帮忙看看",
    "帮我看看",
)
_CONTRACT_NOUNS = (
    "合同",
    "协议",
    "条款",
    "甲方",
    "乙方",
    "违约金",
    "定金",
    "押金",
    "担保",
    "抵押",
    "保密",
    "竞业",
    "租赁",
    "借款",
    "解除",
    "违约责任",
    "付款",
    "签署",
    "买卖",
)

# 风险关键词 → 严重度标签（rubric 打分 + 分析提示共用）
# 2026-08-06 eval 校准：移除"解除/赔偿"（中性词，正常解除权/责任条款误报高，rubric 虚高、coverage 虚低）。
CONTRACT_RISK_KEYWORDS = {
    "免责": "high",
    "概不": "high",
    "单方": "high",
    "空白": "high",
    "最终解释权": "high",
    "违约金": "mid",
    "定金": "mid",
    "押金": "mid",
    "担保": "mid",
    "抵押": "mid",
    "违约责任": "mid",
    "管辖": "mid",
    "仲裁": "mid",
    "保密": "low",
    "竞业": "mid",
    "时效": "mid",
}

# 合同条款段落标记（contract_split 用）：第X条 / 一、 / （一）/ 1. / 1、 / 条款
_CONTRACT_SPLIT_MARK = re.compile(
    r"(?m)^(?=\s*(?:第[一二三四五六七八九十百千零〇0-9]+条|"
    r"[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|"
    r"[\(（]?[0-9]+[\)）、.．]|条款))"
)
_CONTRACT_LABEL_RE = re.compile(
    r"^\s*(第[一二三四五六七八九十百千零〇0-9]+条|[一二三四五六七八九十]+、|"
    r"[\(（]?[0-9]+[\)）、.．])"
)
_MIN_CONTRACT_LEN = 80  # 触发下限（短合同 ~100 字含 2+ 合同名词也应触发；口语短句如"违约金怎么算"仍不触发）
# 审查动词与合同对象的相邻窗口（字符）。超出即视为"提到合同"而非"要审这份合同"。
_CONTRACT_OBJECT_WINDOW = 14
# 条款结构标记数下限：真有合同骨架（第X条 / 一、 / 1.）才自动进合同路径。
_CONTRACT_MARK_MIN = 3


def _has_review_intent(t: str) -> bool:
    """显式审查请求：审查动词与合同对象必须**相邻**（±`_CONTRACT_OBJECT_WINDOW` 字内）。

    2026-10-25 收紧（误套 R1–R5 的第二条通道）：旧版是「全文任一处出现审查动词 +
    全文任一处出现合同名词」——长案情/试题里这两件事必然同时成立（题面写"分析风险"、
    案情提到"合同"），于是整道法律分析题被领进合同审查。改为动宾相邻才算"真的要审"。
    """
    for verb in _REVIEW_VERBS:
        start = 0
        while True:
            pos = t.find(verb, start)
            if pos < 0:
                break
            lo = max(0, pos - _CONTRACT_OBJECT_WINDOW)
            hi = pos + len(verb) + _CONTRACT_OBJECT_WINDOW
            if any(n in t[lo:hi] for n in _CONTRACT_NOUNS):
                return True
            start = pos + len(verb)
    return False


def _has_contract_structure(t: str) -> bool:
    """真有合同骨架：甲乙双方并列，或 ≥3 个条款标记。

    2026-10-25 收紧：旧版长文本分支接受「甲方出现**或**乙方出现」，且 `"条" in t`
    只看单字——案情叙述里"甲方"与"根据条款"都能凑齐。现在要求当事人成对，或有
    真正的分条结构，即文本是合同本身而不是讲合同的文章。
    """
    if "甲方" in t and "乙方" in t:
        return True
    return len(_CONTRACT_SPLIT_MARK.findall(t)) >= _CONTRACT_MARK_MIN


def is_contract_review(text: str) -> bool:
    """触发判定：显式审查请求（动宾相邻），或长文本 + 真实合同骨架。

    防误报：裸"审查"（审查起诉阶段）需配相邻合同名词；"违约金怎么算"等短句无审查动词不触发。
    2026-08-07 收紧长文本自动触发：原"≥2 合同名词"太宽，法律情景题（含"买卖/借款"
    等词）被误判进合同评估、物权/刑法条文不进上下文。
    2026-10-25 再收紧（用户要求）：合同名词必须与审查动词相邻，长文本必须甲乙方成对
    或 ≥3 条条款结构——题面"提到合同"不再进合同路径。
    """
    t = text or ""
    if _has_review_intent(t):
        return True
    return len(t) >= _MIN_CONTRACT_LEN and _has_contract_structure(t)


# 多问法律分析（2026-10-25，评审报告整改第 1 条）：试题/争点题常含"合同、货款、甲方"
# 等合同名词，会被 is_contract_review 误判进 R1–R5 合同审查模具。这里用"显式多问结构"
# 把它们分出来，优先于合同审查判定。
_ISSUE_EXPLICIT_RE = re.compile(r"(?:请|试)?回答\s*[一二三四五六七八九十\d]+\s*(?:个)?问")
_ISSUE_MARKERS = ("考查规范", "考查法条", "逐问作答", "逐问回答")


def is_issue_analysis(text: str) -> bool:
    """多问试题/争点分析判定（确定性，零 LLM）。

    命中任一即真：
    - 显式「请回答六问 / 回答3问」；
    - 「考查规范 / 逐问作答」等试题标记；
    - ≥3 条顶层编号行且全文至少 3 个问号（多问咨询）。

    合同条款编号没有问号，不会误命中。
    """
    t = text or ""
    if _ISSUE_EXPLICIT_RE.search(t):
        return True
    if any(m in t for m in _ISSUE_MARKERS):
        return True
    numbered = re.findall(r"(?m)^\s*(?:\d{1,2}|[一二三四五六七八九十])[.、．)]\s*\S+", t)
    return len(numbered) >= 3 and (t.count("？") + t.count("?")) >= 3


# 多问试题的领域条号补全（纯规则，不查库；`request_bootstrap` 与显式点名的条号合并后直查）。
# 动机（2026-10-25 复核实测）：多问分析提示词第 5 条要求「未届出资期限的股权转让先看
# 《公司法》第八十八条」，但第 88 条只有被显式点名才会进证据——题面点名的是
# 《公司法》第 23、54 条，88 条进不来，模型只能诚实回答「检索条文未提供第八十八条」，
# 该争点因此答不实。这里按**领域事实**补一条，不按题面字面（与防过拟合红线一致）。
_ISSUE_EXTRA_SPECS: list[tuple[tuple[str, ...], tuple[str, ...], list[tuple[str, str]]]] = [
    # (任一命中, 任一命中, 补充条号)
    (
        ("股权转让", "转让股权", "受让股权"),
        ("未届", "认缴", "出资期限"),
        [("公司法", "第八十八条")],  # 未届期股权转让：受让人缴纳、转让人补充（已届期未缴才连带）
    ),
]


def issue_statute_specs(text: str) -> list[tuple[str, str]]:
    """多问试题需要一并取证的条号（领域规则补全），去重保序。"""
    t = text or ""
    out: list[tuple[str, str]] = []
    for any_of, and_any_of, specs in _ISSUE_EXTRA_SPECS:
        if any(k in t for k in any_of) and any(k in t for k in and_any_of):
            for pair in specs:
                if pair not in out:
                    out.append(pair)
    return out


def contract_split(text: str) -> list[tuple[str, str]]:
    """确定性条款切分：按段落标记（第X条/一、/1.…）切分，返回 [(label, content)]。

    纯逻辑、零 LLM，结构性保证"不遗漏真实条款"。无标记 → 整段作为一条（label="全文"）；
    切不动的复杂格式（表格/附件）兜底为整段，不硬切。
    """
    t = (text or "").strip()
    if not t:
        return []
    marks = list(_CONTRACT_SPLIT_MARK.finditer(t))
    if not marks:
        return [("全文", t)]
    out: list[tuple[str, str]] = []
    # 保留首个标记前的引言/首段（2026-08-06 diagnosing-bugs：原实现只遍历条标，
    # 条标之前内容无归属被丢弃——结构性漏条款）
    if marks[0].start() > 0:
        pre = t[: marks[0].start()].strip()
        if pre:
            out.append(("前言", pre))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
        seg = t[m.start() : end].strip()
        if not seg:
            continue
        lm = _CONTRACT_LABEL_RE.match(seg)
        out.append((lm.group(1) if lm else f"段{i + 1}", seg))
    return out or [("全文", t)]


def clause_risk_tags(clause_text: str) -> list[str]:
    """风险关键词打标签：命中返回风险词列表（rubric 打分 + 分析提示用）。"""
    t = clause_text or ""
    return [k for k in CONTRACT_RISK_KEYWORDS if k in t]


def rubric_risk_level(clauses: list[tuple[str, str]]) -> tuple[str, str]:
    """总体风险等级 rubric 打分（确定性，防"极高风险"夸大）。

    分数 = 高风险词命中×2 + 中风险词命中×1；等级：极高/高/中/低。
    返回 (等级, 判定依据)。
    """
    hi = mid = risk_clauses = 0
    for _, seg in clauses:
        tags = clause_risk_tags(seg)
        hi += sum(1 for k in tags if CONTRACT_RISK_KEYWORDS[k] == "high")
        mid += sum(1 for k in tags if CONTRACT_RISK_KEYWORDS[k] == "mid")
        if tags:
            risk_clauses += 1
    score = hi * 2 + mid
    if hi >= 2 and risk_clauses >= 2:
        level = "极高"
    elif score >= 5 or hi >= 2:
        level = "高"
    elif score >= 2:
        level = "中"
    else:
        level = "低"
    return level, f"高风险词命中 {hi} 处、中风险词 {mid} 处、涉风险条款 {risk_clauses} 条"


# ==================== 合同数据构建（main/eval 共用单一来源，2026-08-06） ====================
# 从 main.py 迁入：IO 函数与纯函数同仓，eval 脚本可干净复用（不 import main 触发顶层副作用）。
_CLAUSE_MAPPING_CACHE: dict | None = None


def load_clause_supplements() -> dict:
    """模块级缓存加载 contract_clause_supplements.json（避免每条款重复磁盘读）。"""
    global _CLAUSE_MAPPING_CACHE
    if _CLAUSE_MAPPING_CACHE is None:
        mapping_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contract_clause_supplements.json")
        try:
            with open(mapping_path, encoding="utf-8") as _f:
                _CLAUSE_MAPPING_CACHE = json.load(_f)
        except Exception:
            _CLAUSE_MAPPING_CACHE = {}
    return _CLAUSE_MAPPING_CACHE


# 劳动条款特征词（code-review 边界盲区修复，2026-08-06）：扩充至试用期/工资/社保等，
# 纯"试用期"条款若含"解除"不再漏判为劳动。不纳入"培训"——培训服务合同（消费场景）会误伤。
_LABOR_KEYWORDS = (
    "劳动合同",
    "竞业",
    "劳动报酬",
    "经济补偿",
    "试用期",
    "工资",
    "社保",
    "社会保险",
    "住房公积金",
    "服务期",
    "带薪年休假",
)


def is_labor_clause(clause_text: str) -> bool:
    """劳动条款判定（contract_supplement_docs 法域隔离用）。"""
    return any(k in (clause_text or "") for k in _LABOR_KEYWORDS)


def contract_supplement_docs(clause_text: str, cutoff: str | None = None) -> list:
    """条款 → 数据驱动法条（contract_clause_supplements.json 精确直查）；未命中回落一次检索。

    - 合同类型→法域杜绝错绑：劳动条款只引劳动法，不命中民法典通用条款（含"解除"——
      劳动解除走劳动合同法36/39/46/47/87，不引民法典563）
    - 时效别名：json 键"诉讼时效"同时匹配含"时效"的条款
    - `cutoff`：历史查询基准日，两条取数通道（精确直查、语义回落）都必须带上，
      否则历史日期下的合同证据会静默变薄。
    """
    from retrieval import exact_article_lookup, retrieve  # noqa: PLC0415

    mapping = load_clause_supplements()
    labor = is_labor_clause(clause_text)
    _CIVIL_GENERIC = ("违约金", "定金", "担保", "抵押", "免责", "租赁", "借款", "买卖", "格式条款", "解除")
    matched: list = []
    for kw, specs in mapping.items():
        hit = kw in clause_text or (kw == "诉讼时效" and "时效" in clause_text)
        if not hit:
            continue
        if kw == "担保" and "保修" in clause_text:
            continue  # "承担保修"含子串"担保"，属保修条款非担保合同（code-review 2026-08-06）
        if labor and kw in _CIVIL_GENERIC:
            continue  # 劳动合同条款不命中民事通用条款（杜绝错绑）
        for s in specs:
            matched += exact_article_lookup(s.get("source", ""), s.get("article", ""), cutoff=cutoff)
    if not matched:
        matched = retrieve(clause_text, k=3, cutoff=cutoff)  # 未命中回落语义检索
    return matched


def build_contract_data(text: str, cutoff: str | None = None) -> dict:
    """确定性骨架：切分条款 → 每条款配法条 → 证据块 + rubric 风险等级。

    `cutoff`（历史查询基准日）：必须在**构建时**传给每条款配法条，而不是构建完再过滤结果——
    `blocks[*]["articles"]` 与 `docs` 同源，`main._contract_messages` 读的是前者。
    """
    t = (text or "").strip()
    truncated = len(t) > settings.contract_max_chars
    if truncated:
        t = t[: settings.contract_max_chars]
    clauses = contract_split(t)
    blocks = []
    all_docs: list = []
    for idx, (label, seg) in enumerate(clauses, 1):
        docs = contract_supplement_docs(seg, cutoff=cutoff)
        all_docs += docs
        blocks.append(
            {
                "n": idx,
                "label": label,
                "text": seg[:600],
                "articles": sorted({d.metadata.get("article", "") for d in docs})[:3],
                "tags": clause_risk_tags(seg),
            }
        )
    level, basis = rubric_risk_level(clauses)
    return {
        "truncated": truncated,
        "need_clarify": len(t) < 80,  # 触发但无合同全文（如"帮我审合同"）→ 反问要内容
        "blocks": blocks,
        "docs": all_docs,
        "level": level,
        "basis": basis,
    }
