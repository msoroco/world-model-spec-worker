"""Bind the first exact turn to a marked synthetic source diagnostic."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__approach_near_depart_right'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')


def main():
    assignment = REPO / 'inputs' / ROOT.name / 'assignment.json'
    template = REPO / 'work/heldout__C10365__NRS-484B-100__motor_vehicle_driver/diagnostic-stop_responds.json'
    diagnostic = json.loads(template.read_text())
    files = diagnostic['files']
    for name in ('officer_context.json', 'officer_direction.json',
                 'subject_motion.json', 'subject_motion_history.jsonl'):
        files.pop(name, None)
    files['fixture-provenance.json'] = json.dumps({
        'provenance_kind': 'synthetic_fixture', 'source_case': template.stem,
        'source_sha256': sha(template),
        'scope': 'CPU graph and video transfer with newly authored C109705 map and body records; no physical turn evidence'}) + '\n'
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines() if line.strip()]
    mapping = [json.loads(line) for line in files['video_frames.jsonl'].splitlines() if line.strip()]
    if len(trace) != 9 or len(mapping) != len(trace):
        raise ValueError('Diagnostic original trace and frame count differs')
    geometry = {'source_directionality': 'one_way', 'destination_directionality': 'two_directional',
                'maneuver': 'left_turn', 'intersection_id': 'synthetic-junction-1',
                'map_source': {'name': 'synthetic-turn-geometry', 'template_sha256': sha(template)},
                'source_left_curb': [[99.0, 0.0], [99.0, 12.0]],
                'destination_centerline': [[95.0, 2.0], [110.0, 2.0]],
                'source_road_id': 1, 'destination_road_id': 2,
                'driving_lane_signs': {'source': [-1], 'destination': [-1, 1]}}
    files['road_geometry.json'] = json.dumps(geometry) + '\n'
    frames = []
    for index, (state, frame) in enumerate(zip(trace, mapping)):
        if state['frame'] != frame['carla_frame'] or state['time_s'] != frame['time_s']:
            raise ValueError('Transferred diagnostic frame join differs')
        phase = 'approach' if index < 3 else 'inside_intersection' if index < 6 else 'leaving_intersection'
        x = 99.5 + index * .12
        y = 1.0 if phase == 'leaving_intersection' else 3.5 - index * .12
        corners = [[x, y], [x+.4, y], [x+.4, y+.3], [x, y+.3]]
        frames.append({'frame': state['frame'], 'time_s': state['time_s'],
                       'subject_id': 'synthetic-turn-subject', 'phase': phase,
                       'ground_corners': corners})
    files['body_footprints.json'] = json.dumps({'subject_id': 'synthetic-turn-subject', 'frames': frames}) + '\n'
    files['body_footprints.jsonl'] = ''.join(json.dumps(row) + '\n' for row in frames)
    fixture = ROOT / 'diagnostic-approach_near_depart_right.json'
    write(fixture, diagnostic, compact=True)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(fixture.relative_to(REPO)), 'sha256': sha(fixture)}],
              'generator': {'source': str(fixture.relative_to(REPO)), 'sha256': sha(fixture)}}
    recipe_path = ROOT / 'diagnostic-recipe-approach_near_depart_right.json'
    write(recipe_path, recipe)
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    requirement = ('One-way approach and two-directional entered highway left turn: '
                   'measure approach distance from the left curb and departure side of the entered centerline; '
                   'reserve practicability for independent review')
    plan['selected_branch'] = json.loads(assignment.read_text())['branches'][0]['branch']
    plan['requirement_dispositions'] = [{
        'requirement': requirement, 'source': str(assignment.relative_to(REPO)),
        'status': 'selected_required', 'case_ids': [row['case_id'] for row in plan['cases']],
        'evidence_or_gap': 'Original Native map and body measurements planned; synthetic diagnostic does not establish physical completion or legal practicability.'}]
    write(ROOT / 'case-plan.json', plan)
    proposals = {'status': 'draft', 'cell_id': 'C109705', 'actor': 'motor_vehicle_driver',
                 'cases': [{'case_id': CASE, 'target_law_id': 'NRS-484B-400-4',
                            'target_type': 'boundary_probe',
                            'rationale': 'Measure near-left-curb approach and right-of-centerline departure without a legal cutoff.',
                            'variable_assignments': {
                                'approach_left_curb_offset_m': {'kind': 'world_setup', 'value': 1.25},
                                'departure_centerline_offset_m': {'kind': 'controller', 'value': 1.80},
                                'approach_left_curb_distance_m': {'kind': 'measurement', 'value': None},
                                'departure_centerline_signed_m': {'kind': 'measurement', 'value': None}},
                            'unresolved_judgment_calls': ['as close as practicable to the left-hand curb'],
                            'recording_description': json.loads((ROOT / 'config.json').read_text())['case']['recording_description'],
                            'paired_probe_id': 'approach_curb_position',
                            'deliberate_differences': ['approach_left_curb_offset_m'],
                            'probe': {'primary_variable': 'approach_left_curb_offset_m',
                                      'comparison_or_standard': 'original full-body approach-to-curb distance',
                                      'target_value_or_branch': 1.25}}]}
    (ROOT / 'proposals').mkdir(exist_ok=True)
    write(ROOT / 'proposals/cases.json', proposals)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{'disposition_index': 0, 'requirement': requirement,
                    'source': str(assignment.relative_to(REPO)), 'output_key': 'turn_geometry',
                    'method': 'measure_turn', 'value_type': 'object', 'kind': 'measured',
                    'inputs': ['road_geometry.json', 'body_footprints.json',
                               'body_footprints.jsonl', 'video_frames.jsonl', 'trace.jsonl']}],
                'negative': {'remove': ['road_geometry.json'],
                             'error_contains': 'Missing required source: road_geometry.json'}}
    contract_path = ROOT / 'measurement-contract-approach_near_depart_right.json'
    write(contract_path, contract)
    selected = json.loads((ROOT / 'construction-probe-manifest.json').read_text())['cases'][0]
    manifest = {'format': 'worker-compatibility-manifest', 'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'cases': [{**selected, 'kind': 'delivery',
                    'measurement_contract': contract_path.name,
                    'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
                    'fixture_recipe': str(recipe_path.relative_to(REPO)),
                    'acquisition': {
                        'approach_left_curb_distance_m': {'entrypoint': 'turn_finalizer.py',
                            'method': 'original body corners relative to map left curb',
                            'evidence': 'road_geometry.json, body_footprints.jsonl and original frame map'},
                        'departure_centerline_signed_m': {'entrypoint': 'turn_finalizer.py',
                            'method': 'original body corners relative to entered road directed centerline',
                            'evidence': 'road_geometry.json, body_footprints.jsonl and original frame map'}}}]}
    write(ROOT / 'probe-compatibility-manifest.json', manifest)
    print('Bound first exact C109705 diagnostic and measurement contract')


if __name__ == '__main__':
    main()
