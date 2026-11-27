"""Draft source-bound semantic stages for marked and unmarked crosswalks."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
A = json.loads((ROOT / 'assignment.json').read_text())
LAW, CELL, ACTOR = (A[k] for k in ('law_id', 'cell_id', 'actor'))
TEXT = A['law']['text']
TEMPLATE = LAW + '@' + ACTOR
KINDS = ('marked', 'unmarked')

def write(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def named(name, description):
    return {'name': name, 'unit': 'structured record', 'description': description}

def main():
    refs = {}
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                                    'relevance_type': 'direct pedestrian crosswalk caution encounter',
                                    'confidence': 'high',
                                    'notes': 'Supplemental C230221 branch distinguishes original marked and unmarked crossing contexts.'}],
                 'borderline_excluded': []}
    for stage in ('relevance_batch', 'relevance'):
        refs[stage] = write(stage + '.json', relevance)
    judgment = {'phrase': 'Exercise proper caution upon observing a pedestrian',
                'note': 'No numeric legal caution or near-crosswalk cutoff is supplied.'}
    params = [{'name': 'crosswalk_kind', 'kind': 'world_setup',
               'range_or_domain': 'marked or unmarked, proved from original Native map readback'}]
    refs['template'] = write('template.json', {'template_id': TEMPLATE, 'law_id': LAW,
        'actor': ACTOR, 'quote': TEXT,
        'structure': {'law_id': LAW,
                      'activation': {'condition': 'Motor-vehicle driver receives an original scripted observation input for a pedestrian in or near a source-reviewed marked or unmarked crosswalk.', 'numeric_conditions': []},
                      'obligation': {'description': 'Exercise proper caution upon observing the pedestrian.', 'type': 'must', 'numeric_conditions': []},
                      'exceptions': [],
                      'timing': {'description': 'Original observation-input and response history during the crossing encounter.', 'numeric_conditions': []},
                      'judgment_calls_needed': [judgment]},
        'parameter_refs': params})
    observations = [named('ego_body_history', 'Original motor-vehicle body and route history.'),
                    named('pedestrian_body_history', 'Separate original pedestrian body and crosswalk route.'),
                    named('ego_speed_and_brake_history', 'Original speed and brake commands.'),
                    named('driver_observation_input_history', 'Instrumented scripted-driver observation input, distinct from visibility or cognition.'),
                    named('crosswalk_context', 'Original map, intersection, curb, crossing extent and marking readback.'),
                    named('participant_classification_context', 'Original motor-vehicle and pedestrian classifications.'),
                    named('contact_events', 'Original contact history.'),
                    named('camera_frame_map', 'Original synchronized four-camera identities.')]
    contexts = [named('crosswalk_site_context', 'Original OpenDRIVE and Native crossing kind, intersection and curbs.'),
                named('driver_input_context', 'Scripted driver input source; human observation unresolved.')]
    refs['judgment_observables'] = [write('judgment-1.json', {'template_id': TEMPLATE,
        'phrase': judgment['phrase'], 'note': judgment['note'], 'status': 'draft',
        'observable_requirements': {'observables': observations, 'context_inputs': contexts,
            'sweep_dimensions': [{'name': 'crosswalk_kind', 'unit': 'categorical',
                                  'description': 'Original marked versus unmarked physical crossing context.'}],
            'landmarks': [], 'recording_needs': observations,
            'limitations': ['Scripted input does not prove human cognition.',
                            'Crossing kind and brake response do not decide legal proper caution.']}})]
    refs['bindings'] = write('bindings.json', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'established_contexts': ['road intersection', 'reviewed crossing and curbs', 'motor-vehicle travel', 'pedestrian crossing'],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in params]})
    channels = [{'name': item['name'], 'unit': item['unit'], 'sampling_rate_hz': 20,
                 'method': item['description'], 'time_window': 'approach through pedestrian crossing',
                 'reference_frame': 'CARLA world with original frame and time',
                 'uncertainty': '20 Hz sampling and simulator body precision'} for item in observations]
    recording = {'channels': channels,
                 'context_inputs': [{'name': item['name'], 'unit': item['unit'],
                                     'method': item['description']} for item in contexts],
                 'limitations': ['Native crossing and camera pixels require physical verification.',
                                 'Human observation, statutory near and legal proper caution remain unresolved.']}
    cases = [{'case_id': ROOT.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Common intersection and controller baseline.',
              'variable_assignments': {'crosswalk_kind': {'kind': 'world_setup', 'value': 'marked', 'note': 'Reference crossing category only.'}},
              'recording_description': recording,
              'unresolved_judgment_calls': [judgment['phrase']]}]
    for kind in KINDS:
        cases.append({'case_id': ROOT.name + '__' + kind + '_crosswalk', 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'rationale': 'Original ' + kind + ' crosswalk context with fixed driver and pedestrian policy.',
            'variable_assignments': {'crosswalk_kind': {'kind': 'world_setup', 'value': kind,
                'note': 'Original map readback, not a legal verdict.'}},
            'recording_description': recording,
            'unresolved_judgment_calls': [judgment['phrase']],
            'paired_probe_id': ROOT.name + '__crosswalk_pair',
            'deliberate_differences': ['crosswalk_kind'],
            'probe': {'primary_variable': 'crosswalk_kind',
                      'comparison_or_standard': 'Original marking, intersection, body and response history; proper caution unresolved.',
                      'target_value_or_branch': kind}})
    refs['cases'] = write('cases.json', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
        'cases': cases, 'sweep_specs': [{'sweep_id': 'c230221-crosswalk-kind',
                                       'target_law_id': LAW, 'judgment_refs': [judgment],
                                       'status': 'incomplete',
                                       'rationale': 'Actual crossing and legal judgment require physical source review.',
                                       'missing_inputs': ['Original marked and unmarked intersection maps with matched geometry',
                                                          'Human observation and proper-caution review']}],
        'sweeps_expanded': True})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': ROOT.name, 'stages': refs})

if __name__ == '__main__':
    main()
