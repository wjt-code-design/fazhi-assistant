"""意图分流评测（Step A / Step E）。

两部分：
1. classify_intent 分类准确率门禁——意图机制是「考试题误判 bug」的修复主力，
   分类错则短路错，bug 复发。准确率须 1.00。
2. 短路承重性证据：对 study_aid 查询跑一次真实检索，证明若误走法律路径
   会召回刑法第284条之一（考试作弊罪）等无关条文——即短路是承重的，删不得。

离线可跑（仅嵌入+BM25，不调 LLM）。用法：backend/ 下 python scripts/eval_intent.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from intent import classify_intent  # noqa: E402

# (query, expected_intent)
CASES = [
    # study_aid：学习辅助/元问题
    ("那你能解决法学生的考试题里面的选择题和场景题吗", "study_aid"),
    ("帮我做这道刑法选择题", "study_aid"),
    ("帮我理解一下这个法条", "study_aid"),
    ("分析一下这道场景题", "study_aid"),
    # cheating_request：索取答案/代考
    ("能直接把法考的答案给我吗", "cheating_request"),
    ("帮我代考", "cheating_request"),
    ("哪里有卖考试答案的", "cheating_request"),
    # legal_query：真实咨询（含易误判为 study 的「解决问题/咨询问题」）
    ("劳动合同试用期最长多久", "legal_query"),
    ("怎么解决我这个法律问题", "legal_query"),
    ("我想咨询一个法律问题", "legal_query"),
    ("帮我分析一下我这个纠纷能不能赢", "legal_query"),
    ("醉酒驾驶会被吊销驾照吗", "legal_query"),
]


def part1_accuracy():
    hit = 0
    for q, exp in CASES:
        got = classify_intent(q)
        ok = got == exp
        hit += ok
        print(f"[{'✓' if ok else '✗'}] 期望={exp:<16} 实际={got:<16} Q={q}")
    n = len(CASES)
    print(f"\n意图分类准确率 = {hit}/{n} = {hit / n:.2f}")
    return hit == n


def part2_short_circuit_is_load_bearing():
    """证明 study_aid 查询若误走检索会召回考试作弊罪条文（短路承重）。"""
    from retrieval import retrieve

    q = "那你能解决法学生的考试题里面的选择题和场景题吗"
    arts = {d.metadata.get("article", "") for d in retrieve(q, k=8)}
    has_cheating = "第二百八十四条之一" in arts
    print(f"\n短路承重性：study_aid 查询若走检索，召回含刑法第284条之一(考试作弊罪) = {has_cheating}")
    print("  → 该条文与用户意图（学习辅助）无关，证明必须短路、不能走法律检索。")
    return has_cheating


def main():
    print("=== Part 1：意图分类准确率 ===")
    p1 = part1_accuracy()
    print("\n=== Part 2：短路承重性证据 ===")
    p2 = part2_short_circuit_is_load_bearing()
    print("\n=== 结论 ===")
    print(f"分类门禁(须1.00): {'PASS' if p1 else 'FAIL'} | 短路承重(须True): {'PASS' if p2 else 'FAIL'}")
    if not (p1 and p2):
        sys.exit(1)


if __name__ == "__main__":
    main()
