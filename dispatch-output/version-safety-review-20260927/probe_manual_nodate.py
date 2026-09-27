"""A/B probe: does an undated manual re-save still replace the previous chunk?

Run the SAME script against two trees (HEAD copy vs working-tree copy):
  python -B probe_manual_nodate.py <tree>/backend <fresh chroma dir>
Reports how many chunks end up in the collection after two saves of the same
(title, article) with no effective_from.
"""

import os
import sys

tree = os.path.abspath(sys.argv[1])
chroma_dir = os.path.abspath(sys.argv[2])
os.environ["CHROMA_DIR"] = chroma_dir
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(chroma_dir + "_app.db").replace("\\", "/")
os.environ.setdefault("JWT_SECRET", "vsr-ci-only")
os.environ.setdefault("LLM_API_KEY", "not-for-real-calls")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:9/v1")
os.environ["EMBEDDING_PROVIDER"] = "local"
sys.path.insert(0, tree)

import knowledge_service as ks  # noqa: E402
import law_versions  # noqa: E402

print("tree:", tree)
print("law_versions file:", law_versions.__file__)
print("has _same_article_body:", hasattr(law_versions, "_same_article_body"))

title, article = "受控探针法", "第一条"
first = "第一条　当事人应当按照约定履行自己的义务。"
second = "第一条　当事人应当按照约定履行自己的义务。"  # identical re-save (typo-fix flow)

n1 = ks.add_text(first, source=title, article=article, origin="manual", extra_meta={})
n2 = ks.add_text(second, source=title, article=article, origin="manual", extra_meta={})
got = ks._collection().get(where={"$and": [{"source": title}, {"article": article}]}, include=["metadatas"])
ids = got["ids"]
metas = got.get("metadatas") or []
print(f"add#1 returned {n1}, add#2 returned {n2}")
print(f"blocks for ({title},{article}) after two undated saves = {len(ids)}")
for vid in {str((m or {}).get('version_id')) for m in metas}:
    print("  stored version_id:", vid)
same_ids = len({i for i in ids})
print("DISTINCT_IDS", same_ids)
print("VERDICT", "REPLACED(no duplicate)" if len(ids) == n1 else f"DUPLICATED (+{len(ids) - n1} extra blocks)")

# third save WITH a date, same derived identity -> does it replace?
n3 = ks.add_text(
    second, source=title, article=article, origin="manual", extra_meta={"effective_from": "2024-01-01"}
)
got3 = ks._collection().get(where={"$and": [{"source": title}, {"article": article}]}, include=["metadatas"])
print(f"after a third save carrying effective_from=2024-01-01: blocks={len(got3['ids'])} (add returned {n3})")
