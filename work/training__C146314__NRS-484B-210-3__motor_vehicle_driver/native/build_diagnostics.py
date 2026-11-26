"""Build source-shaped, source-hashed right-pass CPU fixture recipes; no recordings."""
import hashlib
import json
from pathlib import Path

from geometry import open_drive

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name
NATIVE = ROOT / 'native'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), sort_keys=True) + '\n')


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, separators=(',', ':'), sort_keys=True) + '\n'
                            for v in values))


def body_xy(x, y):
    return [[round(x + dx, 6), round(y + dy, 6)]
            for dx in (-2.25, 2.25) for dy in (-.9, .9)]


def body_xyz(x, y):
    return [[px, py, z] for px, py in body_xy(x, y) for z in (0, 1.5)]


def graph_node(name, actor_id, x, y, sem_class):
    return {'id': name, 'attributes': {'entity_id': actor_id, 'sem_class': sem_class,
            'vertex': [round(x, 6), y, .5], 'forward': [1, 0, 0],
            'threedbbox': body_xyz(x, y)}}


def build_case(suffix, lead_y, ego_y):
    base = NATIVE / 'diagnostic' / suffix
    source = base / 'sources'
    road = source / 'road.xodr'
    road.parent.mkdir(parents=True, exist_ok=True)
    road.write_text(open_drive())
    road_hash = sha(road)
    native, frame_map, trace, evidence, native_frames, graphs = [], [], [], [], [], []
    for i in range(600):
        frame, time = i, round(i / 20, 6)
        ex, lx = round(20 + i * .4, 6), round(60 + i * .25, 6)
        native.append({'video_frame': i, 'native_frame': frame, 'time_s': time,
                       'source_kind': 'synthetic_cpu_pass', 'case_id': AID + '__' + suffix,
                       'native_map_sha256': road_hash, 'paved_right_edge_y_m': -8.0,
                       'ego': {'actor_id': 10, 'blueprint_id': 'vehicle.tesla.model3',
                               'center_xyz_m': [ex, ego_y, .5], 'body_xy_m': body_xy(ex, ego_y),
                               'velocity_xyz_mps': [8, 0, 0], 'speed_mps': 8},
                       'lead': {'actor_id': 11, 'blueprint_id': 'vehicle.tesla.model3',
                                'center_xyz_m': [lx, lead_y, .5], 'body_xy_m': body_xy(lx, lead_y),
                                'velocity_xyz_mps': [5, 0, 0], 'speed_mps': 5}})
        frame_map.append({'video_frame': i, 'carla_frame': frame, 'native_frame': frame,
                          'time_s': time, 'camera_native_frames': {name: frame for name in CAMERAS}})
        trace.append({'frame': frame, 'time_s': time,
                      'position_m': [ex, ego_y, .5], 'heading_deg': 0,
                      'speed_mps': 8, 'speed_mph': 8 / .44704})
        evidence.append({'actor_id': 10, 'original_frame': frame, 'recording_time_s': time,
                         'replay_frame': frame, 'replay_simulation_time_s': time,
                         'ego': {'body_vertices_m': body_xyz(ex, ego_y),
                                 'position_m': [ex, ego_y, .5], 'heading_deg': 0,
                                 'speed_mps': 8, 'speed_provenance': 'synthetic_cpu_pass',
                                 'synthetic_diagnostic': True},
                         'other_actors': [{'actor_id': 11, 'body_vertices_m': body_xyz(lx, lead_y),
                                           'position_m': [lx, lead_y, .5], 'speed_mps': 5}],
                         'world': {'road_projection': {'road_id': 1,
                                                       'lane_id': -2 if suffix == 'probe_a' else -3,
                                                       'section_id': 0, 's_m': ex},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_path = f'graphs/base/{i:08d}.adapter.json'
        native_frames.append({'adapter_graph': graph_path, 'base': graph_path,
                              'edges': 0, 'frame': i, 'nodes': 2, 'simulation_time': time})
        graphs.append({'path': graph_path,
                       'attributes': {'frame': i, 'simulation_time_s': time,
                                      'source': 'C146314 right-pass CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [graph_node('ego', 10, ex, ego_y, 'ego'),
                                 graph_node('lead', 11, lx, lead_y, 'vehicle')],
                       'edges': []})
    lines(source / 'native_motion.jsonl', native)
    lines(source / 'video_frames.jsonl', frame_map)
    lines(source / 'trace.jsonl', trace)
    lines(source / 'capture/evidence.jsonl', evidence)
    write(source / 'acquisition-provenance.json', {'diagnostic_fixture': True,
          'physical_acceptance_claimed': False, 'provenance_kind': 'synthetic_cpu_pass'})
    write(source / 'capture/manifest.json', {'extraction_confirmed': True, 'frames': 600,
          'sources': {'road.xodr': road_hash, 'trace.jsonl': sha(source / 'trace.jsonl')},
          'synthetic_diagnostic': True})
    specification = {'files': {
        'capture/native/frames.jsonl': ''.join(json.dumps(v, separators=(',', ':'), sort_keys=True) + '\n'
                                                  for v in native_frames),
        'capture/recorder_info.txt': 'Synthetic C146314 CPU right-pass diagnostic; not original Native evidence.\n'
        'Create 10: vehicle.tesla.model3 (0)\nCreate 11: vehicle.tesla.model3 (0)\n'},
        'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 600,
                    'width': 1920 if name == 'overview' else 1280,
                    'height': 1080 if name == 'overview' else 720,
                    'fps': 20, 'color': 'black'} for name in CAMERAS]}
    spec_path = base / 'fixture-spec.json'
    write(spec_path, specification)
    sources = [{'path': str(path.relative_to(source)),
                'source': str(path.relative_to(ROOT.parents[1])), 'sha256': sha(path)}
               for path in sorted(source.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
              'generator': {'source': str(spec_path.relative_to(ROOT.parents[1])),
                            'sha256': sha(spec_path)}}
    write(base / 'fixture-recipe.json', recipe)
    return {'case': suffix, 'spec_bytes': spec_path.stat().st_size,
            'sources': len(sources), 'recipe_sha256': sha(base / 'fixture-recipe.json')}


if __name__ == '__main__':
    print(json.dumps([build_case('probe_a', -2.0, -6.0),
                      build_case('probe_b', -6.0, -8.7)]))
