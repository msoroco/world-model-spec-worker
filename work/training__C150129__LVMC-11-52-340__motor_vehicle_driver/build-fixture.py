"""Generate small textual, explicitly synthetic parking compatibility recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native.geometry import geometry, open_drive


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
FRAMES = 600
RATE = 20


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def text(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def lines(values):
    return ''.join(text(value) for value in values)


def body(x, y=-5.25):
    return [[x + dx, y + dy, z] for dx in (-2.0, 2.0)
            for dy in (-.8, .8) for z in (8.0, 9.5)]


def make(suffix, target_x):
    case_id = ASSIGNMENT + '__' + suffix
    directory = HERE / 'cases' / suffix
    directory.mkdir(parents=True, exist_ok=True)
    road = open_drive() + '\n'
    road_path = HERE / 'selected-road.xodr'
    road_path.write_text(road)
    source_text = {field: 'Synthetic CPU source for ' + field + '; no municipal authority claimed.\n'
                   for field in ('city_street', 'council_designation',
                                 'posting_or_marking', 'subject_vehicle_status')}
    inventory = geometry()
    inventory.update(assignment_id=ASSIGNMENT,
                     source_kind='synthetic_native_sample',
                     space_id='city-space-01',
                     space_polygon_xy_m=inventory['city_space_polygon_xy_m'],
                     native_marker_actor_id=17,
                     native_marker_blueprint='static.prop.streetsign',
                     city_street_source_id=None,
                     council_designation_source_id=None,
                     posting_or_marking_source_id=None,
                     posting_space_id=None,
                     subject_status_source_id=None,
                     subject_city_vehicle=None)
    inventory_text = text(inventory)
    review = {'format': 'c150129-independent-source-review-v1',
              'assignment_id': ASSIGNMENT, 'case_id': case_id,
              'native_inventory_sha256': sha_bytes(inventory_text.encode())}
    assertions = {
        'city_street': {'is_city_street': True},
        'council_designation': {'designated_for_city_vehicles': True,
                                'space_id': 'city-space-01'},
        'posting_or_marking': {'posted_or_marked': True,
                               'space_id': 'city-space-01',
                               'native_marker_actor_id': 17},
        'subject_vehicle_status': {'subject_city_vehicle': False},
    }
    for field, values in assertions.items():
        review[field] = dict(values,
                             path='source_context/' + field + '.txt',
                             sha256=sha_bytes(source_text[field].encode()),
                             source_id='synthetic-' + field,
                             review_method='Synthetic fixture source join; independent real review pending')
    poses, frame_map, trace, evidence, graph_index, graphs = [], [], [], [], [], []
    for i in range(FRAMES):
        frame, time_s = i + 1000, i / RATE
        x = -38 + (target_x + 38) * min(i / 150, 1)
        speed = 0 if 200 <= i < 500 else 2
        poses.append({'video_frame': i, 'native_frame': frame, 'time_s': time_s,
                      'vehicle_id': 'subject', 'vehicle_xy_m': [x, -5.25],
                      'yaw_rad': 0, 'bbox_half_length_m': 2.0,
                      'bbox_half_width_m': .8, 'speed_mps': speed,
                      'blueprint_id': 'vehicle.tesla.model3'})
        frame_map.append({'video_frame': i, 'carla_frame': frame,
                          'native_frame': frame, 'time_s': time_s})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': -5.25, 'z': 8.5},
                      'position_m': [x, -5.25, 8.5], 'heading_deg': 0,
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': [speed, 0, 0],
                      'control': {'throttle': 0, 'brake': 1 if speed == 0 else 0,
                                  'hand_brake': False}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 1, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, -5.25, 8.5],
                                 'heading_deg': 0, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': body(x),
                                 'synthetic_diagnostic': True},
                         'participants': {},
                         'world': {'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0},
                                   'road_projection': {'road_id': 1, 'lane_id': -2,
                                                       'section_id': 0, 's_m': x + 50}}})
        graph_rel = f'graphs/base/{frame:08d}.adapter.json'
        graph_index.append({'frame': frame, 'simulation_time': time_s,
                            'base': graph_rel, 'adapter_graph': graph_rel,
                            'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + graph_rel,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'source': 'C150129 synthetic parking fixture',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego',
                                  'attributes': {'entity_id': 1, 'sem_class': 'ego',
                                                 'vertex': [x, -5.25, 8.5],
                                                 'forward': [1.0, 0.0, 0.0],
                                                 'threedbbox': body(x)}}],
                       'edges': []})
    trace_text = lines(trace)
    capture_manifest = {'synthetic_diagnostic': True,
                        'extraction_confirmed': True, 'frames': FRAMES,
                        'sources': {'trace.jsonl': sha_bytes(trace_text.encode()),
                                    'road.xodr': sha_bytes(road.encode())}}
    files = {'parking-inventory.json': inventory_text,
             'review.json': text(review),
             'vehicle-poses.jsonl': lines(poses),
             'video_frames.jsonl': lines(frame_map),
             'trace.jsonl': trace_text,
             'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(graph_index),
             'capture/manifest.json': json.dumps(capture_manifest, indent=2) + '\n',
             'capture/recorder_info.txt': 'Synthetic CPU parking diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n'}
    files.update({'source_context/' + field + '.txt': value
                  for field, value in source_text.items()})
    videos = [{'path': name + '.mkv', 'frames': FRAMES,
               'width': width, 'height': height, 'fps': RATE, 'color': color}
              for name, width, height, color in (
                  ('overview', 1920, 1080, 'blue'),
                  ('approach', 1280, 720, 'green'),
                  ('reference_corner', 1280, 720, 'white'),
                  ('driver_reference', 1280, 720, 'red'))]
    spec = {'files': files, 'graphs': graphs, 'videos': videos}
    spec_path = directory / 'fixture-spec.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': 'work/' + ASSIGNMENT + '/selected-road.xodr',
                           'sha256': sha_bytes(road.encode())}],
              'generator': {'source': 'work/' + ASSIGNMENT + '/cases/' + suffix + '/fixture-spec.json',
                            'sha256': sha_bytes(spec_path.read_bytes())}}
    (directory / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case_id, 'spec_bytes': spec_path.stat().st_size,
            'recipe_sha256': sha_bytes((directory / 'fixture-recipe.json').read_bytes())}


def main():
    print(json.dumps([make('controlled_1', -12), make('controlled_2', 12)],
                     sort_keys=True))


if __name__ == '__main__':
    main()
