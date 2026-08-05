"""合同评估确定性 verifier（零 LLM，纯函数，可单测）。ADR-014 二期 eval 门控。

验证「LLM 报告」对「确定性骨架」的忠实度，量一期真实缺口：
  - coverage：合同风险条款（contract_split + clause_risk_tags 打标）被报告覆盖的比例
    ——抓"漏条款"：报告没提合同里真实存在的风险条款
  - no_fab：报告引用的"原文摘录"是否都在合同里——抓"编造条款"
  - cite_ok / cite_supported：条文真实在库且属于该点命中集——抓"引错条/引对条不对题"
  - structure_ok：每条 R_n 是否五要素完整——抓"输出松散、缺失修改建议"
  - level_match：报告结论风险等级 vs rubric 确定性打分——抓"风险等级夸大/淡化"

设计原则：所有金标由确定性函数即时生成（contract_split + rubric + 命中条文），
不手写主观金标（防 metric-gaming，与 ADR-014 金标校准原则一致）。
"""

import re

# ==================== 报告解析 ====================

_R_ENTRY_RE = re.compile(r"(?:R\s*[_\-\s]*|风险\s*[_\-\s]*|【R)\s*(\d+)")
_QUOTE_RE = re.compile(
    r"[「『]([^」』]{3,})[」』]|“([^”]{3,})”|\"([^\"]{3,})\"|‘([^’]{3,})’|'([^']{3,})'"
)
_STRUCTURE_KEYS = ("位置", "严重度", "原文", "法条", "建议")
# 报告等级提取：兼容「总体风险等级：高」「风险等级为较高」等写法
# 2026-08-06 修复：容忍 markdown 加粗（**高**）/引号干扰等级词提取
_LEVEL_RE = re.compile(r"(?:总体)?风险(?:等级)?[：:为是][\s《“\"'`*　]*(极高|较高|中|较低|低|高)")
# 风险等级相邻映射（rubric 四级，报告可能用"较高/较低"等同义）
_ADJ = {
    "极高": {"高"},
    "高": {"极高", "中", "较高"},
    "中": {"高", "低", "较高", "较低"},
    "低": {"中", "较低"},
    "较高": {"高", "中"},
    "较低": {"低", "中"},
}


def _norm(s: str) -> str:
    """归一化：去空白、去标点（中文数字字母保留）——锚点/摘录对位，容忍格式差异。"""
    return re.sub(r"[\s\W_]+", "", s or "")


def parse_risk_entries(answer: str) -> list[str]:
    """切出报告所有 R_n 风险条目原文。无 R 标记 → []（未结构化，structure 记 0）。"""
    ans = answer or ""
    marks = list(_R_ENTRY_RE.finditer(ans))
    entries: list[str] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(ans)
        seg = ans[m.start() : end].strip()
        if seg:
            entries.append(seg)
    return entries


def extract_quoted_fragments(text: str) -> list[str]:
    """提取报告中的引号原文摘录（「」/“”/""/'' 内 ≥3 字）。"""
    out = []
    for m in _QUOTE_RE.finditer(text or ""):
        for g in m.groups():
            if g and g.strip():
                out.append(g.strip())
    return out


# ==================== 覆盖（漏条款） ====================

def _segment_keys(label: str, seg_text: str) -> list[str]:
    """条款段 → 识别锚点集：条号（第X条）+ 归一化段首 12 字。报告含任一锚点视为覆盖。

    条号最特异（SYSTEM 模板要求报告按"条款位置"标注，模型会抄合同条号）；
    无条号段（前言/全文/数字序号）用段首锚点兜底。
    """
    keys: list[str] = []
    ln = _norm(label or "")
    if ln:
        keys.append(ln)
    head = _norm(seg_text or "")[:12]
    if head and head not in keys:
        keys.append(head)
    return keys


def coverage(answer: str, clauses: list[tuple[str, str]]) -> tuple[float, list[int]]:
    """风险条款覆盖率：带风险标签的段中被报告提及的比例（漏条款检测）。

    clauses 来自确定性 contract_split；仅统计 clause_risk_tags 打标的段（真实风险条款）。
    返回 (覆盖率, 未覆盖段索引 list[1-based])。无风险条款 → 1.0（无可漏）。
    """
    from domain_rules import clause_risk_tags

    ans_n = _norm(answer or "")
    total = covered = 0
    uncovered: list[int] = []
    for idx, (label, seg) in enumerate(clauses, 1):
        if not clause_risk_tags(seg):
            continue
        total += 1
        if any(k and k in ans_n for k in _segment_keys(label, seg)):
            covered += 1
        else:
            uncovered.append(idx)
    return (covered / total if total else 1.0, uncovered)


