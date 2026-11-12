"""Prepare the fifth C158190 case's semantic and measurement bindings.

These files are review drafts. They do not select the case or alter existing
source-bound delivery receipts for the four selected cases.
"""

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TARGET = HERE / 'cases/through_mid'
CASE = HERE.name + '__yield_nearest_view_mid_speed'
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.measurement_contract import validate, verify_report


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    primary = next(row for row in proposal['cases'] if row['case_id'].endswith('__yield_nearest_view_through_approaches'))
    case = copy.deepcopy(primary)
    case['case_id'] = CASE
    case['rationale'] = ('Same governed approach and approaching through actor as the 2 m/s '
                         'view-speed case; compare a commanded 4 m/s view-stage target '
                         'without a legal speed cutoff or physical outcome claim.')
    case['variable_assignments']['commanded_view_speed']['value'] = 4.0
    write(TARGET / 'proposal-draft.json', case)

    plan = json.loads((HERE / 'case-plan.json').read_text())
    if CASE not in {row['case_id'] for row in plan['cases']}:
        plan['cases'].append({'case_id': CASE, 'target_law_id': 'NRS-484B-257-1',
                              'purpose': 'Same-traffic 4 m/s commanded view-stage comparison draft'})
    for row in plan['requirement_dispositions']:
        if row['status'] == 'selected_required' and CASE not in row['case_ids']:
            row['case_ids'].append(CASE)
    plan['planning_status'] = 'partial_draft_mid_speed_unselected'
    write(TARGET / 'case-plan-draft.json', plan)

    contract = json.loads((HERE / 'measurement-contract.json').read_text())
    write(TARGET / 'measurement-contract-draft.json', contract)
    construction = json.loads((TARGET / 'construction.json').read_text())
    code = next(row['content'] for row in construction['files'] if row['path'] == 'finalizer.py')
    rows = validate(contract, plan['requirement_dispositions'], code, CASE)
    fixture = REPO / '.runtime-work/c158190-mid-sources-v1/fixture'
    report = json.loads((REPO / '.runtime-work/c158190-mid-sources-v1/positive/analysis-report.json').read_text())
    measurements = verify_report(contract, report, fixture)
    if report['case_id'] != CASE or measurements['speed_at_closest_view_mps']['value'] != 4.0:
        raise ValueError('Mid-speed draft contract did not bind the intended case and measurement')
    print(json.dumps({'case_id': CASE, 'selected_requirements': len(rows),
                      'source_bound_measurements': len(measurements),
                      'measured_view_speed_mps': measurements['speed_at_closest_view_mps']['value'],
                      'selected_delivery_case': False}, indent=2))


if __name__ == '__main__':
    main()
