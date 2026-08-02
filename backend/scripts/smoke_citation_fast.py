"""选引行为快速门禁（非 LLM、零 token，进 pre-commit/CI）。

守确定性部分（不调 LLM）：
- 意图分类正确（classify_intent）
- 检索是否召回期望条文（选引的地基——召回不到，生成阶段就不可能引到）
- 引用校验逻辑（citation_verify 对编造条文应报、对在库条文不报）

含 LLM 生成的部分在 smoke_citation_full.py（release 门禁）。

用法：cd backend && python scripts/smoke_citation_fast.py（退出码非 0 = 失败）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from dotenv import load_dotenv

load_dotenv(".env")

from intent import classify_intent  # noqa: E402
from retrieval import retrieve, citation_verify  # noqa: E402

# (query, expected_sources, expected_articles, expected_intent)
# 检索层直接能召回的用例（不依赖 _pre 的定向补充逻辑）
RETRIEVAL_CASES = [
    ("公司违法解除劳动合同，赔偿金怎么算？", ["劳动合同法"], ["第八十七条"], "legal_query"),
    ("公司合同到期不续签，经济补偿金怎么算？", ["劳动合同法"], ["第四十七条"], "legal_query"),
    ("劳动合同试用期最长能约定多久？", ["劳动合同法"], ["第十九条"], "legal_query"),
    ("周末加班，加班费怎么算？", ["劳动法"], ["第四十四条"], "legal_query"),
    ("机动车发生交通事故，交强险先赔还是商业险先赔？", ["民法典"], ["第一千二百一十三条"], "legal_query"),
    ("交了定金又不想买了，定金能退吗？", ["民法典"], ["第五百八十六条", "第五百八十七条"], "legal_query"),
    ("网购商品七天无理由退货需要满足什么条件？", ["消费者权益保护法"], ["第二十五条"], "legal_query"),
]

# 引用校验罐头样例（非 LLM）：
# (answer, in_kb 判定中「在库的条号」，期望结果)
VERIFY_CASES = [
    ("依据《刑法》第十三条和《劳动合同法》第八十七条。", {"第十三条", "第八十七条"}, []),          # 全在库 → 不报
    ("依据《刑法》第九百九十九条。", {"第十三条"}, ["《刑法》第九百九十九条"]),                        # 编造 → 报
    ("《中华人民共和国刑法》第二十条、《刑法》第20条。", {"第二十条"}, []),                            # 全称/简称/数字归一 → 不报
]


def main():
    n = fail = 0

    def check(ok, label):
        nonlocal n, fail
        n += 1
        if not ok:
            fail += 1
            print(f"  [FAIL] {label}")
        else:
            print(f"  [PASS] {label}")

    print("=== 意图分类 ===")
    for q, _es, _ea, exp in RETRIEVAL_CASES:
        got = classify_intent(q)
        check(got == exp, f"intent({q[:18]}) = {got}, 期望 {exp}")

    print("=== 检索召回期望条文（选引地基）===")
    for q, _es, ea, _i in RETRIEVAL_CASES:
        docs = retrieve(q, k=6)
        arts = {d.metadata.get("article", "") for d in docs}
        ok = any(a in arts for a in ea)
        check(ok, f"retrieve({q[:18]}) 召回 {ea}")

    print("=== 引用校验（罐头）===")
    for answer, in_kb_arts, expected in VERIFY_CASES:
        in_kb = lambda name, art: __import__("retrieval", fromlist=["_normalize_article"])._normalize_article(art) in in_kb_arts
        got = citation_verify(answer, in_kb)
        check(got == expected, f"citation_verify({answer[:18]}...) = {got}, 期望 {expected}")

    print(f"\nfast 门禁：{n - fail}/{n} 通过" + ("，FAIL!" if fail else ""))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