# ==================== 编造（引号摘录对位） ====================

def fabricated_fragments(answer: str, contract: str) -> list[str]:
    """报告引号摘录不在合同原文的片段（归一化比对）。LLM 改写摘录会误报，需人工复核。"""
    c_n = _norm(contract or "")
    return [f for f in extract_quoted_fragments(answer) if _norm(f) and _norm(f) not in c_n]


# ==================== 结构完整度 / 等级 ====================

def structure_score(entry: str) -> float:
    """R_n 条目五要素完整度 0-1：标签词命中或 | 字段分段计分。

    2026-08-06 修复：label 全命中时优先判满——部分报告用「严重度|条款位置」的 2 字段
    `|` 头 + 换行标签正文，pipe 字段数只有 3 却五要素齐全，原实现提前返回 0.5。
    """
    e = entry or ""
    if not e:
        return 0.0
    label_hits = sum(1 for k in _STRUCTURE_KEYS if k in e)
    pipe_fields = [p for p in e.split("|") if p.strip()]
    if label_hits == len(_STRUCTURE_KEYS) or len(pipe_fields) >= 5:
        return 1.0
    if len(pipe_fields) >= 3:
        return 0.5
    return label_hits / len(_STRUCTURE_KEYS)


def report_level(answer: str) -> str | None:
    """从报告提取总体风险等级；找不到 → None。兼容「总体风险等级：高」「风险等级：较高」。"""
    m = _LEVEL_RE.search(answer or "")
    if m:
        return m.group(1)
    return None


def level_match(answer: str, rubric_level: str) -> str:
    """报告等级 vs rubric 确定性等级：match / diff_adj（相邻）/ diff_far / none。"""
    rl = report_level(answer)
    if rl is None or not rubric_level:
        return "none"
    if rl == rubric_level:
        return "match"
    if rubric_level in _ADJ.get(rl, set()):
        return "diff_adj"
    return "diff_far"


# ==================== 条文提取 / 归一化（eval 侧轻量版） ====================
# retrieval.extract_citations 同口径但纯正则、零 BGE 依赖——eval 步骤2（后端运行中）
# 不能 import retrieval（模块级加载 embedding，双 BGE 进程冲突）。golden 命中集
# 也用本函数归一化，保证报告条文与命中集可比对。±1000 范围中文数字足够合同条文。

_CN = "零一二三四五六七八九"
_ART_NUM_RE = re.compile(r"第\s*([一二三四五六七八九十百千零0-9]+)\s*条")
_ART_FULL_RE = re.compile(r"《([^》]+)》\s*第\s*([一二三四五六七八九十百千零0-9]+)\s*条")


def _cn_to_arab(s: str) -> str:
    """中文数字→阿拉伯（支持 一~九千九百九十九；含"零"容错）。无法解析返回原串。"""
    total = section = digit = 0
    for ch in s or "":
        if ch == "零":
            continue
        if ch in _CN:
            digit = _CN.index(ch)
        elif ch == "十":
            section += digit * 10 if digit else 10
            digit = 0
        elif ch == "百":
            section += digit * 100 if digit else 100
            digit = 0
        elif ch == "千":
            section += digit * 1000 if digit else 1000
            digit = 0
        elif ch == "万":
            total = (total + section) * 10000
            section = digit = 0
        else:
            return s  # 非中文数字 → 保持原样
    total += section + digit
    return str(total) if total else s


def norm_article(art: str) -> str:
    """条号归一化为「第N条」（中文数字→阿拉伯）。兼容完整"第X条"或纯条号数字。"""
    a = (art or "").strip()
    m = _ART_NUM_RE.search(a)
    if m:
        return "第" + _cn_to_arab(m.group(1)) + "条"
    if re.fullmatch(r"[一二三四五六七八九十百千零0-9]+", a):
        return "第" + _cn_to_arab(a) + "条"
    return a


def cited_articles(answer: str) -> set[str]:
    """报告引用的《法名》第X条 → 归一化条号集合（防编造/引错条比对用）。"""
    return {norm_article(m.group(2)) for m in _ART_FULL_RE.finditer(answer or "")}
