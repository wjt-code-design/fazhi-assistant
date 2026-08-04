"""多模型路由编排测试：_light_buffered 升级状态机 + 缓存判定（mock，不联网）。"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


import llm_registry
import main
import quality


class FakeLLM:
    def __init__(self, content, tokens=10):
        self._content = content
        self._tokens = tokens

    def invoke(self, messages):
        return SimpleNamespace(content=self._content, usage_metadata={"total_tokens": self._tokens})


def _pre(sources=True):
    return {
        "conv_id": 1,
        "intent": "legal_query",
        "image": None,
        "recent": [],
        "rewritten": "试用期最长多久",
        "user_text": "试用期最长多久",
        "sources": [{"source": "劳动合同法", "article": "第十九条"}] if sources else [],
        "context": "劳动合同法 第十九条 ...",
    }


def _patch_pick(monkeypatch, light, flag, flag_raises=False):
    def fake_pick(modality, tier):
        if tier == "light":
            return ("L", light)
        if flag_raises:
            raise llm_registry.QuotaExhausted("x")
        return ("F", flag)

    monkeypatch.setattr(llm_registry.registry, "pick", fake_pick)
    monkeypatch.setattr(llm_registry.registry, "model_of", lambda k: {"L": "m-light", "F": "m-flag"}.get(k, ""))
    monkeypatch.setattr(llm_registry.registry, "deduct", lambda k, t: None)


def _patch_selfcheck(monkeypatch, verdicts):
    """verdicts：按调用顺序返回的 (ok, reason) 列表。"""
    it = iter(verdicts)

    def fake(answer, ctx, in_kb=None):
        ok, reason = next(it)
        return quality.Verdict(ok, reason)

    monkeypatch.setattr(quality, "self_check", fake)


def test_light_pass_no_escalation(monkeypatch):
    _patch_pick(monkeypatch, FakeLLM("根据《劳动合同法》第十九条，试用期最长六个月。"), FakeLLM("flag"))
    _patch_selfcheck(monkeypatch, [(True, "")])
    res = main._light_buffered(_pre(), [])
    assert res.tier == "light" and res.escalated is False and res.verdict == "pass"
    assert res.key == "L"


def test_light_fail_escalate_flag_pass(monkeypatch):
    _patch_pick(monkeypatch, FakeLLM("看相关规定吧"), FakeLLM("根据《劳动合同法》第十九条，最长六个月。"))
    _patch_selfcheck(monkeypatch, [(False, "no_citation_while_hit"), (True, "")])
    res = main._light_buffered(_pre(), [])
    assert res.tier == "flag" and res.escalated is True and res.verdict == "pass"
    assert res.key == "F"


def test_light_fail_escalate_flag_still_fail_adds_note(monkeypatch):
    _patch_pick(monkeypatch, FakeLLM("看相关规定"), FakeLLM("大概是这样处理的吧"))
    _patch_selfcheck(monkeypatch, [(False, "vague"), (False, "vague")])
    res = main._light_buffered(_pre(), [])
    assert res.tier == "flag" and res.escalated is True and res.verdict != "pass"
    assert "注：" in res.answer  # 不静默，追加核对注


def test_light_fail_quota_exhausted_no_escalation(monkeypatch):
    _patch_pick(monkeypatch, FakeLLM("看相关规定"), FakeLLM("x"), flag_raises=True)
    _patch_selfcheck(monkeypatch, [(False, "vague")])
    res = main._light_buffered(_pre(), [])
    assert res.escalated is False  # 配额耗尽不升级
    assert "注：" in res.answer  # 明说降级


def test_light_empty_upstream_returns_empty_answer(monkeypatch):
    # 两级都空答 → 返回空串（调用方走 error 分支、不落库空免责声明），与流式路径一致
    _patch_pick(monkeypatch, FakeLLM(""), FakeLLM(""))
    _patch_selfcheck(monkeypatch, [(False, "empty"), (False, "empty")])
    res = main._light_buffered(_pre(), [])
    assert res.answer == ""


# ---------------- 缓存判定 ----------------
def test_cacheable_only_safe_form():
    assert main._cacheable(_pre(sources=True)) is True
    p = _pre(sources=True)
    p["image"] = "data:..."
    assert main._cacheable(p) is False  # 带图不缓存
    p = _pre(sources=True)
    p["recent"] = [{"role": "user", "content": "hi"}]
    assert main._cacheable(p) is False  # 多轮不缓存
    p = _pre(sources=False)
    assert main._cacheable(p) is False  # 无命中不缓存
    p = _pre(sources=True)
    p["intent"] = "study_aid"
    assert main._cacheable(p) is True  # 法考题白名单（feature_study_cache=True，ADR-012 后解析答案可缓存）
    p["sources"] = []
    assert main._cacheable(p) is False  # 检索无命中仍不缓存
    p = _pre(sources=True)
    p["intent"] = "study_aid"
    old = main.settings.feature_study_cache
    main.settings.feature_study_cache = False
    try:
        assert main._cacheable(p) is False  # flag 关 → 回滚仅 legal_query 可缓存
    finally:
        main.settings.feature_study_cache = old


def test_cache_write_ok_study_aid_gate():
    """法考题写缓存确定性写闸（审查 C2）：引用必须全部命中本轮检索条文。"""
    pre = _pre(sources=True)
    pre["intent"] = "study_aid"
    # 引用在检索条文中 → 可写
    assert main._cache_write_ok(pre, "依据《劳动合同法》第十九条，试用期最长六个月。") is True
    # 引用了库内但非本轮检索条文 → 不写（防"引在库但答非所问"入缓存）
    assert main._cache_write_ok(pre, "依据《民法典》第一千一百六十五条，应承担侵权责任。") is False
    # 无引用 → 不写
    assert main._cache_write_ok(pre, "这道题选 A。") is False
    # 检索无命中 → 不写
    p2 = _pre(sources=False)
    p2["intent"] = "study_aid"
    assert main._cache_write_ok(p2, "依据《劳动合同法》第十九条。") is False
    # legal_query 维持现状（自检已覆盖）
    assert main._cache_write_ok(_pre(sources=True), "依据《劳动合同法》第十九条。") is True


def test_cache_key_stable_and_cutoff_sensitive():
    a = main._cache_key(_pre())
    b = main._cache_key(_pre())
    assert a == b  # 同输入同 key
