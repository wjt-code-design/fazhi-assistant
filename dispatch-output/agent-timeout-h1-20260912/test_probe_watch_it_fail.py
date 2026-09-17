"""watch-it-fail 探针（诊断用，不属于仓库测试集，CI 不会收集）。

把生产代码在本进程内临时回退到「修复前」行为，确认新增反例确实为**预期原因**变红：
- 去掉预算闸门（_rerank_budget_allows 恒 True）→ 到期后仍会开远程调用，反例必须红。
- 去掉超时分类（_RERANK_TIMEOUT_ERRORS 置空）→ 超时被当成普通失败换模型+标记耗尽，反例必须红。

方法：直接复用 tests/test_retrieval_rerank.py 里的反例函数体，只替换被测行为。
"""

import os
import sys

BACKEND = r"C:\Users\33393\Desktop\ai-legal-helper\backend"
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "tests"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(BACKEND, ".env"))

import retrieval  # noqa: E402
import test_retrieval_rerank as t  # noqa: E402


def _run_expecting_red(label, fn, monkeypatch):
    try:
        fn(monkeypatch)
    except AssertionError as exc:
        print(f"[WATCH-IT-FAIL OK] {label}: {exc}", flush=True)
        return
    raise AssertionError(f"[WATCH-IT-FAIL FAILED] {label}: 反例没有变红，说明它测不到该缺陷")


def test_probe_budget_gate(monkeypatch):
    """修复前：无预算闸门 → 反例 test_rerank_skips_remote_call_when_budget_is_insufficient 必须红。"""
    monkeypatch.setattr(retrieval, "_rerank_budget_allows", lambda _deadline: True)
    _run_expecting_red(
        "预算闸门", t.test_rerank_skips_remote_call_when_budget_is_insufficient, monkeypatch
    )


def test_probe_timeout_classification(monkeypatch):
    """修复前：超时=普通失败 → 反例 test_rerank_timeout_degrades_... 必须红。"""
    monkeypatch.setattr(retrieval, "_RERANK_TIMEOUT_ERRORS", ())
    _run_expecting_red(
        "超时分类", t.test_rerank_timeout_degrades_without_switching_model_or_marking_depleted, monkeypatch
    )
