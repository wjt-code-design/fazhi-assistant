"""领域规则集中地（single source of truth）。

硬编码的条文映射、场景关键词、提示词规则统一放这里，避免散落在 main.py：
- 条文映射（作弊 / 格式条款 / 引用选择）只改这里，main.py 不感知细节
- 提示词规则从这里导入，main.py 只负责拼接

复用 retrieval.exact_article_lookup 做精确条号命中。
"""

from retrieval import exact_article_lookup


def _lookup_all(specs: list[tuple[str, str]]):
    """按 (source, article) 精确查找，返回 Document 列表（顺序 = 传入顺序）。"""
    docs = []
    for source, article in specs:
        docs += exact_article_lookup(source, article)
    return docs


# ==================== 作弊 / 考试场景条文 ====================
# 作弊路径定向检索考试作弊相关条文，使释法引用有据（避免通用检索召回无关条文）。
CHEATING_DOCS_SPEC = [
    ("刑法", "第二百八十四条之一"),  # 组织考试作弊罪
    ("治安管理处罚法", "第二十七条"),  # 冒名顶替 / 伪造证件等
]


def cheating_docs():
    return _lookup_all(CHEATING_DOCS_SPEC)


# ==================== 消费者格式条款场景 ====================
# 商家单方限制消费者权利的关键词（命中即补充格式条款条文到检索上下文）
CC_KEYWORDS = ("拆封不退", "概不退款", "不予退款", "最终解释权", "格式条款", "概不退换", "拒退")


def is_consumer_clause_scenario(text: str) -> bool:
    """检测「商家单方限制消费者权利 / 格式条款」场景，命中则补充格式条款条文到检索上下文。"""
    t = text or ""
    if any(k in t for k in CC_KEYWORDS):
        return True
    return ("退货" in t or "退款" in t) and ("条款" in t or "免责" in t or "无效" in t or "退" in t)


# 格式条款 / 消费者权利兜底条文：民法典496/497（格式条款）、消保法26（限制消费者权利条款无效）。
CONSUMER_CLAUSE_DOCS_SPEC = [
    ("民法典", "第四百九十六条"),  # 格式条款定义
    ("民法典", "第四百九十七条"),  # 格式条款无效情形
    ("消费者权益保护法", "第二十六条"),  # 排除限制消费者权利条款无效
]


def consumer_clause_docs():
    return _lookup_all(CONSUMER_CLAUSE_DOCS_SPEC)


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
)
