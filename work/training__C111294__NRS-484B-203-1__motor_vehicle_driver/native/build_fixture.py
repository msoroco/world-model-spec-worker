"""Build source-shaped, explicitly synthetic CPU diagnostics for both selected cases."""
import hashlib
import json
from pathlib import Path

from route import requested_rows

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = Path.cwd().resolve()
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')


def put_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n'
                            for row in rows))


def body(x, y, half_x=2, half_y=1):
    return [[x + sx * half_x, y + sy * half_y, z]
            for sx in (-1, 1) for sy in (-1, 1) for z in (0, 1.5)]


def graph(frame, x, y, ox, oy):
    def node(name, actor_id, px, py, heading, vertices):
        return {'id': name, 'attributes': {'entity_id': actor_id,
                'sem_class': 'ego' if actor_id == 10 else 'vehicle',
                'vertex': [px, py, .5], 'forward': heading,
                'threedbbox': vertices}}
    return {'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
            'attributes': {'frame': frame, 'simulation_time_s': frame / 20,
                           'synthetic_diagnostic': True},
            'nodes': [node('ego', 10, x, y, [1, 0, 0], body(x, y)),
                      node('oncoming', 11, ox, oy, [-1, 0, 0], body(ox, oy))],
            'edges': []}


def build(case):
    rows = list(requested_rows(case))
    source = HERE / 'diagnostic' / case
    source.mkdir(parents=True, exist_ok=True)
    put(source / 'pavement-survey.json', {
        'source_kind': 'synthetic_original_shape', 'diagnostic_fixture': True,
        'one_lane_each_direction_verified': True,
        'paved_left_y_m': -4, 'paved_right_y_m': 4, 'paved_center_y_m': 0,
        'physical_acceptance_claimed': False, 'legal_compliance': 'unassessed'})
    motions, mappings, traces, evidence, native_frames, graphs = [], [], [], [], [], []
    for frame, row in enumerate(rows):
        x, y, _ = row['ego_center_xyz_m']
        ox, oy, _ = row['oncoming_center_xyz_m']
        ego = {'actor_id': 10, 'center_xyz_m': [x, y, 1.5],
               'body_xyz_m': body(x, y), 'velocity_xyz_mps': [5, 0, 0]}
        other = {'actor_id': 11, 'center_xyz_m': [ox, oy, 1.5],
                 'body_xyz_m': body(ox, oy), 'velocity_xyz_mps': [-5, 0, 0]}
        motions.append({'native_frame': frame, 'video_frame': frame,
                        'time_s': frame / 20, 'ego': ego, 'oncoming': other,
                        'source_kind': 'synthetic_original_shape'})
        mappings.append({'native_frame': frame, 'carla_frame': frame,
                         'video_frame': frame, 'time_s': frame / 20,
                         'camera_native_frames': {name: frame for name in CAMERAS}})
        traces.append({'frame': frame, 'time_s': frame / 20,
                       'position': {'x': x, 'y': y, 'z': 1.5},
                       'position_m': [x, y, 1.5], 'speed_mph': 5 / .44704,
                       'velocity_mps': [5, 0, 0], 'speed_mps': 5,
                       'control': {}, 'heading_deg': 0,
                       'source_kind': 'synthetic_original_shape'})
        evidence.append({'actor_id': 10, 'original_frame': frame,
                         'recording_time_s': frame / 20, 'replay_frame': frame,
                         'replay_simulation_time_s': frame / 20,
                         'ego': {'position_m': [x, y, 1.5], 'heading_deg': 0,
                                 'speed_mps': 5, 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': ego['body_xyz_m'],
                                 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 11, 'position_m': [ox, oy, 1.5],
                                           'body_vertices_m': other['body_xyz_m']}],
                         'world': {'road_projection': {'road_id': 111294, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x + 100},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        relative = f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'frame': frame, 'simulation_time': frame / 20,
                              'adapter_graph': relative, 'base': relative,
                              'nodes': 2, 'edges': 0})
        graphs.append(graph(frame, x, y, ox, oy))
    for name, data in [('native-motion.jsonl', motions), ('video_frames.jsonl', mappings),
                       ('trace.jsonl', traces), ('capture/evidence.jsonl', evidence)]:
        put_rows(source / name, data)
    put(source / 'capture/manifest.json', {'extraction_confirmed': True, 'frames': 600,
        'sources': {'road.xodr': sha(HERE / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True})
    spec = {'files': {'capture/native/frames.jsonl': ''.join(
                json.dumps(row, sort_keys=True) + '\n' for row in native_frames),
            'capture/recorder_info.txt': 'Synthetic C111294 CPU diagnostic; no CARLA recorder\n'
                                         'Create 10: vehicle.tesla.model3 (0)\n'
                                         'Create 11: vehicle.audi.tt (0)\n'},
            'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600, 'fps': 20,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'color': 'black'} for name in CAMERAS]}
    spec_path = HERE / f'diagnostic-{case}-fixture-spec.json'
    put(spec_path, spec)
    refs = ['pavement-survey.json', 'native-motion.jsonl', 'video_frames.jsonl',
            'trace.jsonl', 'capture/evidence.jsonl', 'capture/manifest.json']
    recipe = {'format': 'worker-fixture-recipe',
              'generator': {'source': str(spec_path.relative_to(REPO)),
                            'sha256': sha(spec_path)},
              'sources': [{'path': name, 'source': str((source / name).relative_to(REPO)),
                           'sha256': sha(source / name)} for name in refs]}
    recipe_path = HERE / f'diagnostic-{case}-fixture-recipe.json'
    put(recipe_path, recipe)
    return {'case': case, 'spec_sha256': sha(spec_path),
            'recipe_sha256': sha(recipe_path), 'source_count': len(refs)}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in ('0.45', '0.55')]))
