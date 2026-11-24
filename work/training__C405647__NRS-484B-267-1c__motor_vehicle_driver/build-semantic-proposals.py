"""Build source-grounded semantic drafts for the selected whole-body passage, official and officer-direction comparisons."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = A['law']
TID = LAW['id'] + '@' + A['actor']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def parameter(kind, value, unit):
    return {'kind': kind, 'value': value, 'unit': unit}


def main():
    relevance = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
        'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
                           'applies_to': [A['actor']], 'relevance_type': 'direct',
                           'confidence': 'high',
                           'notes': 'The selected clause governs a driver response to the immediate approach of a qualifying emergency or regulatory vehicle.'}],
        'borderline_excluded': []}
    r1 = put('relevance-batch.json', relevance)
    r2 = put('relevance.json', relevance)
    parameters = [
        {'name': 'requested_passage_wait', 'kind': 'controller',
         'range_or_domain': ['wait_until_full_passage', 'early_release']},
        {'name': 'observed_release_after_full_passage', 'kind': 'subject_behavior',
         'range_or_domain': [True, False, None]},
        {'name': 'officer_direction_request', 'kind': 'world_setup',
         'range_or_domain': [True, False, None]},
        {'name': 'qualified_emergency_approach', 'kind': 'world_setup',
         'range_or_domain': [True, False, None]}]
    judgments = [
        {'phrase': 'immediate approach of an authorized emergency vehicle or official regulatory vehicle using qualifying flashing lights',
         'note': 'Authority, lamps, approach timing and any officer direction require original source and pixel review.'},
        {'phrase': 'stop and remain in such position until the vehicle has passed',
         'note': 'Record original subject stop, full bodies and first movement against full-body passage; synthetic requests do not prove the physical event.'},
        {'phrase': 'except when otherwise directed by a law enforcement officer',
         'note': 'Verify original officer identity, direction content, recipient and time; visible stand-in alone is insufficient.'}]
    template = {'template_id': TID, 'law_id': LAW['id'], 'actor': A['actor'],
        'quote': LAW['text'], 'status': 'draft',
        'structure': {'law_id': LAW['id'],
            'activation': {'condition': 'immediate approach of a qualifying emergency or regulatory vehicle using required flashing lamps, unless otherwise directed by an officer',
                           'numeric_conditions': []},
            'obligation': {'description': 'stop and remain in such position until the qualifying approaching vehicle has passed, except when otherwise directed by a law enforcement officer',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [{'source_clause': 'except when otherwise directed by a law enforcement officer',
                            'description': 'An officer may direct a different response; original direction remains unverified.'}],
            'timing': {'description': 'upon immediate approach until the whole approaching vehicle has passed; no invented numeric cutoff',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': parameters}
    r3 = put('template.json', template)
    observed = []
    for i, judgment in enumerate(judgments):
        result = {'template_id': TID, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': 'subject_body', 'unit': 'structured',
                                 'description': 'Original time-indexed vehicle body and speed relative to road edge.'}],
                'context_inputs': [{'name': 'emergency_body', 'unit': 'structured',
                                    'description': 'Original actor approach and camera join; authority, lamps, officer direction and signage require separate source review.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'video_frame_join', 'unit': 'structured',
                                     'description': 'Retain original four camera and actor frame joins.'}],
                'limitations': [judgment['note'], 'Synthetic diagnostic does not establish a legal verdict.']}}
        observed.append(put(f'judgment_observables_{i}.json', result))
    bindings = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
        'established_contexts': ['Authored road geometry and actor approach; verify original source before use'],
        'law_refs': [{'template_id': TID, 'binding_kind': 'direct'}],
        'context_refs': [],
        'fixed_parameters': [{'name': 'emergency_approach_context', 'value': 'held_fixed',
                              'rationale': 'Both cases share road, actor, timing, traffic controls and camera profile; actual authority and lamps remain unverified.'}],
        'variable_parameters': [dict(item, used_by_laws=[LAW['id']]) for item in parameters]}
    r4 = put('bindings.json', bindings)
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    first = manifest['cases'][0]
    first_construction = json.loads((HERE / first['construction']).read_text())
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'No qualifying emergency approach is asserted; neutral context is unselected.',
        'variable_assignments': {
            'requested_passage_wait': parameter('controller', 'early_release', 'categorical'),
            'observed_release_after_full_passage': parameter('subject_behavior', None, 'boolean'),
            'officer_direction_request': parameter('world_setup', False, 'boolean'),
            'qualified_emergency_approach': parameter('world_setup', False, 'boolean')},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments],
        'recording_description': first_construction['recording_description']}]
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        cases.append({'case_id': entry['case_id'], 'target_law_id': LAW['id'],
            'target_type': 'judgment_sweep',
            'rationale': 'Compare saved requested stop-and-remain timing with all activation and exception judgments unresolved until original review.',
            'variable_assignments': {
                'requested_passage_wait': parameter('controller', 'wait_until_full_passage' if suffix in ('probe_a', 'official_1') else 'early_release', 'categorical'),
                'observed_release_after_full_passage': parameter('subject_behavior', None, 'boolean'),
                'officer_direction_request': parameter('world_setup', suffix == 'exception_1_2', 'boolean'),
                'qualified_emergency_approach': parameter('world_setup', None, 'boolean')},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'paired_probe_id': HERE.name + '__' + suffix.rsplit('_', 1)[0] + '_pair',
            'deliberate_differences': ['officer_direction_request' if suffix.startswith('exception') else 'requested_passage_wait'],
            'probe': {'primary_variable': 'officer_direction_request' if suffix.startswith('exception') else 'requested_passage_wait',
                      'comparison_or_standard': 'observed subject release frame relative to approaching full-body passage frame',
                      'target_value_or_branch': suffix},
            'recording_description': construction['recording_description']})
    proposal = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
        'cases': cases, 'sweeps_expanded': True,
        'sweep_specs': [{'sweep_id': HERE.name + '__raw_full_body_passage_wait',
            'target_law_id': LAW['id'], 'status': 'incomplete',
            'judgment_refs': judgments,
            'rationale': 'Six raw saved stop-and-remain constructions prepared; original activation, exception and legal closest-feasible review remains.',
            'missing_inputs': ['Original Native authority, lamps and officer context',
                               'Independent legal judgment of immediate approach and full-body passage wait']} ]}
    r5 = put('cases.json', proposal)
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': observed, 'bindings': r4, 'cases': r5}})
    print(json.dumps({'selected_cases': len(cases), 'judgments': len(judgments)}))


if __name__ == '__main__':
    main()
