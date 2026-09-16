"""取证核心：C09 run-8 检索侧——工具实际召回了什么（服务端步骤记录 agent_evidence/agent_steps）。

问题：Agent 引用了民法典496/497/577 但缺消法26；检索到底召回没召回消法26？
"""
import sqlite3
import json

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = con.cursor()

# run-8 的 C09 会话：conversations created_at ~ 2026-09-08 16:2x UTC（第9题）
cur.execute("""SELECT id FROM conversations WHERE created_at >= '2026-09-08 16:00' AND created_at < '2026-09-08 16:40' ORDER BY id""")
conv_ids = [r[0] for r in cur.fetchall()]
print("run-8 窗口 conversations:", conv_ids)

for cid in conv_ids:
    cur.execute("SELECT id FROM agent_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 1", (cid,))
    row = cur.fetchone()
    if not row:
        continue
    run_id = row[0]
    cur.execute("SELECT tool_name, reason_code, result_summary, created_at FROM agent_steps WHERE agent_run_id=? ORDER BY created_at", (run_id,))
    steps = cur.fetchall()
    print(f"\n--- conv {cid} run {run_id[:8]} steps={len(steps)} ---")
    for tn, rc, rs, ts in steps:
        print(f"  [{ts[11:19]}] {tn} rc={rc} summary={(rs or '')[:180]}")
con.close()