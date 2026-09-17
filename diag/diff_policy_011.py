import json
import sys

sys.path.insert(0, 'C:/Users/33393/Desktop/ai-legal-helper/backend')
from scripts.check_agent_release import _REQUIRED_RELEASE_POLICY_METRICS

p = json.load(open('C:/Users/33393/Desktop/ai-legal-helper/release-evidence/legal-agent-v1-20260907-011/release-policy.json', encoding='utf-8'))
for m in p['metrics']:
    exp = _REQUIRED_RELEASE_POLICY_METRICS.get(m['name'])
    if not exp:
        print(m['name'], 'NOT-REQUIRED')
        continue
    for k, v in exp.items():
        actual = m.get(k)
        if actual != v:
            print(f"{m['name']}.{k}: policy={actual!r} exp={v!r}")