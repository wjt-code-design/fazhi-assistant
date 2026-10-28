"""R15 绊线的 watch-it-fail 留痕（B3，2026-09-18）。

证明「拦住这条 draft 的就是 law_version_crosses_watershed 这道判定」：把判定打桩成
恒 False（= 本批新增的门不存在），其余一切不变，断言该 draft 会一路 PASS 交付给用户。

一键复现：
    cd backend && ./venv/Scripts/python.exe -m pytest tests/_r15_tripwire_probe.py -q -m "not slow"
"""

from __future__ import annotations

from datetime import date

import pytest

import settings as settings_module
from legal_workflow import limitation_calc
from legal_workflow.verifier import DeterministicVerifier, VerificationVerdict
from legal_workflow.writer import EvidenceBoundedWriter
from tests.test_phantom_check import SingleClaimGenerator
from tests.test_r15_version_tripwire import _TIMING_CLAIM, _state_with_pre_watershed_fact


@pytest.fixture(autouse=True)
def _stub_gate(monkeypatch: pytest.MonkeyPatch):
    """开关开 + 判定恒 False —— 等价于"本批这道门还没写"的世界。"""
    monkeypatch.setattr(settings_module.settings, "law_version_tripwire_check", True)
    monkeypatch.setattr(limitation_calc, "law_version_crosses_watershed", lambda *a, **k: False)


def test_without_the_gate_the_cross_watershed_answer_ships():
    state = _state_with_pre_watershed_fact()
    draft = EvidenceBoundedWriter(SingleClaimGenerator(_TIMING_CLAIM)).render(state).draft
    assert draft is not None, "前置失效：草稿都没生成，本留痕需重做"
    verdict = DeterministicVerifier().verify(state, draft, law_as_of=date(2026, 9, 18))
    assert verdict.verdict is VerificationVerdict.PASS, (
        f"门被桩掉后仍被拦下（{verdict.reason_code}）⇒ 该缺陷其实已被别的门覆盖，本留痕需重做"
    )
