"""系统性根因分析：run-6/run-8 逐题失败面 + writer payload 侧证据（final 有产出的题到底缺什么）。"""
import json
import re

BASE = r"C:\Users\33393\Desktop\ai-legal-helper\release-evidence\legal-agent-v1-complex-v1-20260907"
HEADERS = ["已确认事实", "尚不确定的事实", "核心法律争点", "法律依据", "分情形分析", "可执行建议与风险提示"]

frozen = json.load(open(BASE + r"\frozen-cases-v1.json", encoding="utf-8"))["cases"]
REQ = {c["id"]: c.get("required_laws", []) for c in frozen}

for run in ["gate5-dev-run-6", "gate5-dev-run-8"]:
    d = json.load(open(BASE + rf"\gate2-run-{run}-sessions.json", encoding="utf-8"))
    print(f"===== {run} =====")
    for cid in sorted(d["results"]):
        r = d["results"][cid]
        txt = r.get("final_text", "")
        six = sum(1 for h in HEADERS if h in txt)
        cites = re.findall(r"《([^》]{1,40})》第([0-9一二三四五六七八九十百零〇]+)条", txt)
        # 数字条号转 int（简单）
        def cn2n(s):
            if s.isdigit():
                return int(s)
            m = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"百":100,"零":0}
            total, sec = 0, 0
            for ch in s:
                if ch in m:
                    v = m[ch]
                    if v == 100:
                        total += (sec or 1) * 100; sec = 0
                    else:
                        sec = v if sec == 0 or sec >= 10 else sec * 10 + v
            return total + sec
        got = {(law.strip(), cn2n(n)) for law, n in cites}
        need = {(str(x[0]), int(x[1])) for x in REQ.get(cid, [])}
        miss = need - got
        print(f"{cid} err={r['error_codes']} six={six}/6 cites={len(cites)} 缺金标依据={sorted(miss) if miss else '无'} chars={len(txt)}")