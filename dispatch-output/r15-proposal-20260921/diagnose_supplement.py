"""R15/遗留缺陷诊断：5 条 slow 失败的根因取证（只读，不改任何代码/数据）。

待定因的现象（`tests/test_scenario_supplement.py`，慢测）：
  ① 继承场景 要《民法典》第 1155 条  ⇒ 查空
  ② 劳动争议 要《劳动合同法》47/53 条 ⇒ 查空
  ③ 保证合同 要《民法典》692/693 条  ⇒ 查空
  ④ `exact_article_lookup("公司法","第四十九条")` ⇒ 查空
  ⑤ 全部"补充组"条文（刑法20 / 刑诉法246 …）⇒ 查空

已有线索：**这 5 个源在 KB 里都存在**（99 个源里含 公司法/民法典/劳动合同法/刑法/刑事诉讼法）
⇒ 所以"库里没有"未必成立。本探针按**四层边界**取证据，定位到底断在哪一层：
  L4 KB 数据层：该 source 在库里到底有哪些 article 值？第四十九条/692 条在不在？
                metadata 里 effective_from/effective_to/status 是什么（是否被时效过滤掉）？
  L3 检索层   ：chroma 里按 (source=X) 能取到多少条？按 (source=X, article=Y) 呢？
  L2 函数层   ：`exact_article_lookup(src, art)` 返回多少条（含票 I-6 加的回退是否触发）？
  L1 断言层   ：测试实际断言的形状（上面的数字是"条号字符串 in 列表"）。
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO / "backend" / ".env")

import retrieval as R

CASES = [
    ("民法典", "第一千一百五十五条"),
    ("劳动合同法", "第四十七条"),
    ("民法典", "第六百九十二条"),
    ("公司法", "第四十九条"),
    ("刑法", "第二十条"),
    ("刑事诉讼法", "第二百四十六条"),
]


def main() -> int:
    col = R.vectorstore._collection
    data = col.get(include=["metadatas"])
    metas = [dict(m or {}) for m in (data.get("metadatas") or [])]
    out: dict = {"total_docs": len(metas), "cases": {}}

    for src, art in CASES:
        same_src = [m for m in metas if str(m.get("source", "")) == src]
        arts = sorted({str(m.get("article", "")) for m in same_src})
        hit_art = [m for m in same_src if str(m.get("article", "")) == art]
        try:
            looked = R.exact_article_lookup(src, art)
            looked_n = len(looked)
        except Exception as e:  # noqa: BLE001 - 诊断要看到异常
            looked_n = f"EXC {e!r}"
        sample = same_src[0] if same_src else {}
        out["cases"][f"{src}|{art}"] = {
            "L4_source_docs": len(same_src),
            "L4_article_present": bool(hit_art),
            "L4_article_sample": arts[:6],
            "L4_status_values": sorted({str(m.get("status", "")) for m in hit_art})
            or None,
            "L4_effective_from": sorted(
                {str(m.get("effective_from", "")) for m in hit_art}
            )
            or None,
            "L4_effective_to": sorted({str(m.get("effective_to", "")) for m in hit_art})
            or None,
            "L2_exact_article_lookup": looked_n,
            "L4_sample_metadata": {
                k: sample.get(k)
                for k in (
                    "source",
                    "article",
                    "status",
                    "effective_from",
                    "effective_to",
                )
            },
        }

    (pathlib.Path(__file__).resolve().parent / "diagnose-supplement.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline=""
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
