"""Draft canonical stages for the assigned pedestrian backing alternative."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
LAW = 'NRS-484B-113-3'
CELL = 'C111301'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
PHRASE = 'yield the right-of-way to moving traffic and pedestrians'


def write(folder, name, value):
    path = folder / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    folder = HERE / 'proposals'
    folder.mkdir(exist_ok=True)
    assignment = json.loads((HERE.parents[1] / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    text = assignment['law']['text']
    cases = {case['case_id'] for case in plan['cases']}
    expected = {AID + '__pedestrian_yield', AID + '__pedestrian_continue'}
    if cases != expected:
        raise ValueError('exact assigned pedestrian backing cases changed')
    description = {
        'channels': [
            {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
             'method': 'source-sealed original Native actor readback and four-camera frame join',
             'time_window': 'all 900 consecutive original world ticks',
             'reference_frame': 'original CARLA world frame',
             'uncertainty': 'actual motion, visibility and statutory priority require independent review'}
            for name in ('vehicle_reverse_response', 'moving_pedestrian_corridor_exposure')],
        'context_inputs': [
            {'name': 'backing_context', 'unit': 'structured',
             'method': 'reviewed original OpenDRIVE, actor poses and backing route packet'}],
        'limitations': ['A controller command or synthetic fixture does not prove a lawful yield.',
                        'Moving-traffic alternative and physical participant visibility remain unresolved.']}
    parameters = [
        {'name': 'reverse_response', 'kind': 'controller',
         'range_or_domain': 'hold/brake during measured corridor occupancy or continue reverse'},
        {'name': 'pedestrian_corridor_exposure', 'kind': 'world_setup',
         'range_or_domain': 'same original moving pedestrian route and timing'},
        {'name': 'reverse_route', 'kind': 'world_setup',
         'range_or_domain': 'source-bound original map and junction route'},
        {'name': 'capture_profile', 'kind': 'world_setup',
         'range_or_domain': 'four original cameras, 20 Hz, 900 frames'}]
    relevance = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': text,
                                    'applies_to': [ACTOR], 'confidence': 'low',
                                    'relevance_type': 'backing interaction with a moving pedestrian',
                                    'notes': 'The moving-traffic alternative and exact backing context need separate review.'}],
                 'borderline_excluded': []}
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR,
                'template_id': TEMPLATE, 'quote': text,
                'structure': {'activation': {'condition': 'Driver backs a vehicle while a moving pedestrian is exposed.',
                                             'numeric_conditions': []},
                              'obligation': {'type': 'must', 'description': 'Yield right of way to the moving pedestrian.',
                                             'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'Join original backing and pedestrian exposure frames.',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': PHRASE,
                                                         'note': 'Original motion and priority remain for independent review.'}]},
                'parameter_refs': parameters}
    vehicle = {'name': 'vehicle_reverse_response', 'unit': 'structured',
               'description': 'Original control, reverse speed and body position per Native frame.'}
    pedestrian = {'name': 'moving_pedestrian_corridor_exposure', 'unit': 'structured',
                  'description': 'Original pedestrian body/velocity and source-derived corridor overlap.'}
    judgment = {'status': 'draft', 'template_id': TEMPLATE, 'phrase': PHRASE,
                'note': 'Original motion and priority remain for independent review.',
                'observable_requirements': {'observables': [vehicle, pedestrian],
                                            'context_inputs': [{'name': 'backing_context', 'unit': 'structured',
                                                                'description': 'Reviewed original road and backing maneuver.'}],
                                            'sweep_dimensions': [], 'landmarks': [],
                                            'recording_needs': [vehicle, pedestrian],
                                            'limitations': ['Moving-traffic alternative is separate.',
                                                            'Physical completion and legal priority are unresolved.']}}
    bindings = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
                'context_refs': [],
                'established_contexts': ['Frozen intersection/travel/pedestrian-control cell; original backing site pending'],
                'fixed_parameters': [{'name': 'assigned_cell', 'value': CELL,
                                      'rationale': 'Frozen catalog identity, not physical acceptance'}],
                'variable_parameters': [dict(p, used_by_laws=[LAW]) for p in parameters]}
    def assignments(kind):
        return {'reverse_response': {'kind': 'controller',
                                     'value': 'hold/brake' if kind == 'pedestrian_yield' else 'continue reverse'},
                'pedestrian_corridor_exposure': {'kind': 'world_setup', 'value': 'same moving pedestrian'},
                'reverse_route': {'kind': 'world_setup', 'value': 'same source-bound reverse route'},
                'capture_profile': {'kind': 'world_setup', 'value': 'four original cameras, 20 Hz, 900 frames'}}
    rows = [{'case_id': AID + '__semantic_baseline', 'target_law_id': None,
             'target_type': 'baseline', 'rationale': 'Reference only; no separate recording.',
             'variable_assignments': assignments('pedestrian_yield'),
             'recording_description': description,
             'unresolved_judgment_calls': [PHRASE]}]
    for case_id in sorted(cases):
        kind = case_id.removeprefix(AID + '__')
        rows.append({'case_id': case_id, 'target_law_id': LAW,
                     'target_type': 'boundary_probe', 'paired_probe_id': 'pedestrian_yield_response',
                     'deliberate_differences': ['reverse_response'],
                     'probe': {'primary_variable': 'reverse_response',
                               'comparison_or_standard': 'same original moving pedestrian corridor exposure',
                               'target_value_or_branch': kind},
                     'rationale': 'Observe backing response with moving pedestrian: ' + kind,
                     'variable_assignments': assignments(kind),
                     'recording_description': description,
                     'unresolved_judgment_calls': [PHRASE]})
    case_stage = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR, 'cases': rows,
                  'sweep_specs': [{'sweep_id': 'pedestrian_yield_response',
                                   'target_law_id': LAW,
                                   'judgment_refs': [{'phrase': PHRASE,
                                                      'note': 'Original motion and priority remain for independent review.'}],
                                   'status': 'incomplete',
                                   'missing_inputs': ['Reviewed original backing site and moving pedestrian source'],
                                   'rationale': 'No engineering brake or distance threshold is a legal cutoff.'}]}
    stages = {'relevance_batch': write(folder, 'relevance_batch.json', relevance),
              'relevance': write(folder, 'relevance.json', relevance),
              'template': write(folder, 'template.json', template),
              'judgment_observables': [write(folder, 'judgment-1.json', judgment)],
              'bindings': write(folder, 'bindings.json', bindings),
              'cases': write(folder, 'cases.json', case_stage)}
    write(folder, 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                           'assignment_id': AID, 'stages': stages})
    return {'selected_cases': len(cases), 'stage_count': 6}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
