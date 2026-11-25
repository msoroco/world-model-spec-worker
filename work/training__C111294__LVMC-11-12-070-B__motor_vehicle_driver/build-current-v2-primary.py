"""Build a source-hashed current v2 synthetic primary diagnostic recipe."""
import hashlib
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def main():
    source = HERE / 'current-v2-probe-1-fixture'
    source.mkdir(exist_ok=True)
    generated = runpy.run_path(str(HERE / 'prove-yield-sequence.py'))
    native = generated['rows'](True)
    lines(source / 'native_samples.jsonl', native)
    (source / 'road.xodr').write_bytes((HERE / 'native/road.xodr').read_bytes())
    write(source / 'diagnostic-source-manifest.json', {
        'case_id': CASE, 'source_kind': 'synthetic_native_sample',
        'sha256': {name: sha(source / name) for name in ('road.xodr', 'native_samples.jsonl')}})
    mapping, trace, evidence, frames, graphs = [], [], [], [], []
    for row in native:
        index = row['video_frame']
        frame = row['native_frame']
        time = row['time_s']
        ego = row['through']
        entrant = row['entrant']
        speed = ego['speed_mps']
        y = ego['y_m']
        body = [[ego['x_m']-1, y-2, 0], [ego['x_m']+1, y-2, 0],
                [ego['x_m']-1, y, 0], [ego['x_m']+1, y, 0]]
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': ego['x_m'], 'y': y-1, 'z': 0.5},
                      'position_m': [ego['x_m'], y-1, 0.5], 'heading_deg': 270.0,
                      'velocity_mps': [0.0, -speed, 0.0],
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': frame, 'recording_time_s': time,
                         'replay_frame': frame, 'replay_simulation_time_s': time,
                         'actor_id': 107,
                         'ego': {'body_vertices_m': body, 'position_m': [ego['x_m'], y-1, 0.5],
                                 'heading_deg': 270.0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'weather': {}, 'road_projection': {
                             'road_id': ego['road_id'], 'section_id': 0,
                             'lane_id': ego['lane_id'], 's_m': float(index) / 10}}})
        frames.append({'frame': frame, 'simulation_time': time, 'time_s': time,
                       'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                       'synthetic_diagnostic': True})
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame, 'simulation_time_s': time},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'vertex': [ego['x_m'], y-1, 0.5], 'sem_class': 'ego',
                           'forward': [0.0, -1.0, 0.0], 'entity_id': 107,
                           'carla_speed': speed, 'special_class': 'ego'}},
                          {'id': 'entrant', 'attributes': {
                           'vertex': [entrant['x_m'], entrant['y_m'], 0.5],
                           'sem_class': 'vehicle.audi.tt', 'forward': [1.0, 0.0, 0.0],
                           'entity_id': 108, 'carla_speed': entrant['speed_mps']}}],
                       'edges': []})
    lines(source / 'video_frames.jsonl', mapping)
    lines(source / 'trace.jsonl', trace)
    lines(source / 'capture/evidence.jsonl', evidence)
    lines(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text(
        'Create 107: vehicle.tesla.model3\nCreate 108: vehicle.audi.tt\nSynthetic diagnostic source frames: 600\n')
    write(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    spec = HERE / 'current-v2-probe-1-fixture-spec.json'
    write(spec, {'files': {}, 'graphs': graphs,
                 'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                             'height': height, 'fps': 20, 'color': 'black'}
                            for name, width, height in
                            [('overview', 1920, 1080), ('approach', 1280, 720),
                             ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]]})
    recipe = HERE / 'current-v2-probe-1-fixture-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe',
                   'sources': [{'path': p.relative_to(source).as_posix(),
                                'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                               for p in sorted(source.rglob('*')) if p.is_file()],
                   'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                 'sha256': sha(spec)}})
    contract = HERE / 'current-v2-probe-1-measurement-contract.json'
    draft = json.loads((HERE / 'branch-measurements-v2-probe-1.json').read_text())
    if draft['case_id'] != CASE or len(draft['requirements']) != 3:
        raise ValueError('Three exact case measurements required')
    write(contract, draft)
    manifest = json.loads((HERE / 'draft-primary-manifest.json').read_text())
    entry = manifest['cases'][0]
    entry['fixture_recipe'] = recipe.relative_to(ROOT).as_posix()
    entry['measurement_contract'] = contract.name
    entry['measurement_procedure'] = {'entrypoint': 'finalize.py',
                                      'output_schema': 'c111294-saved-analysis-v1'}
    manifest['cases'] = [entry]
    destination = HERE / 'current-v2-probe-1-primary-manifest.json'
    write(destination, manifest)
    print(json.dumps({'manifest': sha(destination), 'recipe': sha(recipe),
                      'spec': sha(spec), 'sources': len(json.loads(recipe.read_text())['sources'])}))


if __name__ == '__main__':
    main()
