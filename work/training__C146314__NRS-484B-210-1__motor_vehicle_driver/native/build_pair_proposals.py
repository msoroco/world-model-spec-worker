"""Stage paragraph (d) case requests for exact CPU compatibility development."""
import json
from pathlib import Path

from build_selected_paragraph_d import recording

HERE = Path(__file__).resolve().parent
CASE = HERE.parent


def assignments(obstruction):
    return {
        'requested_right_lane_obstruction': {'kind': 'world_setup',
                                             'value': obstruction,
                                             'unit': 'categorical'},
        'commanded_right_pass': {'kind': 'controller', 'value': True,
                                 'unit': 'categorical'},
        'observed_right_pass': {'kind': 'subject_behavior', 'value': None,
                                'unit': 'structured'},
        'observed_one_way_designation': {'kind': 'subject_behavior',
                                         'value': None, 'unit': 'structured'}}


def build():
    plan = json.loads((CASE / 'case-plan.json').read_text())
    items = []
    baseline_id = CASE.name + '__baseline'
    items.append({'case_id': baseline_id, 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Shared authored paragraph (d) road and lead; no baseline recording selected.',
        'variable_assignments': assignments(None),
        'recording_description': recording(baseline_id),
        'unresolved_judgment_calls': ['Original legal one-way designation and obstruction significance require independent review.']})
    for suffix, obstruction in [('witness_1', False), ('witness_2', True)]:
        case_id = CASE.name + '__' + suffix
        source = next(c for c in plan['cases'] if c['case_id'] == case_id)
        items.append({'case_id': case_id, 'target_law_id': 'NRS-484B-210-1',
            'target_type': 'boundary_probe',
            'rationale': source['physical_target'] + '; legal and physical outcome unresolved.',
            'paired_probe_id': CASE.name + '__paragraph_d_pavement_pair',
            'deliberate_differences': ['requested_right_lane_obstruction'],
            'probe': {'primary_variable': 'requested_right_lane_obstruction',
                'comparison_or_standard': 'source-reviewed obstruction significance during right-side pass',
                'target_value_or_branch': {'requested_right_lane_obstruction': obstruction}},
            'variable_assignments': assignments(obstruction),
            'recording_description': recording(case_id),
            'unresolved_judgment_calls': ['Original legal one-way designation and obstruction significance require independent review.']})
    result = {'cell_id': 'C146314', 'actor': 'motor_vehicle_driver',
        'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True,
        'cases': items}
    target = CASE / 'proposals/cases.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return {'staged_cases': len(items) - 1,
            'remaining_cases': len(plan['cases']) - (len(items) - 1)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
