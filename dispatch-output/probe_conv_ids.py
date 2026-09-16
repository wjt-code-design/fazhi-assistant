"""决定性验证：run-4/6 sessions 中的 conv_id 是否存在于 app.db conversations 表。"""
import json
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = con.cursor()

run_conv_ids = {}
for run, fname in [("gate5-dev-run-4", "gate2-run-run-4-cont-sessions.json"),
                   ("gate5-dev-run-6", "gate2-run-gate5-dev-run-6-sessions.json")]:
    p = rf"C:\Users\33393\Desktop\ai-legal-helper\release-evidence\legal-agent-v1-complex-v1-20260907\{fname}"
    d = json.load(open(p, encoding="utf-8"))
    for cid, r in d["results"].items():
        run_conv_ids.setdefault(run, {})[cid] = r.get("conv_id")

for run, m in run_conv_ids.items():
    print(f"--- {run} ---")
    for cid, conv in sorted(m.items()):
        if conv is None:
            print(f"{cid}: conv_id=None")
            continue
        cur.execute("SELECT COUNT(*) FROM conversations WHERE id=?", (conv,))
        exists = cur.fetchone()[0] > 0
        if exists:
            cur.execute("SELECT created_at FROM conversations WHERE id=?", (conv,))
            ts = cur.fetchone()[0]
        else:
            ts = None
        print(f"{cid}: conv={conv} in_db={exists} created={ts}")
con.close()