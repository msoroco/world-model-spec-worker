"""Source-hashed synthetic lane-change fixtures for CPU compatibility only."""
import hashlib
import json
from pathlib import Path

from layout import check as check_layout, open_drive
from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
VIEWS = (('overview', 1920, 1080), ('approach', 1280, 720),
         ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, separators=(',', ':'), allow_nan=False) + '\n'
                            for v in values))


def body(x, y):
    return [[x - 2, y - 0.9], [x + 2, y - 0.9],
            [x + 2, y + 0.9], [x - 2, y + 0.9]]


def build(suffix):
    if suffix not in CASES:
        raise ValueError('Unknown exact selected case')
    check_layout()
    case_id = PACKAGE.name + '__' + suffix
    construction = json.loads((HERE / 'selected' / suffix / 'construction.json').read_text())
    config = json.loads(next(f['content'] for f in construction['files']
                             if f['path'] == 'config.json'))
    source = PACKAGE / 'selected-source' / suffix
    source.mkdir(parents=True, exist_ok=True)
    road = source / 'road.xodr'
    road.write_text(open_drive() + '\n')
    write(source / 'driving-context.json', {
        'source_kind': 'synthetic_native_sample', 'case_id': case_id,
        'cell_id': 'C245490', 'law_id': 'NRS-484B-223-1b',
        'actor': 'motor_vehicle_driver', 'same_direction_marked_lane_count': 2,
        'occupied_lane_id': -2, 'target_lane_id': -1,
        'controller_gap_rule_m': 12.0,
        'controller_gap_rule_is_legal_threshold': False,
        'fixture_kind': 'synthetic_diagnostic_only',
        'legal_verdict': None,
    })
    write(source / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False,
    })
    recorder = source / 'capture' / 'recorder_info.txt'
    recorder.parent.mkdir(parents=True, exist_ok=True)
    recorder.write_text('Create 107: vehicle.tesla.model3\nCreate 108: vehicle.tesla.model3\nCreate 109: vehicle.tesla.model3\n')
    trace, evidence, frame_map, native_frames, motion = [], [], [], [], []
    x0 = -20.0
    rear_distance = config['target_vehicle_behind_m']
    gap = rear_distance - 4.0
    signal_command = config['signal_start_frame']
    signal_observed = signal_command + 1
    for i in range(600):
        native = 100 + i
        t = i / 20
        x = x0 + i * 0.2
        lateral = min(1.8, (i - 180) * 0.03) if i >= 180 else 0.0
        y = -5.25 + lateral
        rear_x = x - rear_distance
        front_x = x + 35.0
        lane = -1 if lateral + 0.9 > 1.75 else -2
        trace.append({'frame': native, 'time_s': t,
                      'position': {'x': x, 'y': y, 'z': 1},
                      'position_m': [x, y, 1], 'heading_deg': 0,
                      'speed_mps': 4, 'speed_mph': 8.947745168,
                      'velocity_mps': [4, 0, 0],
                      'control': {'throttle': 0.2, 'brake': 0,
                                  'hand_brake': False},
                      'synthetic_diagnostic': True,
                      'speed_provenance': 'synthetic_native_sample'})
        ego_body = body(x, y)
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': 107, 'recording_time_s': t,
                         'replay_simulation_time_s': t,
                         'ego': {'position_m': [x, y, 1], 'heading_deg': 0,
                                 'speed_mps': 4,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': [[u, v, z] for u, v in ego_body
                                                     for z in (0, 1.5)]},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': lane, 's_m': x + 100}}})
        frame_map.append({'native_frame': native, 'carla_frame': native,
                          'video_frame': i, 'time_s': t,
                          'camera_native_frames': {view: native for view, _, _ in VIEWS}})
        native_frames.append({'frame': native, 'time_s': t,
                              'simulation_time': t, 'synthetic_diagnostic': True,
                              'adapter_graph': f'graphs/base/{native:08d}.adapter.json'})
        motion.append({'source_kind': 'synthetic_native_sample',
                       'native_frame': native, 'video_frame': i, 'time_s': t,
                       'position_m': [x, y, 1], 'velocity_mps': [4, 0, 0],
                       'same_direction_marked_lane_count': 2,
                       'occupied_lane_id': -2, 'current_lane_id': lane,
                       'occupied_lane_half_width_m': 1.75,
                       'ego_body_half_width_m': 0.9,
                       'ego_lateral_offset_from_occupied_lane_center_m': lateral,
                       'target_direction_indicator_requested_on': i >= signal_command,
                       'target_direction_indicator_observed_on': i >= signal_observed,
                       'target_front_position_m': [front_x, -1.75, 1],
                       'target_rear_position_m': [rear_x, -1.75, 1],
                       'target_front_surface_gap_m': 31.0,
                       'target_rear_surface_gap_m': gap,
                       'target_lane_min_surface_gap_m': gap,
                       'target_lane_closing_speed_mps': 0.0,
                       'driver_safety_ascertainment': None})
    checks = [{'source_kind': 'synthetic_native_sample',
               'native_frame': 270, 'video_frame': 170,
               'action': config['check_action'],
               'sampled_target_lane_gap_m': gap if config['check_action'] == 'evaluated' else None,
               'engineering_rule_id': 'controller-gap-check-v1' if config['check_action'] == 'evaluated' else None,
               'decision_to_depart': gap >= 12.0 if config['check_action'] == 'evaluated' else None,
               'legal_threshold_claimed': False,
               'source_actor_ids': ['108', '109']}]
    files = {'trace.jsonl': trace, 'capture/evidence.jsonl': evidence,
             'video_frames.jsonl': frame_map,
             'capture/native/frames.jsonl': native_frames,
             'native-ego-frames.jsonl': motion,
             'native-driver-checks.jsonl': checks}
    for name, items in files.items():
        rows(source / name, items)
    write(source / 'capture' / 'manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'required_observations': [], 'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(road),
                    'trace.jsonl': sha(source / 'trace.jsonl')}})
    generator = {
        'files': {},
        'graphs': [{'path': f'capture/native/graphs/base/{100+i:08d}.adapter.json',
                    'attributes': {'frame': 100+i}, 'nodes': [], 'edges': []}
                   for i in range(600)],
        'videos': [{'path': view + '.mkv', 'frames': 600,
                    'width': width, 'height': height, 'fps': 20, 'color': 'blue'}
                   for view, width, height in VIEWS],
    }
    generator_path = PACKAGE / ('selected-generator-' + suffix + '.json')
    write(generator_path, generator)
    names = ('acquisition-provenance.json', 'capture/evidence.jsonl',
             'capture/manifest.json', 'capture/native/frames.jsonl',
             'capture/recorder_info.txt', 'trace.jsonl', 'video_frames.jsonl',
             'road.xodr', 'driving-context.json', 'native-ego-frames.jsonl',
             'native-driver-checks.jsonl')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': str((source / name).relative_to(ROOT)),
                           'sha256': sha(source / name)} for name in names],
              'generator': {'source': str(generator_path.relative_to(ROOT)),
                            'sha256': sha(generator_path)}}
    recipe_path = PACKAGE / ('selected-recipe-' + suffix + '.json')
    write(recipe_path, recipe)
    return str(recipe_path.relative_to(ROOT))


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in CASES]))
