"""011 agent 采集：loan-limitations-01 / law-date-conflict-15 失败行重采合并。
纪律：新 execution id（eval011-agent-retry2-20260907）；原失败行保留在 rows.json；
backup 保留原 agent-capture。"""
import json
import shutil

BASE = 'C:/Users/33393/Desktop/ai-legal-helper'
AG = f'{BASE}/release-evidence/legal-agent-v1-20260907-011/agent-capture.json'
RETRY = f'{BASE}/diag/011-agent-retry2-draft.json'
BACKUP = f'{BASE}/diag/official-011-agent-capture.json.fail2-orig'

shutil.copy2(AG, BACKUP)
retry = json.load(open(RETRY, encoding='utf-8'))
by_id = {c['id']: c for c in retry['cases']}
ag = json.load(open(AG, encoding='utf-8'))
replaced = []
for i, c in enumerate(ag['cases']):
    if c['id'] in by_id:
        ag['cases'][i] = by_id[c['id']]
        replaced.append(c['id'])
json.dump(ag, open(AG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('replaced:', replaced)
print('backup:', BACKUP)