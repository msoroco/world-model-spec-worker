"""Write source-shaped textual median-turn CPU fixtures; media stays ignored."""
import hashlib
import json
from pathlib import Path
import sys

PKG = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).resolve().parent
sys.path.insert(0, str(PKG))
from median_scene import BARRIER_BOUNDS, CAMERAS, CASES, MEDIAN_BOUNDS, OPENING_BOUNDS, request

VIDEOS = [{'path': name+'.mkv', 'frames': 600, 'width': width,
           'height': height, 'fps': 20, 'color': 'black'}
          for name, width, height in CAMERAS]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def lines(values):
    return ''.join(json.dumps(row, sort_keys=True, allow_nan=False)+'\n'
                   for row in values)


def build(suffix):
    req = request(suffix)
    probe = 'probe_a' if suffix == 'through_opening' else 'probe_b'
    source = PKG/'fixtures/median'/probe
    source_rows = [json.loads(line) for line in (source/'body.jsonl').read_text().splitlines()]
    if len(source_rows) != 600:
        raise ValueError('Original diagnostic source changed')
    folder = NATIVE/'diagnostic'/suffix
    folder.mkdir(parents=True, exist_ok=True)
    context = {'source_kind': 'synthetic_native_sample', 'diagnostic_fixture': True,
        'case_id': PKG.name+'__'+suffix,
        'median_bounds_m': MEDIAN_BOUNDS, 'opening_bounds_m': OPENING_BOUNDS,
        'barrier_bounds_m': BARRIER_BOUNDS,
        'public_authority_establishment': 'pending_original_source',
        'native_roadways': None, 'legal_verdict': None}
    put(folder/'median-context.json', json.dumps(context, indent=2)+'\n')
    motion, frame_map, trace, evidence, native_frames, graphs, body_history = [], [], [], [], [], [], []
    for i, row in enumerate(source_rows):
        body = row['native_body_xy_m']
        x = sum(point[0] for point in body)/4
        y = sum(point[1] for point in body)/4
        speed = row['speed_mps']
        body3 = [[point[0], point[1], z] for point in body for z in (0, 1.5)]
        ego = {'center_xyz_m': [x, y, 1.5], 'yaw_deg': 0 if i < 100 else 90,
               'body_xy_m': body, 'speed_mps': speed,
               'velocity_xyz_mps': [0, speed, 0]}
        body_history.append({'frame': i, 'time_s': i/20,
            'body_vertices_m': body3, 'heading_deg': ego['yaw_deg']})
        motion.append({'native_frame': i, 'video_frame': i, 'time_s': i/20,
            'source_kind': 'synthetic_native_sample', 'ego': ego,
            'route_target_index': min(3, i//150), 'legal_verdict': None})
        frame_map.append({'video_frame': i, 'native_frame': i,
            'carla_frame': i, 'time_s': i/20,
            'camera_native_frames': {name: i for name, _, _ in CAMERAS}})
        trace.append({'frame': i, 'time_s': i/20,
            'position': {'x': x, 'y': y, 'z': 1.5}, 'position_m': [x, y, 1.5],
            'velocity_mps': [0, speed, 0], 'speed_mps': speed,
            'speed_mph': speed*2.2369362921, 'heading_deg': ego['yaw_deg'],
            'control': {}, 'source_kind': 'synthetic_native_sample'})
        evidence.append({'replay_frame': i, 'original_frame': i,
            'recording_time_s': i/20, 'replay_simulation_time_s': i/20,
            'actor_id': 10,
            'ego': {'position_m': [x, y, 1.5], 'heading_deg': ego['yaw_deg'],
                    'speed_mps': speed, 'body_vertices_m': body3,
                    'synthetic_diagnostic': True,
                    'speed_provenance': 'synthetic_native_sample'},
            'other_actors': [],
            'world': {'road_projection': {'road_id': 1241631,
                'lane_id': -1, 'section_id': 0, 's_m': x+70},
                'weather': {'cloudiness': 0, 'fog_density': 0,
                    'precipitation': 0, 'wetness': 0}}})
        graph_path = f'capture/native/graphs/base/{i:08d}.adapter.json'
        native_frames.append({'frame': i, 'simulation_time': i/20,
            'nodes': 1, 'edges': 0,
            'base': f'graphs/base/{i:08d}.adapter.json',
            'adapter_graph': f'graphs/base/{i:08d}.adapter.json'})
        graphs.append({'path': graph_path,
            'attributes': {'frame': i, 'simulation_time_s': i/20,
                'synthetic_diagnostic': True}, 'edges': [],
            'nodes': [{'id': 'ego', 'attributes': {'entity_id': 10,
                'sem_class': 'ego', 'vertex': [x, y, 1.5],
                'forward': [1, 0, 0], 'threedbbox': body3}}]})
    for name, value in (('native-median.jsonl', motion),
                        ('body_history.jsonl', body_history),
                        ('video_frames.jsonl', frame_map),
                        ('trace.jsonl', trace),
                        ('capture/evidence.jsonl', evidence)):
        put(folder/name, lines(value))
    capture_manifest = {'extraction_confirmed': True, 'frames': 600,
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': hashlib.sha256(req['source_map'].encode()).hexdigest(),
                    'trace.jsonl': sha(folder/'trace.jsonl')}}
    put(folder/'capture/manifest.json', json.dumps(capture_manifest, sort_keys=True)+'\n')
    spec = {'files': {'capture/native/frames.jsonl': lines(native_frames),
        'capture/recorder_info.txt': 'Synthetic C124163 CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\n'},
        'graphs': graphs, 'videos': VIDEOS}
    spec_path = NATIVE/f'diagnostic-{suffix}-fixture-spec.json'
    put(spec_path, json.dumps(spec, separators=(',', ':'))+'\n')
    sources = []
    for name in ('median-context.json', 'native-median.jsonl',
                 'body_history.jsonl',
                 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                 'capture/manifest.json'):
        path = folder/name
        sources.append({'path': name, 'source': str(path.relative_to(Path.cwd())),
                        'sha256': sha(path)})
    recipe = {'format': 'worker-fixture-recipe',
        'generator': {'source': str(spec_path.relative_to(Path.cwd())),
                      'sha256': sha(spec_path)}, 'sources': sources}
    recipe_path = NATIVE/f'diagnostic-{suffix}-fixture-recipe.json'
    put(recipe_path, json.dumps(recipe, indent=2)+'\n')
    return {'case': suffix, 'spec_bytes': spec_path.stat().st_size,
            'recipe': str(recipe_path.relative_to(PKG))}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in CASES], indent=2))
