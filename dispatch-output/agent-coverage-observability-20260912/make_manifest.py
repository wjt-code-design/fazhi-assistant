# -*- coding: utf-8 -*-
"""本轮候选清单：覆盖率闸门失败「可归因化」的诊断埋点。

诚实说明：与 H1 轮相同的流程缺口 —— 编辑前未保存字节快照，故只记录 post 哈希与快照，
没有「纯本轮差异」的 diff 产物；改动逐条枚举在 report.md。
"""

import hashlib
import json
import os
import shutil

ROOT = r"C:\Users\33393\Desktop\ai-legal-helper"
OUT = os.path.join(ROOT, "dispatch-output", "agent-coverage-observability-20260912")

CHANGED = [
    "backend/agent/service.py",
    "backend/observability.py",
    "backend/tests/test_agent_chat_integration.py",
]
PRIOR = [
    "backend/tools/contracts.py",
    "backend/tools/gateway.py",
    "backend/tools/legal_retrieval.py",
    "backend/retrieval.py",
    "backend/tests/test_retrieval_rerank.py",
    "backend/tests/test_tool_gateway.py",
]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def lines(p):
    return sum(1 for _ in open(p, "rb"))


def rows(rels):
    out = []
    for rel in rels:
        src = os.path.join(ROOT, rel.replace("/", os.sep))
        dst = os.path.join(OUT, rel.replace("/", "__") + ".after")
        shutil.copy2(src, dst)
        out.append({"path": rel, "sha256": sha(src), "lines": lines(src)})
    return out


payload = {
    "round": "agent-coverage-observability-20260912",
    "purpose": "make coverage-gate terminal failure attributable (H3 C01 could not be attributed)",
    "changed_files": rows(CHANGED),
    "prior_round_files_should_be_unchanged": rows(PRIOR),
    "h1_before_snapshot_note": "pre-edit byte snapshots were again not captured (process gap)",
}
with open(os.path.join(OUT, "candidate-manifest.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(json.dumps(payload, ensure_ascii=False, indent=2))
