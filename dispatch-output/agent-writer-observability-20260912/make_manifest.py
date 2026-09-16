# -*- coding: utf-8 -*-
"""本轮候选清单：writer 侧可归因诊断。

这次**编辑前已存 `.before` 字节快照**（修正前两轮的流程缺口），
因此可给出真实的「本轮差异」：`.before` ↔ `.after` 的行数与 SHA-256。
"""

import hashlib
import json
import os
import shutil

ROOT = r"C:\Users\33393\Desktop\ai-legal-helper"
OUT = os.path.join(ROOT, "dispatch-output", "agent-writer-observability-20260912")

CHANGED = [
    "backend/agent/writer.py",
    "backend/observability.py",
    "backend/tests/test_agent_writer.py",
]
UNTOUCHED = [
    "backend/agent/service.py",
    "backend/tests/test_agent_chat_integration.py",
]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def lines(p):
    return sum(1 for _ in open(p, "rb"))


rows = []
for rel in CHANGED:
    src = os.path.join(ROOT, rel.replace("/", os.sep))
    before = os.path.join(OUT, rel.replace("/", "__") + ".before")
    after = os.path.join(OUT, rel.replace("/", "__") + ".after")
    shutil.copy2(src, after)
    rows.append(
        {
            "path": rel,
            "before_lines": lines(before),
            "after_lines": lines(src),
            "before_sha256": sha(before),
            "after_sha256": sha(src),
            "snapshot_before": os.path.basename(before),
            "snapshot_after": os.path.basename(after),
        }
    )

untouched = []
for rel in UNTOUCHED:
    before = os.path.join(OUT, rel.replace("/", "__") + ".before")
    src = os.path.join(ROOT, rel.replace("/", os.sep))
    untouched.append({"path": rel, "sha_unchanged_by_this_round": sha(src) == sha(before)})

payload = {
    "round": "agent-writer-observability-20260912",
    "purpose": "make writer outcomes attributable (zero-claim vs dropped-claim vs _fail reason/issue)",
    "changed_files": rows,
    "untouched_snapshot_files": untouched,
}
with open(os.path.join(OUT, "candidate-manifest.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(json.dumps(payload, ensure_ascii=False, indent=2))
