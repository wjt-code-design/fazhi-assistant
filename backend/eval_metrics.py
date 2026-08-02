"""评测指标（纯函数，可单测，不依赖 LLM / 网络）。

- recall_at_k：检索召回（命中期望条号的比例）。
- citation_correct：生成答案是否引用了期望条号（规则启发式，免费）。
- citation_present：答案是否含《…》第X条 引用。
忠实度(faithfulness) 需 LLM-judge，成本较高，默认关闭（见 scripts/eval_quality.py 的 EVAL_LLM_JUDGE）。
"""

import re
from collections.abc import Iterable

_CITE_RE = re.compile(r"《[^》]+》\s*第[一二三四五六七八九十百零0-9]+条")


def recall_at_k(retrieved_articles: Iterable[str], expected_articles: Iterable[str]) -> float:
    rev = {a for a in retrieved_articles if a}
    exp = [a for a in expected_articles if a]
    if not exp:
        return 0.0
    return sum(1 for a in exp if a in rev) / len(exp)


def cited_articles(answer: str) -> list[str]:
    return _CITE_RE.findall(answer or "")


def citation_present(answer: str) -> bool:
    return bool(_CITE_RE.search(answer or ""))


def citation_correct(answer: str, expected_articles: Iterable[str]) -> bool:
    cited = "".join(cited_articles(answer))
    return any(a and a in cited for a in expected_articles)
