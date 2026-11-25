"""Build one explicit synthetic boundary transport fixture for public CPU checks."""
import hashlib
import json
from pathlib import Path
import sys

from native.visibility_geometry import open_drive
from prove_boundary_saved import synthetic_packet


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def row_bytes(data):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n'
                   for row in data)


def body(x, y):
    return [[x+dx, y+dy, z] for dx in (-2, 2) for dy in (-1, 1)
            for z in (0, 1.5)]


def build_one(case):
    case_id = case['case_id']
    suffix = case_id.removeprefix(HERE.name+'__')
    target = HERE/'cases'/suffix
    source = target/'source'
    source.mkdir(parents=True, exist_ok=True)
    request = json.loads((HERE/'draft-boundary-cases'/suffix/'primary'/
                          'construction.json').read_text())
    config = json.loads(next(item['content'] for item in request['files']
                             if item['path'] == 'config.json'))
    boundary = config['boundary_request']
    packet = synthetic_packet(boundary['target_distance_ft'],
                              boundary['civil_branch'], boundary['civil_offset_min'])
    packet.pop('overview.mkv')
    packet.pop('approach.mkv')
    packet.pop('reference_corner.mkv')
    packet.pop('driver_reference.mkv')
    packet['road.xodr'] = open_drive().encode()
    context = json.loads(packet['visibility-context.json'])
    context['map_source_sha256'] = hashlib.sha256(packet['road.xodr']).hexdigest()
    context['visibility_weather_source'] = {
        'native_weather_request': 'ClearNoon',
        'independent_conditions_reviewed': False,
        'synthetic_diagnostic': True}
    packet['visibility-context.json'] = json.dumps(context).encode()
    pixel = json.loads(packet['visibility-pixel-review.json'])
    pixel['map_sha256'] = hashlib.sha256(packet['road.xodr']).hexdigest()
    pixel['context_sha256'] = hashlib.sha256(packet['visibility-context.json']).hexdigest()
    packet['visibility-pixel-review.json'] = json.dumps(pixel).encode()
    for name, content in packet.items():
        (source/name).write_bytes(content)
    trace = rows(source/'visibility-trace.jsonl')
    frame_map = rows(source/'video_frames.jsonl')
    source_trace = []
    for item in trace:
        x, y = item['ego_xy_m']
        speed = item.get('ego_speed_mps', 0)
        source_trace.append({'frame': item['native_frame'], 'time_s': item['time_s'],
                             'position': {'x': x, 'y': y, 'z': 0},
                             'position_m': [x, y, 0], 'heading_deg': 0,
                             'speed_mps': speed, 'speed_mph': speed/.44704,
                             'velocity_mps': [speed, 0, 0], 'control': {}})
    (source/'trace.jsonl').write_text(''.join(
        json.dumps(row, allow_nan=False)+'\n' for row in source_trace))
    evidence, native_frames, graphs = [], [], []
    for point, mapped in zip(trace, frame_map):
        index, frame = point['video_frame'], point['native_frame']
        x, y = point['ego_xy_m']
        t = point['time_s']
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 107, 'recording_time_s': t,
                         'replay_simulation_time_s': t,
                         'ego': {'position_m': [x, y, 0], 'heading_deg': 0,
                                 'speed_mps': point['ego_speed_mps'],
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body(x, y)},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'sun_altitude_angle': 10},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': x+350}}})
        native_frames.append({'frame': frame, 'simulation_time': t,
                              'abstract': None, 'base': None, 'nodes': 1, 'edges': 0,
                              'extraction_seconds': 0, 'capture_seconds': 0,
                              'adapter_graph': f'graphs/base/{frame:08d}.adapter.json'})
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame, 'simulation_time_s': t,
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'sem_class': 'ego', 'entity_id': 107, 'vertex': [x, y, 0],
                           'forward': [1, 0, 0], 'threedbbox': body(x, y)}}],
                       'edges': []})
    if len(trace) != 600 or len(frame_map) != 600:
        raise ValueError('diagnostic needs 600 frames')
    capture = source/'capture'
    (capture/'native').mkdir(parents=True, exist_ok=True)
    (capture/'evidence.jsonl').write_text(row_bytes(evidence))
    (capture/'native/frames.jsonl').write_text(row_bytes(native_frames))
    (capture/'recorder_info.txt').write_text(
        'Create 107: vehicle.tesla.model3\nSynthetic CPU diagnostic only; no CARLA recording.\n')
    write(capture/'manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'acquisition': 'synthetic_diagnostic', 'observation_contract_version': 1,
        'required_observations': ['kin.position'],
        'sources': {'road.xodr': sha(source/'road.xodr'),
                    'visibility-trace.jsonl': sha(source/'visibility-trace.jsonl'),
                    'trace.jsonl': sha(source/'trace.jsonl')},
        'synthetic_diagnostic': True, 'case_id': case_id})
    write(source/'acquisition-provenance.json',
          {'case_id': case_id, 'scope': 'synthetic CPU diagnostic; no original pixels'})
    spec = {'files': {}, 'graphs': graphs,
            'videos': [{'path': name+'.mkv', 'frames': 600,
                        'width': 1920 if name == 'overview' else 1280,
                        'height': 1080 if name == 'overview' else 720,
                        'fps': 20, 'color': color}
                       for name, color in zip(VIEWS, ('blue', 'red', 'green', 'white'))]}
    write(target/'diagnostic.json', spec)
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': path.relative_to(source).as_posix(),
                           'source': path.relative_to(ROOT).as_posix(),
                           'sha256': sha(path)}
                          for path in sorted(source.rglob('*')) if path.is_file()],
              'generator': {'source': (target/'diagnostic.json').relative_to(ROOT).as_posix(),
                            'sha256': sha(target/'diagnostic.json')}}
    write(target/'recipe.json', recipe)
    return {'case_id': case_id, 'source_files': len(recipe['sources']),
            'recipe_sha256': sha(target/'recipe.json'), 'synthetic_only': True}


def main():
    cases = json.loads((HERE/'proposals/boundary-cases-draft.json').read_text())['cases']
    if len(sys.argv) == 2:
        cases = [case for case in cases if case['case_id'].endswith('__'+sys.argv[1])]
        if len(cases) != 1:
            raise ValueError('select one exact boundary suffix')
    elif len(sys.argv) != 1:
        raise ValueError('optional one exact boundary suffix')
    result = [build_one(case) for case in cases]
    print(json.dumps({'cases': result, 'count': len(result),
                      'synthetic_only': True}, sort_keys=True))


if __name__ == '__main__':
    main()
