"""One-off copy-only import/idempotence probe. Never accepts a production path."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

TASK_ROOT = Path("C:/Users/33393/AppData/Local/Temp/legal-closeout-20260928").resolve()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--chroma", type=Path, required=True)
    parser.add_argument("--import-twice", action="store_true")
    args = parser.parse_args()
    chroma = args.chroma.resolve()
    if chroma not in [TASK_ROOT / "chroma-import", TASK_ROOT / "chroma-restored"]:
        raise ValueError("Only the two task-owned copy paths are allowed")
    if not (chroma / "chroma.sqlite3").is_file():
        raise ValueError("Copy missing; refusing to initialize an empty database")
    if (args.backend / ".env").exists():
        raise ValueError("Use the clean candidate tree without a real .env")
    os.environ.update(
        DATABASE_URL=f"sqlite:///{TASK_ROOT.as_posix()}/corpus-app.db",
        QUOTA_DB=str(TASK_ROOT / "corpus-quota.sqlite"),
        CHROMA_DIR=str(chroma),
        LLM_API_KEY="test-key-not-for-real-calls",
        LLM_BASE_URL="http://127.0.0.1:1/v1",
        EMBEDDING_PROVIDER="local",
        RERANK_ENABLED="false",
        EMBEDDING_QUOTA_TOTAL="0",
        RERANK_QUOTA_TOTAL="0",
        HF_HUB_OFFLINE="1",
        LANGCHAIN_TRACING_V2="false",
        LANGSMITH_TRACING="false",
    )
    sys.path.insert(0, str(args.backend.resolve()))
    entries = json.loads(args.input.read_text(encoding="utf-8"))["entries"]
    for entry in entries:
        assert hashlib.sha256(entry["content"].encode()).hexdigest() == entry["source_document_sha256"]
    targets = {(entry["title"], entry["article_number"]) for entry in entries}

    from rag_chain import vectorstore
    from scripts import import_laws

    def snapshot():
        data = vectorstore._collection.get(include=["documents", "metadatas"])
        all_rows = sorted(zip(data["ids"], data["documents"], data["metadatas"], strict=True))
        unrelated = [row for row in all_rows if (row[2].get("source"), row[2].get("article")) not in targets]
        selected = [(doc, meta) for _, doc, meta in all_rows if (meta.get("source"), meta.get("article")) in targets]
        selected.sort(key=lambda row: json.dumps(row, sort_keys=True))
        return {
            "count": len(all_rows),
            "all_records_sha256": digest(all_rows),
            "unrelated_records_sha256": digest(unrelated),
            "target_semantics_sha256": digest(selected),
            "targets": [
                {"source": source, "article": article,
                 "records": sum(meta.get("source") == source and meta.get("article") == article for _, meta in selected),
                 "import_records": sum(meta.get("source") == source and meta.get("article") == article and meta.get("origin") == "import" for _, meta in selected)}
                for source, article in sorted(targets)
            ],
        }

    before = snapshot()
    print("SNAPSHOT_BEFORE=" + json.dumps(before, ensure_ascii=False, sort_keys=True))
    if not args.import_twice:
        return
    first = None
    for flags in (["--validate-only"], ["--dry-run"], [], []):
        sys.argv = ["import_laws.py", "--input", str(args.input.resolve()), *flags]
        import_laws.main()
        current = snapshot()
        if flags:
            assert current == before, "Validation/preview changed records"
        else:
            assert current["unrelated_records_sha256"] == before["unrelated_records_sha256"]
            assert all(target["import_records"] == 1 for target in current["targets"]), current
            if first is not None:
                assert current["count"] == first["count"]
                assert current["target_semantics_sha256"] == first["target_semantics_sha256"]
            else:
                first = current
            print("SNAPSHOT_AFTER=" + json.dumps(current, ensure_ascii=False, sort_keys=True))
    print("PASS: isolated import, repeat semantics, and unrelated records")


if __name__ == "__main__":
    main()
