"""审计：核验决策清单中的关键事实断言"""
import json
from pathlib import Path

R = Path('C:/Users/33393/Desktop/ai-legal-helper')

# 1) 各候选 sample_size（调次数 = sample_size × 2 模式 × 候选数）
print("=== 1) sample_size per candidate ===")
total_calls = 0
for d in sorted((R / 'release-evidence').iterdir()):
    rp = d / 'agent-report.json'
    if not rp.exists():
        continue
    rep = json.load(open(d / 'agent-report.json', encoding='utf-8'))
    n = rep.get('sample_size')
    total_calls += n * 2
    print(f"  {d.name}: sample_size={n}")
print(f"  TOTAL calls (all modes): {total_calls}")

# 2) 各候选 agent 路由题数
print("=== 2) routed counts ===")
for tag, d in [('009', 'official-capture-009-agent'), ('010', 'official-capture-010-agent'), ('011', 'official-capture-011-agent')]:
    rows = json.load(open(R / 'diag' / d / 'rows.json', encoding='utf-8'))
    routed = [r['id'] for r in rows if r.get('routed_agent')]
    print(f"  {tag}: {len(routed)} routed -> {routed}")

# 3) 路由题是否全走 clarification（查 trace 事件类型）
print("=== 3) routed cases clarification events ===")
for tag, d in [('010', 'official-capture-010-agent'), ('011', 'official-capture-011-agent')]:
    rows = json.load(open(R / 'diag' / d / 'rows.json', encoding='utf-8'))
    routed = [r['id'] for r in rows if r.get('routed_agent')]
    for cid in routed:
        p = R / 'diag' / d / f'{cid}.sse.json'
        try:
            ev = json.load(open(p, encoding='utf-8'))
            types = [e.get('type') for e in ev]
            has_clar = 'clarification' in types
            print(f"  {tag}/{cid}: clar={has_clar} types={types}")
        except Exception as e:
            print(f"  {tag}/{cid}: ERR {e}")