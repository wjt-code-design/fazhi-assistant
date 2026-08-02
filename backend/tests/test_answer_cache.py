"""回答缓存测试：命中 / miss / TTL / key 含 cutoff / 失效钩子。"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import answer_cache as ac  # noqa: E402


def setup_function():
    ac.clear()


def test_put_then_get_hit():
    k = ac.make_key("试用期最长多久", "legal_query", "2026-08-02", ["劳动合同法|第十九条"])
    ac.put(k, "试用期最长六个月。", [{"source": "劳动合同法", "article": "第十九条"}])
    r = ac.get(k)
    assert r and r["answer"].startswith("试用期") and len(r["sources"]) == 1


def test_get_miss():
    assert ac.get("nonexistent") is None


def test_ttl_expires(monkeypatch):
    monkeypatch.setattr(ac, "TTL", timedelta(seconds=-1))
    k = ac.make_key("x", "legal_query", "2026-08-02", [])
    ac.put(k, "答", [])
    assert ac.get(k) is None  # 已过期


def test_key_differs_by_cutoff():
    a = ac.make_key("q", "legal_query", "2026-08-01", ["x|第一条"])
    b = ac.make_key("q", "legal_query", "2026-08-02", ["x|第一条"])
    assert a != b  # 跨天 key 不同 → 不命中失效条文


def test_key_context_ids_order_independent():
    a = ac.make_key("q", "legal_query", "2026-08-02", ["b|2", "a|1"])
    b = ac.make_key("q", "legal_query", "2026-08-02", ["a|1", "b|2"])
    assert a == b


def test_clear_empties():
    k = ac.make_key("q", "legal_query", "2026-08-02", [])
    ac.put(k, "答", [])
    assert ac.get(k) is not None
    ac.clear()
    assert ac.get(k) is None


def test_invalidate_clears_answer_cache():
    import retrieval as R

    k = ac.make_key("q", "legal_query", "2026-08-02", [])
    ac.put(k, "答", [])
    R.invalidate()
    assert ac.get(k) is None
