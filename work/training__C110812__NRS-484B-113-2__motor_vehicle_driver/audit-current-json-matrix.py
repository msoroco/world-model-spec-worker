"""Verify fresh JSON-graph compatibility receipts and controlled branch values."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    rows = json.loads((HERE / 'current-json-compat-summary.json').read_text())['rows']
    entries = {e['case_id']: e for e in json.loads((HERE / 'draft-execution-manifest.json').read_text())['cases']}
    seen, pairs = set(), {}
    for row in rows:
        case, candidate = row['case_id'], row['candidate_id']
        if case not in entries or (case, candidate) in seen:
            raise ValueError('Foreign or duplicate exact candidate')
        seen.add((case, candidate))
        entry = entries[case]
        ref = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
        for name, digest in (('offline_log', 'offline_log_sha256'),
                             ('compatibility_log', 'compatibility_log_sha256'),
                             ('receipt', 'receipt_sha256'),
                             ('negative_log', 'negative_log_sha256')):
            if sha(HERE / row[name]) != row[digest]:
                raise ValueError('Proof file changed: ' + row[name])
        proof = json.loads((HERE / row['receipt']).read_text())
        if not proof['passed'] or proof['case_id'] != case or proof['candidate_id'] != candidate or \
           proof['construction_sha256'] != ref['construction_sha256'] or \
           proof['fixture_recipe_sha256'] != sha(ROOT / entry['fixture_recipe']) or \
           proof['measurement_contract_sha256'] != sha(HERE / entry['measurement_contract']):
            raise ValueError('Candidate or source binding differs')
        if not {'actual_analysis', 'native_validation', 'lean_decoder', 'render',
                'final_decode', 'four_camera_sources', 'derived_outputs_rebuilt',
                'selected_measurements', 'negative_case_source'} <= set(proof['checks']):
            raise ValueError('Compatibility checks incomplete')
        if proof['negative_log_sha256'] != row['negative_log_sha256'] or \
           proof['negative_error_contains'] not in (HERE / row['negative_log']).read_text():
            raise ValueError('Missing-source rejection absent')
        measures = proof['measurement_examples']['backing_corner_relation']['value']
        pairs[(case.rsplit('__', 1)[-1], candidate)] = (
            measures['relation'], measures['max_reverse_heading_change_deg'])
    if len(seen) != 8:
        raise ValueError('Eight current exact candidates required')
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if pairs[('false', candidate)] != ('backing_straight_through_intersection', 0) or \
           pairs[('true', candidate)] != ('backing_around_street_corner', 90.0):
            raise ValueError('Controlled reverse comparison changed')
    print(json.dumps({'passed': True, 'candidates': len(seen),
                      'comparison': 'straight versus corner reverse',
                      'scope': 'synthetic diagnostics; no physical acceptance'}))


if __name__ == '__main__':
    audit()
