"""Validate source-bound draft law semantics for the C213851 road exit."""
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, data):
    path = HERE / 'proposals' / (name + '.json')
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    return {'path': path.relative_to(HERE).as_posix(), 'sha256': sha(path)}


def named(name, unit, description):
    return {'name': name, 'unit': unit, 'description': description}


def main():
    source = REPO / 'inputs' / HERE.name / 'assignment.json'
    assignment = json.loads(source.read_text())
    law = assignment['law']
    law_id, cell_id, actor = (assignment[key] for key in ('law_id', 'cell_id', 'actor'))
    template_id = law_id + '@' + actor
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    refs = {}
    common = {'request': {'cell': assignment['cell'], 'actor': actor},
              'law_records': {law_id: law}, 'dependencies': []}
    relevance = {
        'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{
            'law_id': law_id, 'quote': law['text'], 'applies_to': [actor],
            'relevance_type': 'specific_match', 'confidence': 'medium',
            'notes': 'Road-to-driveway travel can cross the sidewalk area in a residence district. '
                     'The frozen exit_road maneuver does not establish the separate upon-entering-roadway duty.'
        }], 'borderline_excluded': []}
    for stage in ('relevance_batch', 'relevance'):
        stages.validate(stage, relevance, common)
        refs[stage] = save(stage, relevance)

    judgments = [
        ('immediately prior to driving onto a sidewalk',
         'Retain stopping interval and the first sidewalk-footprint contact; no legal distance or duration cutoff is supplied.'),
        ('as may be necessary to avoid collision',
         'Retain pedestrian and vehicle trajectories and relative spacing; do not turn a conflict proxy into legal necessity.'),
        ('all vehicles approaching on said roadway',
         'This duty is conditional on entering the roadway and cannot be realized by this road-exit-only cell.')]
    template = {
        'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'status': 'draft', 'quote': law['text'],
        'structure': {
            'activation': {'condition': 'driver of a vehicle within a business or residence district emerging or entering an alley, driveway or building',
                           'numeric_conditions': []},
            'obligation': {'type': 'must', 'description': 'stop immediately before the sidewalk area; yield to pedestrians when necessary to avoid collision; upon roadway entry yield to approaching vehicles',
                           'source_clauses': [
                               'shall stop such vehicle immediately prior to driving onto a sidewalk or onto the sidewalk area extending across any alleyway or driveway',
                               'yielding the right-of-way to any pedestrian as may be necessary to avoid collision',
                               'upon entering the roadway shall yield the right-of-way to all vehicles approaching on said roadway'],
                           'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'ordered sidewalk stop, pedestrian yield, and conditional roadway entry yield',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in judgments]},
        'parameter_refs': [
            {'name': 'driveway_sidewalk_geometry', 'kind': 'world_setup', 'range_or_domain': 'source-verified connected road, driveway and sidewalk polygon'},
            {'name': 'district_context', 'kind': 'world_setup', 'range_or_domain': 'source-supported business or residence district'},
            {'name': 'pedestrian_route', 'kind': 'world_setup', 'range_or_domain': 'separate pedestrian sidewalk route'},
            {'name': 'roadway_traffic_context', 'kind': 'world_setup', 'range_or_domain': 'observed roadway vehicles; entry duty conditional'},
            {'name': 'ego_trajectory', 'kind': 'subject_behavior', 'range_or_domain': 'original pose, footprint and heading history'},
            {'name': 'ego_speed', 'kind': 'subject_behavior', 'range_or_domain': 'original measured speed history'},
            {'name': 'commanded_approach_speed', 'kind': 'controller', 'range_or_domain': 'predeclared m/s approach target'},
            {'name': 'commanded_stop_policy', 'kind': 'controller', 'range_or_domain': 'predeclared stop-before-sidewalk or no-stop attempt'},
            {'name': 'commanded_turn_path', 'kind': 'controller', 'range_or_domain': 'road-to-driveway path'}]}
    stages.validate('template', template, {'request': {'law_id': law_id, 'actor': actor},
                    'law_record': law, 'canonical_parameter_rules': rules, 'dependencies': []})
    refs['template'] = save('template', template)

    specs = [
        {
            'observables': [named('stop_to_sidewalk_relation', 'structured', 'vehicle zero-speed frames and footprint-to-sidewalk contact ordering')],
            'context_inputs': [named('sidewalk_geometry', 'structured', 'source-verified sidewalk area and driveway boundary')],
            'sweep_dimensions': [named('stop_position', 'm', 'measured stop position relative to sidewalk boundary')],
            'landmarks': [],
            'recording_needs': [named('ego_pose_speed_footprint', 'structured', 'original frame-joined pose, speed and footprint throughout approach and crossing')],
            'limitations': ['Immediately prior has no statutory numeric distance or stop-duration threshold in this text.']
        },
        {
            'observables': [named('pedestrian_relative_motion', 'structured', 'separate pedestrian and vehicle paths with synchronized positions')],
            'context_inputs': [named('pedestrian_sidewalk_route', 'structured', 'pedestrian route and sidewalk area')],
            'sweep_dimensions': [named('pedestrian_arrival_offset', 's', 'measured offset of pedestrian and vehicle arrival at crossing area')],
            'landmarks': [],
            'recording_needs': [named('pedestrian_vehicle_trace', 'structured', 'original frame-joined pedestrian and vehicle footprint, pose and speed histories')],
            'limitations': ['A time-to-conflict measure is diagnostic; this law supplies no legal collision-necessity cutoff.']
        },
        {
            'observables': [named('roadway_approach_relation', 'structured', 'vehicle approach routes and subject roadway-entry footprint history')],
            'context_inputs': [named('roadway_entry_geometry', 'structured', 'source-verified roadway boundary and incoming lanes')],
            'sweep_dimensions': [named('approaching_vehicle_arrival_offset', 's', 'measured traffic arrival offset relative to subject entry')],
            'landmarks': [],
            'recording_needs': [named('roadway_vehicle_trace', 'structured', 'original frame-joined roadway traffic and subject pose and footprint histories')],
            'limitations': ['Current exit_road cell does not establish subject roadway entry; a distinct compatible cell is required for this conditional branch.']
        }
    ]
    refs['judgment_observables'] = []
    for index, ((phrase, note), requirements) in enumerate(zip(judgments, specs)):
        observable = {'template_id': template_id, 'phrase': phrase, 'note': note,
                      'status': 'draft', 'observable_requirements': requirements}
        stages.validate('judgment_observables', observable,
                        {'request': {'template_id': template_id, 'phrase': phrase, 'note': note}, 'dependencies': []})
        refs['judgment_observables'].append(save(f'judgment_observables_{index}', observable))

    params = [{**entry, 'used_by_laws': [law_id]} for entry in template['parameter_refs']]
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                'established_contexts': [{'name': 'residence_district_exit_road_driveway_entrance',
                                          'source': 'frozen catalog cell; physical geography remains unverified'}],
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [], 'variable_parameters': params}
    stages.validate('bindings', bindings,
                    {'request': {'cell': assignment['cell'], 'actor': actor, 'template_ids': [template_id]},
                     'canonical_parameter_rules': rules, 'dependencies': [template]})
    refs['bindings'] = save('bindings', bindings)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'stages': refs, 'status': 'draft', 'original_native_observed': False}
    save('semantic-index', index)
    proof = {'format': 'c213851-semantic-foundation-v1', 'assignment_id': HERE.name,
             'assignment_sha256': sha(source), 'references': refs,
             'stages_validated': ['relevance_batch', 'relevance', 'template',
                                  'judgment_observables_0', 'judgment_observables_1',
                                  'judgment_observables_2', 'bindings'],
             'cases_stage_validated': False, 'original_native_observed': False}
    save('semantic-foundation-proof', proof)
    print(json.dumps({'validated': proof['stages_validated'],
                      'proof_sha256': sha(HERE / 'proposals/semantic-foundation-proof.json')}))


if __name__ == '__main__':
    if '/.runtime-work/' not in os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', ''):
        raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work/')
    main()
