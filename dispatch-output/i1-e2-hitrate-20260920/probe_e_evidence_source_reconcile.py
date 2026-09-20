"""I-1 附带取证 E：把"宪法条文取不回"钉成一条**可判的根因 + 一条会炸的腿**。

C 腿给的分类是"①库缺"，**那个结论是错的**：D 腿扫全库 metadata 量出
`source == "宪法（1982年）"` 有 138 个 chunk ⇒ 宪法**在库里**，只是带年份后缀，
而 `canon_source("宪法")` 原样返回"宪法"、映射表里没有任何含"宪法"的条目 ⇒ 键对不上。

本脚本做三件事，每件都要能独立红：
① 全量对账：QA 语料引用的 source 集合 ∖ 主库 99 个 source 集合 = 差集（不许只看样本）；
② 对差集里每一项，找主库里以它为前缀的 source 名（验证"带年份后缀"这一族假设）；
③ **假设检验**：直接用主库里的全名再查一次 `exact_article_lookup`，
   若取回 ⇒ 根因坐实为"简称映射缺失"，修法是映射表加一条；若仍取不回 ⇒ 我的假设被推翻，
   就照实写"另有原因"，不许把 ①② 的读数拼成一个没验过的结论。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

COPY = pathlib.Path(os.environ["I1_COPY_BACKEND"])
OUT = pathlib.Path(__file__).resolve().parent / "probe-E-evidence-source-reconcile.json"
sys.path.insert(0, str(COPY))
os.chdir(COPY)


def main() -> int:
    import domain_rules
    import retrieval

    col = retrieval.vectorstore._collection
    kb_meta = col.get(include=["metadatas"])
    kb_sources = {
        (m or {}).get("source", "") or "<空>" for m in (kb_meta["metadatas"] or [])
    }

    import knowledge_service as ks

    qmeta = ks._qa_store._collection.get(include=["metadatas"])
    rows = []
    bad_json = 0  # 证据 JSON 解析不了的条数：以前是 `except: pass` 静默丢掉，S110 逼着把它变成读数
    for m in qmeta["metadatas"] or []:
        ev = (m or {}).get("evidence", "") or ""
        srcs = []
        if "|" in ev:
            srcs.append(ev.split("|", 1)[0].strip())
        elif ev.lstrip().startswith("["):
            try:
                for r in json.loads(ev):
                    s = (r or {}).get("source", "")
                    if s:
                        srcs.append(s.strip())
            except Exception:  # noqa: BLE001  坏 JSON 不能打断全量对账，但必须**计数进读数**（否则是静默丢弃）
                bad_json += 1
        rows.append((srcs, ev))

    qa_sources = {s for srcs, _ in rows for s in srcs}
    missing = sorted(s for s in qa_sources if s not in kb_sources)

    # ② 前缀探针：主库里有没有以该名字开头的 source（年份后缀假设）
    prefix_hits = {
        s: sorted(
            {k for k in kb_sources if k.startswith(s) or s.startswith(k.split("（")[0])}
        )[:6]
        for s in missing
    }

    # ③ 假设检验：用全名重查那两条被拦的
    test = []
    for s in missing:
        full_list = prefix_hits.get(s) or []
        for full in full_list:
            for art in ("第二条", "第三十五条"):
                docs = retrieval.exact_article_lookup(full, art)
                test.append(
                    {
                        "简称": s,
                        "全名": full,
                        "article": art,
                        "取回条数": len(docs),
                        "meta样例": [
                            {
                                "article": (d.metadata or {}).get("article"),
                                "status": (d.metadata or {}).get("status"),
                                "effective_from": (d.metadata or {}).get(
                                    "effective_from"
                                ),
                            }
                            for d in docs[:2]
                        ],
                    }
                )

    n_blocked = sum(1 for srcs, ev in rows if any(s in missing for s in srcs))
    rep = {
        "qa_rows": len(rows),
        "qa_evidence_json_unparseable": bad_json,
        "qa_distinct_sources": len(qa_sources),
        "kb_distinct_sources": len(kb_sources),
        "qa_sources_not_in_kb": missing,
        "qa_rows_affected_by_missing_source": n_blocked,
        "prefix_candidates_in_kb": prefix_hits,
        "hypothesis_test_fullname_lookup": test,
        "canon_source_maps_宪法": domain_rules.canon_source("宪法"),
        "canon_source_maps_宪法全名": domain_rules.canon_source("宪法（1982年）"),
    }
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
