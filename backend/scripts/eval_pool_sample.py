"""抽样「出题素材池」：从生产向量库按法律来源分层抽取条文，供独立助手反向出题。

为什么从索引里抽样而不是从 laws_clean 文本抽样：评测度量的是「向量库召回」，
金标必须是库里真实存在的 (source, article)，否则 recall 无法判定。

用法：
  python scripts/eval_pool_sample.py --n 30 --out ../data/eval_pool_v1.json
  python scripts/eval_pool_sample.py --n 150 --out ../data/eval_pool_v1.json --seed 20261025

输出结构：
  {"meta": {...}, "items": [{"pid": "p001", "source": "刑法", "article": "第三百九十九条",
                             "chapter": "...", "text": "..."}]}
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

import chromadb

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_DIR = os.path.join(REPO, "backend", "chroma_db")
COLLECTION = "legal_provisions_te4"
EVAL_SET = [
    os.path.join(REPO, "data", "eval_set.json"),
    os.path.join(REPO, "data", "eval_set_gen_v1.json"),
]


def _load_used():
    """已覆盖的 (source, article)：同时排除旧基线题与新增题集，避免重复出题。"""
    used = set()
    for path in EVAL_SET:
        if not os.path.exists(path):
            continue
        for c in json.load(open(path, encoding="utf-8")):
            for src in c.get("expected_sources", []):
                for art in c.get("expected_articles", []):
                    used.add((src, art))
    return used


def _candidates():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_collection(COLLECTION)
    got = col.get(include=["metadatas", "documents"], limit=col.count())
    out, seen = [], set()
    for meta, doc in zip(got["metadatas"], got["documents"], strict=False):
        src = (meta or {}).get("source") or ""
        art = (meta or {}).get("article") or ""
        text = (doc or "").strip()
        key = (src, art)
        if not src or not art or key in seen:
            continue
        seen.add(key)
        if (meta or {}).get("status") not in ("现行", ""):
            continue
        # 过滤整条/整章式的长条文与过短的宣示性条文，保证能被单条提问
        if not 70 <= len(text) <= 400:
            continue
        # 过滤纯生效/废止条款（无法提出有信息量的问题）
        if "本法自" in text or "本条例自" in text:
            continue
        # 过滤附则（多为适用范围/衔接条款）与港澳基本法（几乎不是真实咨询对象）
        chapter = (meta or {}).get("chapter") or ""
        if "附" in chapter and "则" in chapter:
            continue
        if "基本法" in src:
            continue
        out.append({"source": src, "article": art, "chapter": (meta or {}).get("chapter") or "", "text": text})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--cap", type=int, default=2, help="单一法律最多抽多少条")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rnd = random.Random(args.seed)
    used = _load_used()
    cands = [c for c in _candidates() if (c["source"], c["article"]) not in used]

    groups: dict[str, list[dict]] = {}
    for c in cands:
        groups.setdefault(c["source"], []).append(c)
    for src in groups:
        rnd.shuffle(groups[src])

    picked, quota = [], {src: [args.cap] for src in groups}
    # 轮转抽取：先保证来源广度，再吃满配额
    while len(picked) < args.n:
        progress = False
        for src in sorted(groups, key=lambda s: (-len(groups[s]), s)):
            if len(picked) >= args.n:
                break
            if quota[src][0] <= 0 or not groups[src]:
                continue
            picked.append(groups[src].pop())
            quota[src][0] -= 1
            progress = True
        if not progress:
            break

    items = []
    for i, c in enumerate(picked, 1):
        items.append({"pid": f"p{i:03d}", **c})
    payload = {
        "meta": {
            "collection": COLLECTION,
            "seed": args.seed,
            "n": len(items),
            "sources": len({c["source"] for c in items}),
            "note": "金标 = 本文件 (source, article)；仅供出题改写，不得作为答案参考",
        },
        "items": items,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"抽出 {len(items)} 条 / {payload['meta']['sources']} 部法律 → {args.out}")
    for src, n in sorted(
        ((s, sum(1 for c in items if c["source"] == s)) for s in {c["source"] for c in items}), key=lambda x: -x[1]
    ):
        print(f"  {src}: {n}")
    if len(items) < args.n:
        print(f"警告：候选不足，只抽到 {len(items)} 条（目标 {args.n}）", file=sys.stderr)


if __name__ == "__main__":
    main()
