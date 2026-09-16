# -*- coding: utf-8 -*-
"""watch-it-fail 复验（针对最终代码）：把分桶函数打桩成"全 0"，三个新测试必须变红。

为什么打桩点选 `numeric_violation_buckets` 而不是 `log_writer_summary`：
新测试可能只绑到"日志里有个 dict"这种偶然事实。打桩分桶本身，才能证明它检验的是**分桶是否算对**。
仅诊断用，不进 CI。
"""

import os
import sys
from pathlib import Path

BACKEND = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend")
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))
os.chdir(BACKEND)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=False)

import agent.writer as writer_module  # noqa: E402
import test_agent_writer as t  # noqa: E402

TARGETS = [
    ("② 漏绑分桶", t.test_numeric_violation_bucket_own_issue),
    ("③ 跨争点分桶", t.test_numeric_violation_bucket_other_issues),
    ("① 编造分桶", t.test_numeric_violation_bucket_nowhere),
]

_ZERO = {
    "issue_id": "stub",
    "unsupported_total": 0,
    "in_own_issue_other_sources": 0,
    "in_other_issues": 0,
    "from_unknown_facts": 0,
    "nowhere": 0,
}


def test_probe_zeroed_buckets_make_new_tests_red(monkeypatch, caplog):
    monkeypatch.setattr(writer_module, "numeric_violation_buckets", lambda *a, **k: dict(_ZERO))
    for label, fn in TARGETS:
        try:
            fn(caplog)
        except AssertionError as exc:
            print(f"[WATCH-IT-FAIL OK] {label}: {str(exc)[:90]}", flush=True)
            continue
        raise AssertionError(f"[WATCH-IT-FAIL FAILED] {label}: 打桩成全 0 后测试仍绿，说明它没检验分桶")
