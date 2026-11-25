"""Build both current-runtime exact zone primary CPU diagnostics."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / 'native/zone'
CASE_PREFIX = 'training__C10374__NRS-484B-110__motor_vehicle_driver__selected_c5852cfd__'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build_variant(suffix):
    CASE = CASE_PREFIX + suffix
    source = json.loads((ZONE / f'runtime-drafts/selected_c5852cfd__{suffix}/primary/construction.json').read_text())
    construction = json.loads(json.dumps(source))
    construction['case_id'] = CASE
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    description = {
        'channels': [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                      'method': 'retained Native actor body and sampled speed joined to original frame',
                      'time_window': 'entire 30 s / 600-frame attempt',
                      'reference_frame': 'original Native frame and time',
                      'uncertainty': '50 ms sampled body and speed; official zone and pixels unverified'}
                     for name in ('kin.speed', 'zone_body')],
        'context_inputs': [],
        'limitations': ['Authored rectangle is not proof of official safety-zone designation',
                        'Synthetic camera pixels and body motion have no physical acceptance scope'],
    }
    config.update(case_id=CASE, cell_id='C10374', law_id='NRS-484B-110', actor='motor_vehicle_driver',
                  selected_case_id=CASE, duration_s=30, rate_hz=20,
                  required_atoms=['kin.speed'], source_packets=[],
                  cameras=['overview', 'approach', 'reference_corner', 'driver_reference'],
                  recording_description=description,
                  case={'case_id': CASE, 'recording_description': description})
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    construction['files'].append({'path': 'finalize.py',
                                  'content': (HERE / 'current-v2-finalize.py').read_text()})
    construction['recording_description'] = description
    construction['status'] = 'unselected_current_v2_primary_probe'
    output = HERE / f'current-runtime-v2-{suffix}-construction.json'
    write(output, construction)

    old = json.loads((HERE / 'current-graph-fixture' / f'{suffix}-generator.json').read_text())
    generated = json.loads(json.dumps(old))
    actor_rows = lines(ZONE / f'offline/raw-fixtures/selected_c5852cfd__{suffix}/primary/native-raw-actors.jsonl')
    trace = []
    frame_map = []
    for index, actor in enumerate(actor_rows):
        ego = actor['ego']
        frame = actor['native_frame']
        time = actor['time_s']
        center = ego['center_native_xyz_m']
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': center[0], 'y': center[1], 'z': center[2]},
                      'position_m': center, 'speed_mph': ego['speed_mps'] / .44704,
                      'heading_deg': 0, 'speed_mps': ego['speed_mps'],
                      'control': {}, 'velocity_mps': ego['velocity_native_xyz_mps'],
                      'synthetic_diagnostic': True})
        frame_map.append({'video_frame': index, 'native_frame': frame,
                          'carla_frame': frame, 'time_s': time,
                          'synthetic_diagnostic': True})
    generated['files']['trace.jsonl'] = ''.join(json.dumps(x) + '\n' for x in trace)
    generated['files']['video_frames.jsonl'] = ''.join(json.dumps(x) + '\n' for x in frame_map)
    evidence = [json.loads(line) for line in generated['files']['capture/evidence.jsonl'].splitlines()]
    for row in evidence:
        row['ego']['speed_provenance'] = 'synthetic_native_sample'
        row['ego']['heading_deg'] = 0
        row['world'] = {'weather': {'sun_altitude_angle': 90,
                                    'precipitation': 0, 'wetness': 0}}
    generated['files']['capture/evidence.jsonl'] = ''.join(json.dumps(x) + '\n' for x in evidence)
    generated['files']['capture/recorder_info.txt'] = 'Create 101: vehicle.tesla.model3\n'
    road = ZONE / 'alley-zone.xodr'
    capture_manifest = json.loads(generated['files']['capture/manifest.json'])
    capture_manifest['sources'] = {
        'road.xodr': sha(road),
        'trace.jsonl': hashlib.sha256(generated['files']['trace.jsonl'].encode()).hexdigest(),
    }
    generated['files']['capture/manifest.json'] = json.dumps(capture_manifest) + '\n'
    generated['videos'] = [
        {'path': name + '.mkv', 'frames': 600,
         'width': 1920 if name == 'overview' else 1280,
         'height': 1080 if name == 'overview' else 720,
         'fps': 20, 'color': 'black'}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference', 'forward')]
    spec = HERE / f'current-runtime-v2-{suffix}-generator.json'
    write(spec, generated)
    old_recipe = json.loads((HERE / 'current-graph-fixture' / f'{suffix}-recipe.json').read_text())
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [item for item in old_recipe['sources'] if item['path'] != 'video_frames.jsonl'] +
                         [{'path': 'road.xodr', 'source': road.relative_to(ROOT).as_posix(),
                           'sha256': sha(road)}],
              'generator': {'source': spec.relative_to(ROOT).as_posix(), 'sha256': sha(spec)}}
    recipe_path = HERE / f'current-runtime-v2-{suffix}-recipe.json'
    write(recipe_path, recipe)
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{'disposition_index': 0, 'requirement': 'text-0',
                                  'source': 'NRS 484B.110', 'output_key': 'zone_overlap_frames',
                                  'method': 'measure_zone_overlap', 'value_type': 'number',
                                  'kind': 'measured',
                                  'inputs': ['native-raw-actors.jsonl', 'native-map-readback.json']}],
                'negative': {'remove': ['native-raw-actors.jsonl'],
                             'error_contains': 'Missing required source: native-raw-actors.jsonl'},
                'status': 'unselected_diagnostic'}
    contract_path = HERE / f'current-runtime-v2-{suffix}-measurement-contract.json'
    write(contract_path, contract)
    proposal = {'format': 'worker-case-proposals', 'cases': [{
        'case_id': CASE, 'target_law_id': 'NRS-484B-110',
        'target_type': 'violating_attempt', 'recording_description': description,
        'variable_assignments': {}, 'sweep_measurements': [],
        'claim': 'Diagnostic construction only; official zone designation unverified',
    }]}
    write(HERE / f'current-runtime-v2-{suffix}-proposal.json', proposal)
    runtime = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    manifest = {'format': 'worker-unselected-current-v2-probe-manifest',
                'assignment_id': config['assignment_id'],
                'runtime_manifest_sha256': runtime, 'status': 'draft_not_selected',
                'cases': [{'case_id': CASE, 'kind': 'draft_not_selected',
                           'id': 'primary', 'construction': output.relative_to(HERE).as_posix(),
                           'construction_sha256': sha(output),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Original zone designation, body and pixels require review'},
                           'candidates': [],
                           'measurement_contract': contract_path.relative_to(HERE).as_posix(),
                           'measurement_procedure': {'entrypoint': 'finalize.py',
                                                     'status': 'saved_source_diagnostic'},
                           'fixture_recipe': recipe_path.relative_to(ROOT).as_posix()}]}
    manifest_path = HERE / f'current-runtime-v2-{suffix}-probe-manifest.json'
    write(manifest_path, manifest)
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'construction_sha256': sha(output), 'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    for suffix in ('condition_a', 'condition_b'):
        build_variant(suffix)
