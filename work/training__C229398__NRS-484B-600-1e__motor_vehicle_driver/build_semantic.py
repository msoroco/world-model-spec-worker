"""Build exact-law semantic proposals for the source-reviewed park cell."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = LAW['id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE = LAW_ID + '@' + ACTOR


def put(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C229398', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
                     'applies_to': [ACTOR], 'relevance_type': 'direct',
                     'confidence': 'high',
                     'notes': 'A driving approach in the same road/park/curb recording can be measured separately from the parked interval only after original phase and route review.'}],
                 'borderline_excluded': []}
    r1 = put('relevance_batch.json', relevance)
    r2 = put('relevance.json', relevance)
    judgment = {'phrase': 'a rate of speed greater than 80 miles per hour',
                'note': 'Use original Native velocity during reviewed driving or operating frames; controller request and parked frames are not the measured speed.'}
    params = [
        {'name': 'requested_approach_speed_mph', 'kind': 'controller',
         'range_or_domain': [75.0, 79.5, 85.0]},
        {'name': 'road_curb_route', 'kind': 'world_setup',
         'range_or_domain': ['same original C229398 road and curb']},
        {'name': 'source_phase', 'kind': 'subject_behavior',
         'range_or_domain': ['approach_driving', 'curb_parking', 'parked']},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR,
                'quote': LAW['text'], 'status': 'draft',
                'structure': {'law_id': LAW_ID,
                    'activation': {'condition': 'A person drives or operates a vehicle of any kind or character.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': 'Drive or operate at a rate greater than 80 miles per hour in any event.',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'At any observed instant while driving or operating; the parked interval is separately retained.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [judgment]},
                'parameter_refs': params}
    r3 = put('template.json', template)
    r4 = put('judgment_observables_speed.json', {
        'template_id': TEMPLATE, 'phrase': judgment['phrase'],
        'note': judgment['note'], 'status': 'draft',
        'observable_requirements': {
            'observables': [{'name': 'kin.speed', 'unit': 'structured',
                'description': 'Original Native velocity-derived speed with frame, actor and reviewed driving-phase join.'}],
            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'kin.velocity', 'unit': 'structured',
                'description': 'Retain complete three-axis Native velocity and synchronized original four-view pixels.'}],
            'limitations': [judgment['note'],
                'Synthetic CPU sources cannot establish physical or legal acceptance.']}})
    binding = {'cell_id': 'C229398', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [dict(param, used_by_laws=[LAW_ID]) for param in params]}
    r5 = put('bindings.json', binding)
    recording = json.loads((HERE / 'construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Unselected neutral road/park/curb context.',
              'variable_assignments': {param['name']: {'kind': param['kind'],
                  'value': None, 'unit': 'categorical'} for param in params},
              'unresolved_judgment_calls': [],
              'recording_description': recording}]
    for index, speed in enumerate((75.0, 79.5, 85.0), 1):
        assignments = {
            'requested_approach_speed_mph': {'kind': 'controller', 'value': speed,
                                              'unit': 'miles/hour'},
            'road_curb_route': {'kind': 'world_setup',
                                'value': 'same original C229398 road and curb',
                                'unit': 'categorical'},
            'source_phase': {'kind': 'subject_behavior',
                             'value': None, 'unit': 'categorical'}}
        cases.append({'case_id': HERE.name + f'__probe_0{index}',
            'target_law_id': LAW_ID, 'target_type': 'judgment_sweep',
            'rationale': 'Controlled speed request on one source-reviewed approach-to-curb recording; original achieved speed and same-cell scope remain for independent review.',
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [judgment['phrase']],
            'paired_probe_id': HERE.name + '__speed_boundary',
            'deliberate_differences': ['requested_approach_speed_mph'],
            'probe': {'primary_variable': 'requested_approach_speed_mph',
                      'comparison_or_standard': 'Original Native driving-phase speed around strict greater-than-80 mph source clause',
                      'target_value_or_branch': speed},
            'recording_description': recording, 'selection_rank': index})
    sweep = {'sweep_id': HERE.name + '__speed_boundary', 'target_law_id': LAW_ID,
             'status': 'incomplete', 'judgment_refs': [judgment],
             'rationale': 'Original approach velocity, actor, road, phase and curb completion must be reviewed; request is not measurement.',
             'missing_inputs': ['Original Native velocity and same-cell route/phase/camera review.']}
    r6 = put('cases.json', {'cell_id': 'C229398', 'actor': ACTOR,
                            'status': 'draft', 'sweep_specs': [sweep],
                            'sweeps_expanded': True, 'cases': cases})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': HERE.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': [r4], 'bindings': r5, 'cases': r6}})
    print('Exact-law speed semantic proposals written')


if __name__ == '__main__':
    main()
