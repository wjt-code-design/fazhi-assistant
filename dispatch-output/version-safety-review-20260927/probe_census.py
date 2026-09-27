"""Census of the metadata shapes the replacement criteria can act on (private copy)."""

import os
import sys
from collections import Counter

sys.path.insert(0, "C:/Users/33393/Desktop/ai-legal-helper/backend")
import chromadb  # noqa: E402

coll = chromadb.PersistentClient(path=os.environ["CHROMA_DIR"]).get_collection("legal_provisions_cos")
got = coll.get(include=["metadatas"])
metas = [m or {} for m in (got.get("metadatas") or [])]
n = len(metas)
print("blocks =", n)


def s(m, k):
    return str(m.get(k) or "").strip()


ctr = Counter()
for m in metas:
    has_vid = bool(s(m, "version_id"))
    has_ef = bool(s(m, "effective_from"))
    has_et = bool(s(m, "effective_to"))
    ctr[(f"version_id={'y' if has_vid else 'n'}", f"ef={'y' if has_ef else 'n'}", f"et={'y' if has_et else 'n'}")] += 1
for k, v in sorted(ctr.items()):
    print("shape", k, "->", v)

print("origin:", dict(Counter(s(m, "origin") for m in metas)))
print("status:", dict(Counter(s(m, "status") for m in metas)))
risky = [m for m in metas if s(m, "ef") and not s(m, "version_id")]
print("blocks with a date but NO version_id (same_version arm deletes these without any body check) =", len(risky))
undated = [m for m in metas if not s(m, "ef") and not s(m, "et")]
print("fully undated blocks (legacy_undated pool) =", len(undated))
print("undated & origin in {upload,manual} =", sum(1 for m in undated if s(m, "origin") in ("upload", "manual")))
