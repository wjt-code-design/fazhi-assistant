"""I-1 附带取证 D：主库里到底有没有宪法 —— 把"没有"这句话钉死到可复跑的程度。

C 腿只证了 `source == "宪法"` 取不到文档，而 `canon_source("宪法")` 原样返回"宪法"
⇒ **没排除"库里以全称《中华人民共和国宪法》存在"**（本仓有先例：民诉法→民事诉讼法）。
所以这条要三件一起看：
  ① 把主库全部 chunk 的 `source` 去重列出来（10266 个 chunk，只拉 metadata，不嵌向量）；
  ② 在名单里找任何含"宪法"的名字（含全称、含修正案名）；
  ③ 把 `domain_rules` 的简称→全称映射表里与"宪法"相关的条目打出来（映射缺失本身也是一条结论）。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

COPY = pathlib.Path(os.environ["I1_COPY_BACKEND"])
OUT = pathlib.Path(__file__).resolve().parent / "probe-D-main-corpus-sources.json"
sys.path.insert(0, str(COPY))
os.chdir(COPY)


def main() -> int:
    import domain_rules
    import retrieval

    col = retrieval.vectorstore._collection
    got = col.get(include=["metadatas"])
    metas = got["metadatas"] or []
    tally: dict[str, int] = {}
    for m in metas:
        s = (m or {}).get("source", "") or "<空>"
        tally[s] = tally.get(s, 0) + 1

    xianfa = {s: c for s, c in tally.items() if "宪法" in s}
    # 映射表里与"宪法"相关的条目
    maps = {}
    for attr in dir(domain_rules):
        v = getattr(domain_rules, attr)
        if isinstance(v, dict) and v and all(isinstance(k, str) for k in v):
            hit = {k: vv for k, vv in v.items() if "宪法" in k or "宪法" in str(vv)}
            if hit:
                maps[attr] = hit
    probe = domain_rules.canon_source("宪法")
    rep = {
        "chunks": len(metas),
        "distinct_sources": len(tally),
        "sources_containing_宪法": xianfa,
        "canon_source_宪法_returns": probe,
        "mapping_dicts_with_宪法": maps,
        "top20_sources_by_chunks": sorted(tally.items(), key=lambda kv: -kv[1])[:20],
        "law_names_like_宪法_直接取": {
            name: len(col.get(where={"source": name}, include=[]))
            for name in (
                "宪法",
                "中华人民共和国宪法",
                "《中华人民共和国宪法》",
                "宪法修正案",
            )
        },
    }
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
