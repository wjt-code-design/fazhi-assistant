import json
from pathlib import Path

R = Path('C:/Users/33393/Desktop/ai-legal-helper/release-evidence')
rows = []
for d in sorted(R.iterdir()):
    if not (d / 'agent-report.json').exists():
        continue
    cid = d.name
    try:
        a = json.load(open(d / 'agent-report.json', encoding='utf-8'))
        r = json.load(open(d / 'existing-rag-report.json', encoding='utf-8'))
        rows.append((cid,
                     round(r['metrics']['complex_task_quality'], 4),
                     round(a['metrics']['complex_task_quality'], 4),
                     round(a['metrics']['issue_recall'], 4),
                     round(a['metrics']['evidence_coverage'], 4),
                     round(a['metrics']['clarification_precision'], 4),
                     a['metrics']['fact_hallucinations'] + a['metrics']['permission_bypasses'] + a['metrics']['infinite_loops'] + a['metrics']['illegal_citations']))
    except Exception as e:
        rows.append((cid, 'ERR', str(e)[:60], '', '', '', ''))
for r in rows:
    print(r)