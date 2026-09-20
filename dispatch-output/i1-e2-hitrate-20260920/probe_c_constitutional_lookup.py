"""I-1 附带取证 C：那两条被「证据时效护栏」拦掉的宪法条文，到底是**哪种**拦法。

票 I 的原文假设是"护栏可能静默吃掉本可直返的题"。这句要拆成三种互不相同的结论：
  ① 宪法**根本不在这个向量库里** ⇒ 护栏是**对的**（证据不在库就不该直返），要修的是语料/库；
  ② 在库，但 `canon_source` / `_normalize_article` 归一出来的键与库里存的键**对不上** ⇒ 护栏**误杀**；
  ③ 在库且键对得上，但 `is_valid_by_time` 判 False ⇒ 要看它是按日期判的还是 fail-closed（status 有值而日期缺失）。
三者对票 I 的含义完全不同，所以每条都要各自给读数，不许合并成"护栏有问题"。

只在副本树上跑（`I1_COPY_BACKEND` + 副本 chroma_db），live 库零写入；不发任何 embedding。
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

COPY = pathlib.Path(os.environ["I1_COPY_BACKEND"])
OUT = pathlib.Path(__file__).resolve().parent / "probe-C-constitutional-lookup.json"
sys.path.insert(0, str(COPY))
os.chdir(COPY)

PAIRS = [("宪法", "第三十五条"), ("宪法", "第二条")]


def main() -> int:
    from datetime import date

    import domain_rules
    import retrieval
    import retrieval_core as rc

    today = date.today().isoformat()  # noqa: DTZ011  与生产同源：exact_article_lookup 的 cutoff 就是当日
    col = retrieval.vectorstore._collection
    rep: dict = {"today": today, "main_collection_count": col.count()}

    # 库里到底有没有"宪法"这个 source（用 $contains 扫，避开全量拉 metadata）
    def get_by_source(src: str):
        try:
            return col.get(
                where={"source": {"$contains": src}}, include=["metadatas", "documents"]
            )
        except Exception as e:  # noqa: BLE001  老版本 chroma 不支持 $contains：异常类型要**写进读数**返回，不是吞掉
            return {"error": f"{type(e).__name__}: {e}"}

    like = get_by_source("宪法")
    if "error" in like:
        rep["source_contains_宪法"] = like["error"]
        src_hits = []
    else:
        metas = like["metadatas"] or []
        src_hits = sorted({(m or {}).get("source", "") for m in metas})
        rep["source_contains_宪法"] = {
            "docs": len(metas),
            "distinct_source_names": src_hits[:20],
            "article_samples": sorted({(m or {}).get("article", "") for m in metas})[
                :12
            ],
        }

    rep["canon"] = []
    for src, art in PAIRS:
        cs = domain_rules.canon_source(src)
        na = retrieval._normalize_article(art)
        row = {"输入": f"{src}|{art}", "canon_source": cs, "normalize_article": na}
        # ① 键对得上吗（精确 where 查）
        exact = col.get(
            where={"$and": [{"source": cs}, {"article": na}]}, include=["metadatas"]
        )
        row["exact_where_hits"] = len(exact["ids"])
        if row["exact_where_hits"] == 0:
            # 退一步：只按 source 查，看这个 source 在库里以什么名字存在
            by_src = col.get(where={"source": cs}, include=["metadatas"])
            row["docs_under_canon_source"] = len(by_src["ids"])
            arts = sorted(
                {(m or {}).get("article", "") for m in (by_src["metadatas"] or [])}
            )
            row["articles_under_canon_source_sample"] = arts[:15]
            # 再退一步：article 用未归一的原文查
            raw = col.get(
                where={"$and": [{"source": cs}, {"article": art}]},
                include=["metadatas"],
            )
            row["hits_with_unnormalized_article"] = len(raw["ids"])
        else:
            metas = exact["metadatas"] or []
            row["valid_today"] = [rc.is_valid_by_time(m or {}, today) for m in metas]
            row["time_fields"] = [
                {
                    "status": (m or {}).get("status"),
                    "effective_from": (m or {}).get("effective_from"),
                    "effective_to": (m or {}).get("effective_to"),
                }
                for m in metas[:4]
            ]
        # 结论归类
        if row["exact_where_hits"] == 0:
            row["verdict"] = "② 误杀（canon 后的 source 在库里" + (
                "有文档但条号形状对不上）"
                if row.get("docs_under_canon_source")
                else "完全没有文档 ⇒ 实为①库缺）"
            )
        elif not all(row["valid_today"]):
            row["verdict"] = (
                "③ 时效判 False（看 time_fields 是否因缺日期而 fail-closed）"
            )
        else:
            row["verdict"] = "④ 复核后其实能命中（说明 A 腿那条读数另有原因）"
        rep["canon"].append(row)

    # 语义检索这条路：宪法条文能不能被 retrieve() 召回来（不花 embedding 的话就只看库侧）
    rep["note"] = (
        "本脚本不测查询向量，只测『证据是否可按键取回』与『时效谓词』；"
        "『语义检索能否召回宪法条文』要另发 embedding，属另一台仪器。"
    )
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
