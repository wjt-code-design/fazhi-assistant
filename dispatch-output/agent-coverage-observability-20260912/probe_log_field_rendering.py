# -*- coding: utf-8 -*-
"""独立核验：覆盖率诊断字段是否真能**渲染进日志行**（白名单登记 ≠ 实际渲染）。

动机：JSON formatter 只输出 `_ACCOUNT_FIELDS` 白名单内的 extra 字段，未登记会被**静默丢弃**
（仓库 V2-T8 的既有教训，见 observability.py 顶部注释）。仓库守卫只断言"已登记"，
本脚本补齐"确实渲染"这一环，零外呼。
"""

import json
import logging
import os
import sys
from pathlib import Path

BACKEND = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from observability import _ACCOUNT_FIELDS, _JsonFormatter  # noqa: E402

out = []
out.append("registered_in_whitelist=%s" % ("agent_coverage_issues" in _ACCOUNT_FIELDS))
rec = logging.LogRecord("legal.agent", logging.WARNING, "x", 1, "coverage_gate_terminal_failure", None, None)
rec.verdict = "FAIL_SAFE"
rec.agent_issue_count = 2
rec.agent_coverage_gap_count = 1
rec.agent_coverage_issues = [
    {"issue_id": "issue_a", "claims": 1, "claims_bound_effective_statute": 1, "deficient": False},
    {"issue_id": "issue_b", "claims": 0, "claims_bound_effective_statute": 0, "deficient": True},
]
rec.request_id = "probe"
line = _JsonFormatter().format(rec)
out.append("rendered=" + line)
obj = json.loads(line)
out.append("field_present_in_json=%s" % ("agent_coverage_issues" in obj))
out.append("deficient_row=%s" % [r for r in obj["agent_coverage_issues"] if r["deficient"]])

text = "\n".join(out)
print(text, flush=True)
Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\agent-coverage-observability-20260912\probe-log-rendering.txt"
).write_text(text, encoding="utf-8")
