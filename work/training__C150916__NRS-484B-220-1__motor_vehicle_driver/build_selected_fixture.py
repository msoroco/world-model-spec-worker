"""Generate bounded synthetic CPU diagnostics for the two selected directions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def lines(rows):
    return ''.join(wire(row) for row in rows)


def make(direction):
    case_id = ASSIGNMENT + '__' + direction
    directory = HERE / 'cases' / direction
    directory.mkdir(parents=True, exist_ok=True)
    road = (HERE / 'selected' / 'road.xodr').read_bytes()
    context = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
               'road_id': '1', 'map_source_sha256': sha(road),
               'one_way_designation_source_sha256': None,
               'signposting_source_sha256': None, 'roadway_is_one_way': None,
               'sign_request_ids': [101, 102], 'requested_direction': direction,
               'permitted_direction_xy': [1, 0],
               'governed_longitudinal_extent_m': [-100, 300],
               'native_survey': {'driving_lane_ids': [-2, -1],
                                 'sign_request_ids': [101, 102]},
               'physical_sign_pixels_verified': False,
               'operator_source_review_required': True}
    context_text = wire(context)
    source_text = {key: 'Synthetic CPU one-way diagnostic: ' + key + '; no original Native authority claimed.\n'
                   for key in ('one_way_designation', 'sign_inventory', 'sign_authority',
                               'sign_erection', 'sign_governance')}
    review = {'case_id': case_id, 'native_context_sha256': sha(context_text.encode()),
              'requested_direction': direction, 'synthetic_diagnostic': True,
              'roadway_is_one_way': True, 'sign_official': True,
              'sign_erected': True, 'sign_governs_road': True,
              'physical_sign_pixels_verified': False}
    for key, value in source_text.items():
        review[key] = {'path': 'source_context/' + key + '.txt',
                       'sha256': sha(value.encode()), 'source_id': 'synthetic-' + key}
    poses, maps, traces, evidence, graph_index, graphs = [], [], [], [], [], []
    sign = 1 if direction == 'designated' else -1
    start = -20 if sign == 1 else 220
    for i in range(600):
        native, time_s = 1000 + i, i / 20
        x, y, speed = start + sign * 8 * time_s, 1.75, 8
        corners = [[x - 2, y - .5], [x + 2, y - .5],
                   [x + 2, y + .5], [x - 2, y + .5]]
        cameras = dict.fromkeys(CAMERAS, native)
        poses.append({'video_frame': i, 'time_s': time_s, 'native_frame': native,
                      'camera_native_frames': cameras, 'vehicle_id': 'synthetic-ego',
                      'speed_mps': speed, 'yaw_deg': 0 if sign == 1 else 180,
                      'footprint_corners_xy_m': corners, 'requested_direction': direction})
        maps.append({'video_frame': i, 'time_s': time_s, 'native_frame': native,
                     'carla_frame': native, 'camera_native_frames': cameras})
        body = [[px, py, z] for px, py in corners for z in (8.0, 9.5)]
        traces.append({'frame': native, 'time_s': time_s,
                       'position': {'x': x, 'y': y, 'z': 8.5},
                       'position_m': [x, y, 8.5], 'heading_deg': 0 if sign == 1 else 180,
                       'speed_mps': speed, 'speed_mph': speed / .44704,
                       'velocity_mps': [sign * speed, 0, 0],
                       'control': {'throttle': .2, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': native, 'replay_frame': native,
                         'actor_id': 1, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, y, 8.5],
                                 'heading_deg': 0 if sign == 1 else 180,
                                 'speed_mps': speed, 'body_vertices_m': body,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'participants': {},
                         'world': {'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0},
                                   'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x + 100}}})
        rel = f'graphs/base/{native:08d}.adapter.json'
        graph_index.append({'frame': native, 'simulation_time': time_s,
                            'base': rel, 'adapter_graph': rel, 'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + rel,
                       'attributes': {'frame': native, 'simulation_time_s': time_s,
                                      'source': 'synthetic one-way travel fixture',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'entity_id': 1, 'sem_class': 'ego', 'vertex': [x, y, 8.5],
                           'forward': [sign, 0, 0], 'threedbbox': body}}],
                       'edges': []})
    trace_text = lines(traces)
    files = {'road-context.json': context_text, 'road-review.json': wire(review),
             'vehicle-pose.jsonl': lines(poses), 'video_frames.jsonl': lines(maps),
             'trace.jsonl': trace_text, 'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(graph_index),
             'capture/manifest.json': wire({'synthetic_diagnostic': True,
                                            'extraction_confirmed': True,
                                            'frames': 600,
                                            'sources': {'trace.jsonl': sha(trace_text.encode()),
                                                        'road.xodr': sha(road)}}),
             'capture/recorder_info.txt': 'Synthetic CPU one-way diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n'}
    files.update({'source_context/' + key + '.txt': value for key, value in source_text.items()})
    spec = {'files': files, 'graphs': graphs,
            'videos': [{'path': name + '.mkv', 'frames': 600,
                        'width': width, 'height': height, 'fps': 20, 'color': color}
                       for (name, width, height), color in zip(
                           (('overview', 1920, 1080), ('approach', 1280, 720),
                            ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)),
                           ('blue', 'green', 'white', 'red'))]}
    spec_path = directory / 'fixture-spec.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    plan = HERE / 'case-plan.json'
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': 'work/' + ASSIGNMENT + '/selected/road.xodr',
                           'sha256': sha(road)},
                          {'path': 'case-plan-source.json',
                           'source': 'work/' + ASSIGNMENT + '/case-plan.json',
                           'sha256': sha(plan.read_bytes())}],
              'generator': {'source': 'work/' + ASSIGNMENT + '/cases/' + direction + '/fixture-spec.json',
                            'sha256': sha(spec_path.read_bytes())}}
    (directory / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case_id, 'spec_bytes': spec_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([make(direction) for direction in ('designated', 'opposite')]))
