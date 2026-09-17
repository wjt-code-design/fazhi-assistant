"""搜索能复现 002 corpus logical hash 的规范化变体。

锚点：record_count=10545, canonical_bytes=8840943,
logical_corpus_sha256=d76220e7460789382d5bf40ce45a559b1cf017b2b43842d6056a0117d42e9474
"""
import hashlib
import itertools
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "backend" / "chroma_db" / "chroma.sqlite3"
TARGET_HASH = "d76220e7460789382d5bf40ce45a559b1cf017b2b43842d6056a0117d42e9474"
TARGET_BYTES = 8_840_943
TARGET_COUNT = 10_545
COLLECTIONS = ["legal_provisions_cos", "qa_pairs"]

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = con.cursor()
rows = cur.execute(
    """
    SELECT c.name, e.embedding_id, e.seq_id, e.created_at,
           m.key, m.string_value, m.int_value, m.float_value, m.bool_value
    FROM embeddings e
    JOIN segments s ON e.segment_id = s.id
    JOIN collections c ON s.collection = c.id
    LEFT JOIN embedding_metadata m ON m.id = e.id
    WHERE c.name IN (?, ?)
    ORDER BY c.name, e.embedding_id
    """,
    tuple(COLLECTIONS),
).fetchall()
con.close()

# 按 (collection, embedding_id) 分组
groups: dict[tuple[str, str], dict] = {}
for name, eid, seq_id, created_at, key, sv, iv, fv, bv in rows:
    g = groups.setdefault((name, eid), {"seq_id": seq_id, "created_at": created_at, "meta": {}})
    if key is not None:
        vals = [("s", sv), ("i", iv), ("f", fv), ("b", bv)]
        present = [(t, v) for t, v in vals if v is not None]
        g["meta"][key] = present[0] if present else None

print("groups:", len(groups), "expected:", TARGET_COUNT)


def canon(v: object) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def try_variant(record_shape, top_shape, bool_mode, sort_meta) -> None:
    records = []
    for (name, eid) in sorted(groups.keys()):
        g = groups[(name, eid)]
        meta = {}
        for k in (sorted(g["meta"]) if sort_meta else g["meta"]):
            v = g["meta"][k]
            if v is None:
                meta[k] = None
            else:
                t, raw = v
                if t == "b":
                    meta[k] = (True if raw else False) if bool_mode == "bool" else int(raw)
                elif t == "f":
                    meta[k] = float(raw)
                elif t == "i":
                    meta[k] = int(raw)
                else:
                    meta[k] = raw
        if record_shape == "meta_only":
            rec = meta
        elif record_shape == "full":
            rec = {"collection": name, "embedding_id": eid, "metadata": meta}
        elif record_shape == "full_topic":
            rec = {"collection": name, "embedding_id": eid, "metadata": meta, "origin_seq": "omitted"}
        records.append(rec)

    if top_shape == "bare":
        payload = records
    elif top_shape == "with_collections":
        payload = {"collections": COLLECTIONS, "records": records}
    elif top_shape == "records_key":
        payload = {"records": records}

    data = canon(payload).encode("utf-8")
    h = hashlib.sha256(data).hexdigest()
    tag = f"{record_shape}/{top_shape}/{bool_mode}/sortmeta={sort_meta}"
    if h == TARGET_HASH or len(data) == TARGET_BYTES:
        print("HIT", tag, "bytes=", len(data), "hash=", h[:16])
    return h == TARGET_HASH


for record_shape, top_shape, bool_mode, sort_meta in itertools.product(
    ["meta_only", "full", "full_topic"],
    ["bare", "with_collections", "records_key"],
    ["bool", "int"],
    [True, False],
):
    try_variant(record_shape, top_shape, bool_mode, sort_meta)
print("search done")
