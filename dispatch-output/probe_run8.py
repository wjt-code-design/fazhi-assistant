"""只读：run-8（本地 23:14 起 = UTC 15:14）是否产生 agent_run/agent_steps（确认 Agent 路径生效）。"""
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = con.cursor()
cur.execute("SELECT COUNT(*), MAX(created_at) FROM agent_runs WHERE created_at >= '2026-09-08 15:10'")
n, mx = cur.fetchone()
print("agent_runs since 15:10UTC:", n, "| latest:", mx)
cur.execute("SELECT COUNT(*) FROM agent_steps WHERE created_at >= '2026-09-08 15:10'")
print("agent_steps since 15:10UTC:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM messages WHERE created_at >= '2026-09-08 15:10'")
print("messages since 15:10UTC:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM conversations WHERE created_at >= '2026-09-08 15:10'")
print("conversations since 15:10UTC:", cur.fetchone()[0])
con.close()