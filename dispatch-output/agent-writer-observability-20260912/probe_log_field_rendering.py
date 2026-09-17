# -*- coding: utf-8 -*-
"""独立核验：writer 归因字段是否真能**渲染进日志行**（白名单登记 ≠ 实际渲染）。零外呼。"""

import json
import logging
import os
import sys
from pathlib import Path

BACKEND = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from observability import _ACCOUNT_FIELDS, _JsonFormatter  # noqa: E402

out = ["registered_in_whitelist=%s" % ("agent_writer_summary" in _ACCOUNT_FIELDS)]
rec = logging.LogRecord("legal.agent", logging.WARNING, "x", 1, "writer_render_summary", None, None)
rec.request_id = "probe"
rec.agent_writer_summary = {
    "reason": "NON_CANONICAL_CITATION",
    "has_feedback": True,
    "claims_proposed": 1,
    "claims_accepted": 0,
    "claims_dropped": 0,
    "per_issue": [{"issue_id": "issue-a", "proposed": 1, "accepted": 0, "dropped": 0}],
    "failing_issue_id": "issue-a",
}
line = _JsonFormatter().format(rec)
obj = json.loads(line)
out.append("rendered=" + line)
out.append("field_present_in_json=%s" % ("agent_writer_summary" in obj))
out.append("failing_issue_recoverable=%s" % obj.get("agent_writer_summary", {}).get("failing_issue_id"))

text = "\n".join(out)
print(text, flush=True)
Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\agent-writer-observability-20260912\probe-log-rendering.txt"
).write_text(text, encoding="utf-8")
