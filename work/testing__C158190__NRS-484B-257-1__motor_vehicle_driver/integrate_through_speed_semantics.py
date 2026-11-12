"""Bind exact through-speed drafts to C158190 semantics and requirements."""

import copy
import json
from pathlib import Path

from through_speed_sweep import TARGETS_MPS

ROOT = Path(__file__).resolve().parent
PREFIX = ROOT.name + '__'
BASE = PREFIX + 'yield_nearest_view_through_approaches'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    proposal_path = ROOT / 'proposals/cases.json'
    proposal = json.loads(proposal_path.read_text())
    base = next(item for item in proposal['cases'] if item['case_id'] == BASE)
    known = {item['case_id'] for item in proposal['cases']}
    ids = []
    for target in TARGETS_MPS:
        speed = int(target)
        ident = PREFIX + f'yield_nearest_view_through_speed_{speed}'
        ids.append(ident)
        if ident in known:
            continue
        case = copy.deepcopy(base)
        case['case_id'] = ident
        case['rationale'] = (f'Fixed governed approach with an approaching through actor; '
                             f'commanded through target {target:.1f} m/s for a physical '
                             'immediate-hazard judgment sweep, without a legal cutoff claim.')
        case['variable_assignments']['commanded_through_speed'] = {
            'kind': 'controller', 'value': target, 'unit': 'm/s'}
        case['paired_probe_id'] = 'c158190-through-speed-3-7-11'
        case['deliberate_differences'] = ['commanded_through_speed']
        case['probe'] = {'primary_variable': 'commanded_through_speed',
                         'comparison_or_standard': 'three-point controlled physical contrast; no legal outcome label',
                         'target_value_or_branch': target}
        proposal['cases'].append(case)
    write(proposal_path, proposal)

    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    known = {item['case_id'] for item in plan['cases']}
    for ident in ids:
        if ident not in known:
            plan['cases'].append({'case_id': ident, 'target_law_id': 'NRS-484B-257-1',
                                  'purpose': 'Three-point commanded through-speed judgment sweep'})
    for row in plan['requirement_dispositions']:
        if row['status'] == 'selected_required':
            for ident in ids:
                if ident not in row['case_ids']:
                    row['case_ids'].append(ident)
    comparison_id = 'same_approach_through_speed_3_7_11'
    if comparison_id not in {row['comparison_id'] for row in plan['comparisons']}:
        plan['comparisons'].append({
            'comparison_id': comparison_id, 'case_ids': ids,
            'deliberate_differences': ['commanded through-actor speed target: 3, 7, 11 m/s'],
            'fixed_conditions': ['same yield sign and authored road geometry',
                                 'same ego spawn, speed controller and approach trajectory',
                                 'same through actor spawn, four cameras and duration']})
    write(plan_path, plan)
    print(json.dumps({'exact_cases': ids, 'proposal_cases': len(proposal['cases']),
                      'planned_cases': len(plan['cases']), 'selected_delivery_manifest_changed': False}))


if __name__ == '__main__':
    main()
