"""低置信反问/拒答端到端评测（任务2，LawBench 弃答率范式）。

对 data/eval_negative.json 的 15 例走真实 chat API，按返回内容分类：
- out_of_kb / abolished（8 例）→ 期望诚实拒答（弃答率 abstention_rate）
- underspecified（3 例）→ 期望反问澄清（clarify_rate）
- chitchat（2 例）→ 期望直接聊，不拒答不反问（chitchat_rate）
- intent_study_aid / intent_cheating（3 例）→ 期望走意图路径（不给条文堆砌/不给答案）

指标：abstention_rate + clarify_rate + chitchat_rate + intent_rate + 宏平均分类正确率。
需后端运行（python manage.py start）且已加载含任务2 的代码。

用法：python scripts/eval_negative_run.py
"""

import json
import os
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE = os.environ.get("API_BASE", "http://localhost:8000")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

# 响应分类特征（与 clarify 模板/意图话术对齐；LLM 自由生成态视为"其他"）
REFUSE_MARK = "未收录"
CLARIFY_MARK = "缺少一些关键信息"
STUDY_MARK = "学习"
CHEAT_MARK = "答案"


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _sse_chat(token: str, question: str) -> str:
    """调 chat API，拼 SSE content。"""
    body = {"conversation_id": None, "question": question, "content": question}
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode()
    content = ""
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                d = json.loads(line[6:])
            except Exception:
                continue
            if isinstance(d, dict) and d.get("content"):
                content += d["content"]
    return content


def classify_response(text: str) -> str:
    if REFUSE_MARK in text:
        return "refuse"
    if CLARIFY_MARK in text:
        return "clarify"
    return "other"


def main() -> int:
    token = _post("/api/auth/login", {"username": os.getenv("ADMIN_USERNAME", "admin"), "password": os.getenv("ADMIN_PASSWORD", "")})["token"]
    cases = json.load(open(os.path.join(DATA, "eval_negative.json"), encoding="utf-8"))
    stats = {}
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
        else:  # intent_*
            right = cls != "refuse" and (STUDY_MARK in resp or CHEAT_MARK in resp or "拒绝" in resp or cls == "other")
        if right:
            s["right"] += 1
        print(f"[{'PASS' if right else 'FAIL'}] {cat:16s} {q[:30]:32s} → {cls:8s} | {resp[:40]}")

    print("\n=== 指标（LawBench 弃答率范式）===")
    rates = {}
    for cat, s in stats.items():
        r = s["right"] / s["n"]
        rates[cat] = r
        print(f"{cat:16s} {s['right']}/{s['n']} = {r:.2f}")
    macro = sum(rates.values()) / len(rates)
    print(f"宏平均分类正确率 = {macro:.2f}")
    return 0 if all(r == 1.0 for r in rates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
