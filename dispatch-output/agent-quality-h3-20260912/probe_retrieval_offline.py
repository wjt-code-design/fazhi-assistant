# -*- coding: utf-8 -*-
"""C01 检索质量离线复现（零外呼）：rerank 关闭，只看本地候选池召回。

目的：区分「问题出在 rerank 之前（召回池本身缺目标法条）」还是「rerank 之后（排序被弄坏）」。
不发起任何 HTTP：RERANK_ENABLED=false + HF_HUB_OFFLINE=1 + 本地 embedding。
"""

import os
import sys
from pathlib import Path

BACKEND = Path(r"C:\Users\33393\Desktop\ai-legal-helper\backend")
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

os.environ.update(
    {
        "EMBEDDING_PROVIDER": "local",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "RERANK_ENABLED": "false",
        "ANONYMIZED_TELEMETRY": "false",
    }
)

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env", override=False)
os.environ["RERANK_ENABLED"] = "false"  # 必须在 import retrieval 之后仍生效

import retrieval  # noqa: E402
from settings import settings  # noqa: E402

settings.rerank_enabled = False  # 双保险：settings 已在别处被读取

QUERIES = [
    ("issue_1928 事实是否成立", "公司主张的连续两次绩效不合格事实是否成立？"),
    ("issue_33bf 未经培训调岗是否合法", "即使绩效不合格，公司直接解除合同而未进行培训或调岗是否合法？"),
    ("issue_afa0 能否要求赔偿金", "公司未支付任何经济补偿即解除合同，劳动者能否要求赔偿金？"),
]
REQUIRED = {("劳动合同法", "40"), ("劳动合同法", "43"), ("劳动合同法", "47"), ("劳动合同法", "87")}
CUTOFF = "2026-09-12"

out = []
out.append("rerank_enabled=%s  provider=%s" % (settings.rerank_enabled, settings.embedding_provider))
for label, q in QUERIES:
    out.append("")
    out.append("=== %s ===" % label)
    out.append("query: %s" % q)
    try:
        units = __import__("query_understand").decompose(q)
        out.append("units: %s" % units)
    except Exception as exc:
        out.append("units FAILED: %r" % (exc,))
    try:
        docs = retrieval.retrieve(q, k=8, cutoff=CUTOFF)
        got = []
        for d in docs:
            src = (d.metadata or {}).get("source")
            art = (d.metadata or {}).get("article")
            got.append((src, art))
            out.append("   %-24s %-10s %s" % (src, art, (d.page_content or "")[:60].replace("\n", " ")))
        hit = [r for r in REQUIRED if r in got]
        out.append("   -> required hits: %s" % hit)
    except Exception as exc:
        out.append("retrieve FAILED: %r" % (exc,))

text = "\n".join(out)
print(text, flush=True)
Path(r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\agent-quality-h3-20260912\probe-retrieval-offline.txt").write_text(
    text, encoding="utf-8"
)
