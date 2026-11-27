"""Bind checked taxi constructions to selected CPU preparation records."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150173-owner'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def main():
    draft = json.loads((BASE / 'selected-draft-manifest.json').read_text())
    case_plan = json.loads((BASE / 'case-plan.json').read_text())
    if len(draft['cases']) != 7 or len(case_plan['comparisons']) != 5:
        raise ValueError('Exact seven-case passenger/freight plan required')
    public_summary = BASE / 'native-selected' / 'public-compatibility-summary.json'
    saved_summary = BASE / 'native-selected' / 'saved-processing-summary.json'
    comparison_summary = BASE / 'native-selected' / 'saved-comparison-summary.json'
    for proof in (public_summary, saved_summary, comparison_summary):
        if not proof.is_file():
            raise ValueError('Missing selected public/saved proof: ' + proof.name)
    entries = []
    for item in draft['cases']:
        case_id = item['case_id']
        suffix = case_id.rsplit('__', 1)[1]
        version = 'v24' if suffix.startswith('freight_') else 'v18'
        contract_path = BASE / 'native-selected' / suffix / 'measurement-contract.json'
        if not contract_path.is_file():
            raise ValueError('Missing selected measurement contract: ' + suffix)
        recipe_path = (BASE / 'native' /
                       ('freight-diagnostic' if suffix.startswith('freight_') else 'diagnostic') /
                       suffix / 'fixture-recipe.json')
        if not recipe_path.is_file():
            raise ValueError('Missing exact taxi CPU diagnostic recipe: ' + suffix)
        receipt_map = {}
        for candidate in ('primary', 'fallback1'):
            source = SCRATCH / f'selected-offline-{suffix}-{candidate}-{version}' / 'offline.log'
            if not source.exists() or 'OK' not in source.read_text():
                raise ValueError('Missing passing exact offline check: ' + suffix + ' ' + candidate)
            retained = BASE / 'native-selected' / suffix / (candidate + '-offline.log')
            retained.write_text(source.read_text().strip() + '\n')
            receipt_map[candidate] = {'exit_code': 0,
                                      'log': str(retained.relative_to(BASE)),
                                      'log_sha256': digest(retained),
                                      'construction_sha256': item['construction_sha256'] if candidate == 'primary'
                                      else item['candidates'][0]['construction_sha256']}
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': item['construction'],
                        'construction_sha256': item['construction_sha256'],
                        'candidate_risk': item['candidate_risk'],
                        'candidates': item['candidates'],
                        'measurement_contract': str(contract_path.relative_to(BASE)),
                        'measurement_contract_sha256': digest(contract_path),
                        'fixture_recipe': str(recipe_path.relative_to(ROOT)),
                        'fixture_recipe_sha256': digest(recipe_path),
                        'offline_cpu': receipt_map,
                        'compatibility': {
                            'summary': str(public_summary.relative_to(BASE)),
                            'summary_sha256': digest(public_summary)},
                        'saved_processing': {
                            'summary': str(saved_summary.relative_to(BASE)),
                            'summary_sha256': digest(saved_summary)},
                        'delivery_audit': 'pending'})
    selected = {'format': 'c150173-selected-cpu-preparation-v1',
                'assignment_id': BASE.name, 'delivery_ready': False,
                'original_native_observed': False, 'cases': entries,
                'comparison_ids': [x['comparison_id'] for x in case_plan['comparisons']],
                'independent_request_audit': 'native/audit_draft_comparisons.py',
                'independent_saved_source_audit': 'native/audit_original.py',
                'independent_saved_source_audit_sha256': digest(BASE / 'native' / 'audit_original.py'),
                'independent_saved_comparison_audit': 'native/audit_saved_comparison.py',
                'independent_saved_comparison_audit_sha256': digest(BASE / 'native' / 'audit_saved_comparison.py'),
                'saved_comparison_summary': str(comparison_summary.relative_to(BASE)),
                'saved_comparison_summary_sha256': digest(comparison_summary),
                'source_authority_status': 'unverified', 'legal_verdict': None}
    write(BASE / 'native-selected-cpu.json', selected)
    print(json.dumps({'cases': len(entries), 'offline_receipts': len(entries) * 2,
                      'selected_cpu_sha256': digest(BASE / 'native-selected-cpu.json')}))


if __name__ == '__main__':
    main()
