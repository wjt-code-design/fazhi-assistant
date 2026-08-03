"""法律查询切片（query slicing）：超长查询拆成独立检索单元，杜绝"场景词淹没核心问题"。

背景（2026-08-04 diagnosing-bugs）：法考题长题干（200+ 字场景 + 4 个选项）整句检索时，
场景细节（"边境旅游/6克4克2克/行李包/长途汽车"）在向量与 BM25 两侧都占主导，核心
罪名（如"非法持有毒品罪"→《刑法》348条）被推到双路排名第 9/16，进不了候选池
（候选池=各取前 6 + RRF top12），最终 top-6 丢失 → agent 基于缺失上下文诚实拒答。

机制：把超长查询按选项/句子切成独立检索单元，每段独立走混合检索进候选池，RRF 融合。
含罪名的段落（如选项 A："构成非法持有毒品罪"）独立检索必然命中 348，从机制上杜绝
"整句语义被场景稀释"，不依赖正则提取精度。

触发条件（短查询零开销零变化）：
- 查询 > SLICE_MIN_CHARS（60）才切片
- 法考题：含 "A：/B：/C：/D：" 选项模式 或 "错误的是/正确的是/下列说法" 关键词
  → 按选项切分（题干 + 各选项，上限 SLICE_MAX）
- 普通长文本：按中文标点切句，取前 SLICE_MAX 段

纯逻辑模块，无 LLM 调用，无嵌入；切片结果由调用方（hybrid_retrieve）执行检索。
"""

import re

SLICE_MIN_CHARS = 60
SLICE_MAX = 5  # 段数上限（不含整句保底）：题干 + 4 选项 / 5 个句子。控制延迟，兼顾召回

# 法考题信号：选项模式或"判断正误"措辞
_CHOICE_RE = re.compile(r"[A-D]：")
_JUDGE_MARKS = ("错误的是", "正确的是", "下列说法", "哪一项", "哪些说法")

# 中文标点切句
_SENT_SPLIT_RE = re.compile(r"[，。？；！、\n]")


def _is_exam_question(text: str) -> bool:
    """法考题信号：选项模式或判断正误措辞。"""
    if _CHOICE_RE.search(text):
        return True
    return any(m in text for m in _JUDGE_MARKS)


def _split_by_choice(text: str) -> list[str]:
    """按选项切分：题干 + 每个选项独立成段。保留选项前缀（A：…）供检索定位。"""
    parts = re.split(r"(?=[A-D]：)", text)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) >= 4:  # 过短段（如孤立标点）丢弃
            out.append(p)
    return out[:SLICE_MAX]


def _split_by_sentence(text: str) -> list[str]:
    """按中文标点切句，取较长句（保留有信息量的），上限 SLICE_MAX。"""
    parts = [s.strip() for s in _SENT_SPLIT_RE.split(text)]
    out = [s for s in parts if len(s) >= 6]
    return out[:SLICE_MAX] if out else [text]


def slice_query(query: str) -> list[str]:
    """超长查询切片。返回检索单元列表（第一个永远是整句，保证不回退）。"""
    if len(query) <= SLICE_MIN_CHARS:
        return [query]
    if _is_exam_question(query):
        segs = _split_by_choice(query)
    else:
        segs = _split_by_sentence(query)
    # 整句保底在首位 + 各段去重（整句与段可能相同）
    out = [query]
    for s in segs:
        if s and s != query and s not in out:
            out.append(s)
    return out[: SLICE_MAX + 1]
