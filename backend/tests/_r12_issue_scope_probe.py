"""B3 watch-it-fail 留痕探针（R12 伪调用按争点取数整改，2026-09-18）。

要证明的事：`test_phantom_check.py` 的跨争点用例**确实会因为被修的那个缺陷而红**，
不是只在"实现已改好"的世界里绿着（docs/code-review-standard.md §2 B3）。

做法：不改任何生产代码——把 `phantom_check.issue_executions` 原位换成整改前的
**state 全局**取值语义（所有争点共享同一份"成功工具集 ∪ 是否有证据"）。writer
与 verifier 都只通过 `.get(issue_id, NO_EXECUTION)` 读它，因此可无损替换。

复现命令（一条）：
    cd backend && venv/Scripts/python.exe -m pytest \\
        tests/_r12_issue_scope_probe.py -q --basetemp=<全新目录>

预期：**2 passed**。任何一条转为失败即说明本留痕已对不上代码，须重做而非删除。
文件名以 `_` 开头 ⇒ 不被默认收集（testpaths=tests 只收 test_*.py），只能显式运行。
"""

from __future__ import annotations

import pytest

from agent import phantom_check
from agent.phantom_check import IssueExecution, issue_executions
from agent.writer import EvidenceBoundedWriter, WriterStatus
from tests.test_phantom_check import SingleClaimGenerator, two_issue_state

# 刻意不含数字：否则 issue-b 先被数字白名单门拦下，探针测到的就不是伪调用门。
PHANTOM_ON_UNRESEARCHED_ISSUE = "经检索发现相关依据，对方存在拖欠行为。"


class _SharedFacts(dict):
    """`.get` 对任意争点恒返回同一份事实 = 整改前的全局取值。"""

    def __init__(self, facts: IssueExecution) -> None:
        self._facts = facts

    def get(self, _key, default=None):  # noqa: ANN001, ANN201 - 模拟 dict 的调用点契约
        return self._facts


def _pre_fix_issue_executions(observations) -> _SharedFacts:
    """按整改前语义折叠：tool_success 取全 state 并集，has_evidence 取全局真值。"""
    per_issue = issue_executions(observations)
    tools = (
        frozenset().union(*(execution.tool_success for execution in per_issue.values())) if per_issue else frozenset()
    )
    return _SharedFacts(IssueExecution(tools, any(execution.has_evidence for execution in per_issue.values())))


@pytest.fixture(autouse=True)
def pre_fix_semantics(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(phantom_check, "issue_executions", _pre_fix_issue_executions)
    monkeypatch.setattr("settings.settings.phantom_tool_check", True)


def test_phantom_gate_goes_silent_on_cross_issue_claim():
    """全局取值下，issue-a 的证据把 issue-b 的伪检索声称放过了——门不报。"""
    result = EvidenceBoundedWriter(SingleClaimGenerator(PHANTOM_ON_UNRESEARCHED_ISSUE)).render_issue(
        two_issue_state(), "issue-b"
    )
    assert result.reason_code != "PHANTOM_TOOL_CLAIM", "缺陷已被别的门先行拦下？本留痕需重做"


def test_the_new_test_expectation_does_not_hold_pre_fix():
    """真实用例断言的 (FAIL_SAFE, PHANTOM_TOOL_CLAIM) 在全局取值下必然不成立。"""
    result = EvidenceBoundedWriter(SingleClaimGenerator(PHANTOM_ON_UNRESEARCHED_ISSUE)).render_issue(
        two_issue_state(), "issue-b"
    )
    assert not (result.status is WriterStatus.FAIL_SAFE and result.reason_code == "PHANTOM_TOOL_CLAIM")
