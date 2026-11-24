"""Build one source-hashed current adapter diagnostic for the 300(1) primary."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEVICE = HERE / 'native/device'
CASE = HERE.name + '__probe_1'
RAW = DEVICE / 'offline/raw-fixtures/probe_1/primary'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned file exceeds 2 MiB: ' + str(path))


def jsonl(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def main():
    construction = json.loads((DEVICE / 'runtime-drafts/probe_1/primary/construction.json').read_text())
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    description = {
        'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                      'method': 'retained Native actor body and sampled speed joined to original frame',
                      'time_window': 'entire 30 s / 600-frame attempt',
                      'reference_frame': 'original Native frame and time',
                      'uncertainty': '50 ms sampled body and speed; official placement and pixels unverified'}
                     for name in ('kin.speed', 'device_body')],
        'context_inputs': [],
        'limitations': ['Authored stop landmark does not prove official placement',
                        'Diagnostic camera pixels and body motion are synthetic'],
    }
    config.update(cell_id='C10389', law_id='NRS-484B-300-1', actor='motor_vehicle_driver',
                  selected_case_id=CASE, duration_s=30, rate_hz=20,
                  required_atoms=['kin.speed'], source_packets=[],
                  cameras=['overview', 'approach', 'reference_corner', 'driver_reference'],
                  recording_description=description,
                  case={'case_id': CASE, 'recording_description': description})
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    files['finalize.py']['content'] = (HERE / 'current-v2-finalize.py').read_text()
    construction['recording_description'] = description
    construction['status'] = 'unselected_current_v2_primary_probe'
    construction_path = HERE / 'current-v2-primary-construction.json'
    write(construction_path, construction, compact=True)

    actors = lines(RAW / 'native-raw-actors.jsonl')
    frames = lines(RAW / 'video_frames.jsonl')
    if len(actors) != 600 or len(frames) != 600:
        raise ValueError('Retained source must have 600 frames')
    generator = {'files': {}, 'graphs': [], 'videos': []}
    native_frames = []
    trace = []
    evidence = []
    frame_map = []
    for index, (actor, frame) in enumerate(zip(actors, frames)):
        native = actor['native_frame']
        time = actor['time_s']
        ego = actor['ego']
        if actor['frame'] != index or frame['native_frame'] != native or frame['video_frame'] != index:
            raise ValueError('Retained actor/video frame join changed')
        graph_ref = f'graphs/base/{native:08d}.adapter.json'
        native_frames.append({'frame': native, 'time_s': time, 'simulation_time': time,
                              'adapter_graph': graph_ref, 'synthetic_diagnostic': True})
        center = ego['center_native_xyz_m']
        trace.append({'frame': native, 'time_s': time,
                      'position': {'x': center[0], 'y': center[1], 'z': center[2]},
                      'position_m': center, 'speed_mph': ego['speed_mps'] / .44704,
                      'heading_deg': 0, 'speed_mps': ego['speed_mps'],
                      'control': {}, 'velocity_mps': ego['velocity_native_xyz_mps'],
                      'synthetic_diagnostic': True})
        frame_map.append({'video_frame': index, 'native_frame': native,
                          'carla_frame': native, 'time_s': time,
                          'synthetic_diagnostic': True})
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': ego['actor_id'], 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': center, 'speed_mps': ego['speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'heading_deg': 0, 'body_vertices_m': ego['body_native_xyz_m']},
                         'world': {'weather': {'sun_altitude_angle': 90,
                                               'precipitation': 0, 'wetness': 0}},
                         'synthetic_diagnostic': True})
        generator['graphs'].append({'path': 'capture/native/' + graph_ref,
            'attributes': {'frame': native, 'time_s': time,
                           'synthetic_diagnostic': True, 'source': 'C10389 retained raw actor row'},
            'nodes': [{'id': 'ego', 'attributes': {
                'sem_class': 'ego', 'entity_id': ego['actor_id'],
                'vertex': center, 'forward': [1.0, 0.0, 0.0],
                'threedbbox': ego['body_native_xyz_m'],
                'carla_speed': ego['speed_mps']}}], 'edges': []})
    generator['files']['capture/native/frames.jsonl'] = jsonl(native_frames)
    generator['files']['trace.jsonl'] = jsonl(trace)
    generator['files']['video_frames.jsonl'] = jsonl(frame_map)
    generator['files']['capture/evidence.jsonl'] = jsonl(evidence)
    generator['files']['capture/manifest.json'] = json.dumps({
        'source_kind': 'synthetic_diagnostic', 'frames': 600, 'rate_hz': 20,
        'extraction_confirmed': True, 'original_native_observed': False,
        'sources': {'road.xodr': sha(DEVICE / 'alley-stop.xodr'),
                    'trace.jsonl': hashlib.sha256(generator['files']['trace.jsonl'].encode()).hexdigest()}}) + '\n'
    generator['files']['capture/recorder_info.txt'] = 'Create 101: vehicle.tesla.model3\n'
    generator['videos'] = [
        {'path': name + '.mkv', 'frames': 600,
         'width': 1920 if name == 'overview' else 1280,
         'height': 1080 if name == 'overview' else 720,
         'fps': 20, 'color': 'black'}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference', 'forward')]
    generator_path = HERE / 'current-v2-primary-generator.json'
    write(generator_path, generator, compact=True)
    sources = []
    for name in ('native-map-readback.json', 'native-raw-actors.jsonl',
                 'frame-review.jsonl', 'native-capture-report.json'):
        path = RAW / name
        sources.append({'path': name, 'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    road = DEVICE / 'alley-stop.xodr'
    sources.append({'path': 'road.xodr', 'source': road.relative_to(ROOT).as_posix(), 'sha256': sha(road)})
    recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
              'generator': {'source': generator_path.relative_to(ROOT).as_posix(), 'sha256': sha(generator_path)}}
    recipe_path = HERE / 'current-v2-primary-recipe.json'
    write(recipe_path, recipe)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{'disposition_index': 0, 'requirement': 'NRS-484B-300-1',
                                  'source': 'NRS 484B.300(1)', 'output_key': 'device_response',
                                  'method': 'measure_device_response', 'value_type': 'object',
                                  'kind': 'measured',
                                  'inputs': ['native-raw-actors.jsonl', 'native-map-readback.json']}],
                'negative': {'remove': ['native-raw-actors.jsonl'],
                             'error_contains': 'Missing required source: native-raw-actors.jsonl'},
                'status': 'unselected_diagnostic'}
    contract_path = HERE / 'current-v2-primary-measurement-contract.json'
    write(contract_path, contract)
    proposal = {'format': 'worker-case-proposals', 'cases': [{
        'case_id': CASE, 'target_law_id': 'NRS-484B-300-1',
        'target_type': 'controlled_attempt', 'recording_description': description,
        'variable_assignments': {}, 'sweep_measurements': [],
        'claim': 'Diagnostic construction only; official placement and legal effect unverified'}]}
    write(HERE / 'proposals/cases.json', proposal)
    runtime = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest = {'format': 'worker-unselected-current-v2-probe-manifest',
                'assignment_id': HERE.name, 'runtime_manifest_sha256': runtime,
                'status': 'draft_not_selected', 'cases': [{
                    'case_id': CASE, 'kind': 'draft_not_selected', 'id': 'primary',
                    'construction': construction_path.relative_to(HERE).as_posix(),
                    'construction_sha256': sha(construction_path),
                    'candidate_risk': {'status': 'physical',
                                       'reason': 'Original device placement, body and pixels require review'},
                    'candidates': [],
                    'measurement_contract': contract_path.relative_to(HERE).as_posix(),
                    'measurement_procedure': {'entrypoint': 'finalize.py',
                                              'status': 'saved_source_diagnostic'},
                    'fixture_recipe': recipe_path.relative_to(ROOT).as_posix()}]}
    manifest_path = HERE / 'current-v2-primary-probe-manifest.json'
    write(manifest_path, manifest)
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'construction_sha256': sha(construction_path),
                      'recipe_sha256': sha(recipe_path),
                      'generator_bytes': generator_path.stat().st_size}))


if __name__ == '__main__':
    main()
