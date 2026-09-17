"""只读查询 app.db：按 rowid / 空格格式时间核查 run 落库情况。"""
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = con.cursor()

cur.execute("SELECT rowid, status, last_error_code, degraded_reason, created_at, conversation_id FROM agent_runs ORDER BY rowid DESC LIMIT 10")
print("--- latest 10 agent_runs by rowid ---")
for r in cur.fetchall():
    print(r)

cur.execute("SELECT COUNT(*) FROM agent_runs WHERE created_at >= '2026-09-08 17:45'")
print("runs since 17:45:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM agent_runs WHERE created_at >= '2026-09-08 13:00'")
print("runs since 13:00:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM messages WHERE created_at >= '2026-09-08 17:45'")
print("messages since 17:45:", cur.fetchone()[0])
cur.execute("SELECT rowid, role, substr(content,1,40), created_at FROM messages ORDER BY rowid DESC LIMIT 4")
print("--- latest messages ---")
for r in cur.fetchall():
    print(r)
con.close()