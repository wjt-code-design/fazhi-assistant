"""只读：各表最新写入时间与 13:00 后行数，定位 13:00 后写库去向。"""
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = con.cursor()
cur.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'""")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [c[1] for c in cur.fetchall()]
        timecol = next((c for c in cols if "time" in c.lower() or "created" in c.lower() or "updated" in c.lower()), None)
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        if timecol:
            cur.execute(f"SELECT MAX({timecol}) FROM {t}")
            mx = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {timecol} >= '2026-09-08 13:00'")
            since = cur.fetchone()[0]
            print(f"{t:22s} rows={n:6d} max_{timecol}={str(mx)[:26]:26s} since13:00={since}")
        else:
            print(f"{t:22s} rows={n:6d} (no time col)")
    except Exception as e:
        print(f"{t:22s} ERROR {e}")
con.close()