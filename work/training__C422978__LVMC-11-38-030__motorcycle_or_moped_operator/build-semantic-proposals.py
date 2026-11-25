"""Build source-grounded canonical drafts for the sidewalk motorcycle pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
TID = LAW['id'] + '@' + ASSIGNMENT['actor']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def parameter(kind, value, unit):
    return {'kind': kind, 'value': value, 'unit': unit}


def main():
    manifest = json.loads((HERE / 'selected-30s-draft-execution-manifest.json').read_text())
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                 'status': 'draft', 'relevant_laws': [{
                     'law_id': LAW['id'], 'quote': LAW['text'],
                     'applies_to': [ASSIGNMENT['actor']], 'relevance_type': 'direct',
                     'confidence': 'high',
                     'notes': 'The assigned actor may ride a motorcycle on the sidewalk; original City and pedestrian-use context require review.'}],
                 'borderline_excluded': []}
    rb = put('relevance-batch.json', relevance)
    r = put('relevance.json', relevance)
    judgments = [
        {'phrase': 'sidewalk of the City',
         'note': 'Surveyed City authority and pedestrian-use designation must be established from original sources.'},
        {'phrase': 'ridden upon',
         'note': 'Continuous original motorcycle body, speed and rider posture determine riding on the sidewalk; driveway-rule composition remains unresolved.'},
    ]
    template = {'template_id': TID, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
                'quote': LAW['text'], 'status': 'draft',
                'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'a motorcycle or motor scooter is ridden on a sidewalk of the City',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'No motorcycle or motor scooter shall be ridden upon any sidewalk of the City.',
                                   'type': 'must_not', 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'at every instant ridden upon the sidewalk',
                               'numeric_conditions': []},
                    'judgment_calls_needed': judgments},
                'parameter_refs': [
                    {'name': 'commanded_sidewalk_motorcycle_occupancy', 'kind': 'controller',
                     'range_or_domain': ['roadway_only', 'sidewalk_route']},
                    {'name': 'observed_moving_sidewalk_overlap', 'kind': 'subject_behavior',
                     'range_or_domain': [True, False, None]},
                    {'name': 'city_sidewalk_qualification', 'kind': 'world_setup',
                     'range_or_domain': [True, False, None]}]}
    t = put('template.json', template)
    observed = []
    for i, judgment in enumerate(judgments):
        observed.append(put(f'judgment_observables_{i}.json', {
            'template_id': TID, 'phrase': judgment['phrase'], 'note': judgment['note'],
            'status': 'draft', 'observable_requirements': {
                'observables': [{'name': 'motorcycle_body_speed', 'unit': 'structured',
                                 'description': 'Original time-indexed body footprint, rider posture and speed.'}],
                'context_inputs': [
                    {'name': name, 'unit': 'structured record',
                     'description': 'Source-hashed City, sidewalk and driveway geometry pending authority review.'}
                    for name in ('city_boundary_polygon', 'sidewalk_polygon', 'driveway_crossing_polygons')],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': 'camera_frame_join', 'unit': 'structured',
                                     'description': 'Original synchronized four-camera and motorcycle frame join.'}],
                'limitations': [judgment['note'], 'Synthetic diagnostics establish no City authority or legal verdict.']}}))
    bindings = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                'status': 'draft',
                'established_contexts': ['Authored two-way road with sidewalk lane; original City authority is pending'],
                'law_refs': [{'template_id': TID, 'binding_kind': 'direct'}],
                'context_refs': [],
                'fixed_parameters': [{'name': 'motorcycle_identity_speed_map_camera_duration',
                                      'value': 'held_fixed',
                                      'rationale': 'Both cases retain motorcycle identity, 4 m/s request, road, four cameras and 30 s window.'}],
                'variable_parameters': [dict(item, used_by_laws=[LAW['id']])
                                        for item in template['parameter_refs']]}
    b = put('bindings.json', bindings)
    first_construction = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline',
              'rationale': 'Neutral unselected context with no motorcycle sidewalk route.',
              'variable_assignments': {
                  'commanded_sidewalk_motorcycle_occupancy': parameter('controller', 'roadway_only', 'categorical'),
                  'observed_moving_sidewalk_overlap': parameter('subject_behavior', None, 'boolean'),
                  'city_sidewalk_qualification': parameter('world_setup', None, 'boolean')},
              'unresolved_judgment_calls': [j['phrase'] for j in judgments],
              'recording_description': first_construction['recording_description']}]
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        construction = json.loads((HERE / entry['construction']).read_text())
        cases.append({'case_id': entry['case_id'], 'target_law_id': LAW['id'],
                      'target_type': 'judgment_sweep',
                      'rationale': 'Compare roadway and sidewalk motorcycle requests; preserve original physical and legal uncertainty.',
                      'variable_assignments': {
                          'commanded_sidewalk_motorcycle_occupancy': parameter('controller', 'roadway_only' if suffix == 'witness_1' else 'sidewalk_route', 'categorical'),
                          'observed_moving_sidewalk_overlap': parameter('subject_behavior', None, 'boolean'),
                          'city_sidewalk_qualification': parameter('world_setup', None, 'boolean')},
                      'unresolved_judgment_calls': [j['phrase'] for j in judgments],
                      'paired_probe_id': HERE.name + '__sidewalk_pair',
                      'deliberate_differences': ['commanded_sidewalk_motorcycle_occupancy'],
                      'probe': {'primary_variable': 'commanded_sidewalk_motorcycle_occupancy',
                                'comparison_or_standard': 'original moving motorcycle body overlap with surveyed City sidewalk',
                                'target_value_or_branch': suffix},
                      'recording_description': construction['recording_description']})
    c = put('cases.json', {'cell_id': ASSIGNMENT['cell_id'], 'actor': ASSIGNMENT['actor'],
                           'status': 'draft', 'cases': cases, 'sweeps_expanded': True,
                           'sweep_specs': [{'sweep_id': HERE.name + '__city_sidewalk_observation',
                                            'target_law_id': LAW['id'], 'status': 'incomplete',
                                            'judgment_refs': judgments,
                                            'rationale': 'Two source-bound cases are selected; original City, rider and driveway context remains unreviewed.',
                                            'missing_inputs': ['Original Native motorcycle body and rider posture',
                                                               'Surveyed City pedestrian-use designation and driveway-rule composition']}]})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
                                'assignment_id': HERE.name,
                                'stages': {'relevance_batch': rb, 'relevance': r,
                                           'template': t, 'judgment_observables': observed,
                                           'bindings': b, 'cases': c}})
    print(json.dumps({'selected_cases': 2, 'judgments': len(judgments)}))


if __name__ == '__main__':
    main()
