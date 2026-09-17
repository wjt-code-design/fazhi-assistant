# -*- coding: utf-8 -*-
"""P1 决策实验（零外呼）：概念锚点 + 锚点保底的**召回上限**，以及「措辞鸿沟」的量化。

设计要点（防自欺）：
1. **不循环**：锚点只来自**用户 query 自身的词**，绝不从目标法条正文反推（否则 4/4 无意义）。
2. **绕缓存**：锚点检索前 invalidate()，避免上一条污染（[fz] 教训）。
3. **两问分开答**：
   - Q-A 措辞桥是否存在：query 的词是否出现在目标法条正文里（子串命中）→ 决定"自动派生能否缝合措辞鸿沟"。
   - Q-B 锚点保底上限：对 query 的词做 vector_top/bm25_top top-3 取并集（模拟锚点保底必进结果），
     看必需法条能否被覆盖。这是方案甲的**理论上限**，不是实现效果。
4. rerank 关闭，保证确定性、零外呼。
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
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env", override=False)
os.environ["RERANK_ENABLED"] = "false"

import jieba  # noqa: E402
import retrieval  # noqa: E402
import retrieval_core as rc  # noqa: E402
from settings import settings  # noqa: E402

settings.rerank_enabled = False
CUTOFF = "2026-09-12"
VALID = lambda m: rc.is_valid_by_time(m, CUTOFF)  # noqa: E731

REQUIRED = [("劳动合同法", "第四十条"), ("劳动合同法", "第四十三条"), ("劳动合同法", "第四十七条"), ("劳动合同法", "第八十七条")]
QUERIES = [
    ("q1 事实性问题", "公司主张的连续两次绩效不合格事实是否成立？"),
    ("q2 程序问题", "即使绩效不合格，公司直接解除合同而未进行培训或调岗是否合法？"),
    ("q3 赔偿问题", "公司未支付任何经济补偿即解除合同，劳动者能否要求赔偿金？"),
]
STOP = set("公司 主张 事实 是否 成立 合法 劳动者 能否 要求 直接 解除 合同 即使 任 的 了 与 和 或 在 我 你 他 这 那 不 有 无 为 是 就 都 也 还 要 会 可以 我们".split())

# Q-C 用：法条派生词表里"该 query 能企及"的法定术语（保留复合词）。
# q1 标注：需把"绩效不合格"同义桥到"不能胜任工作"—— 自动派生给不出，故单列。
STATUTORY_ANCHORS = {
    "q1 事实性问题": ["不能胜任工作"],  # 仅经同义桥可得
    "q2 程序问题": ["培训", "调整工作岗位"],
    "q3 赔偿问题": ["经济补偿", "赔偿金", "违法解除"],
}

out = []

# ---- 取目标法条正文（用于 Q-A 措辞桥检查）----
statute_text = {}
for src, art in REQUIRED:
    try:
        docs = retrieval.exact_article_lookup(src, art, CUTOFF)
        statute_text[(src, art)] = docs[0].page_content if docs else ""
    except Exception as exc:  # noqa: BLE001
        statute_text[(src, art)] = ""
        out.append("exact_article_lookup FAILED %s %s: %r" % (src, art, exc))
out.append("目标法条正文长度: %s" % {f"{s}{a}": len(t) for (s, a), t in statute_text.items()})

for label, q in QUERIES:
    out.append("")
    out.append("=== %s ===" % label)
    out.append("query: %s" % q)
    anchors = [w for w in jieba.lcut(q) if len(w) >= 2 and w not in STOP and not w.isdigit()]
    anchors = anchors[:8]
    out.append("anchors(来自 query 自身, cap8): %s" % anchors)

    # Q-A：措辞桥 —— query 的词是否字面出现在目标法条正文
    bridge = {}
    for (src, art), text in statute_text.items():
        hit = [w for w in anchors if w and w in text]
        bridge[f"{src}{art}"] = hit
    out.append("Q-A 字面桥(anchor 出现在该法条正文): %s" % bridge)

    # Q-B：锚点保底上限 —— 每个 anchor 取 vector/bm25 top-3 并集
    covered = set()
    for w in anchors:
        retrieval.invalidate()
        try:
            v = retrieval.vector_top(w, 3, None, valid=VALID)
            b = retrieval.bm25_top(w, 3, None, valid=VALID)
        except Exception as exc:  # noqa: BLE001
            out.append("   anchor %r FAILED: %r" % (w, exc))
            continue
        for d, _ in list(v) + list(b):
            covered.add(((d.metadata or {}).get("source"), (d.metadata or {}).get("article")))
    got = [f"{s}{a}" for (s, a) in REQUIRED if (s, a) in covered]
    out.append("Q-B 锚点保底上限 required 命中: %d/%d %s" % (len(got), len(REQUIRED), got))
    out.append("    (并集大小 %d 条)" % len(covered))

    # Q-C：**法定术语锚点**上限 —— 公平版。锚点是法条派生词表里"该 query 能企及"的术语，
    # 保留复合词（jieba 会把"经济补偿"切成"经济"+"补偿"，Q-B 因此低估）。
    # 注意："绩效不合格 → 不能胜任工作" 属**同义桥**，自动派生**给不出来**，此处单独标注。
    stat = STATUTORY_ANCHORS[label]
    covered2 = set()
    for w in stat:
        retrieval.invalidate()
        try:
            v = retrieval.vector_top(w, 3, None, valid=VALID)
            b = retrieval.bm25_top(w, 3, None, valid=VALID)
        except Exception as exc:  # noqa: BLE001
            out.append("   statutory anchor %r FAILED: %r" % (w, exc))
            continue
        for d, _ in list(v) + list(b):
            covered2.add(((d.metadata or {}).get("source"), (d.metadata or {}).get("article")))
    got2 = [f"{s}{a}" for (s, a) in REQUIRED if (s, a) in covered2]
    out.append("Q-C 法定术语锚点上限 required 命中: %d/%d %s" % (len(got2), len(REQUIRED), got2))
    out.append("    anchors=%s (并集 %d 条)" % (stat, len(covered2)))

text = "\n".join(out)
print(text, flush=True)
Path(
    r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\agent-coverage-observability-20260912\probe-p1-anchor-ceiling.txt"
).write_text(text, encoding="utf-8")
