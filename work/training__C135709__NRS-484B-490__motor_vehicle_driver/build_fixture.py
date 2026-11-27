"""Generate small, explicitly synthetic source fixtures for both selected cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from geometry import open_drive

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FIELDS = ('highway', 'narrow_designation', 'official_authority',
          'device_erection', 'device_content', 'governed_extent')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def lines(rows):
    return ''.join(wire(row) for row in rows)


def make(suffix, x):
    case_id = ASSIGNMENT + '__' + suffix
    directory = HERE / 'cases' / suffix
    road = open_drive() + '\n'
    (directory / 'road.xodr').write_text(road)
    native = {'assignment_id': ASSIGNMENT, 'case_id': case_id,
              'source_kind': 'synthetic_native_sample', 'map_sha256': sha(road.encode()),
              'map_name': 'synthetic-C135709',
              'native_survey': {'requested_device_id': '490', 'sign_pixels_verified': False},
              'requested_governed_extent_xyxy_m': [-20, -3.1, 20, 0],
              'requested_parking_xy_m': [x, -2], 'original_source_refs': None,
              'official_authority_verified': False, 'narrow_highway_verified': False,
              'governed_extent_verified': False, 'physical_verified': False,
              'legal_verdict': None}
    native_text = wire(native)
    source_text = {name: 'Synthetic C135709 CPU source: ' + name +
                   '; not original official authority or legal narrowness.\n'
                   for name in FIELDS}
    review = {'case_id': case_id, 'native_context_sha256': sha(native_text.encode()),
              'synthetic_diagnostic': True, 'roadway_is_highway': True,
              'narrow_highway_designated': True, 'device_is_official': True,
              'device_erected': True, 'device_prohibits_parking': True,
              'device_id': '490', 'governed_road_id': '1',
              'governed_extent_xyxy_m': [-20, -3.1, 20, 0],
              'measured_road_width_m': 5.6,
              'narrow_section_source_id': 'synthetic-narrow-section',
              'device_official_source_id': 'synthetic-official-device',
              'sources': {name: {'path': 'source_context/' + name + '.txt',
                                 'sha256': sha(source_text[name].encode()),
                                 'source_id': 'synthetic-' + name}
                          for name in FIELDS}}
    poses, frame_map, trace, evidence, graph_index, graphs = [], [], [], [], [], []
    for i in range(600):
        frame, time_s, y = 1000 + i, i / 20, -2.0
        corners = [[x-2, y-.6], [x+2, y-.6], [x+2, y+.6], [x-2, y+.6]]
        cameras = dict.fromkeys(CAMERAS, frame)
        poses.append({'video_frame': i, 'time_s': time_s, 't_s': time_s,
                      'native_frame': frame, 'camera_native_frames': cameras,
                      'vehicle_id': 'synthetic-ego', 'speed_mps': 0,
                      'x_m': x, 'y_m': y, 'bbox_half_length_m': 2,
                      'bbox_half_width_m': .6, 'footprint_corners_xy_m': corners})
        frame_map.append({'video_frame': i, 'time_s': time_s,
                          'native_frame': frame, 'carla_frame': frame,
                          'camera_native_frames': cameras})
        body = [[px, py, z] for px, py in corners for z in (8, 9.5)]
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': 8.5},
                      'position_m': [x, y, 8.5], 'heading_deg': 0,
                      'speed_mps': 0, 'speed_mph': 0,
                      'velocity_mps': [0, 0, 0],
                      'control': {'throttle': 0, 'brake': 1, 'hand_brake': True}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 1, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': [x, y, 8.5], 'heading_deg': 0,
                                 'speed_mps': 0, 'body_vertices_m': body,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'participants': {},
                         'world': {'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0},
                                   'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x + 70}}})
        rel = f'graphs/base/{frame:08d}.adapter.json'
        graph_index.append({'frame': frame, 'simulation_time': time_s,
                            'base': rel, 'adapter_graph': rel, 'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + rel,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'source': 'synthetic C135709 narrow parking fixture',
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
                                            'extraction_confirmed': True,
                                            'frames': 600,
                                            'sources': {'trace.jsonl': sha(trace_text.encode()),
                                                        'road.xodr': sha(road.encode())}}),
             'capture/recorder_info.txt': 'Synthetic C135709 CPU diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n'}
    files.update({'source_context/' + name + '.txt': source_text[name] for name in FIELDS})
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
                           'sha256': sha((directory / 'road.xodr').read_bytes())}],
              'generator': {'source': 'work/' + ASSIGNMENT + '/cases/' + suffix + '/fixture-spec.json',
                            'sha256': sha(spec_path.read_bytes())}}
    (directory / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case_id': case_id, 'spec_bytes': spec_path.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([make('probe_01', 35.0), make('probe_02', 0.0)]))
