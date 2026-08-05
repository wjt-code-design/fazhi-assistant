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


def _lookup_all(specs: list[tuple[str, str]]):
    """按 (source, article) 精确查找，返回 Document 列表（顺序 = 传入顺序）。"""
    from retrieval import exact_article_lookup  # noqa: PLC0415

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


def consumer_clause_docs():
    return _lookup_all(CONSUMER_CLAUSE_DOCS_SPEC)


# ==================== 消费欺诈 / 退一赔三场景 ====================
# 复合问题里检索 top-k 常被电商法占满，漏掉消保法55条（退一赔三），故定向补充。
FRAUD_KEYWORDS = (
    "欺诈", "退一赔三", "退一赔十", "假一赔", "假货", "假冒伪劣", "以假充真",
    "以次充好", "虚假宣传", "三倍赔偿", "赔偿三倍", "假货赔偿",
)


def is_consumer_fraud_scenario(text: str) -> bool:
    """检测「消费欺诈 / 退一赔三」场景，命中则补充消保法55条到检索上下文。"""
    t = text or ""
    return any(k in t for k in FRAUD_KEYWORDS)


# 消费欺诈惩罚性赔偿：消保法55条（退一赔三，食品等另有食安法148 假一赔十，按需扩展）。
CONSUMER_FRAUD_DOCS_SPEC = [
    ("消费者权益保护法", "第五十五条"),  # 欺诈退一赔三 / 惩罚性赔偿
]


def consumer_fraud_docs():
    return _lookup_all(CONSUMER_FRAUD_DOCS_SPEC)


# ==================== 复杂度分级 / 质量自检常量 ====================
# 高利害/多解主题词：命中任一 → 视为复杂问题（走旗舰模型，避免轻量翻车）
COMPLEX_KEYWORDS = (
    "刑事", "罪名", "拘留", "判刑", "缓刑", "取保候审", "自首", "立功",
    "劳动仲裁", "工伤", "解除劳动合同", "经济补偿", "赔偿金",
    "离婚", "抚养", "继承", "遗嘱", "房产", "股权", "破产",
    "诉讼时效", "管辖权", "证据", "举证", "行政复议", "行政诉讼",
)

# 含糊填充话（仅当回答"无引用"时才算含糊；有引用不算）
VAGUE_PHRASES = (
    "相关法律", "相关法条", "相关规定", "法律原则", "具体需咨询",
    "请咨询律师", "具体情况具体分析", "视情况而定", "依法处理",
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
}


def canon_source(name: str) -> str:
    return SOURCE_ALIAS.get(name, name)


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


# ==================== 合同 / 文书风险评估（确定性骨架，2026-08-06） ====================
# 对抗收敛更优解：不靠 LLM 规划点（12000 字喂入只产出 ≤5 点，已证失败形态），
# 纯函数保证"不漏真实条款"。is_contract_review 触发 + contract_split 切条款 +
# 风险关键词打标签 + rubric 打分。零 LLM、零检索（条款切分层）。
_REVIEW_VERBS = ("审查", "审核", "评估", "审一下", "帮我审", "分析风险", "风险点", "把关", "有没有问题", "帮忙看看", "帮我看看")
_CONTRACT_NOUNS = ("合同", "协议", "条款", "甲方", "乙方", "违约金", "定金", "押金", "担保", "抵押", "保密", "竞业", "租赁", "借款", "解除", "违约责任", "付款", "签署", "买卖")

# 风险关键词 → 严重度标签（rubric 打分 + 分析提示共用）
# 2026-08-06 eval 校准：移除"解除/赔偿"（中性词，正常解除权/责任条款误报高，rubric 虚高、coverage 虚低）。
CONTRACT_RISK_KEYWORDS = {
    "免责": "high", "概不": "high", "单方": "high", "空白": "high", "最终解释权": "high",
    "违约金": "mid", "定金": "mid", "押金": "mid", "担保": "mid", "抵押": "mid",
    "违约责任": "mid", "管辖": "mid", "仲裁": "mid",
    "保密": "low", "竞业": "mid", "时效": "mid",
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


def is_contract_review(text: str) -> bool:
    """触发判定：显式审查请求 + 合同名词，或长文本（≥150 字）+ ≥2 合同名词/含当事人词。

    防误报：裸"审查"（审查起诉阶段）需配合同名词；"违约金怎么算"等短句无审查动词不触发。
    """
    t = text or ""
    if any(v in t for v in _REVIEW_VERBS) and any(n in t for n in _CONTRACT_NOUNS):
        return True
    if len(t) >= _MIN_CONTRACT_LEN and (
        sum(1 for n in _CONTRACT_NOUNS if n in t) >= 2 or "甲方" in t or "乙方" in t
    ):
        return True
    return False


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
        seg = t[m.start():end].strip()
        if not seg:
            continue
        lm = _CONTRACT_LABEL_RE.match(seg)
        out.append((lm.group(1) if lm else f"段{i+1}", seg))
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
        mapping_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "contract_clause_supplements.json"
        )
        try:
            with open(mapping_path, encoding="utf-8") as _f:
                _CLAUSE_MAPPING_CACHE = json.load(_f)
        except Exception:
            _CLAUSE_MAPPING_CACHE = {}
    return _CLAUSE_MAPPING_CACHE


# 劳动条款特征词（code-review 边界盲区修复，2026-08-06）：扩充至试用期/工资/社保等，
# 纯"试用期"条款若含"解除"不再漏判为劳动。不纳入"培训"——培训服务合同（消费场景）会误伤。
_LABOR_KEYWORDS = (
    "劳动合同", "竞业", "劳动报酬", "经济补偿", "试用期", "工资", "社保",
    "社会保险", "住房公积金", "服务期", "带薪年休假",
)


def is_labor_clause(clause_text: str) -> bool:
    """劳动条款判定（contract_supplement_docs 法域隔离用）。"""
    return any(k in (clause_text or "") for k in _LABOR_KEYWORDS)


def contract_supplement_docs(clause_text: str) -> list:
    """条款 → 数据驱动法条（contract_clause_supplements.json 精确直查）；未命中回落一次检索。

    - 合同类型→法域杜绝错绑：劳动条款只引劳动法，不命中民法典通用条款（含"解除"——
      劳动解除走劳动合同法36/39/46/47/87，不引民法典563）
    - 时效别名：json 键"诉讼时效"同时匹配含"时效"的条款
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
        if labor and kw in _CIVIL_GENERIC:
            continue  # 劳动合同条款不命中民事通用条款（杜绝错绑）
        for s in specs:
            matched += exact_article_lookup(s.get("source", ""), s.get("article", ""))
    if not matched:
        matched = retrieve(clause_text, k=3)  # 未命中回落语义检索
    return matched


def build_contract_data(text: str) -> dict:
    """确定性骨架：切分条款 → 每条款配法条 → 证据块 + rubric 风险等级。"""
    t = (text or "").strip()
    truncated = len(t) > settings.contract_max_chars
    if truncated:
        t = t[: settings.contract_max_chars]
    clauses = contract_split(t)
    blocks = []
    all_docs: list = []
    for idx, (label, seg) in enumerate(clauses, 1):
        docs = contract_supplement_docs(seg)
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
