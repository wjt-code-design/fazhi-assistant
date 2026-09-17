# -*- coding: utf-8 -*-
"""watch-it-fail 复验（针对**最终代码**）：把诊断发射打桩成 no-op，新测试必须变红。

为什么还要再验一次：新测试可能只绑到了"某处有日志"这种偶然事实。
这里显式去掉发射（`log_writer_summary` → no-op），若测试仍绿，说明它测不到目标行为。
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
    ("(a) 模型没产 claim", t.test_writer_summary_distinguishes_zero_claims_from_dropped),
    ("(b) 产出后被丢弃", t.test_writer_summary_shows_dropped_claim_for_missing_evidence),
    ("失败原因+争点", t.test_writer_summary_reports_failing_reason_and_issue),
]


def test_probe_emission_removed_makes_new_tests_red(monkeypatch, caplog):
    monkeypatch.setattr(writer_module, "log_writer_summary", lambda *a, **k: None)
    for label, fn in TARGETS:
        try:
            fn(caplog)
        except (AssertionError, IndexError) as exc:
            # AssertionError = 显式断言失败；IndexError = 取不到日志记录（发射确已消失）
            print(f"[WATCH-IT-FAIL OK] {label}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            continue
        raise AssertionError(f"[WATCH-IT-FAIL FAILED] {label}: 去掉发射后测试仍绿，说明它绑错了对象")
