"""Read-only forensic dump for the version-safety review.

Points at a PRIVATE copy of the real chroma dir. Prints, for every candidate
entry, the stored blocks it would delete and the exact residual difference.
"""

import io
import json
import os
import sys

sys.path.insert(0, "C:/Users/33393/Desktop/ai-legal-helper/backend")

OUT = io.StringIO()


def p(*a):
    print(*a, file=OUT)


import chromadb  # noqa: E402
from law_versions import _norm_text, _same_article_body, replaceable_version_ids, version_metadata  # noqa: E402

CHROMA = os.environ["CHROMA_DIR"]
coll = chromadb.PersistentClient(path=CHROMA).get_collection("legal_provisions_cos")
p("collection count =", coll.count())

data = json.load(open(sys.argv[1], encoding="utf-8"))
for e in data["entries"]:
    title, article = e["title"].strip(), e["article_number"].strip()
    extra = version_metadata(e, title=title, article=article, content=e["content"])
    ex = coll.get(
        where={"$and": [{"source": title}, {"article": article}]},
        include=["metadatas", "documents"],
    )
    plan = replaceable_version_ids(
        ex["ids"],
        ex.get("metadatas") or [],
        version_id=extra["version_id"],
        effective_from=extra["effective_from"],
        effective_to=extra["effective_to"],
        documents=ex.get("documents") or [],
        new_content=e["content"],
    )
    p("\n" + "=" * 70)
    p(f"ENTRY {title} {article}")
    p(f"  new: from={extra['effective_from']!r} to={extra['effective_to']!r} status={extra['status']!r}")
    p(f"  stored={len(ex['ids'])} same_version={len(plan.same_version)} legacy={len(plan.legacy_undated)} "
      f"coexist={len(plan.coexist)} compatible={len(plan.compatible_versions)} conflicts={len(plan.conflicts)}")
    for i, (doc_id, meta) in enumerate(zip(ex["ids"], ex.get("metadatas") or [])):
        meta = meta or {}
        text = (ex.get("documents") or [""] * len(ex["ids"]))[i]
        bucket = "REPLACE" if doc_id in plan.replaceable else ("CONFLICT" if doc_id in plan.conflicts else "KEEP")
        p(f"  --- [{bucket}] id={doc_id}")
        p(f"      meta keys: origin={meta.get('origin')!r} version_id={str(meta.get('version_id'))[:12]!r} "
          f"ef={meta.get('effective_from')!r} et={meta.get('effective_to')!r} status={meta.get('status')!r} "
          f"chapter={meta.get('chapter')!r} article={meta.get('article')!r}")
        p(f"      OLD ({len(text)} chars): {text!r}")
        p(f"      NEW ({len(e['content'])} chars): {e['content']!r}")
        # residual: what the strict body check tolerated
        art = _norm_text(str(meta.get("article") or ""))
        lines = text.strip().splitlines()
        chap = _norm_text(str(meta.get("chapter") or ""))
        popped = ""
        if chap and lines and _norm_text(lines[0]) == chap:
            popped = lines.pop(0)
        old_n = _norm_text("\n".join(lines))
        new_n = _norm_text(e["content"])
        if new_n.startswith(art):
            new_n = new_n[len(art):]
        p(f"      chapter-line popped: {popped!r}")
        p(f"      old_minus_article == new? {old_n[len(art):] == new_n}")
        p(f"      _same_article_body={_same_article_body(text, e['content'], meta)}")
        p(f"      OLD len(norm after prefix)={len(old_n[len(art):])} NEW len(norm)={len(new_n)}")
        if old_n[len(art):] != new_n:
            p(f"      OLD tail: {old_n[len(art):][:200]!r}")
            p(f"      NEW tail: {new_n[:200]!r}")

open(sys.argv[2], "w", encoding="utf-8").write(OUT.getvalue())
print("WROTE", sys.argv[2])
