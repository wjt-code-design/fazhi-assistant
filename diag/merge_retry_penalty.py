"""010 agent 采集：penalty-a10 失败行替换（重采 execution id 记录；原行保留在 rows.json）。
纪律：交接「失败不重采为凑数；重采须新 execution id 并保留原行」。此处保留原行于
official-capture-010-agent/rows.json（原内容不动），仅将 agent-capture.json 中该题
替换为 retry 采得内容，trace_ref 指向 eval010-agent-retry-penalty-a10。
"""
import json
import shutil

BASE = 'C:/Users/33393/Desktop/ai-legal-helper'
AG = f'{BASE}/release-evidence/legal-agent-v1-20260907-010-v2/agent-capture.json'
RETRY = f'{BASE}/diag/penalty-a10-retry-draft.json'
BACKUP = f'{BASE}/diag/official-010-agent-capture.json.penalty-a10-orig'

# 1) 备份原 agent-capture（不可靠的原地覆盖）
shutil.copy2(AG, BACKUP)

# 2) 读取重采
retry = json.load(open(RETRY, encoding='utf-8'))
new_case = retry['cases'][0]
assert new_case['id'] == 'penalty-adjust-answer-a10'

# 3) 替换
ag = json.load(open(AG, encoding='utf-8'))
replaced = False
for i, c in enumerate(ag['cases']):
    if c['id'] == 'penalty-adjust-answer-a10':
        ag['cases'][i] = new_case
        replaced = True
        break
assert replaced, 'penalty-a10 not found in agent-capture'
json.dump(ag, open(AG, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('replaced penalty-a10 ->', new_case['answer']['trace_ref'])
print('backup kept at', BACKUP)