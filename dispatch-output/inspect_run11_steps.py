"""run-11 G2 扇出取证：查 agent_steps 确认 retrieve_laws 扇出是否发生。"""
import json
import sqlite3

DB = r"C:\Users\33393\Desktop\ai-legal-helper\backend\app.db"
with open(
    r"C:\Users\33393\Desktop\ai-legal-helper\release-evidence\legal-agent-v1-complex-v1-20260907\gate2-run-gate5-dev-run-11-sessions.json",
    encoding="utf-8",
) as f:
    data = json.load(f)

# 每个 case 的 conv_id
conv_map = {cid: r.get("conv_id") for cid, r in data["results"].items()}
print("conv map:", conv_map)

conn = sqlite3.connect(DB)
cur = conn.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(agent_steps)")]
print("agent_steps cols:", cols)

# 查 C02 的步骤流
for cid in ["C02"]:
    conv = conv_map[cid]
    if not conv:
        continue
    run = cur.execute("SELECT id FROM agent_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 1", (conv,)).fetchone()
    if not run:
        print(f"{cid}: no agent_run for conv {conv}")
        continue
    steps = cur.execute(
        "SELECT * FROM agent_steps WHERE agent_run_id=? ORDER BY created_at ASC LIMIT 60", (run[0],)
    ).fetchall()
    print(f"\n===== {cid} conv={conv} run={run[0]} steps={len(steps)} =====")
    for s in steps[:40]:
        d = {c: (str(v)[:220] if v is not None else None) for c, v in zip(cols, s)}
        print(json.dumps(d, ensure_ascii=False))

conn.close()