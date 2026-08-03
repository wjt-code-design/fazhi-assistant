"""相关性评测（基准步骤4）：eval_set 抽 10 例真实问答，LLM judge 打分是否答所问。

判定：0=答非所问 1=部分相关 2=完全相关（准确回答）。通过率 = (1+2) 分占比。
诚实标注：单一 judge（qwen3.7-plus）、无人工金标——相关性是主观度量，数字仅供参考。

用法：python scripts/eval_relevance.py（10 例 × chat + judge ≈ 20 次 LLM）
输出：docs/benchmark_results/relevance_<ts>.json
"""

import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from llm_registry import registry  # noqa: E402

BASE = os.getenv("API_BASE", "http://localhost:8000")
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "..", "docs", "benchmark_results")
N_SAMPLE = 10

_JUDGE_SYS = (
    "你是回答相关性评审。用户问了一个法律问题，助手给出回答。"
    "判断回答是否回应了用户的问题：2=完全相关且正面回应问题，1=部分相关（擦边/泛泛），0=答非所问。"
    "只输出一个数字 0/1/2。"
)


def _login() -> str:
    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"username": os.getenv("ADMIN_USERNAME", "admin"), "password": os.getenv("ADMIN_PASSWORD", "")}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["token"]


def _chat(token: str, q: str) -> str:
    body = {"conversation_id": None, "question": q, "content": q}
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    out = ""
    with urllib.request.urlopen(req, timeout=180) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data: "):
                continue
            raw = line[6:]
            if raw == "[DONE]":
                break
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if isinstance(d, dict) and d.get("content"):
                out += d["content"]
    return out


def _judge(llm, q: str, ans: str) -> int:
    msgs = [SystemMessage(content=_JUDGE_SYS), HumanMessage(content=f"问题：{q}\n回答：{ans[:600]}")]
    try:
        out = str(llm.invoke(msgs)).strip()
        for ch in out:
            if ch in "012":
                return int(ch)
    except Exception:
        pass
    return 0


def main() -> None:
    token = _login()
    llm = registry.get()
    cases = [c for c in json.load(open(os.path.join(DATA, "eval_set.json"), encoding="utf-8")) if c.get("question")]
    sample = cases[:N_SAMPLE]
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for i, c in enumerate(sample, 1):
        q = c["question"]
        ans = _chat(token, q)
        score = _judge(llm, q, ans)
        rows.append({"q": q[:20], "score": score})
        print(f"[{i}/{len(sample)}] score={score} {q[:22]}")
        time.sleep(0.3)  # 给限流留余量

    n_pass = sum(1 for r in rows if r["score"] >= 1)
    n_full = sum(1 for r in rows if r["score"] == 2)
    result = {
        "ts": time.strftime("%Y%m%d-%H%M%S"),
        "n": len(rows),
        "relevance_rate_ge1": round(n_pass / len(rows), 4),  # 完全/部分相关占比
        "full_relevance_rate": round(n_full / len(rows), 4),  # 完全相关占比
        "note": "单一 judge（qwen3.7-plus），无人工金标——相关性主观，仅供参考",
        "scores": [r["score"] for r in rows],
    }
    print(f"\n=== 相关性 ===\n相关（≥1）占比 {result['relevance_rate_ge1']}（{n_pass}/{len(rows)}）| 完全相关 {result['full_relevance_rate']}（{n_full}/{len(rows)}）")
    out = os.path.join(OUT_DIR, f"relevance_{result['ts']}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"结果落盘：{out}")


if __name__ == "__main__":
    main()
