"""I-2(a) 地基：真实 `qa_pairs` 语料的**只读**盘点 + 全量元数据备份（回滚用）。

为什么先做这个：I-2(a) 要往**真实语料**写一个新字段（票面明令这类写入需 Owner 点头）。
写之前必须有三样东西：① 到底有多少条、现有 metadata 有哪些键；② **逐条备份**（回滚路径）；
③ 基准日从哪来（必须是可审计来源，不是推断）。

本脚本**只读**：`collection.get`，不 upsert、不 update、不 delete。绝不写库。
（写动作留给 `apply_i2_basis_metadata.py`，且必须先过本脚本产出的备份与盘点。）

用法：backend/venv/Scripts/python.exe dispatch-output/hij-i-20260920/probe_i2_corpus_inventory.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(OUT))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

import _qa_corpus

COLLECTION = "qa_pairs"


def main() -> int:
    # ⚠️ 必须走守卫助手：`retrieval.vectorstore._collection` 是**法条主库**（10266 条），
    # 不是 QA 语料 —— 2026-09-20 实测取错过一次，见 `_qa_corpus.py` 的 docstring。
    col = _qa_corpus.get_qa_collection()
    data = col.get(include=["metadatas", "documents"])
    ids = list(data.get("ids") or [])
    metas = list(data.get("metadatas") or [])
    docs = list(data.get("documents") or [])

    keys: dict[str, int] = {}
    for m in metas:
        for k in m or {}:
            keys[k] = keys.get(k, 0) + 1
    with_fp = sum(1 for m in metas if (m or {}).get("options_fingerprint"))
    has_time = sum(
        1
        for m in metas
        if any(
            k in (m or {}) for k in ("generated_at", "created_at", "law_as_of_basis")
        )
    )

    summary = {
        "collection": getattr(col, "name", COLLECTION),
        "n_records": len(ids),
        "metadata_keys": keys,
        "with_options_fingerprint": with_fp,
        "with_any_time_field": has_time,
        "sample_metadata": metas[0] if metas else None,
        "distinct_source_len": len({(m or {}).get("source", "") for m in metas}),
    }
    # 逐条备份（回滚用）：id + 原 metadata（不含 document 正文，正文不进备份以免体积翻倍）
    backup = [{"id": i, "metadata": m} for i, m in zip(ids, metas, strict=False)]
    (OUT / "corpus-backup-qa_pairs.json").write_text(
        json.dumps(
            {"summary": summary, "records": backup}, ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
        newline="",
    )
    (OUT / "01-corpus-inventory.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"备份条数={len(backup)}  备份文件=corpus-backup-qa_pairs.json")
    print(f"文档数(仅统计,不入备份)={len(docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
