"""窄域事实绊线：无条件借款清偿陈述。不是通用语义蕴含判断。"""

import re
from collections.abc import Iterable

_STATUS = re.compile(
    r"(?:该|本笔|这笔)?借款(?:尚未(?:清偿|还清)|未(?:清偿|还清)|"
    r"(?:已|已经)(?:全部(?:清偿|偿还)|还清))"
)
_UNCERTAIN = re.compile(r"[？?‘’“”\"]|如果|假如|若|是否|可能|据称|曾经|此前|后来|另一笔|多笔|两笔")


def _statuses(text: str) -> set[bool]:
    if _UNCERTAIN.search(text):
        return set()
    result = set()
    for clause in re.split(r"[，,。；;！!\n]", text):
        clause = clause.strip()
        if _STATUS.fullmatch(clause):
            result.add("未" not in clause)
    return result


def settlement_conflicts(claim: str, fact_texts: Iterable[str]) -> bool:
    """只匹配独立清偿短句；条件、引语、时间变更、多笔借款不作自动判定。"""
    facts = list(fact_texts)
    if any(_UNCERTAIN.search(text) for text in facts):
        return False
    known = set().union(*(_statuses(text) for text in facts))
    return len(known) == 1 and bool(_statuses(claim) - known)
