"""取证：C09 run-8（唯一零错误的六段式成功案例）引用了什么 vs 金标要什么。"""
import json
import re

BASE = r"C:\Users\33393\Desktop\ai-legal-helper\release-evidence\legal-agent-v1-complex-v1-20260907"
d = json.load(open(BASE + r"\gate2-run-gate5-dev-run-8-sessions.json", encoding="utf-8"))
txt = d["results"]["C09"]["final_text"]
cites = re.findall(r"《([^》]{1,40})》第([0-9一二三四五六七八九十百零〇]+)条", txt)
print("C09 run-8 全部引用：")
for law, n in cites:
    print(" -", law, n)
print()
print("金标 required_laws：民法典:496, 民法典:497, 民法典:577, 消费者权益保护法:26")
print()
print("=== 六段式标题分布 ===")
for h in ["已确认事实", "尚不确定的事实", "核心法律争点", "法律依据", "分情形分析", "可执行建议与风险提示"]:
    i = txt.find(h)
    print(f"{h}: {'✓ 位置' + str(i) if i >= 0 else '✗ 缺失'}")