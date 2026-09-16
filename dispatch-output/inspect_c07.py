"""C07 失败取证：查 messages + audit_logs 中 run-11 时段记录。"""
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

if "messages" in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cols = [r[1] for r in cur.execute("PRAGMA table_info(messages)")]
    print("messages cols:", cols)
    rows = cur.execute(
        "SELECT * FROM messages WHERE created_at >= '2026-09-09 07:00' ORDER BY created_at ASC LIMIT 40"
    ).fetchall()

if "audit_logs" in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cols2 = [r[1] for r in cur.execute("PRAGMA table_info(audit_logs)")]
    print("\naudit_logs cols:", cols2)
    rows2 = cur.execute(
        "SELECT * FROM audit_logs ORDER BY rowid DESC LIMIT 15"
    ).fetchall()
    for r in rows2:
        print("audit:", {c: str(v)[:150] for c, v in zip(cols2, r)})

conn.close()