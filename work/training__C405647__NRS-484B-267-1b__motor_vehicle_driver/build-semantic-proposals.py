"""Build source-grounded semantic drafts for the selected emergency-approach pair."""
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
        {'name': 'commanded_right_edge_response', 'kind': 'controller',
         'range_or_domain': ['approach_edge', 'hold_lane']},
        {'name': 'observed_edge_position', 'kind': 'subject_behavior',
         'range_or_domain': [True, False, None]},
        {'name': 'qualified_emergency_approach', 'kind': 'world_setup',
         'range_or_domain': [True, False, None]}]
    judgments = [
        {'phrase': 'immediate approach of an authorized emergency vehicle or official regulatory vehicle using qualifying flashing lights',
         'note': 'Authority, lamps, approach timing and any officer direction require original source and pixel review.'},
        {'phrase': 'as close as possible to the right-hand edge or curb and clear of any intersection',
         'note': 'Record full body, edge, road geometry, feasible space and intersection geometry; synthetic edge position does not establish legal closeness.'},
        {'phrase': 'paved shoulder where lawfully placed signage permits listed vehicle categories',
         'note': 'Review original signage, shoulder surface and category evidence before applying the shoulder restriction.'}]
    template = {'template_id': TID, 'law_id': LAW['id'], 'actor': A['actor'],
        'quote': LAW['text'], 'status': 'draft',
        'structure': {'law_id': LAW['id'],
            'activation': {'condition': 'immediate approach of a qualifying emergency or regulatory vehicle using required flashing lamps, unless otherwise directed by an officer',
                           'numeric_conditions': []},
            'obligation': {'description': 'immediately drive parallel and as close as possible to the right-hand edge or curb, clear of intersection; do not stop on signed permitted shoulder',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [{'source_clause': 'except when otherwise directed by a law enforcement officer',
                            'description': 'An officer may direct a different response; original direction remains unverified.'}],
            'timing': {'description': 'upon immediate approach; no invented numeric cutoff',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': parameters}
    r3 = put('template.json', template)
    observed = []
    for i, judgment in enumerate(judgments):
        result = {'template_id': TID, 'phrase': judgment['phrase'],
            'note': judgment['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': 'subject_pose_body_speed', 'unit': 'structured',
                                 'description': 'Original time-indexed vehicle body and speed relative to road edge.'}],
                'context_inputs': [{'name': 'approach_pose', 'unit': 'structured',
                                    'description': 'Original actor approach and camera join; authority, lamps, officer direction and signage require separate source review.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'camera_frame_join', 'unit': 'structured',
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
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    first = manifest['cases'][0]
    first_construction = json.loads((HERE / first['construction']).read_text())
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'No qualifying emergency approach is asserted; neutral context is unselected.',
        'variable_assignments': {
            'commanded_right_edge_response': parameter('controller', 'hold_lane', 'categorical'),
            'observed_edge_position': parameter('subject_behavior', None, 'boolean'),
            'qualified_emergency_approach': parameter('world_setup', False, 'boolean')},
        'unresolved_judgment_calls': [j['phrase'] for j in judgments],
        'recording_description': first_construction['recording_description']}]
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        cases.append({'case_id': entry['case_id'], 'target_law_id': LAW['id'],
            'target_type': 'judgment_sweep',
            'rationale': 'Compare saved requested right-edge movement with all activation and exception judgments unresolved until original review.',
            'variable_assignments': {
                'commanded_right_edge_response': parameter('controller', 'approach_edge' if suffix == 'reference' else 'hold_lane', 'categorical'),
                'observed_edge_position': parameter('subject_behavior', None, 'boolean'),
                'qualified_emergency_approach': parameter('world_setup', None, 'boolean')},
            'unresolved_judgment_calls': [j['phrase'] for j in judgments],
            'paired_probe_id': HERE.name + '__edge_pair',
            'deliberate_differences': ['commanded_right_edge_response'],
            'probe': {'primary_variable': 'commanded_right_edge_response',
                      'comparison_or_standard': 'observed body position at right edge before approach catch-up',
                      'target_value_or_branch': suffix},
            'recording_description': construction['recording_description']})
    proposal = {'cell_id': A['cell_id'], 'actor': A['actor'], 'status': 'draft',
        'cases': cases, 'sweeps_expanded': True,
        'sweep_specs': [{'sweep_id': HERE.name + '__raw_edge_geometry',
            'target_law_id': LAW['id'], 'status': 'incomplete',
            'judgment_refs': judgments,
            'rationale': 'Two raw saved edge-response constructions prepared; original activation, exception and legal closest-feasible review remains.',
            'missing_inputs': ['Original Native authority, lamps, officer and shoulder context',
                               'Independent legal judgment of immediacy and closest feasible edge']} ]}
    r5 = put('cases.json', proposal)
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': observed, 'bindings': r4, 'cases': r5}})
    print(json.dumps({'selected_cases': len(cases), 'judgments': len(judgments)}))


if __name__ == '__main__':
    main()
