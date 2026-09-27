"""Read-only census of the real corpus copy: how many articles are multi-fragment.

Why: `law_versions._same_article_body` requires the *whole* article body to match one
stored block. If an article lives as N>1 blocks, no single block equals the full text,
so a later import of that article can never replace them automatically.
"""

import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "C:/Users/33393/Desktop/ai-legal-helper/backend")
import chromadb  # noqa: E402

coll = chromadb.PersistentClient(path=os.environ["CHROMA_DIR"]).get_collection("legal_provisions_cos")
got = coll.get(include=["metadatas"])
ids = got["ids"]
metas = got.get("metadatas") or []
print("total blocks =", len(ids))

groups = defaultdict(list)
for doc_id, m in zip(ids, metas):
    m = m or {}
    groups[(str(m.get("source") or ""), str(m.get("article") or ""))].append(m)

multi = {k: v for k, v in groups.items() if len(v) > 1}
print("distinct (source, article) groups =", len(groups))
print("groups with >1 block =", len(multi))
print("blocks inside those groups =", sum(len(v) for v in multi.values()))

dated_multi = {k: v for k, v in multi.items() if any(str(m.get("effective_from") or "") for m in v)}
print("of those, groups where any block carries effective_from =", len(dated_multi))

origin_ctr = Counter()
for v in multi.values():
    for m in v:
        origin_ctr[str(m.get("origin") or "")] += 1
print("origin distribution inside multi-block groups:", dict(origin_ctr))

arts = sorted(multi, key=lambda k: -len(multi[k]))[:10]
print("largest 10 groups:")
for k in arts:
    lens = [len(str(m.get("_dummy") or "")) for m in []]
    print(f"  {k[0]!r} {k[1]!r} -> {len(multi[k])} blocks{'' if not lens else ''}")

no_article = sum(1 for k in groups if not k[1])
print("groups with EMPTY article key =", no_article)
print("blocks with empty article =", sum(len(v) for k, v in groups.items() if not k[1]))
