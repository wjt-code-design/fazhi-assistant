"""回答一致性评测（组1b，LLM judge 为主 + difflib 辅助）。

同一问题的 2 个同义改写各问一次（绕开答案缓存——缓存 key 含问题文本与条文 ids，
改写文本不同必然 miss），比较两份回答是否实质一致。

缓存旁路断言（P0-4 加强）：改写对文本两两不同且 ≠ eval_set 原题（脚本启动断言）；
本地核对两改写与 eval_set 原题的检索条文 ids，记录两两 ids_overlap 供审计。
诚实标注边界：缓存 key 用 router 归一化后的 rewritten + ids——两改写被归并为同文且
ids 重合时理论上仍可能命中缓存；脚本记录改写对与原文的 ids_overlap 并在极高重合时
打标 possible_cache_collision，供人工复核，不做硬断言（ids 重合本身合法）。

判据（grilling 修订）：LLM judge 0/1/2 为主（judge>=1 即通过）；difflib 相似仅作
辅助记录，不设硬阈值（中文措辞差异下 difflib 不可靠）。

用法：cd backend && python scripts/eval_consistency.py（10 题 × 2 问 + 10 judge ≈ 30 次 LLM）
输出：docs/benchmark_results/consistency_<ts>.json
"""

import difflib
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import _client  # noqa: E402
import _judge  # noqa: E402

from retrieval import retrieve  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "paraphrases.json")
EVAL_SET = os.path.join(os.path.dirname(__file__), "..", "..", "data", "eval_set.json")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "benchmark_results")


def _src_ids(q: str) -> set[str]:
    """本地检索该问法命中的条文 id 集合（source|article），用于旁路审计。"""
    return {f"{d.metadata.get('source','')}|{d.metadata.get('article','')}" for d in retrieve(q, k=6)}


def _overlap(a: set[str], b: set[str]) -> float:
    """Jaccard 重合度。"""
    return round(len(a & b) / max(len(a | b), 1), 3)


def main() -> None:
    data = json.load(open(DATA, encoding="utf-8"))
    cases = data["consistency"]
    originals = {c["question"] for c in json.load(open(EVAL_SET, encoding="utf-8"))}

    # 缓存旁路断言：改写文本不与原题重复、两两不同
    all_paras = [p for c in cases for p in c["paraphrases"]]
    assert len(all_paras) == len(set(all_paras)), "改写对存在重复文本"
    assert not originals & set(all_paras), "改写文本与 eval_set 原题重复（会命中之前的答案缓存）"

    token = _client.login()
    llm = _judge.pick_text_llm()
    rows = []
    n_pass = 0
    for c in cases:
        q, p1, p2 = c["question"], c["paraphrases"][0], c["paraphrases"][1]
        a1 = _client.chat(token, p1)
        a2 = _client.chat(token, p2)
        ids1, ids2, ids0 = _src_ids(p1), _src_ids(p2), _src_ids(q)
        score = _judge.consistent(llm, q, a1, a2) if a1 and a2 else 0
        ratio = round(difflib.SequenceMatcher(None, a1, a2).ratio(), 3)
        ok = score >= 1
        n_pass += ok
        # 缓存碰撞风险打标：两改写与原文 ids 重合度都很高 + 答案长度完全相同 → 疑似同一缓存/零信息
        collide = ids1 == ids2 and len(a1) == len(a2) and len(a1) > 0
        rows.append(
            {
                "id": c["id"],
                "question": q,
                "judge_score": score,
                "difflib_ratio": ratio,
                "ids_overlap_p1p2": _overlap(ids1, ids2),
                "ids_overlap_p1_orig": _overlap(ids1, ids0),
                "ids_overlap_p2_orig": _overlap(ids2, ids0),
                "possible_cache_collision": bool(collide),
                "pass": bool(ok),
                "answer_lens": [len(a1), len(a2)],
            }
        )
        print(
            f"[{c['id']}] judge={score} difflib={ratio} p1p2={rows[-1]['ids_overlap_p1p2']} "
            f"collide={int(collide)} {'PASS' if ok else 'FAIL'} {q[:20]}",
            flush=True,
        )
        time.sleep(1.2)  # 限流 60/min 退避（429 由 _client 退避）

    n = len(rows)
    n_collide = sum(1 for r in rows if r["possible_cache_collision"])
    summary = {
        "n": n,
        "pass_rate": round(n_pass / n, 4),
        "mean_judge": round(sum(r["judge_score"] for r in rows) / n, 3),
        "mean_difflib": round(sum(r["difflib_ratio"] for r in rows) / n, 3),
        "possible_cache_collisions": n_collide,
        "note": "judge 为主（>=1 通过）；difflib 仅辅助不设阈值；temp=0 定 judge；"
        "ids_overlap 记录改写对/原文重合供审计，collide 打标不做硬断言（ids 重合本身合法）",
    }
    print(f"\n一致率 = {summary['pass_rate']}（{n_pass}/{n}）| 疑似缓存碰撞 {n_collide} 例")
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(OUT_DIR, f"consistency_{ts}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "summary": summary, "rows": rows}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"落盘：{out}")


if __name__ == "__main__":
    main()
