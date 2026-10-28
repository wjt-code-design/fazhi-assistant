"""选引行为快速门禁（非 LLM、零 token，进 pre-commit/CI）。

守确定性部分（不调 LLM）：
- 意图分类正确（classify_intent）
- 检索是否召回期望条文（选引的地基——召回不到，生成阶段就不可能引到）。判据是 `(法名, 条号)` 联合：
  主集合 `legal_provisions_cos` 里 第十九条 被 97 部法共用、第四十四条 87 部，只看条号等于没判。
- 引用校验逻辑（citation_verify 对编造条文应报、对在库条文不报）

含 LLM 生成的部分在 smoke_citation_full.py（release 门禁）。
判据本体由 `tests/test_smoke_citation_assertions.py` 用假召回结果钉住（不连真实 Chroma/模型）。

用法：cd backend && python scripts/smoke_citation_fast.py（退出码非 0 = 失败）
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)


def source_key(name: str) -> str:
    """法名归一：走 `retrieval._source_key` 这唯一口径（去"中华人民共和国"前缀 + 剥尾部年份括注）。

    刻意不叫 `norm_source`：`retrieval._norm_source` 已有一个同名但更弱的函数（只去前缀、不剥括注），
    近名异义会把后来人引到错的那一份上。
    延迟到调用时 import：`retrieval` 在 import 期就建 Chroma 客户端并加载 BGE，
    而本文件的判据用例必须在无模型的环境下跑得动。
    """
    from retrieval import _source_key

    return _source_key(name)


def normalize_article(art: str) -> str:
    """条号归一：走 `retrieval._normalize_article`（〇→零、阿拉伯数字→中文数字）。同上延迟 import。"""
    from retrieval import _normalize_article

    return _normalize_article(art)


def recall_hit(docs, expected_sources, expected_articles, norm_source=source_key, norm_article=normalize_article):
    """召回结果里是否存在**同一条**文档同时满足：法名在期望集合内、条号在期望列表内。

    "任中一条"语义保留（期望列表给多条时，命中任意一条即算召回）。
    法名与条号分别落在两条不同文档上不算命中——`any(src...) and any(art...)` 的写法在 k=6 的池子里几乎恒绿。
    """
    want_sources = {norm_source(str(s)) for s in expected_sources}
    want_articles = {norm_article(str(a)) for a in expected_articles}
    for doc in docs:
        meta = getattr(doc, "metadata", None) or {}
        src = norm_source(str(meta.get("source") or ""))
        art = norm_article(str(meta.get("article") or ""))
        if src in want_sources and art in want_articles:
            return True
    return False


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
    ("依据《刑法》第十三条和《劳动合同法》第八十七条。", {"第十三条", "第八十七条"}, []),  # 全在库 → 不报
    ("依据《刑法》第九百九十九条。", {"第十三条"}, ["《刑法》第九百九十九条"]),  # 编造 → 报
    ("《中华人民共和国刑法》第二十条、《刑法》第20条。", {"第二十条"}, []),  # 全称/简称/数字归一 → 不报
]


def main():
    # 重依赖全部留在 main() 里：`tests/test_smoke_citation_assertions.py` 要 import 本文件测判据本体，
    # import 期加载 BGE / 改 cwd / 读 .env 都会把那条路堵死（CI 上没有 .env）。
    sys.path.insert(0, BACKEND)
    os.chdir(BACKEND)
    from dotenv import load_dotenv

    load_dotenv(".env")

    import complexity
    import quality
    from intent import classify_intent
    from retrieval import citation_verify, retrieve

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

    print("=== 检索召回期望条文（按 法名×条号 配对）===")
    for q, es, ea, _i in RETRIEVAL_CASES:
        docs = retrieve(q, k=6)
        check(recall_hit(docs, es, ea), f"retrieve({q[:18]}) 召回 {es}×{ea}")

    print("=== 引用校验（罐头）===")
    for answer, in_kb_arts, expected in VERIFY_CASES:

        def in_kb(name, art, arts=in_kb_arts):
            return normalize_article(art) in arts

        got = citation_verify(answer, in_kb)
        check(got == expected, f"citation_verify({answer[:18]}...) = {got}, 期望 {expected}")

    print("=== 复杂度路由 / 回答自检（罐头）===")
    check(complexity.admit_light("试用期最长多久", False, "legal_query", [], True), "admit_light 短+命中+单轮 → 放行")
    check(not complexity.admit_light("工伤赔偿怎么算", False, "legal_query", [], True), "admit_light 高利害词 → 拒绝")
    check(not complexity.admit_light("试用期最长多久", False, "legal_query", [], False), "admit_light 无命中 → 拒绝")
    check(
        not complexity.admit_light("试用期最长多久", False, "legal_query", [{"role": "user"}], True),
        "admit_light 多轮 → 拒绝",
    )

    def _kb_true(name, art):
        return True

    check(
        not quality.self_check("根据法律规定结合具体案情分析处理此事即可。", True, in_kb=_kb_true).ok,
        "self_check 命中却无引用 → FAIL",
    )
    check(
        quality.self_check("根据《劳动合同法》第十九条，试用期最长不得超过六个月。", True, in_kb=_kb_true).ok,
        "self_check 命中且有在库引用 → PASS",
    )
    check(quality.self_check("", True, in_kb=_kb_true).reason == "empty", "self_check 空答 → empty")

    print(f"\nfast 门禁：{n - fail}/{n} 通过" + ("，FAIL!" if fail else ""))
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
