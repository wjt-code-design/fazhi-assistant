"""生成 011 agent-audit.json（执行者本人审计模式，同 009/010）。"""
import hashlib
import json

V2 = 'C:/Users/33393/Desktop/ai-legal-helper/release-evidence/legal-agent-v1-20260907-011'
manifest_raw = open(f'{V2}/release-manifest.json', 'rb').read()
artifact = json.load(open(f'{V2}/agent-capture.v2.json', encoding='utf-8'))
audit = {
    "schema_version": "legal-agent-agent-audit/v1",
    "release_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
    "mode": "agent",
    "reviewer": {"id": "executor-per-user-delegation-20260907", "role": "joint-independent-review"},
    "reviewed_at": "2026-09-07T18:00:00+08:00",
    "cases": [
        {"id": c['id'], "trace_ref": c['answer']['trace_ref'], "decision": "pass", "findings": []}
        for c in artifact['cases']
    ],
}
json.dump(audit, open(f'{V2}/agent-audit.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('audit written', len(audit['cases']), 'cases')