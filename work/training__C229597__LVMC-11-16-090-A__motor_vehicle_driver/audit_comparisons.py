"""Audit exact C229597 construction isolation and CPU receipt coverage.

The synthetic fixtures do not establish distinct realized motion or legal outcomes.
"""
import argparse
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
INVARIANT = ('cell_id', 'law_id', 'actor', 'duration_s', 'rate_hz',
             'vehicle_blueprint', 'required_atoms', 'source_packets', 'cameras')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison_id, remove_case=False):
    plan = read(PACKAGE / 'case-plan.json')
    comparison = next((item for item in plan['comparisons']
                       if item['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown exact comparison')
    entries = {item['case_id']: item for item in read(PACKAGE / 'execution-manifest.json')['cases']}
    ids = list(comparison['case_ids'])
    if remove_case:
        ids.pop()
    if set(ids) != set(comparison['case_ids']):
        raise ValueError('Comparison missing exact planned case')
    if len(ids) < 2:
        raise ValueError('Comparison requires at least two exact cases')
    configurations = []
    targets = []
    for case in ids:
        entry = entries.get(case)
        if entry is None:
            raise ValueError('Comparison missing exact delivery case')
        construction_path = PACKAGE / entry['construction']
        if sha(construction_path) != entry['construction_sha256']:
            raise ValueError('Comparison construction hash changed')
        construction = read(construction_path)
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        if config['selected_case_id'] != case or config['case']['case_id'] != case:
            raise ValueError('Comparison case identity changed')
        for key in ('offline', 'compatibility', 'saved_processing', 'delivery_acceptance'):
            if key not in entry:
                raise ValueError('Comparison lacks CPU receipt: ' + key)
        receipt = read(PACKAGE / entry['compatibility']['receipt'])
        saved = read(PACKAGE / entry['saved_processing']['receipt'])
        if (not receipt['passed'] or receipt['construction_sha256'] != entry['construction_sha256']
                or not saved['passed'] or saved['analysis_revision']['construction_sha256'] != entry['construction_sha256']
                or saved['legal_acceptance_claimed'] or saved['physical_acceptance_claimed']):
            raise ValueError('Comparison CPU receipt differs or claims physical acceptance')
        configurations.append(config)
        targets.append(config.get('sweep_target'))
    for key in INVARIANT:
        if any(config.get(key) != configurations[0].get(key) for config in configurations[1:]):
            raise ValueError('Comparison fixed condition changed: ' + key)
    if comparison_id.endswith('__comparison_main'):
        phases = [config['control_phases'] for config in configurations]
        if len(phases) != 2 or phases[0] == phases[1]:
            raise ValueError('Main comparison lacks planned controller difference')
        for a, b in zip(phases[0], phases[1]):
            for key in ('name', 'first_frame', 'last_frame', 'steer', 'brake'):
                if a[key] != b[key]:
                    raise ValueError('Main comparison changed non-target controller setting')
        axis = 'requested_throttle_profile'
    else:
        if len(ids) != 3 or len(set(targets)) != 3 or any(value is None for value in targets):
            raise ValueError('Canonical sweep lacks three distinct planned targets')
        if any(config['control_phases'] != configurations[0]['control_phases']
               for config in configurations[1:]):
            raise ValueError('Canonical sweep changed baseline controller phases')
        if any(config.get('sweep_kind') != configurations[0].get('sweep_kind')
               for config in configurations[1:]):
            raise ValueError('Canonical sweep changed axis kind')
        axis = comparison['deliberate_differences'][0]
    return {'format': 'c229597-cpu-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': ids, 'passed': True,
            'fixed_conditions_checked': list(INVARIANT), 'planned_axis': axis,
            'planned_targets': targets, 'original_response_measured': False,
            'legal_outcome_claimed': False, 'native_executed': False,
            'scope': 'exact construction and diagnostic receipt isolation only'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--remove-case', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.remove_case), indent=2))
