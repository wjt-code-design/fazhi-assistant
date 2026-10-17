"""受控沉淀采纳后必须清缓存（纠错闭环不静默失效）。"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import knowledge_service as ks  # noqa: E402
import retrieval  # noqa: E402


class _FakeCand:
    question = "q"
    answer = "修正后的答案"
    evidence = ""
    status = ""
    # 真行由 `models.QaCandidate.created_at`（default=utcnow）保证有值 ⇒ 替身也得有，
    # 否则本文件的假绿来自"替身比真对象少一列"（采纳路径要把这一列传给写侧当基准日）。
    created_at = datetime(2026, 9, 1, 3, 0, 0)


class _FakeDb:
    def get(self, cls, cand_id):
        return _FakeCand()

    def commit(self):
        pass

    def refresh(self, r):
        pass


def test_approve_invalidates_cache(monkeypatch):
    monkeypatch.setattr(ks, "add_qa_pair", lambda *a, **k: None)
    called = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: called.append(1))
    ks.decide_candidate(_FakeDb(), 1, "approved")
    assert called == [1]


def test_reject_invalidates_cache(monkeypatch):
    """W06-IMPL 改写（原钉「拒绝不清缓存」）：拒绝走形状 B，必须调 invalidate 停第三条出口（§4 项 1）。

    这是票未点名、但与 §4 项 1 / `test_qa_revocation_lifecycle` 同一契约的特征化腿：旧断言 `called == []`
    钉的正是被本轮修掉的缺陷，故照 revocation 那条一样改写成「拒绝清一次缓存」，不删。
    """
    monkeypatch.setattr(ks, "add_qa_pair", lambda *a, **k: None)
    called = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: called.append(1))
    ks.decide_candidate(_FakeDb(), 1, "rejected")
    assert called == [1]


def test_approve_passes_candidate_date_as_basis(monkeypatch):
    """采纳路径的**接缝**：把候选产生日交给写侧当基准日（不是让写侧自己落今天）。

    本票其余用例把 `add_qa_pair` 打桩吞掉参数 ⇒ 看不见这条线；`test_qa_basis_write_side.py`
    量的是"落库后存的到底是什么"（走真写侧）。两处都要有：这条钉接线，那条钉结果。
    """
    seen = {}
    monkeypatch.setattr(ks, "add_qa_pair", lambda *a, **k: seen.update(args=a, kwargs=k))
    monkeypatch.setattr(retrieval, "invalidate", lambda: None)
    ks.decide_candidate(_FakeDb(), 1, "approved")
    assert seen["kwargs"]["basis"] == "2026-09-01" == _FakeCand.created_at.date().isoformat()
