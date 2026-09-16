# -*- coding: utf-8 -*-
"""决定性实验（零外呼）：不同 query 表述对「必需法条召回」的影响。

目的：在动手改代码**之前**用证据决定方案走向 —— 如果换成有锚点/法律概念的 query 能召回
必需法条，那问题在 query 构造；如果换了也召不回，那问题在索引/嵌入，方案要另立。

约束（来自 [fz] 教训）：评测必须**绕缓存**测真实，否则数字失真。
本脚本每条 query 前调用 retrieval.invalidate() 清缓存/重建，并逐条打印。
rerank 关闭（RERANK_ENABLED=false）以保证确定性、零外呼。
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
os.environ["RERANK_ENABLED"] = "false"

import retrieval  # noqa: E402
from settings import settings  # noqa: E402

settings.rerank_enabled = False

# ⚠️ 2026-09-12 修正：元数据里的 article 是**中文条号**（"第四十七条"），
# 不是阿拉伯数字。此前用 ("劳动合同法","40") 的期望集合**永远匹配不上**，
# required_hits 恒为 0/4 —— 那是测量 bug，不是召回结论（[fz] 评测污染类教训）。
# 格式依据：tests/test_retrieval_rerank.py 的 `_in_top(docs, "公司法", "第四十七条")`。
REQUIRED = {
    ("劳动合同法", "第四十条"),
    ("劳动合同法", "第四十三条"),
    ("劳动合同法", "第四十七条"),
    ("劳动合同法", "第八十七条"),
}
CUTOFF = "2026-09-12"

CASES = [
    ("REAL-q1（现状：事实性问题）", "公司主张的连续两次绩效不合格事实是否成立？"),
    ("REAL-q2（现状：程序问题）", "即使绩效不合格，公司直接解除合同而未进行培训或调岗是否合法？"),
    ("REAL-q3（现状：赔偿问题）", "公司未支付任何经济补偿即解除合同，劳动者能否要求赔偿金？"),
    ("A 法律概念关键词", "绩效不合格 不能胜任工作 解除劳动合同"),
    ("B 法名+条号锚点", "劳动合同法第四十条 第四十三条 第四十七条"),
    ("C 法条要件句", "不能胜任工作 经过培训或者调整工作岗位 仍不能胜任工作 提前三十日书面通知 解除劳动合同"),
    ("D 罪名/概念混合", "不能胜任工作解除劳动合同 工会程序 经济补偿标准 二倍赔偿金"),
]

out = []
out.append("rerank_enabled=%s  cache_bypassed=invalidate() per query" % settings.rerank_enabled)
for label, q in CASES:
    retrieval.invalidate()  # [fz] 教训：绕缓存，避免上一条污染下一条
    try:
        docs = retrieval.retrieve(q, k=8, cutoff=CUTOFF)
    except Exception as exc:  # noqa: BLE001
        out.append("")
        out.append("=== %s ===" % label)
        out.append("query: %s" % q)
        out.append("  FAILED: %r" % (exc,))
        continue
    got = [((d.metadata or {}).get("source"), (d.metadata or {}).get("article")) for d in docs]
    hits = [f"{s}{a}" for (s, a) in REQUIRED if (s, a) in got]
    out.append("")
    out.append("=== %s ===" % label)
    out.append("query: %s" % q)
    out.append("  top8: %s" % [f"{s}{a}" for s, a in got])
    out.append("  required_hits: %d/%d %s" % (len(hits), len(REQUIRED), hits))

text = "\n".join(out)
print(text, flush=True)
Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\agent-coverage-observability-20260912\probe-query-formulations.txt"
).write_text(text, encoding="utf-8")
