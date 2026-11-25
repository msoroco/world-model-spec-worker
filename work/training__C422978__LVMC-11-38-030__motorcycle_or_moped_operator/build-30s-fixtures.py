"""Inventory portable 600-frame synthetic sources for two motorcycle witnesses."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SAVED = ROOT / '.runtime-work/c422978-30s-saved'
OUT = HERE / 'extended-primary/public-fixture'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in values))


def main(case):
    source = SAVED / (case + '-primary')
    out = OUT / case
    out.mkdir(parents=True, exist_ok=True)
    observed = [json.loads(line) for line in (source / 'native-observed.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (source / 'video_frames.jsonl').read_text().splitlines()]
    for name in ('native-observed.jsonl', 'native-map-readback.json',
                 'video_frames.jsonl', 'city-context.json'):
        (out / name).write_bytes((source / name).read_bytes())
    (out / 'road.xodr').write_bytes((HERE / 'native/road.xodr').read_bytes())
    trace, evidence, frames, graphs = [], [], [], []
    for row, frame in zip(observed, mapping):
        index, native, time = row['frame'], row['native_frame'], row['time_s']
        x, y = row['center_native_xy_m']
        body = [[px, py, z] for px, py in row['body_native_xy_m'] for z in (0, 1.5)]
        trace.append({'frame': native, 'time_s': time,
                      'position': {'x': x, 'y': y, 'z': .5},
                      'position_m': [x, y, .5], 'heading_deg': 0,
                      'speed_mps': row['speed_mps'],
                      'speed_mph': row['speed_mps'] / .44704,
                      'velocity_mps': [row['speed_mps'], 0, 0],
                      'control': {'throttle': .3, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [x, y, .5], 'heading_deg': 0,
                                 'speed_mps': row['speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': row['native_lane_id'],
                                                       's_m': x}}})
        name = f'{native:08d}'
        graph = f'graphs/base/{name}.adapter.json'
        graphs.append({'path': 'capture/native/' + graph,
                       'attributes': {'frame': native, 'simulation_time_s': time,
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'sem_class': 'ego', 'entity_id': 107,
                           'vertex': [x, y, .5], 'forward': [1, 0, 0],
                           'threedbbox': body}}], 'edges': []})
        frames.append({'frame': native, 'simulation_time': time,
                       'time_s': time, 'base': graph,
                       'abstract': f'graphs/abstract/{name}.pkl',
                       'adapter_graph': graph, 'synthetic_diagnostic': True})
    lines(out / 'trace.jsonl', trace)
    lines(out / 'capture/evidence.jsonl', evidence)
    lines(out / 'capture/native/frames.jsonl', frames)
    (out / 'capture/recorder_info.txt').write_text('Create 107: vehicle.kawasaki.ninja\n')
    (out / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 600,
        'acquisition': 'synthetic_diagnostic', 'observation_contract_version': 1,
        'required_observations': ['kin.velocity', 'rel.occupies'],
        'sources': {'road.xodr': sha(out / 'road.xodr'),
                    'trace.jsonl': sha(out / 'trace.jsonl')},
        'synthetic_diagnostic': True}, separators=(',', ':')) + '\n')
    (out / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False}, separators=(',', ':')) + '\n')
    files = [{'path': path.relative_to(out).as_posix(),
              'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
             for path in sorted(out.rglob('*')) if path.is_file()]
    spec = {'files': {}, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                        'height': height, 'fps': 20, 'color': color}
                       for name, width, height, color in (
                           ('overview', 1920, 1080, 'blue'),
                           ('approach', 1280, 720, 'red'),
                           ('reference_corner', 1280, 720, 'green'),
                           ('driver_reference', 1280, 720, 'white'))]}
    spec_path = HERE / 'extended-primary' / (case + '-diagnostic.json')
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE / 'extended-primary' / (case + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'case': case, 'recipe_sha256': sha(recipe_path),
                      'sources': len(files), 'graphs': len(graphs)}))


if __name__ == '__main__':
    for name in ('witness_1', 'witness_2'):
        main(name)
