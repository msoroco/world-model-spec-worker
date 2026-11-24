"""Source-grounded canonical draft stages for the selected signed U-turn pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'
LAW = 'NRS-484B-403-2'
ACTOR = 'motor_vehicle_driver'
QUOTE = 'If an official traffic-control device indicates that a U-turn is prohibited, the driver shall obey the directions of the device.'


def put(name, data):
    path = PROPOSALS / name
    path.write_text(json.dumps(data, indent=2) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    rel = {'cell_id': 'C104538', 'actor': ACTOR, 'status': 'draft',
           'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
                              'relevance_type': 'direct', 'confidence': 'high',
                              'notes': 'The frozen turn-prohibition device and driver U-turn cell directly engage this text; official status and applicability await original review.'}],
           'borderline_excluded': []}
    r0 = put('relevance-batch.json', rel)
    r1 = put('relevance.json', rel)
    template_id = LAW + '@' + ACTOR
    template = {'template_id': template_id, 'law_id': LAW, 'actor': ACTOR, 'quote': QUOTE,
                'status': 'draft', 'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'An official traffic-control device indicates a U-turn prohibition applicable at the place of the driver maneuver.', 'numeric_conditions': []},
                    'obligation': {'type': 'must', 'description': 'The driver obeys the directions of that device.', 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Review the device and actual driver path at the governed place and time.', 'numeric_conditions': []},
                    'judgment_calls_needed': []},
                'parameter_refs': [{'name': 'requested_turn_path', 'kind': 'controller',
                                    'range_or_domain': ['through', 'u_turn']}]}
    r2 = put('template.json', template)
    binding = {'cell_id': 'C104538', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Frozen hill-crest cell proposes a turn-prohibition cue; original official status, device directions and applicable place require review.'],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': 'requested_turn_path', 'kind': 'controller',
                                        'range_or_domain': ['through', 'u_turn'], 'used_by_laws': [LAW]}]}
    r3 = put('bindings.json', binding)
    cases = json.loads((PROPOSALS / 'cases.json').read_text())
    description = cases['cases'][0]['recording_description']
    baseline = {'case_id': HERE.name + '__neutral_baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Unselected shared context reference; no recording or legal result.',
                'variable_assignments': {'requested_turn_path': {'kind': 'controller', 'value': 'through'}},
                'recording_description': description, 'unresolved_judgment_calls': []}
    for index, case in enumerate(cases['cases']):
        request = 'through' if index == 0 else 'u_turn'
        case['target_type'] = 'compliant_attempt' if index == 0 else 'violating_attempt'
        case['paired_probe_id'] = 'signed_u_turn_path'
        case['deliberate_differences'] = ['requested_turn_path']
        case['probe'] = {'primary_variable': 'requested_turn_path',
                         'comparison_or_standard': 'controlled request under the same proposed device; actual movement and legal applicability unverified',
                         'target_value_or_branch': request}
        case['variable_assignments'] = {'requested_turn_path': {'kind': 'controller', 'value': request}}
        case['recording_description'] = description
    cases['cases'].insert(0, baseline)
    cases['sweep_specs'] = []
    cases['status'] = 'draft'
    r4 = put('cases.json', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'stages': {'relevance_batch': r0, 'relevance': r1, 'template': r2,
                        'judgment_observables': [], 'bindings': r3, 'cases': r4}}
    r5 = put('semantic-index.json', index)
    print(json.dumps({'index_sha256': r5['sha256'], 'selected_cases': 2}))


if __name__ == '__main__':
    main()
