"""run-11 C02 证据取证：查 agent_evidence 表，对比金标法条。"""
import json
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cols = [r[1] for r in cur.execute("PRAGMA table_info(agent_evidence)")]
print("agent_evidence cols:", cols)

run_id = "259c38d5-7f6c-4b83-9c70-19333d363e9e"
rows = cur.execute("SELECT * FROM agent_evidence WHERE agent_run_id=?", (run_id,)).fetchall()
print(f"\nC02 evidence count:", len(rows))
for r in rows:
    d = {c: (str(v)[:300] if v is not None else None) for c, v in zip(cols, r)}
    print(json.dumps(d, ensure_ascii=False))

conn.close()