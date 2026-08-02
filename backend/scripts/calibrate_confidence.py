"""置信度标定（任务2）：对 eval 集跑 grounded_top_score（top1 余弦），
输出正负样本分布 → 人工读分界后回填 clarify.TH_LOW。

用法：python scripts/calibrate_confidence.py（真实 KB + 本地嵌入，约 30s）
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from retrieval import grounded_top_score  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


def dump(path: str, tag: str) -> None:
    cases = json.load(open(path, encoding="utf-8"))
    scores = []
    for c in cases:
        q = c.get("question") or ""
        if not q:
            continue
        scores.append((grounded_top_score(q), q[:34]))
    scores.sort(key=lambda t: t[0], reverse=True)
    print(f"--- {tag}（{len(scores)} 例）---")
    for s, q in scores:
        print(f"{s:.3f}  {q}")
    print()


if __name__ == "__main__":
    dump(os.path.join(DATA, "eval_set.json"), "正向 eval_set（应直接答）")
    dump(os.path.join(DATA, "eval_negative.json"), "负向 eval_negative（应拒答/反问/聊）")
