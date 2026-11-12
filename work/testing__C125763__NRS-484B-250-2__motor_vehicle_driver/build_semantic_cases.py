"""Build C125763's draft canonical case stage from its exact constructions.

The diagnostic cases remain unresolved legal probes. This builder does not
change selected case IDs, construction files, or physical acceptance status.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PROPOSALS = ROOT / 'proposals'
LAW = 'NRS-484B-250-2'


def main():
    cases_path = PROPOSALS / 'cases.json'
    document = json.loads(cases_path.read_text())
    selected = [item for item in document['cases'] if item['target_type'] != 'baseline']
    if len(selected) != 4:
        raise ValueError('Four exact selected C125763 cases required')
    binding_path = PROPOSALS / 'bindings.json'
    binding = json.loads(binding_path.read_text())
    if not any(item['name'] == 'other_approach_relation' for item in binding['variable_parameters']):
        binding['variable_parameters'].append({
            'name': 'other_approach_relation', 'kind': 'world_setup',
            'range_or_domain': 'source-grounded relative approach side or opposite direction',
            'used_by_laws': [LAW]})
    descriptions = []
    for item in selected:
        suffix = item['case_id'].removeprefix(ASSIGNMENT + '__')
        construction = json.loads((ROOT / 'cases' / suffix / 'construction.json').read_text())
        description = construction['recording_description']
        if item['recording_description'] != description:
            raise ValueError('Selected case recording description differs from construction: ' + suffix)
        descriptions.append(description)
        variables = item['variable_assignments']
        variables.update({
            'commanded_approach_speed': {'kind': 'controller', 'value': 5, 'unit': 'm/s'},
            'commanded_turn_path': {'kind': 'controller',
                                    'value': 'other_left_turn_waypoints' if suffix == 'yield_opposite_left_turn' else 'travel_waypoints',
                                    'unit': 'structured record'},
            'ego_speed': {'kind': 'subject_behavior', 'value': None, 'unit': 'm/s'},
            'opposite_direction_left_turn': {'kind': 'world_setup',
                                             'value': 'controller_intended' if suffix == 'yield_opposite_left_turn' else 'not_requested',
                                             'unit': 'categorical'},
            'other_approach_relation': {'kind': 'world_setup',
                                        'value': ('other_on_ego_left' if suffix == 'yield_ego_right_near_time'
                                                  else 'opposite_direction' if suffix == 'yield_opposite_left_turn'
                                                  else 'other_on_ego_right'),
                                        'unit': 'categorical'},
        })
        item['unresolved_judgment_calls'] = [
            'approximately the same time', 'yield the right-of-way',
            'official traffic-control devices', 'intending to or is making a left turn']
        item['deliberate_differences'] = (
            ['other_approach_relation'] if suffix == 'yield_ego_right_near_time' else
            ['other_release_frame'] if suffix == 'yield_ego_left_separated' else
            ['other_approach_relation', 'commanded_turn_path', 'opposite_direction_left_turn']
            if suffix == 'yield_opposite_left_turn' else [])
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Shared authored median-opening diagnostic reference; physical identity unverified',
                'variable_assignments': copy.deepcopy(selected[0]['variable_assignments']),
                'unresolved_judgment_calls': [],
                'recording_description': copy.deepcopy(descriptions[0])}
    document['cases'] = [baseline, *selected]
    document['status'] = 'draft'
    template = json.loads((PROPOSALS / 'template.json').read_text())
    sweeps = []
    for index, judgment in enumerate(template['structure']['judgment_calls_needed'], 1):
        sweeps.append({
            'sweep_id': f'c125763-{index}', 'target_law_id': LAW,
            'judgment_refs': [{'phrase': judgment['phrase'], 'note': judgment.get('note', '')}],
            'status': 'incomplete', 'mode': 'one_dimensional', 'axes': [], 'landmarks': [],
            'rationale': 'Exact CPU source probes exist; a physical judgment sweep needs verified Native motion and site geometry.',
            'variable_assignments': copy.deepcopy(baseline['variable_assignments']),
            'recording_description': copy.deepcopy(descriptions[0]),
            'missing_inputs': ['Verified Native motion, original site geometry, and physical sweep range for ' + judgment['phrase']]})
    document['sweep_specs'] = sweeps
    document['sweeps_expanded'] = False
    binding_path.write_text(json.dumps(binding, indent=2) + '\n')
    cases_path.write_text(json.dumps(document, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(selected), 'baseline': baseline['case_id'],
                      'judgment_sweep_plans': len(sweeps), 'status': 'draft'}))


if __name__ == '__main__':
    main()
