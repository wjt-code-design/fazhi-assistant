# -*- coding: utf-8 -*-
"""生成 H1 候选清单 + 快照。

诚实说明：4 个生产文件在编辑前**未**保存字节级快照（流程缺口），因此本脚本只记录
「H1 之后」的 SHA-256/行数作为新基线，并提供 .h1-after 快照。改动内容以 Edit 级别
逐条枚举在 h0-h1-findings.md 与汇报中。
"""

import hashlib
import json
import os
import shutil

ROOT = r"C:\Users\33393\Desktop\ai-legal-helper"
OUT = os.path.join(ROOT, "dispatch-output", "agent-timeout-h1-20260912")

FILES = [
    "backend/tools/contracts.py",
    "backend/tools/gateway.py",
    "backend/tools/legal_retrieval.py",
    "backend/retrieval.py",
    "backend/tests/test_retrieval_rerank.py",
    "backend/tests/test_tool_gateway.py",
]

# 第一轮候选（应当保持不动；H0 已核验全部匹配）
FIRST_ROUND = [
    "backend/agent/service.py",
    "backend/agent/runtime.py",
    "backend/agent/controller.py",
    "backend/agent/planner.py",
    "backend/tests/test_agent_chat_integration.py",
    "backend/tests/test_agent_runtime.py",
    "backend/tests/test_agent_gate.py",
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def lines(p):
    with open(p, "rb") as f:
        return sum(1 for _ in f)


manifest = []
for rel in FILES:
    src = os.path.join(ROOT, rel.replace("/", os.sep))
    dst = os.path.join(OUT, rel.replace("/", "__") + ".h1-after")
    shutil.copy2(src, dst)
    manifest.append(
        {
            "path": rel,
            "h1_after_sha256": sha256(src),
            "h1_after_lines": lines(src),
            "snapshot": os.path.basename(dst),
            "h1_before_snapshot": None,
            "note": "pre-H1 snapshot not captured before editing (process gap)",
        }
    )

first_round = [
    {"path": rel, "current_sha256": sha256(os.path.join(ROOT, rel.replace("/", os.sep)))}
    for rel in FIRST_ROUND
]

payload = {
    "round": "agent-timeout-h1-20260912",
    "disjoint_from_first_round": True,
    "h1_files": manifest,
    "first_round_files_unchanged_by_h1": first_round,
}
with open(os.path.join(OUT, "candidate-manifest-h1.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(json.dumps(payload, ensure_ascii=False, indent=2))
