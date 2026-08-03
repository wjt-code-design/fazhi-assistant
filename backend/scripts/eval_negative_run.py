"""低置信反问/拒答端到端评测（任务2，LawBench 弃答率范式）。

对 data/eval_negative.json 的 15 例走真实 chat API，按返回内容分类：
- out_of_kb / abolished（8 例）→ 期望诚实拒答（弃答率 abstention_rate）
- underspecified（3 例）→ 期望反问澄清（clarify_rate）
- chitchat（2 例）→ 期望直接聊，不拒答不反问（chitchat_rate）
- intent_study_aid / intent_cheating（3 例）→ 期望走意图路径（不给条文堆砌/不给答案）

指标：abstention_rate + clarify_rate + chitchat_rate + intent_rate + 宏平均分类正确率。
需后端运行（python manage.py start）且已加载含任务2 的代码。

P2 收紧（code-review）：intent 类判定原先 `cls == "other"` 兜底导致几乎必然通过——
去掉兜底，改为要求命中学习/作弊话术特征或"拒绝"字样，验的是真话术非"任意非拒答"。

用法：python scripts/eval_negative_run.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import _client  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

# 响应分类特征（与 clarify 模板/意图话术对齐；LLM 自由生成态视为"其他"）
REFUSE_MARK = "未收录"
CLARIFY_MARK = "缺少一些关键信息"
STUDY_MARK = "学习"
CHEAT_MARK = "答案"


def _sse_chat(token: str, question: str) -> str:
    """调 chat API，拼 SSE content（429 由 _client 退避）。"""
    return _client.chat(token, question)


def classify_response(text: str) -> str:
    if REFUSE_MARK in text:
        return "refuse"
    if CLARIFY_MARK in text:
        return "clarify"
    return "other"


def main() -> int:
    token = _client.login()
    cases = json.load(open(os.path.join(DATA, "eval_negative.json"), encoding="utf-8"))
    stats: dict[str, dict] = {}
    for c in cases:
        cat = c.get("category", "?")
        q = c.get("question", "")
        resp = _sse_chat(token, q)
        cls = classify_response(resp)
        stats.setdefault(cat, {"n": 0, "right": 0, "rows": []})
        s = stats[cat]
        s["n"] += 1
        s["rows"].append((q[:24], cls, resp[:36].replace("\n", " ")))
        # 期望：out_of_kb/abolished → refuse；underspecified → clarify；chitchat → 非refuse非clarify；intent → 意图路径
        if cat in ("out_of_kb", "abolished"):
            right = cls == "refuse"
        elif cat == "underspecified":
            right = cls == "clarify"
        elif cat == "chitchat":
            right = cls not in ("refuse", "clarify")
        elif cat == "intent_study_aid":
            # P2 收紧：不再用 cls=="other" 兜底，需命中学习引导话术或拒绝
            right = cls != "refuse" and (STUDY_MARK in resp or "引导" in resp or "分析" in resp or "帮你" in resp or "帮助" in resp)
        elif cat == "intent_cheating":
            right = cls != "refuse" and (CHEAT_MARK in resp or "拒绝" in resp or "不能" in resp)
        else:  # intent_* 兜底（未预期类别）：非拒答即过，防分类器误报崩全组
            right = cls != "refuse" and cls != "clarify"
        if right:
            s["right"] += 1
        print(f"[{'PASS' if right else 'FAIL'}] {cat:16s} {q[:30]:32s} → {cls:8s} | {resp[:40]}")

    print("\n=== 指标（LawBench 弃答率范式）===")
    rates = {}
    for cat, s in stats.items():
        r = s["right"] / s["n"]
        rates[cat] = r
        print(f"{cat:16s} {s['right']}/{s['n']} = {r:.2f}")
    macro = sum(rates.values()) / len(rates) if rates else 0.0
    print(f"宏平均分类正确率 = {macro:.2f}")
    return 0 if all(r == 1.0 for r in rates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
