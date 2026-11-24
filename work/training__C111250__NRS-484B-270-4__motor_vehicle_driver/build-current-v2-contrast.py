"""Build a source-hashed, unselected 600-frame current-v2 primary diagnostic."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__controlled_2'
SOURCE = HERE / 'current-v2-contrast-sources'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in records))


def main():
    base = json.loads((HERE / 'draft-within_cycle_lane-construction.json').read_text())
    config = json.loads(next(item['content'] for item in base['files'] if item['path'] == 'config.json'))
    config.update(candidate_id='primary', required_atoms=[], source_packets=[],
                  cameras=[{'name': n, 'fps': 20} for n in ('overview', 'approach', 'reference_corner', 'driver_reference')],
                  case={'case_id': CASE}, supported_case_ids=[CASE],
                  status='unselected_cpu_diagnostic')
    recording = {'channels': [
        {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
         'method': 'Retained source-bound Native diagnostic rows',
         'time_window': 'entire 30 s / 600 frame attempt',
         'reference_frame': 'original Native frame and time',
         'uncertainty': '50 ms frame bracket; physical and legal review pending'}
        for name in ('vehicle_body', 'cycle_facility')],
        'context_inputs': [],
        'limitations': ['Synthetic CPU source only; official designation and subsection 3 exception unverified']}
    base['recording_description'] = recording
    base['files'] = [item for item in base['files'] if item['path'] != 'config.json']
    base['files'].append({'path': 'config.json', 'content': json.dumps(config, indent=2, sort_keys=True) + '\n'})
    base['files'].append({'path': 'finalize.py', 'content': (HERE / 'native/finalize_v2_contrast.py').read_text()})
    base['files'].append({'path': 'measure_saved.py', 'content': (HERE / 'native/measure_saved.py').read_text()})
    base['status'] = 'unselected_cpu_diagnostic'
    construction = HERE / 'current-v2-contrast-construction.json'
    write(construction, base)

    import sys
    sys.path.insert(0, str(HERE / 'native'))
    from facility import open_drive
    road = SOURCE / 'road.xodr'
    SOURCE.mkdir(parents=True, exist_ok=True)
    road.write_text(open_drive())
    facility_context = {'facility_x_m': [3.5, 5.5], 'intersection_y_m': [-7.0, 7.0],
                        'source_kind': 'synthetic_cpu_diagnostic',
                        'official_designation_proven': False}
    write(SOURCE / 'facility-context.json', facility_context)
    trace, frame_map, evidence, footprints, graphs, native_frames = [], [], [], [], [], []
    for frame in range(600):
        time = frame / 20
        x = 4.5
        y = -70 + 0.17 * frame
        body = [[x + dx, y + dy] for dx, dy in
                ((-0.9, -2.2), (0.9, -2.2), (0.9, 2.2), (-0.9, 2.2))]
        vertices = [[px, py, z] for px, py in body for z in (0.0, 1.5)]
        footprints.append({'native_frame': frame, 'time_s': time, 'body_xy_m': body, 'speed_mps': 3.4,
                           'source_kind': 'synthetic_cpu_diagnostic'})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': x, 'y': y, 'z': 0.5},
                      'position_m': [x, y, 0.5], 'heading_deg': 90,
                      'speed_mps': 3.4, 'speed_mph': 3.4 * 2.2369362920544,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        frame_map.append({'carla_frame': frame, 'native_frame': frame,
                          'time_s': time, 'video_frame': frame})
        evidence.append({'original_frame': frame, 'recording_time_s': time,
                         'ego': {'body_vertices_m': vertices, 'position_m': [x, y, 0.5],
                                 'heading_deg': 90, 'speed_mps': 3.4,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'replay_frame': frame, 'replay_simulation_time_s': time,
                         'actor_id': 107,
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -2, 's_m': y + 100}}})
        relative = f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame': frame, 'simulation_time': time,
                              'adapter_graph': relative, 'base': relative,
                              'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + relative,
                       'attributes': {'frame': frame, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True,
                                      'source': 'C111250 cycle facility diagnostic'},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'sem_class': 'ego', 'entity_id': 107,
                           'vertex': [x, y, 0.5], 'forward': [0.0, 1.0, 0.0],
                           'threedbbox': vertices}}], 'edges': []})
    rows(SOURCE / 'body-history.jsonl', footprints)
    rows(SOURCE / 'trace.jsonl', trace)
    rows(SOURCE / 'video_frames.jsonl', frame_map)
    rows(SOURCE / 'capture/evidence.jsonl', evidence)
    write(SOURCE / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(road), 'trace.jsonl': sha(SOURCE / 'trace.jsonl')}})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(
                json.dumps(row, separators=(',', ':')) + '\n' for row in native_frames),
            'capture/recorder_info.txt': 'synthetic CPU diagnostic; no CARLA recorder\nCreate 107: vehicle.carlamotors.carlacola (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': 'black'}
                       for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    spec_path = HERE / 'current-v2-contrast-fixture-spec.json'
    write(spec_path, spec)
    sources = []
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file():
            sources.append({'path': str(path.relative_to(SOURCE)),
                            'source': str(path.relative_to(REPO)), 'sha256': sha(path)})
    recipe_path = HERE / 'current-v2-contrast-fixture-recipe.json'
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': str(spec_path.relative_to(REPO)),
                                      'sha256': sha(spec_path)}})
    contract_path = HERE / 'current-v2-contrast-measurement-contract.json'
    write(contract_path, {'format': 'worker-measurement-contract', 'case_id': CASE,
                          'requirements': [{'disposition_index': 0,
                                            'requirement': 'NRS-484B-270-4',
                                            'source': 'NRS 484B.270(4)',
                                            'output_key': 'cycle_lane_intersection_measurement',
                                            'method': 'measure_cycle_lane', 'value_type': 'object',
                                            'kind': 'measured',
                                            'inputs': ['facility-context.json', 'body-history.jsonl',
                                                       'video_frames.jsonl', 'trace.jsonl',
                                                       'capture/evidence.jsonl']}],
                          'negative': {'remove': ['body-history.jsonl'],
                                       'error_contains': 'Missing required source: body-history.jsonl'},
                          'status': 'unselected_contract_draft'})
    runtime = json.loads((REPO / 'batch.json').read_text())
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': HERE.name, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': runtime['runtime']['source_manifest_sha256'],
                'cases': [{'case_id': CASE, 'kind': 'draft_not_selected', 'id': 'primary',
                           'construction': construction.name,
                           'construction_sha256': sha(construction),
                           'fixture_recipe': str(recipe_path.relative_to(REPO)),
                           'measurement_contract': contract_path.name,
                           'measurement_procedure': {'entrypoint': 'finalize.py'},
                           'recording_description': recording, 'candidates': [],
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Original designation, exception, and body pixels need review'}}]}
    manifest_path = HERE / 'current-v2-contrast-manifest.json'
    write(manifest_path, manifest)
    write(HERE / 'proposals/cases.json', {'format': 'worker-case-proposals',
          'cases': [{'case_id': CASE, 'target_law_id': 'NRS-484B-270-4',
                     'target_type': 'attempt',
                     'rationale': 'Unselected within-cycle-lane intersection CPU diagnostic',
                     'variable_assignments': {'cycle_lane_occupancy_requested': True},
                     'recording_description': recording}]})
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
                      'spec_sha256': sha(spec_path), 'construction_sha256': sha(construction)}))


if __name__ == '__main__':
    main()
