"""Source-hashed synthetic timing fixtures for public CPU compatibility only."""
import hashlib
import json
from pathlib import Path

from layout import open_drive
from runner import CAMERAS, SUFFIXES, is_stop, requested_speed

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                            for row in rows))


def build(suffix):
    if suffix not in SUFFIXES:
        raise ValueError('Unknown selected case')
    case_id = HERE.name + '__' + suffix
    source = HERE / 'selected-source' / suffix
    source.mkdir(parents=True, exist_ok=True)
    config = json.loads((HERE / 'native' / 'bundles' / suffix / 'construction.json').read_text())
    config = json.loads(next(item['content'] for item in config['files']
                             if item['path'] == 'config.json'))
    signal_frame = config['signal_command_frame']
    write_json(source / 'rear-signal-context.json', {
        'source_kind': 'synthetic_cpu', 'cell_id': 'C230259',
        'public_highway_reviewed': False, 'immediate_rear_reviewed': False,
        'signal_appropriateness_reviewed': False, 'legal_suddenness_reviewed': False,
        'hand_signal_observed': False, 'diagnostic_deceleration_mps2': 3.0,
        'diagnostic_bound_is_statutory': False,
        'fixture_kind': 'synthetic_diagnostic_only'})
    write_json(source / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False})
    (source / 'road.xodr').write_text(open_drive() + '\n')
    recorder = source / 'capture' / 'recorder_info.txt'
    recorder.parent.mkdir(parents=True, exist_ok=True)
    recorder.write_text('Create 107: vehicle.tesla.model3\nCreate 108: vehicle.audi.tt\n')
    actor_rows = []
    camera_rows = []
    frame_map = []
    trace = []
    evidence = []
    native_frames = []
    x = -20.0
    rear_x = -36.0
    previous_speed = 8.0
    for index in range(600):
        native = 100 + index
        time = index / 20
        speed = requested_speed(suffix, index)
        if index:
            x += speed / 20
            rear_x += speed / 20
        acceleration = (speed - previous_speed) * 20 if index else 0.0
        previous_speed = speed
        lamp = index >= signal_frame
        body = [[x - 2, -2.65], [x + 2, -2.65],
                [x + 2, -.85], [x - 2, -.85]]
        rear_body = [[rear_x - 2, -2.65], [rear_x + 2, -2.65],
                     [rear_x + 2, -.85], [rear_x - 2, -.85]]
        ego = {'actor_id': 107, 'blueprint_id': 'vehicle.tesla.model3',
               'center_xy_m': [x, -1.75], 'body_xy_m': body, 'lane_id': -1,
               'speed_mps': speed, 'acceleration_x_mps2': acceleration}
        rear = {'actor_id': 108, 'blueprint_id': 'vehicle.audi.tt',
                'center_xy_m': [rear_x, -1.75], 'body_xy_m': rear_body,
                'lane_id': -1, 'speed_mps': speed,
                'acceleration_x_mps2': acceleration}
        actor_rows.append({'case_id': case_id, 'frame': index,
            'native_frame': native, 'time_s': time,
            'source_kind': 'synthetic_cpu', 'ego': ego, 'rear': rear,
            'ego_lane_id': -1, 'rear_lane_id': -1, 'rear_is_behind': True,
            'surface_gap_m': x - 2 - (rear_x + 2),
            'ego_speed_mps': speed, 'ego_accel_longitudinal_mps2': acceleration,
            'brake_lamp_commanded': lamp, 'brake_lamp_observed': lamp,
            'hand_signal': 'none'})
        trace.append({'frame': native, 'time_s': time,
            'position': {'x': x, 'y': -1.75, 'z': 1},
            'position_m': [x, -1.75, 1], 'heading_deg': 0,
            'speed_mps': speed, 'speed_mph': speed * 2.2369362920544,
            'velocity_mps': [speed, 0, 0],
            'control': {'throttle': 0, 'brake': 0, 'hand_brake': False},
            'synthetic_diagnostic': True,
            'speed_provenance': 'synthetic_native_sample'})
        evidence.append({'original_frame': native, 'replay_frame': native,
            'actor_id': 107, 'recording_time_s': time,
            'replay_simulation_time_s': time,
            'ego': {'position_m': [x, -1.75, 1], 'heading_deg': 0,
                    'speed_mps': speed,
                    'speed_provenance': 'synthetic_native_sample',
                    'body_vertices_m': [[u, v, z] for u, v in body for z in (0, 1.5)]},
            'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                 'wetness': 0, 'fog_density': 0},
                      'road_projection': {'road_id': 1, 'section_id': 0,
                                          'lane_id': -1, 's_m': x + 100}}})
        frame_map.append({'native_frame': native, 'carla_frame': native,
                          'video_frame': index, 'time_s': time,
                          'camera_native_frames': {name: native for name, *_ in CAMERAS}})
        native_frames.append({'frame': native, 'time_s': time,
                              'simulation_time': time, 'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{native:08d}.adapter.json'})
        for name, *_ in CAMERAS:
            camera_rows.append({'frame': index, 'camera': name,
                                'native_frame': native,
                                'rgb_sha256': hashlib.sha256(
                                    f'{case_id}:{index}:{name}'.encode()).hexdigest()})
    files = {'trace.jsonl': trace, 'capture/evidence.jsonl': evidence,
             'actor-sources.jsonl': actor_rows, 'camera-frames.jsonl': camera_rows,
             'video_frames.jsonl': frame_map,
             'capture/native/frames.jsonl': native_frames}
    for name, rows in files.items():
        write_rows(source / name, rows)
    write_json(source / 'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600, 'required_observations': [],
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    generator = {'files': {}, 'graphs': [
        {'path': f'capture/native/graphs/base/{100 + i:08d}.adapter.json',
         'attributes': {'frame': 100 + i}, 'nodes': [], 'edges': []}
        for i in range(600)],
        'videos': [{'path': name + '.mkv', 'frames': 600,
                    'width': width, 'height': height, 'fps': 20, 'color': 'blue'}
                   for name, width, height, *_ in CAMERAS]}
    generator_path = HERE / ('selected-generator-' + suffix + '.json')
    write_json(generator_path, generator)
    source_names = ('acquisition-provenance.json', 'capture/evidence.jsonl',
                    'capture/manifest.json', 'capture/native/frames.jsonl',
                    'capture/recorder_info.txt', 'trace.jsonl', 'video_frames.jsonl',
                    'road.xodr', 'rear-signal-context.json', 'actor-sources.jsonl',
                    'camera-frames.jsonl')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': str((source / name).relative_to(REPO)),
                           'sha256': sha(source / name)} for name in source_names],
              'generator': {'source': str(generator_path.relative_to(REPO)),
                            'sha256': sha(generator_path)}}
    recipe_path = HERE / ('selected-recipe-' + suffix + '.json')
    write_json(recipe_path, recipe)
    return {'case_id': case_id, 'recipe': str(recipe_path.relative_to(REPO))}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in SUFFIXES]))
