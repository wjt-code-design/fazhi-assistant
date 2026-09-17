"""用修复后的 capture 适配器重评 010 采集（方括号引用补齐后 evidence 变化）。"""
import json
import sys

sys.path.insert(0, 'C:/Users/33393/Desktop/ai-legal-helper/backend')
from scripts.capture_eval import _split_sentences, _case_laws_for_sentence, _match_case_issues  # noqa: E402

CASES = 'C:/Users/33393/Desktop/ai-legal-helper/release-evidence/legal-agent-v1-20260907-010-v2/frozen-eval-cases.json'
cases = {c['id']: c for c in json.load(open(CASES, encoding='utf-8'))}

for mode, fn in [('rag', 'C:/Users/33393/Desktop/ai-legal-helper/diag/official-capture-010-rag/rows.json'),
                 ('agent', 'C:/Users/33393/Desktop/ai-legal-helper/diag/official-capture-010-agent/rows.json')]:
    rows = json.load(open(fn, encoding='utf-8'))
    changed = []
    for r in rows:
        cid = r['id']
        ans = r.get('answer') or ''
        case = cases[cid]
        # 重算 claims 绑定（与 capture 主流程同逻辑）
        bound_claims = []
        for sent in _split_sentences(ans):
            laws = _case_laws_for_sentence(sent, case.get('expected_laws', []))
            for law in laws:
                bound_claims.append(law)
        old_claims = set()
        for sc in r.get('claims_draft', []):
            old_claims.update(sc.get('evidence_ids', []))
        new_ev = sorted(set(bound_claims))
        old_ev = sorted(old_claims)
        if new_ev != old_ev:
            changed.append((cid, old_ev, new_ev))
    print(f'{mode}: claims evidence changed for {len(changed)} cases')
    for cid, old, new in changed:
        print('  ', cid, '| old:', old, '| new:', new)