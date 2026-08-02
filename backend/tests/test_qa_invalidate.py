"""受控沉淀采纳后必须清缓存（纠错闭环不静默失效）。"""
import os
import sys

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


def test_reject_does_not_invalidate(monkeypatch):
    monkeypatch.setattr(ks, "add_qa_pair", lambda *a, **k: None)
    called = []
    monkeypatch.setattr(retrieval, "invalidate", lambda: called.append(1))
    ks.decide_candidate(_FakeDb(), 1, "rejected")
    assert called == []
