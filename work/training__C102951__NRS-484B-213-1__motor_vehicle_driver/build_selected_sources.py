"""Bind the three synthetic saved probes to explicit 600-frame source packets.

These are CPU diagnostics. They do not claim Native CARLA acquisition or a
physical/legal outcome. Generated cameras and adapter graphs stay in scratch.
"""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')


def save_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
                            for row in values))


def build(distance):
    key = str(distance)
    source = HERE / 'selected-sources' / key
    saved = HERE / 'native/saved-fixtures' / key
    raw = HERE / 'native/raw-fixtures' / key
    source.mkdir(parents=True, exist_ok=True)
    rows = load_rows(saved / 'native-observed.jsonl')
    mapping = load_rows(raw / 'video_frames.jsonl')
    assert len(rows) == len(mapping) == 600
    for name, original in [('native-observed.jsonl', saved / 'native-observed.jsonl'),
                           ('road-readback.json', saved / 'road-readback.json'),
                           ('video_frames.jsonl', raw / 'video_frames.jsonl'),
                           ('road.xodr', HERE / 'native/road.xodr')]:
        (source / name).write_bytes(original.read_bytes())
    traces, evidence, graphs, native_frames = [], [], [], []
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        native = row['native_frame']
        time = row['time_s']
        assert row['frame'] == index and frame['native_frame'] == native
        assert abs(frame['time_s'] - time) < 1e-6
        x, y = row['ego_x_m'], row['ego_y_m']
        traces.append({'frame': native, 'time_s': time,
                       'position': {'x': x, 'y': y, 'z': 0.5},
                       'position_m': [x, y, 0.5], 'heading_deg': 0,
                       'speed_mps': row['ego_speed_mps'],
                       'speed_mph': row['ego_speed_mps'] / .44704,
                       'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
                       'velocity_mps': [row['ego_speed_mps'], 0, 0]})
        body = [[x + dx, y + dy, z] for dx, dy in
                ((-2.2, -1.0), (-2.2, 1.0), (2.2, 1.0), (2.2, -1.0))
                for z in (0, 1.5)]
        evidence.append({'original_frame': native, 'recording_time_s': time,
                         'replay_frame': native, 'replay_simulation_time_s': time,
                         'actor_id': 107,
                         'ego': {'body_vertices_m': body, 'position_m': [x, y, 0.5],
                                 'heading_deg': 0, 'speed_mps': row['ego_speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': x + 300}},
                         'original_observations': {}})
        graph_relative = f'graphs/base/{native:08d}.adapter.json'
        graph_path = 'capture/native/' + graph_relative
        graphs.append({'path': graph_path,
                       'attributes': {'frame': native, 'simulation_time_s': time,
                                      'source': 'C102951 saved synthetic CPU probe',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'entity_id': 107, 'forward': [1, 0, 0], 'sem_class': 'ego',
                           'threedbbox': body, 'vertex': [x, y, 0.5]}}], 'edges': []})
        native_frames.append({'frame': native, 'simulation_time': time,
                              'adapter_graph': graph_relative, 'base': graph_relative,
                              'nodes': 1, 'edges': 0})
    save_rows(source / 'trace.jsonl', traces)
    save_rows(source / 'capture/evidence.jsonl', evidence)
    save(source / 'capture/manifest.json', {'frames': 600, 'extraction_confirmed': True,
                                           'source_kind': 'synthetic_cpu',
                                           'sources': {'road.xodr': sha(source / 'road.xodr'),
                                                       'trace.jsonl': sha(source / 'trace.jsonl')}})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(
        json.dumps(row, separators=(',', ':')) + '\n' for row in native_frames),
                      'capture/recorder_info.txt': 'Create 107: vehicle.tesla.model3 (0, 0, 0) at (0, 0, 0)\nC102951 synthetic CPU fixture; no physical acquisition\n'},
            'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': 'black'} for name in CAMERAS]}
    spec_path = HERE / f'selected-{key}-spec.json'
    save(spec_path, spec)
    names = ('native-observed.jsonl', 'road-readback.json', 'video_frames.jsonl',
             'trace.jsonl', 'road.xodr', 'capture/evidence.jsonl', 'capture/manifest.json')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': str((source / name).relative_to(ROOT)),
                           'sha256': sha(source / name)} for name in names],
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE / f'selected-{key}-recipe.json'
    save(recipe_path, recipe)
    return {'distance_m': distance, 'source_count': len(names), 'spec_sha256': sha(spec_path),
            'recipe_sha256': sha(recipe_path),
            'max_returned_size': max(p.stat().st_size for p in source.rglob('*') if p.is_file())}


if __name__ == '__main__':
    print(json.dumps([build(distance) for distance in (70, 120, 170)], sort_keys=True))
