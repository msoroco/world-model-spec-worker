"""Independent binding audit of eight current-runtime recipe receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary = json.loads((HERE / 'current-v2-summary.json').read_text())
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    entries = {e['case_id']: e for e in manifest['cases']}
    seen = set()
    pairs = {}
    for item in summary['candidates']:
        for name, hash_name in (('receipt', 'receipt_sha256'),
                                ('analysis_log', 'analysis_log_sha256'),
                                ('negative_log', 'negative_log_sha256')):
            if sha(HERE / item[name]) != item[hash_name]:
                raise ValueError('Current proof file changed: ' + item[name])
        proof = json.loads((HERE / item['receipt']).read_text())
        case = item['case_id']; candidate = item['candidate_id']
        if (case, candidate) in seen or case not in entries:
            raise ValueError('Duplicate or foreign case candidate')
        seen.add((case, candidate))
        entry = entries[case]
        ref = entry if candidate == 'primary' else next(
            (r for r in entry['candidates'] if r['id'] == candidate), None)
        if not ref or sha(HERE / ref['construction']) != ref['construction_sha256']:
            raise ValueError('Exact candidate construction changed')
        if proof['case_id'] != case or proof['candidate_id'] != candidate or \
           proof['construction_sha256'] != ref['construction_sha256'] or \
           proof['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or \
           proof['fixture_recipe_sha256'] != sha(ROOT / entry['fixture_recipe']) or \
           proof['measurement_contract_sha256'] != sha(HERE / entry['measurement_contract']):
            raise ValueError('Current proof identity or input binding differs')
        if proof['passed'] is not True or not {
            'actual_analysis', 'native_validation', 'lean_decoder', 'render',
            'final_decode', 'four_camera_sources', 'derived_outputs_rebuilt',
            'selected_measurements', 'negative_case_source'} <= set(proof['checks']):
            raise ValueError('Incomplete current proof')
        if proof['negative_log_sha256'] != item['negative_log_sha256'] or \
           proof['negative_error_contains'] not in (HERE / item['negative_log']).read_text():
            raise ValueError('Current negative rejection missing')
        if proof['log_sha256'] != item['analysis_log_sha256']:
            raise ValueError('Analysis log differs')
        measurements = proof['measurement_examples']
        relation = measurements['backing_corner_relation']['value']['relation']
        heading = measurements['backing_corner_relation']['value']['max_reverse_heading_change_deg']
        pairs[(case.split('__')[-1], candidate)] = (relation, heading)
    if len(seen) != 8:
        raise ValueError('Eight exact current-runtime candidates required')
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if pairs[('false', candidate)] != ('backing_straight_through_intersection', 0) or \
           pairs[('true', candidate)] != ('backing_around_street_corner', 90.0):
            raise ValueError('Controlled pair measurements differ')
    print(json.dumps({'passed': True, 'receipts': len(seen),
                      'comparison': 'straight reverse versus corner reverse',
                      'scope': 'synthetic unselected; no physical acceptance'}))


if __name__ == '__main__':
    main()
