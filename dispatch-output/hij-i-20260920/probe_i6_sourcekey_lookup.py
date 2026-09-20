"""I-6 先红/后绿读数：真实 KB（只读）。

要证明的三件事（都从**真实知识库**读，不桩任何函数）：
  ① 库内**确实**存在带年份括注的源名（`宪法（1982年）`），且它的条号取得到
     ⇒ "这 2 条其实有据可查" 这个说法站得住；
  ② `exact_article_lookup("宪法", <真实条号>)` 今天 **取空**（miss）——这是先红的那一面；
  ③ 同族的 `article_in_kb("宪法", <真实条号>)` **已经是 True**
     ⇒ 说明"容忍源名差异"的能力本仓早就有（`_source_key`），只是 `exact_article_lookup` 没用它。

只读：只用 `collection.get`。不 upsert / 不 update / 不 delete。
用法：backend/venv/Scripts/python.exe dispatch-output/hij-i-20260920/probe_i6_sourcekey_lookup.py <标签>
      ⇒ 落盘 `i6-lookup-<标签>.json`（**标签必传**：第一版把文件名写死成 before，
      改后再跑就把 before 的 json 覆盖了 —— before 读数只剩 stdout 那一份，白丢一次取证）。
      ⚠️ **stdout 永远一并重定向到文件**：那才是不可被覆盖的原始证据。
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

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

import retrieval as R

BRACKETED = "宪法（1982年）"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    label = sys.argv[1]
    out: dict = {"label": label}
    col = R.vectorstore._collection

    # ① 找出库里所有"带括注"的源名 + 给 `宪法（1982年）` 取几个真实条号
    data = col.get(include=["metadatas"])
    srcs = sorted(
        {str((m or {}).get("source", "") or "") for m in (data["metadatas"] or [])}
    )
    bracketed = [s for s in srcs if "（" in s or "(" in s]
    out["n_sources"] = len(srcs)
    out["sources_with_bracket"] = bracketed

    con = col.get(where={"source": BRACKETED}, include=["metadatas"])
    arts = [str((m or {}).get("article", "") or "") for m in (con["metadatas"] or [])]
    out[f"n_rows_{BRACKETED}"] = len(arts)
    sample_arts = [a for a in arts if a][:5]
    out["sample_articles"] = sample_arts

    # ②③ 逐条对照：精确命中是否有救、容忍版本是否已 True
    per_art = []
    for art in sample_arts:
        per_art.append(
            {
                "article": art,
                "exact_lookup_short_name": len(R.exact_article_lookup("宪法", art)),
                "exact_lookup_full_name": len(R.exact_article_lookup(BRACKETED, art)),
                "article_in_kb_short_name": bool(R.article_in_kb("宪法", art)),
                "source_in_kb_short_name": bool(R.source_in_kb("宪法")),
                "_source_key(BRACKETED)": R._source_key(BRACKETED),
                "_source_key(宪法)": R._source_key("宪法"),
            }
        )
    out["per_article"] = per_art

    (OUT / f"i6-lookup-{label}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
