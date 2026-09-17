"""受控沉淀判定（纯逻辑，无重型依赖，便于单测）。

只有"高有据 + 带法条引用 + 非空答"的问答才进入待审，避免幻觉/低质答案污染知识库。
"""

import re

CITATION_RE = re.compile(r"《[^》]+》\s*第[一二三四五六七八九十百零0-9]+条|根据《[^》]+》")
# 有据分入门门槛（用户要求 2026-08-07：有据分 <0.7 不收录，不进待审队列）
DEFAULT_GROUNDED_THRESHOLD = 0.7
MIN_ANSWER_LEN = 20


def has_citation(answer: str) -> bool:
    return bool(CITATION_RE.search(answer or ""))


def should_curate(grounded: float, answer: str, threshold: float = DEFAULT_GROUNDED_THRESHOLD) -> bool:
    a = answer or ""
    return grounded >= threshold and has_citation(a) and len(a) > MIN_ANSWER_LEN
