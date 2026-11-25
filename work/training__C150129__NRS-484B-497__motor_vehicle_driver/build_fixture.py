"""Generate source-hashed, explicitly synthetic four-camera NRS diagnostics."""
import hashlib
import json
from pathlib import Path

from native.geometry import open_drive

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CASES = (('witness_1', True), ('witness_2', False),
         ('exception_1_1', False), ('exception_1_2', True))
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def lines(rows):
    return ''.join(wire(row) for row in rows)


def make(suffix, permission):
    case_id = ASSIGNMENT + '__' + suffix
    directory = HERE / 'cases' / suffix
    directory.mkdir(parents=True, exist_ok=True)
    road = open_drive(permission) + '\n'
    road_path = directory / 'road.xodr'
    road_path.write_text(road)
    native = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
              'road_id': '1', 'map_source_sha256': sha(road.encode()),
              'permission_device_requested': permission, 'device_id': '497' if permission else None,
              'centerline_origin_xy_m': [0, 0], 'permitted_direction_xy': [1, 0],
              'street_half_width_m': 6.5,
              'native_survey': {'permission_device_requested': permission},
              'physical_sign_pixels_verified': False}
    native_text = wire(native)
    source_text = {name: 'Synthetic NRS 484B.497 CPU source: ' + name + '; no official authority claimed.\n'
                   for name in ('one_way_designation', 'street_boundary', 'device_inventory',
                                'device_authority', 'device_content', 'device_erection', 'device_governance')}
    review = {'case_id': case_id, 'native_context_sha256': sha(native_text.encode()),
              'synthetic_diagnostic': True, 'roadway_is_laned': True,
              'roadway_is_one_way': True, 'permission_device_present': permission,
              'device_official': permission, 'device_erected': permission,
              'notice_permits_left_standing_or_parking': permission,
              'device_governs_road_id': '1' if permission else None}
    for name, value in source_text.items():
        if name.startswith('device_') and name != 'device_inventory' and not permission:
            continue
        review[name] = {'path': 'source_context/' + name + '.txt',
                        'sha256': sha(value.encode()), 'source_id': 'synthetic-' + name}
    poses, frame_map, trace, evidence, graph_index, graphs = [], [], [], [], [], []
    for i in range(600):
        frame, time_s = 1000 + i, i / 20
        x = -30 + min(i / 180, 1) * 45
        y = 2.0
        speed = 0 if i >= 210 else 2
        corners = [[x - 2, y - .5], [x + 2, y - .5],
                   [x + 2, y + .5], [x - 2, y + .5]]
        camera_frames = dict.fromkeys(CAMERAS, frame)
        poses.append({'video_frame': i, 'time_s': time_s, 'native_frame': frame,
                      'camera_native_frames': camera_frames, 'vehicle_id': 'synthetic-ego',
                      'speed_mps': speed, 'footprint_corners_xy_m': corners})
        frame_map.append({'video_frame': i, 'time_s': time_s,
                          'native_frame': frame, 'carla_frame': frame,
                          'camera_native_frames': camera_frames})
        body = [[px, py, z] for px, py in corners for z in (8.0, 9.5)]
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': 8.5},
                      'position_m': [x, y, 8.5], 'heading_deg': 0,
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': [speed, 0, 0],
                      'control': {'throttle': 0, 'brake': int(speed == 0),
                                  'hand_brake': speed == 0}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 1, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, y, 8.5], 'heading_deg': 0,
                                 'speed_mps': speed, 'body_vertices_m': body,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'participants': {},
                         'world': {'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0},
                                   'road_projection': {'road_id': 1, 'lane_id': 1,
                                                       'section_id': 0, 's_m': x + 60}}})
        rel = f'graphs/base/{frame:08d}.adapter.json'
        graph_index.append({'frame': frame, 'simulation_time': time_s,
                            'base': rel, 'adapter_graph': rel, 'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + rel,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'source': 'synthetic NRS one-way parking fixture',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 1,
                                                             'sem_class': 'ego',
                                                             'vertex': [x, y, 8.5],
                                                             'forward': [1, 0, 0],
                                                             'threedbbox': body}}],
                       'edges': []})
    trace_text = lines(trace)
    files = {'road-context.json': native_text, 'road-review.json': wire(review),
             'vehicle-pose.jsonl': lines(poses), 'video_frames.jsonl': lines(frame_map),
             'trace.jsonl': trace_text, 'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(graph_index),
             'capture/manifest.json': wire({'synthetic_diagnostic': True,
                                            'extraction_confirmed': True, 'frames': 600,
                                            'sources': {'trace.jsonl': sha(trace_text.encode()),
                                                        'road.xodr': sha(road.encode())}}),
             'capture/recorder_info.txt': 'Synthetic CPU NRS diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n'}
    files.update({'source_context/' + name + '.txt': value
                  for name, value in source_text.items()
                  if name in review})
    spec = {'files': files, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                        'height': height, 'fps': 20, 'color': color}
                       for (name, width, height), color in zip(
                           (('overview', 1920, 1080), ('approach', 1280, 720),
                            ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)),
                           ('blue', 'green', 'white', 'red'))]}
    spec_path = directory / 'fixture-spec.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': 'work/' + ASSIGNMENT + '/cases/' + suffix + '/road.xodr',
                           'sha256': sha(road_path.read_bytes())}],
              'generator': {'source': 'work/' + ASSIGNMENT + '/cases/' + suffix + '/fixture-spec.json',
                            'sha256': sha(spec_path.read_bytes())}}
    (directory / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case_id, 'spec_bytes': spec_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([make(*case) for case in CASES]))
