"""Add the 4 m/s same-traffic case to canonical planning for CPU compatibility.

The separate manifest is diagnostic; it does not select this case for delivery.
"""

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / 'cases/through_mid'
CASE = HERE.name + '__yield_nearest_view_mid_speed'
PRIMARY = HERE.name + '__yield_nearest_view_through_approaches'


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    proposal_path = HERE / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    if CASE not in {row['case_id'] for row in proposal['cases']}:
        proposal['cases'].append(json.loads((TARGET / 'proposal-draft.json').read_text()))
        write(proposal_path, proposal)

    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if CASE not in {row['case_id'] for row in plan['cases']}:
        plan['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-257-1',
                              'purpose': 'Same-traffic 4 m/s commanded view-stage comparison'})
    for row in plan['requirement_dispositions']:
        if row['status'] == 'selected_required' and CASE not in row['case_ids']:
            row['case_ids'].append(CASE)
    comparison = 'same_approaching_traffic_view_speed_2_vs_4'
    if comparison not in {row['comparison_id'] for row in plan['comparisons']}:
        plan['comparisons'].append({
            'comparison_id': comparison, 'case_ids': [PRIMARY, CASE],
            'deliberate_differences': ['commanded view-stage ego target: 2 m/s versus 4 m/s'],
            'fixed_conditions': ['governing yield sign and absent stop line/near crosswalk',
                                 'same approaching through actor and start location',
                                 'same authored road geometry, cameras and 30-second duration'],
        })
    write(plan_path, plan)

    selected = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = copy.deepcopy(selected['cases'][0])
    for key in ('candidates', 'negative', 'offline', 'compatibility', 'delivery_acceptance'):
        entry.pop(key, None)
    construction = TARGET / 'construction.json'
    entry.update(case_id=CASE, kind='diagnostic_unselected',
                 construction='cases/through_mid/construction.json',
                 construction_sha256=hashlib.sha256(construction.read_bytes()).hexdigest(),
                 measurement_contract='cases/through_mid/measurement-contract-draft.json',
                 fixture_recipe=str((TARGET / 'diagnostic-recipe.json').relative_to(HERE.parents[1])),
                 candidate_risk={'status': 'physical',
                                 'reason': 'realized 4 m/s view speed, through-actor timing and four-camera visibility require Native source review'})
    manifest_path = HERE / 'mid-speed-compatibility-manifest.json'
    if manifest_path.exists():
        separate = json.loads(manifest_path.read_text())
        current = separate['cases'][0]
        for key in ('case_id', 'construction', 'construction_sha256',
                    'measurement_contract', 'fixture_recipe'):
            if current.get(key) != entry[key]:
                raise ValueError('Existing fifth-case proof manifest changed: ' + key)
    else:
        separate = {key: selected[key] for key in ('format', 'assignment_id', 'runtime_manifest_sha256')}
        separate['cases'] = [entry]
        write(manifest_path, separate)
    print(json.dumps({'case_id': CASE, 'proposal_cases': len(proposal['cases']),
                      'planned_cases': len(plan['cases']), 'comparison': comparison,
                      'selected_delivery_manifest_changed': False}, indent=2))


if __name__ == '__main__':
    main()
