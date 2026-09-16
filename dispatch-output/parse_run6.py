"""解析 run-6 sessions：逐题错误/输出/六段式标题检查。"""
import json
import re

p = r"C:\Users\33393\Desktop\ai-legal-helper\release-evidence\legal-agent-v1-complex-v1-20260907\gate2-run-gate5-dev-run-6-sessions.json"
d = json.load(open(p, encoding="utf-8"))
res = d["results"]

HEADERS = ["已确认事实", "尚不确定的事实", "核心法律争点", "法律依据", "分情形分析", "可执行建议与风险提示"]

print("case | errors | final_chars | six_headers | final_text_head")
for cid in sorted(res.keys()):
    r = res[cid]
    txt = r.get("final_text", "")
    found = [h for h in HEADERS if h in txt]
    head = txt[:160].replace("\n", " ")
    print(f"{cid} | {';'.join(r['error_codes']) or '-'} | {r['final_chars']} | {len(found)}/{len(HEADERS)} {found} | {head}")

print("\n===== C05 full final_text =====")
print(res["C05"].get("final_text", ""))
print("\n===== C07 final_text (excerpt 400) =====")
print(res["C07"].get("final_text", "")[:400])