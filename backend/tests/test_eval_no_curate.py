"""评测隔离（2026-10-27）：`X-Eval-No-Curate: 1` ⇒ 答案照常落库，但不进受控沉淀。

判据（两条腿）：
  ① 带评测头 ⇒ `ks.create_candidate` 不被调用（不产生 qa_candidates / qa_pairs 写入）；
  ② 不带评测头 ⇒ 原有沉淀路径不变（`create_candidate` 恰好一次）。

第二条是反向钉子：只证"带头跳过"而不证"不带头仍然收"，会把"永远不收"的坏修法判成绿。
"""

from unittest.mock import MagicMock

import pytest

import main
from tests import _sse_harness as harness


@pytest.fixture
def curation_spy(monkeypatch):
    spy = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(main.ks, "create_candidate", spy)
    monkeypatch.setattr(main, "grounded_top_score", lambda q: 0.95)
    monkeypatch.setattr(main, "should_curate", lambda grounded, answer: True)
    return spy


def _chat(monkeypatch, *, headers=None):
    with harness.sse_client(monkeypatch) as client:
        token = harness.login(client)
        frames = harness.chat_frames(
            client,
            token,
            "劳动合同试用期最长多久？",
            extra={"no_cache": True},
            headers=headers,
        )
        assert harness.error_of(frames) == []
    return frames


def test_eval_header_skips_curation(monkeypatch, curation_spy):
    _chat(monkeypatch, headers={"X-Eval-No-Curate": "1"})
    curation_spy.assert_not_called()


def test_without_header_still_curates(monkeypatch, curation_spy):
    _chat(monkeypatch)
    curation_spy.assert_called_once()
