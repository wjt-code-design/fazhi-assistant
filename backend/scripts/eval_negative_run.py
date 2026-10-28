"""低置信反问/拒答端到端评测（任务2，LawBench 弃答率范式）。

对 data/eval_negative.json 的 15 例走真实 chat API，按返回内容分类：
- out_of_kb（5 例）→ 期望拒答，或显式说明「知识库暂无该法全文」（2026-10-26 口径修正）
- abolished（2 例）→ 期望声明该法已废止并给出现行替代依据（2026-10-26 口径修正）
- underspecified（3 例）→ 期望反问澄清（clarify_rate）
- chitchat（2 例）→ 期望直接聊，不拒答不反问（chitchat_rate）
- intent_study_aid / intent_cheating（3 例）→ 期望走意图路径（不给条文堆砌/不给答案）

口径修正（2026-10-26）：abolished 原按「必须拒答」判，「原《合同法》第五十二条已被《民法典》
取代，现行依据为…」这种正确回答会被判红。现要求同时出现废止声明与现行替代依据。

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

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)

import _client  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

# 响应分类特征（与 clarify 模板/意图话术对齐；LLM 自由生成态视为"其他"）
REFUSE_MARK = "未收录"
CLARIFY_MARK = "缺少一些关键信息"
STUDY_MARK = "学习"
CHEAT_MARK = "答案"

# 2026-10-26 基线复核：弃答模板约 60 字，而实测有答复先给出完整「结论卡」实质作答，
# 只在句末补一句「…未收录于本知识库」。只查关键词会把这种答复判成拒答（假阳性），
# 故拒答必须同时满足「模板句在」且「答复很短」。
REFUSE_MAX_LEN = 200

# 已废止法律的正确行为：声明废止 + 指出现行替代依据（2026-10-26 口径修正）
ABOLISH_MARKS = ("废止", "失效", "取代")
REPLACEMENT_MARKS = ("民法典", "现行")

# 库外法源的「显式说明」措辞：E19 注记是代码写死的（`main.py`），但措辞避开
# `quality._HONEST_REFUSE_MARKS`，故两种历史写法都收（旧「未收录」口径仍可能在库外缓存里出现）。
OUT_OF_KB_ANSWERS = ("知识库暂无", "知识库未收录")


def _sse_chat(token: str, question: str) -> str:
    """调 chat API，拼 SSE content（429 由 _client 退避）。"""
    return _client.chat(token, question)


def classify_response(text: str) -> str:
    t = text.strip()
    if CLARIFY_MARK in t:
        return "clarify"
    # 拒答＝模板句在且答复短；长答复视为实质作答（哪怕句末附了未收录说明）
    if REFUSE_MARK in t and len(t) < REFUSE_MAX_LEN:
        return "refuse"
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
        # 期望：out_of_kb → 拒答或显式说明未收录；abolished → 废止声明+替代依据；underspecified → clarify；chitchat → 非refuse非clarify；intent → 意图路径
        if cat == "out_of_kb":
            # 口径修正（2026-10-26）：库外法不再要求整题拒答——「有检索依据时不为裸名
            # 拒答」是 2026-08-04 的刻意设计；但必须显式告知该法未收录，否则用户会以为
            # 答复依据就是它点名的那部法（系统会确定性追加「知识库暂无《X》全文」）。
            right = cls == "refuse" or any(m in resp for m in OUT_OF_KB_ANSWERS)
        elif cat == "abolished":
            # 2026-10-26 口径修正：正确行为是「声明废止 + 给出现行替代依据」，不是拒答
            right = any(m in resp for m in ABOLISH_MARKS) and any(m in resp for m in REPLACEMENT_MARKS)
        elif cat == "underspecified":
            right = cls == "clarify"
        elif cat == "chitchat":
            right = cls not in ("refuse", "clarify")
        elif cat == "intent_study_aid":
            # P2 收紧：不再用 cls=="other" 兜底，需命中学习引导话术或拒绝
            right = cls != "refuse" and (
                STUDY_MARK in resp or "引导" in resp or "分析" in resp or "帮你" in resp or "帮助" in resp
            )
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
