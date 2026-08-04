"""高频考点 QA 对种子（ADR-012 块1.2，grilling 定稿）：有界语义入口，零 LLM 成本。

- 只给高频考点条文造"自然问法 → 条文内容"QA 对（用户真实会问的问法，非模板化条号问法）。
- answer = 条文原文（exact_article_lookup 从库取，不改写）；evidence = "法名|条号" 供时效校验。
- 幂等：已存在近同题（search_qa ≥0.99）则跳过；可重复运行。
- **绝不全量 10266 条**（LLM 全量生成烧穿配额；本脚本为确定性数据种子）。

用法：cd backend && venv\\Scripts\\python.exe qa_seeds.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# 高频考点：自然问法 → (法名, 条号)。answer 从库取条文原文。
SEEDS: list[tuple[str, str, str]] = [
    # 刑法 / 刑诉法
    ("正当防卫成立需要什么条件？", "刑法", "第二十条"),
    ("故意杀人的刑罚是怎么规定的？", "刑法", "第二百三十二条"),
    ("贩卖毒品多少数量构成犯罪？", "刑法", "第三百四十七条"),
    ("死刑由哪个机关核准？", "刑事诉讼法", "第二百四十六条"),
    # 民法典
    ("高空抛物致人损害由谁承担责任？", "民法典", "第一千二百五十四条"),
    ("过错责任的构成要件是什么？", "民法典", "第一千一百六十五条"),
    ("离婚冷静期是多少天？", "民法典", "第一千零七十七条"),
    ("定金条款有什么法律规定？", "民法典", "第五百八十六条"),
    ("格式条款的效力有什么规定？", "民法典", "第四百九十六条"),
    ("诉讼时效是几年？", "民法典", "第一百八十八条"),
    ("法定继承的第一顺序是什么？", "民法典", "第一千一百二十七条"),
    ("机动车交通事故的赔偿顺序怎么规定？", "民法典", "第一千二百一十三条"),
    ("自然人之间的借款合同什么时候成立？", "民法典", "第六百七十九条"),
    # 其他
    ("试用期最长可以约定多久？", "劳动合同法", "第十九条"),
    ("网购七天无理由退货适用于哪些商品？", "消费者权益保护法", "第二十五条"),
    ("个人信息处理要遵循什么原则？", "个人信息保护法", "第五条"),
    ("保证担保的保证方式怎么约定？", "民法典", "第六百八十六条"),
]


def main() -> int:
    import knowledge_service as ks
    from retrieval import exact_article_lookup

    added = skipped = missing = 0
    for question, source, article in SEEDS:
        # 幂等：近同题已存在则跳过（阈值 0.99 = 几乎同一问法）
        if ks.search_qa(question, threshold=0.99):
            skipped += 1
            print(f"  - 已存在（跳过）：{question}")
            continue
        docs = exact_article_lookup(source, article)
        if not docs:
            missing += 1
            print(f"  ✗ 库内未找到 {source} {article}：{question}")
            continue
        answer = "\n".join(d.page_content for d in docs[:1])
        ks.add_qa_pair(question, answer, evidence=f"{source}|{article}")
        added += 1
        print(f"  + {question}  →  {source} {article}")
    print(f"\n完成：新增 {added} / 跳过 {skipped} / 缺失 {missing}（共 {len(SEEDS)} 条种子）")
    return 0 if missing == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
