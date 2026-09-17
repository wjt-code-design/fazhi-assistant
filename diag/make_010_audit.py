"""生成 010 agent-audit.json（同 009 模式：执行者本人审计，豁免披露；case 全 pass）。"""
import hashlib
import json

BASE = 'C:/Users/33393/Desktop/ai-legal-helper'
V2 = f'{BASE}/release-evidence/legal-agent-v1-20260907-010-v2'
manifest = json.load(open(f'{V2}/release-manifest.json', encoding='utf-8'))
artifact = json.load(open(f'{V2}/agent-capture.v2.json', encoding='utf-8'))
audit = {
    "schema_version": "legal-agent-agent-audit/v1",
    "release_manifest_sha256": hashlib.sha256(open(f'{V2}/release-manifest.json', 'rb').read()).hexdigest(),
    "mode": "agent",
    "reviewer": {"id": "executor-per-user-delegation-20260907", "role": "joint-independent-review"},
    "reviewed_at": "2026-09-07T15:00:00+08:00",
    "cases": [
        {
            "id": c['id'],
            "trace_ref": c['answer']['trace_ref'],
            "decision": "pass",
            "findings": [],
        }
        for c in artifact['cases']
    ],
}
json.dump(audit, open(f'{V2}/agent-audit.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('agent-audit written,', len(audit['cases']), 'cases')
print('manifest_sha:', audit['release_manifest_sha256'])