"""I-1 台架 A：E2 语料的**零成本库存清点**（不发任何 embedding、不碰 live 树）。

要回答的问题（票 I 的 I-1 的前半）：`qa_pairs` 这份持久语料到底有多大、
它的三道护栏**按构造**今天各拦住多少条 —— 这给出 E2 直返的**上限**：
一条 evidence 已失效的记录，无论问法多准都不会直返。

口径写死在这里，别在回报里改口：
- 读的是 `%TEMP%/i1-e2-hitrate/tree/chroma_db`（live `backend/chroma_db` 的整目录副本），
  所以"打开即回写"回的是副本，不是生产库。
- `exact_article_lookup` 的 cutoff 用 `date.today()` ⇒ 与生产同一时刻同一语义。
- 本脚本**不**给命中率。命中率要 B 腿（要嵌请求），这里只给分母与结构。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import date

HERE = pathlib.Path(__file__).resolve().parent
LIVE_TREE = (
    HERE.parent.parent
)  # dispatch-output/<本目录> -> 仓库根（**只用它找副本树，不 import 真码**）
COPY_BACKEND = pathlib.Path(os.environ["I1_COPY_BACKEND"])
OUT = HERE / "probe-A-corpus-inventory.json"

sys.path.insert(0, str(COPY_BACKEND))
os.chdir(COPY_BACKEND)  # 让 BASE_DIR / app.db / chroma_db 全部落在副本树内


def main() -> int:
    import knowledge_service as ks
    import rag_chain
    import retrieval

    resolved = {
        "copy_backend": str(COPY_BACKEND),
        "CHROMA_DIR_resolved": rag_chain.CHROMA_DIR,
        "QA_COLLECTION_NAME": rag_chain.QA_COLLECTION_NAME,
        "MAIN_COLLECTION_NAME": rag_chain.COLLECTION_NAME,
        "embedding_provider": __import__("settings").settings.embedding_provider,
        "today": date.today().isoformat(),  # noqa: DTZ011  与生产同源：exact_article_lookup 内部就取当日
    }
    # 硬门：确认我们读的不是 live 目录。落在生产路径上就立刻退出，不产生任何读数。
    live = (LIVE_TREE / "backend" / "chroma_db").resolve()
    if pathlib.Path(rag_chain.CHROMA_DIR).resolve() == live:
        print("ABORT：CHROMA_DIR 解析到了 live 目录，拒绝在生产库上做任何事。")
        return 3

    qa_col = ks._qa_store._collection
    got = qa_col.get(include=["metadatas", "documents"])
    n = len(got["ids"])
    metas = got["metadatas"] or []
    docs = got["documents"] or []

    ev_kind = {"pipe": 0, "json": 0, "empty": 0, "other": 0}
    fp_present = 0
    ev_valid = 0
    ev_invalid_samples = []
    for i, m in enumerate(metas):
        evidence = (m or {}).get("evidence", "") or ""
        q_fp = (m or {}).get("options_fingerprint", "") or ""
        if q_fp:
            fp_present += 1
        if not evidence:
            ev_kind["empty"] += 1
            continue
        if "|" in evidence:
            ev_kind["pipe"] += 1
            src, art = evidence.split("|", 1)
            ok = bool(retrieval.exact_article_lookup(src, art))
        elif evidence.lstrip().startswith("["):
            ev_kind["json"] += 1
            ok = True
            try:
                for r in json.loads(evidence):
                    s = (r or {}).get("source", "")
                    a = (r or {}).get("article", "")
                    if s and a and not retrieval.exact_article_lookup(s, a):
                        ok = False
                        break
            except Exception:  # noqa: BLE001  取证脚本：坏 JSON 不许打断整次清点（它会被记成"这条不过护栏"）
                ok = False
        else:
            ev_kind["other"] += 1
            ok = False
        if ok:
            ev_valid += 1
        elif len(ev_invalid_samples) < 5:
            ev_invalid_samples.append(
                {"question": (docs[i] or "")[:60], "evidence": evidence[:80]}
            )

    # 语料问题的长度/是否带选项：带选项的题面才会被指纹护栏管住
    with_options = sum(
        1 for d in docs if d and ("A." in d or "A、" in d or "A．" in d or "选项" in d)
    )

    readings = {
        "resolved": resolved,
        "qa_corpus_size": n,
        "metadata_key_union": sorted({k for m in metas for k in (m or {})}),
        "evidence_kind": ev_kind,
        "fingerprint_present": fp_present,
        "evidence_valid_today": ev_valid,
        "evidence_invalid_samples": ev_invalid_samples,
        "questions_with_options": with_options,
        "distinct_sources": len({(m or {}).get("origin") for m in metas}),
    }
    OUT.write_text(json.dumps(readings, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(readings, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
