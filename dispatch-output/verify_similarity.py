# 验收用一次性脚本：隐藏集 vs 开发集 initial_question 防照抄比对（字符 bigram Jaccard）
import json
import re


def norm(s: str) -> str:
    return re.sub(r"[\s，。、；：\"'（）()？！!…—·『』「」\[\]]", "", s)


def bigrams(s: str) -> set:
    s = norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()


T1 = r"C:\Users\33393\Desktop\ai-legal-helper\dispatch-output\task1"
hidden = json.load(open(T1 + r"\hidden-cases-v1.json", encoding="utf-8"))["cases"]
dev = json.load(
    open(
        r"C:\Users\33393\Desktop\ai-legal-helper\release-evidence\legal-agent-v1-complex-v1-20260907\frozen-cases-v1.json",
        encoding="utf-8",
    )
)["cases"]
devmap = {c["id"]: c.get("initial_question", "") for c in dev}

worst = (0.0, None)
for h in hidden:
    for did, dq in devmap.items():
        b1, b2 = bigrams(h.get("initial_question", "")), bigrams(dq)
        j = len(b1 & b2) / len(b1 | b2) if (b1 | b2) else 0.0
        if j > worst[0]:
            worst = (j, (h["id"], did))
        if j >= 0.3:
            print("HIGH SIM", h["id"], did, round(j, 3))
print("worst pair:", worst)

# verdict 通过数重算：统计各 run 逐题结论（含"不通过"次数 = 5 - 通过数）
for f in ["verdict-a.md", "verdict-b.md"]:
    txt = open(T1 + "\\" + f, encoding="utf-8").read()
    nf = txt.count("**不通过**")
    print(f, "不通过数 =", nf, "=> 通过 =", 5 - nf)