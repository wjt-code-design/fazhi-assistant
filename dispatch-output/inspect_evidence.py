"""取证核心2：检索质量——agent_evidence 表里 run-8 各 run 究竟 materialize 了哪些法条证据。

关键问题：缺的金标法条（如消法26、劳动合同法40）到底是 (a) 检索没召回，还是 (b) 召回了但被丢弃/没用。
"""
import sqlite3
import json

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = con.cursor()
cur.execute("PRAGMA table_info(agent_evidence)")
cols = [c[1] for c in cur.fetchall()]
print("agent_evidence cols:", cols)

runs = {
    "C09(2285)": "5f702685",
    "C08(2286)": "867e1eb5",
}
for label, prefix in runs.items():
    cur.execute("SELECT id FROM agent_runs WHERE id LIKE ?", (prefix + "%",))
    rid = cur.fetchone()
    if not rid:
        print(label, "run not found")
        continue
    rid = rid[0]
    cur.execute("SELECT COUNT(*) FROM agent_evidence WHERE agent_run_id=?", (rid,))
    n = cur.fetchone()[0]
    print(f"\n--- {label} run={rid[:8]} evidence rows={n} ---")
    cur.execute("""SELECT source_identifier, provenance, substr(snippet,1,60), source_type FROM agent_evidence WHERE agent_run_id=? LIMIT 25""", (rid,))
    for src, art, snip, st in cur.fetchall():
        print(f"  [{st}] {src} | {art}: {snip}")
con.close()