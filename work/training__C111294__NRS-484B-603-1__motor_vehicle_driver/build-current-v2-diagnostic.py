"""Build source-hashed 600-frame current-runtime diagnostics from exact drafts."""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIX = sys.argv[1] if len(sys.argv) > 1 else 'probe_a'
SELECTED_CANDIDATE = sys.argv[2] if len(sys.argv) > 2 else 'primary'
if SUFFIX not in ('probe_a', 'probe_b'):
    raise ValueError('Unknown exact case')
if SELECTED_CANDIDATE not in ('primary', 'fallback1'):
    raise ValueError('Unknown candidate')
CASE = HERE.name + '__' + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def rows(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in data))


def main():
    draft = json.loads((HERE / f'duration-600-drafts/{SUFFIX}/{SELECTED_CANDIDATE}/construction.json').read_text())
    construction = json.loads(json.dumps(draft))
    frozen = sha(ROOT / 'inputs' / HERE.name / 'assignment.json')
    for file in construction['files']:
        if file['path'] == 'runner.py':
            file['content'] = file['content'].replace('runtime/pipeline/scenario_pipeline', 'runtime/scenario_pipeline').replace('runtime/pipeline/python', 'runtime/python')
        if file['path'] not in ('authored-road.xodr', 'geometry.py'):
            file['content'] = (file['content'].replace('ego_forward', 'approach')
                               .replace('ego_side', 'reference_corner')
                               .replace('junction.mkv', 'driver_reference.mkv')
                               .replace('"junction"', '"driver_reference"')
                               .replace("'junction'", "'driver_reference'"))
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['frozen_source_hashes'][0]['sha256'] = frozen
            if SUFFIX == 'probe_b' and SELECTED_CANDIDATE == 'fallback1':
                # Match probe A's cross-traffic speed when both fallbacks are used.
                config['knobs']['other_speed_mps'] = 5
            file['content'] = json.dumps(config, indent=2) + '\n'
        if file['path'] == 'measurement-contract.json':
            contract = json.loads(file['content'])
            contract['format'] = 'worker-measurement-contract'
            file['content'] = json.dumps(contract, indent=2) + '\n'
        if file['path'] == 'finalize.py':
            file['content'] = file['content'].replace(
                'from __future__ import annotations\n',
                'from __future__ import annotations\nimport math\n', 1)
            old = '    evidence = []\n    for channel in config["recording_description"]["channels"]:'
            new = '''    original_rows = _rows(folder, "native_samples.jsonl")
    channel_dir = folder / "channels"
    if channel_dir.exists():
        raise ValueError("Derived channels already exist")
    channel_dir.mkdir()
    value_of = {
        "ego_pose": lambda row: row["ego_position_m"],
        "ego_speed": lambda row: math.sqrt(sum(v*v for v in row["ego_velocity_mps"])),
        "observed_speed": lambda row: math.sqrt(sum(v*v for v in row["ego_velocity_mps"])) / .44704,
        "other_vehicle_pose": lambda row: row["other_position_m"],
    }
    for channel in config["recording_description"]["channels"]:
        name = channel["name"]
        with (channel_dir / (name + ".jsonl")).open("x") as stream:
            for row in original_rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": value_of[name](row),
                                         "source_sha256": _sha(folder / "native_samples.jsonl")}) + "\\n")
    evidence = []
    for channel in config["recording_description"]["channels"]:'''
            if old not in file['content']:
                raise ValueError('Current finalizer channel anchor absent')
            file['content'] = file['content'].replace(old, new)
    bundle = HERE / (f'current-v2-{SUFFIX}-diagnostic' if SELECTED_CANDIDATE == 'primary'
                     else f'current-v2-{SUFFIX}-{SELECTED_CANDIDATE}-diagnostic')
    write(bundle / 'construction.json', construction)
    contract = json.loads(next(f['content'] for f in construction['files']
                               if f['path'] == 'measurement-contract.json'))
    contract_path = HERE / f'current-v2-{SUFFIX}-measurement-contract.json'
    if SELECTED_CANDIDATE == 'primary':
        write(contract_path, contract)
    elif contract_path.is_file() and json.loads(contract_path.read_text()) != contract:
        raise ValueError('Fallback measurement contract differs from primary')
    source = HERE / f'current-v2-{SUFFIX}-source'
    source.mkdir(exist_ok=True)
    raw_text = next(f['content'] for f in construction['files']
                    if f['path'] == ('draft-fixtures/decrease-synthetic-native.jsonl' if SUFFIX == 'probe_a'
                                   else 'draft-fixtures/hold-synthetic-native.jsonl'))
    raw = [json.loads(line) for line in raw_text.splitlines()]
    native, trace, evidence, mapping, body, frames, graphs = [], [], [], [], [], [], []
    for index, sample in enumerate(raw):
        frame, time_s = index + 100, (index + 1) / 20
        x, y, z = sample['ego_position_m']
        velocity = sample['ego_velocity_mps']
        speed = math.sqrt(sum(v*v for v in velocity))
        vertices = [[x + dx, y + dy, z + height] for dx in (-2.0, 2.0)
                    for dy in (-1.0, 1.0) for height in (0, 1.5)]
        sample.update(native_frame=frame, time_s=time_s,
                      ego_body_vertices_m=vertices,
                      other_body_vertices_m=[[sample['other_position_m'][0] + dx,
                                               sample['other_position_m'][1] + dy, 0]
                                              for dx in (-2.0, 2.0) for dy in (-1.0, 1.0)])
        native.append(sample)
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': z}, 'position_m': [x, y, z],
                      'heading_deg': 90.0, 'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': velocity,
                      'control': {'throttle': .5, 'brake': 0, 'hand_brake': False},
                      'synthetic_diagnostic': True})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': sample['ego_actor_id'], 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, y, z], 'heading_deg': 90.0,
                                 'speed_mps': speed, 'velocity_mps': velocity,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': vertices},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': index * speed / 20}}})
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time_s})
        body.append({'frame': frame, 'time_s': time_s, 'body_vertices_m': vertices})
        frames.append({'frame': frame, 'time_s': time_s, 'simulation_time': time_s,
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                       'synthetic_diagnostic': True})
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame, 'simulation_time_s': time_s},
                       'nodes': [{'id': 'ego', 'attributes': {'vertex': [x, y, z],
                           'sem_class': 'ego', 'forward': [0.0, 1.0, 0.0],
                           'entity_id': sample['ego_actor_id'], 'carla_speed': speed,
                           'special_class': 'ego'}}], 'edges': []})
    for name, data in [('native_samples.jsonl', native), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence), ('video_frames.jsonl', mapping),
                       ('body_history.jsonl', body), ('capture/native/frames.jsonl', frames)]:
        rows(source / name, data)
    original_road = HERE / 'draft-fixtures/road.xodr'
    (source / 'road.xodr').write_bytes(original_road.read_bytes())
    write(source / 'context.json', {'intersection_and_other_vehicle': {
        'role': 'motor_vehicle_driver', 'route': 'synthetic cross-traffic lane'},
        'diagnostic_fixture': True, 'territorial_applicability_verified': False})
    (source / 'capture/recorder_info.txt').write_text('Create 101: vehicle.tesla.model3\nCreate 202: vehicle.tesla.model3\n')
    write(source / 'capture/manifest.json', {'extraction_confirmed': True, 'frames': 600,
        'required_observations': [], 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    spec = HERE / f'current-v2-{SUFFIX}-generator.json'
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    write(spec, {'files': {}, 'graphs': graphs,
                 'videos': [{'path': c['name'] + '.mkv', 'frames': 600,
                             'width': c['width'], 'height': c['height'],
                             'fps': 20, 'color': 'black'} for c in config['cameras']]})
    recipe = HERE / f'current-v2-{SUFFIX}-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe',
                   'sources': [{'path': p.relative_to(source).as_posix(),
                                'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                               for p in sorted(source.rglob('*')) if p.is_file()],
                   'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                 'sha256': sha(spec)}})
    manifest = json.loads((HERE / 'draft-execution-manifest-600.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == CASE)
    if SELECTED_CANDIDATE == 'primary':
        entry['construction'] = (bundle / 'construction.json').relative_to(HERE).as_posix()
        entry['construction_sha256'] = sha(bundle / 'construction.json')
    entry['fixture_recipe'] = recipe.relative_to(ROOT).as_posix()
    entry['measurement_contract'] = contract_path.name
    entry['kind'] = 'draft_not_selected'
    entry['candidates'] = [] if SELECTED_CANDIDATE == 'primary' else [{
        'id': SELECTED_CANDIDATE,
        'construction': (bundle / 'construction.json').relative_to(HERE).as_posix(),
        'construction_sha256': sha(bundle / 'construction.json'),
    }]
    if SELECTED_CANDIDATE != 'primary':
        primary = json.loads((HERE / f'current-v2-{SUFFIX}-diagnostic-manifest.json').read_text())['cases'][0]
        entry['construction'] = primary['construction']
        entry['construction_sha256'] = primary['construction_sha256']
    manifest['cases'] = [entry]
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    path = HERE / (f'current-v2-{SUFFIX}-diagnostic-manifest.json' if SELECTED_CANDIDATE == 'primary'
                   else f'current-v2-{SUFFIX}-{SELECTED_CANDIDATE}-diagnostic-manifest.json')
    write(path, manifest)
    print(json.dumps({'manifest_sha256': sha(path), 'recipe_sha256': sha(recipe),
                      'construction_sha256': sha(bundle / 'construction.json')}))


if __name__ == '__main__':
    main()
