"""只读核查 §5 已知限制中可由既有证据验证的条目。

5.1 full_closure = 0/10（run-14 与 run-15 均如此）
5.2 run-14 completed 7/10 → run-15 completed 6/10
5.3 "5 争点需 19 步"是实测（run-15 C08）
5.6 run-14 的 C06 与 modelarm-qwen36 的 C07 预运行失败，分母 9 题
"""

from __future__ import annotations

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[2]
EV = ROOT / "release-evidence" / "legal-agent-v1-complex-v1-20260907"

RUNS = {
    "run-14": "gate5-dev-run-14-qwen38-t8",
    "run-15": "gate5-dev-run-15-qwen38-t8b",
    "run-13(qwen38对照)": "gate5-dev-run-13-qwen38",
    "qwen36(对照)": "gate5-dev-modelarm-qwen36",
}


def load(run: str) -> dict:
    return json.loads((EV / f"gate2-run-{run}-sessions.json").read_text(encoding="utf-8"))


print("=" * 74)
print("§5.1 / §5.2 — full_closure 与 completed 计数")
print("=" * 74)
for label, run in RUNS.items():
    d = load(run)
    res = d["results"]
    n = len(res)
    completed = sum(1 for c in res.values() if c.get("agent_completed"))
    # full_closure 的候选字段名探测
    keys = set()
    for c in res.values():
        keys |= set(c.keys())
    closure_keys = sorted(k for k in keys if "clos" in k.lower() or "full" in k.lower())
    fc = None
    if closure_keys:
        fc = sum(1 for c in res.values() if c.get(closure_keys[0]))
    print(f"  {label:<20} 题数={n:<3} agent_completed={completed}/{n}")
    print(f"      closure 相关字段 = {closure_keys if closure_keys else '（sessions.json 无此字段）'}")
    if closure_keys and fc is not None:
        print(f"      {closure_keys[0]} = {fc}/{n}")

print()
print("  注：full_closure 可能在 checkpoint.json 而非 sessions.json，下面单独探测。")
for label, run in RUNS.items():
    p = EV / f"gate2-run-{run}-checkpoint.json"
    if not p.exists():
        print(f"  {label:<20} checkpoint 不存在")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    hits = sorted(k for k in d.keys() if "clos" in k.lower() or "full" in k.lower())
    print(f"  {label:<20} checkpoint 顶层键={sorted(d.keys())[:10]}")
    if hits:
        for k in hits:
            v = d[k]
            print(f"        {k} = {v if not isinstance(v, (list, dict)) else type(v).__name__ + f'(len={len(v)})'}")

print()
print("=" * 74)
print("§5.3 — run-15 C08 的争点数与步数")
print("=" * 74)
d15 = load(RUNS["run-15"])
c08 = d15["results"].get("C08", {})
print(f"  C08 可用字段 = {sorted(c08.keys())}")
print(f"  C08 rounds = {len(c08.get('rounds') or [])}")
print(f"  C08 error_codes = {c08.get('error_codes')}")
print(f"  C08 agent_completed = {c08.get('agent_completed')}")
print(f"  C08 conv_id = {c08.get('conv_id')}")

print()
print("=" * 74)
print("§5.6 — 预运行失败（无 agent_run 记录）的题")
print("=" * 74)
for label, run in (("run-14", RUNS["run-14"]), ("qwen36", RUNS["qwen36(对照)"])):
    d = load(run)
    res = d["results"]
    no_record = [cid for cid in sorted(res) if not res[cid].get("agent_completed")]
    print(f"  {label:<8} agent_completed=False 的题 = {no_record}")
    print(f"           分母（completed 为真）= {sum(1 for c in res.values() if c.get('agent_completed'))}/10")
