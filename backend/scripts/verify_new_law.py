"""新增法律条文的端到端稳健性验证（2026-08-04，用户"后续添加新条文会不会检索不到"）。

模拟真实场景：新增一部含 4 类代表性条文的「验证法」，验证全链路：
  1. 普通条文（民商事）能否被检索命中（向量 + BM25 双路）
  2. 含罪名条文（如"非法采矿罪"）→ 罪名锚点能否召回
  3. 含法条引用条文（引用其他法）→ 引用锚点能否召回
  4. 条号直查（新增法名的精确条号命中，parse_article_query + exact_article_lookup）
  5. 新增后 source_in_kb 法名集合更新
  6. 幂等：重复导入不堆积；更新条文生效
  7. 误拒答防护：问新法名不误拒答（有据即 direct）

注意：条号必须用中文数字（"第二十五条"）——真实上传经 split_law_document 提取中文
条号，与 parse_article_query 归一化口径一致；用阿拉伯数字（"第25条"）会查不到。

用法：cd backend && python scripts/verify_new_law.py（结束后自动清理验证法）
结果：print 逐项 PASS/FAIL，全部通过 exit 0。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from knowledge_service import _collection, add_text  # noqa: E402
from retrieval import bm25_top, retrieve, source_in_kb  # noqa: E402

SRC = "验证法"
passes = 0
fails = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passes, fails
    if cond:
        passes += 1
        print(f"  ✅ {name}")
    else:
        fails += 1
        print(f"  ❌ {name} {detail}")


def cleanup() -> None:
    col = _collection()
    ids = col.get(where={"source": SRC})["ids"] or []
    for did in ids:
        col.delete(ids=[did])
    import retrieval
    retrieval.invalidate()
    print(f"  清理验证法：删除 {len(ids)} 条")


def main() -> None:
    # 1. 普通条文（企业破产重整）
    add_text(
        "第三十条　人民法院裁定受理破产重整申请的，重整期间债务人可以申请管理人许可后继续营业。",
        SRC, "第三十条", origin="manual", extra_meta={"effective_from": "2024-01-01"},
    )
    # 2. 含罪名条文（非法采矿罪）
    add_text(
        "第四十五条　违反矿产资源法的规定，未取得采矿许可证擅自采矿，情节严重的，构成非法采矿罪，依法追究刑事责任。",
        SRC, "第四十五条", origin="manual",
    )
    # 3. 含法条引用条文
    add_text(
        "第五十条　依照《刑法》第二百六十四条盗窃公私财物数额较大的，处三年以下有期徒刑。",
        SRC, "第五十条", origin="manual",
    )
    # 4. 条号直查（中文条号——真实上传 split_law_document 用中文条号，见 verify 说明）
    add_text(
        "第二十五条　本法关于验证事项的规则是第25号条款，应当遵守执行。",
        SRC, "第二十五条", origin="manual",
    )
    print("=== 新增验证法（3 条）完成 ===\n")

    print("=== 1. 普通条文检索 ===")
    docs = retrieve("企业破产重整期间能否继续营业？", k=4)
    check("普通条文被检索命中", any(d.metadata.get("source") == SRC for d in docs),
          f"top={[d.metadata.get('source') for d in docs]}")
    # 双路：BM25 单独也要能命中
    b = bm25_top("破产重整 继续营业 管理人许可", 10)
    check("BM25 路命中新条文", any(d.metadata.get("source") == SRC for d, _ in b))

    print("\n=== 2. 罪名锚点（非法采矿罪）===")
    docs = retrieve("非法采矿罪的构成要件是什么？", k=6)
    top2 = [d.metadata.get("source", "") + d.metadata.get("article", "") for d in docs]
    check("罪名锚点召回非法采矿罪条文", any(d.metadata.get("source") == SRC and d.metadata.get("article") == "第四十五条" for d in docs),
          f"top={top2}")

    print("\n=== 3. 法条引用锚点 ===")
    docs = retrieve("盗窃数额较大处几年有期徒刑？", k=6)
    top3 = [d.metadata.get("source", "") + d.metadata.get("article", "") for d in docs]
    check("引用锚点召回第五十条", any(d.metadata.get("source") == SRC and d.metadata.get("article") == "第五十条" for d in docs),
          f"top={top3}")

    print("\n=== 3.5 条号直查（新增法名的精确条号）===")
    from retrieval import exact_article_lookup, parse_article_query
    parsed = parse_article_query("验证法第二十五条")
    exact = exact_article_lookup("验证法", "第二十五条") if parsed else []
    check(f"条号直查「验证法第二十五条」命中（parse={parsed}）", len(exact) > 0,
          f"exact={len(exact)}")

    print("\n=== 4. 法名集合更新 ===")
    check("source_in_kb(验证法) 为 True", source_in_kb(SRC))

    print("\n=== 5. 幂等与更新 ===")
    col = _collection()
    before = len(col.get(where={"source": SRC})["ids"] or [])
    add_text(
        "第三十条　人民法院裁定受理破产重整申请的，重整期间债务人可以申请管理人许可后继续营业。",
        SRC, "第三十条", origin="manual",
    )
    after = len(col.get(where={"source": SRC})["ids"] or [])
    check(f"重复导入不堆积（{before} → {after}）", after == before, f"before={before} after={after}")
    # 更新条文内容
    add_text(
        "第三十条　（修订）人民法院裁定受理破产重整申请的，重整期间由管理人决定是否继续营业。",
        SRC, "第三十条", origin="manual",
    )
    docs = retrieve("破产重整期间管理人决定是否继续营业", k=4)
    check("条文更新生效（检索到修订内容）",
          any(d.metadata.get("source") == SRC and "修订" in d.page_content for d in docs))

    print("\n=== 6. 误拒答防护（问新法名不误拒答）===")
    # 模拟 decide：验证法在库 → 有据 → direct
    import clarify
    got = clarify.decide("legal_query", f"{SRC}规定的破产重整程序是什么？", has_sources=True)
    check(f"问验证法（在库）→ direct（非 refuse），got={got}", got == "direct")

    print(f"\n=== 结果：{passes} PASS / {fails} FAIL ===")
    cleanup()
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
