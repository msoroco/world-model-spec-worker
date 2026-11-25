"""Build source-hashed draft semantic proposals for the selected crosswalk cases."""
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
PROPOSALS = HERE / 'proposals'


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    original = json.loads(SOURCE.read_text())
    law_id, cell_id, actor = (original[k] for k in ('law_id', 'cell_id', 'actor'))
    quote = original['law']['text']
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote,
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'high',
                                    'notes': 'Road/park/crosswalk cell permits a source-reviewed marked-crosswalk probe.'}],
                 'borderline_excluded': []}
    relevance_batch = write('relevance_batch.json', relevance)
    relevance_ref = write('relevance.json', relevance)
    judgments = [
        {'phrase': 'marked crosswalk',
         'note': 'Marking and complete extent require original Native pixels and independent source review.'},
        {'phrase': 'stop, stand or park',
         'note': 'Original control and motion support action review but do not decide the legal action type.'},
        {'phrase': 'except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device',
         'note': 'Each textual qualification requires source-bound context and independent review.'},
    ]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'condition': 'A vehicle is within twenty feet of a marked crosswalk.',
                                   'numeric_conditions': [{'variable': 'distance_to_marked_crosswalk_m',
                                                           'operator': '<', 'value': 6.096, 'unit': 'm'}]},
                    'obligation': {'type': 'must_not',
                                   'description': 'Do not stop, stand or park a vehicle in the specified place, subject to the exact source qualifications.',
                                   'numeric_conditions': []},
                    'exceptions': [{'trigger': 'Necessary traffic conflict, law compliance, or officer/device direction applies.',
                                    'effect': 'The source prohibition is qualified.',
                                    'replacement_obligation': 'Follow the applicable law or direction.',
                                    'source_clause': judgments[2]['phrase']}],
                    'timing': {'description': 'During the observed stop, stand or park; no statutory duration is stated.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': judgments},
                'parameter_refs': []}
    template_ref = write('template.json', template)
    channels = [('crosswalk_extent', 'structured',
                 'Original Native crosswalk geometry and independently reviewed marking source.'),
                ('subject_vehicle_pose_and_extent', 'structured',
                 'Original Native vehicle pose, extent and motion over the complete capture.'),
                ('control_intent', 'structured',
                 'Original applied command stream, joined to motion and independent context sources.')]
    judgment_refs = []
    for i, (judgment, (name, unit, description)) in enumerate(zip(judgments, channels), 1):
        item = {'template_id': template_id, 'phrase': judgment['phrase'],
                'note': judgment['note'], 'status': 'draft',
                'observable_requirements': {
                    'observables': [{'name': name, 'unit': unit, 'description': description}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [{'name': name, 'unit': unit, 'description': description}],
                    'limitations': ['These sources do not alone establish physical marking, statutory necessity, directions, or a legal verdict.']}}
        judgment_refs.append(write(f'judgment-{i}.json', item))
    variables = [
        {'name': 'requested_parking_position', 'kind': 'controller',
         'range_or_domain': 'far, nominal twenty-foot boundary, or near engineering target',
         'used_by_laws': [law_id]},
        {'name': 'requested_action_control_policy', 'kind': 'controller',
         'range_or_domain': 'park, stop, or stand command policy', 'used_by_laws': [law_id]},
        {'name': 'distance_to_marked_crosswalk_m', 'kind': 'subject_behavior',
         'range_or_domain': 'source-reviewed measured distance; legal measurement convention unresolved',
         'used_by_laws': [law_id]},
    ]
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                'established_contexts': [{'name': 'road_park_crosswalk',
                                          'source': 'frozen C229397 catalog cell; marked paint remains unverified'}],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [], 'variable_parameters': variables}
    bindings_ref = write('bindings.json', bindings)
    existing = json.loads((PROPOSALS / 'cases.json').read_text())
    recording = existing['cases'][0]['recording_description']
    def assignments(position, action):
        return {'requested_parking_position': {'kind': 'controller', 'value': position},
                'requested_action_control_policy': {'kind': 'controller', 'value': action},
                'distance_to_marked_crosswalk_m': {'kind': 'subject_behavior', 'value': None}}
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Unselected neutral definition; no physical recording claimed.',
                'variable_assignments': assignments('outside', 'park'),
                'unresolved_judgment_calls': [], 'recording_description': copy.deepcopy(recording)}
    cases = [baseline]
    distance = {'controlled_1': 12.0, 'boundary_20ft': 6.096, 'controlled_2': 3.0}
    for old in existing['cases']:
        item = copy.deepcopy(old)
        suffix = item['case_id'].rsplit('__', 1)[-1]
        if suffix in distance:
            item['target_type'] = 'boundary_probe'
            item['paired_probe_id'] = 'c229397_parking_distance'
            item['deliberate_differences'] = ['requested_parking_position']
            item['epsilon_used'] = True
            item['probe'] = {'primary_variable': 'distance_to_marked_crosswalk_m',
                             'comparison_or_standard': 'twenty-foot engineering target; legal distance convention unresolved',
                             'target_value_or_branch': suffix,
                             'threshold_ref': 'activation.numeric_conditions[0]',
                             'operator': '<', 'unit': 'm', 'test_value': distance[suffix]}
            item['variable_assignments'] = assignments(suffix, 'park')
        else:
            item['target_type'] = 'judgment_sweep'
            item['paired_probe_id'] = 'c229397_action_policy'
            item['deliberate_differences'] = ['requested_action_control_policy']
            item['probe'] = {'primary_variable': 'requested_action_control_policy',
                             'comparison_or_standard': 'original motion and control history; legal action unresolved',
                             'target_value_or_branch': suffix}
            item['variable_assignments'] = assignments('controlled_2', suffix)
        item['unresolved_judgment_calls'] = [j['phrase'] for j in judgments]
        cases.append(item)
    sweep = {'sweep_id': 'crosswalk_qualitative_context', 'target_law_id': law_id,
             'judgment_refs': judgments, 'status': 'incomplete',
             'rationale': 'Original marked paint, action classification, and each statutory qualification require independent source review.',
             'missing_inputs': ['Original physical marking and motion', 'Original traffic, law, officer and device source review']}
    canonical = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'sweep_specs': [sweep], 'sweeps_expanded': True, 'cases': cases}
    cases_ref = write('canonical-cases.json', canonical)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
             'stages': {'relevance_batch': relevance_batch, 'relevance': relevance_ref,
                        'template': template_ref, 'judgment_observables': judgment_refs,
                        'bindings': bindings_ref, 'cases': cases_ref}}
    write('semantic-index.json', index)
    print(json.dumps({'stage_count': 5 + len(judgments), 'case_count': len(cases),
                      'semantic_index_sha256': hashlib.sha256((PROPOSALS / 'semantic-index.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
