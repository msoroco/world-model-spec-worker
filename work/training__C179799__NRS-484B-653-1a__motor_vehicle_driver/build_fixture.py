"""Build exact, explicitly synthetic 600-frame person-interaction CPU fixtures."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native.person_scene import MODES, open_drive

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def lines(rows):
    return ''.join(wire(row) for row in rows)


def speed_for(mode, t):
    start, duration = (6, 3) if mode == 'earlier_response' else (8, 2)
    if t < start:
        return 8.0
    if t < start + duration:
        return 8.0 - 6.0*(t-start)/duration
    return 2.0


def make(suffix, mode):
    case_id = ASSIGNMENT + '__selected_ce719cfa__' + suffix
    folder = HERE / 'cases' / suffix
    road = open_drive() + '\n'
    (folder / 'road.xodr').write_text(road)
    packet = {
        'case_id': case_id, 'source_kind': 'synthetic_diagnostic',
        'synthetic_diagnostic': True, 'access_kind': 'highway',
        'highway_or_public_access_source': 'synthetic authored road only; legal highway status unresolved',
        'driver_identity_source': 'synthetic conventional driver actor 1',
        'vehicle_class_source': 'synthetic vehicle actor 1',
        'worker_identity_source': 'synthetic distinct person actor 2',
        'worker_role_source': 'synthetic roadside worker requested role',
        'worker_route_relation_source': 'synthetic worker outside right driving lane edge',
        'sight_line_source': 'synthetic clear road request, actual sight lines unverified',
        'surface_condition_source': 'synthetic dry pavement request',
        'nearby_property_source': 'synthetic surrounding property not established',
        'physical_verified': False, 'legal_verdict': None}
    context = {'source_kind': 'synthetic_native_sample',
               'driving_road_id': 1, 'driving_lane_id': -1,
               'driving_lane_width_m': 3.5,
               'highway_or_public_access_verified': False,
               'surface_and_sight_lines_verified': False}
    raw, frame_map, trace, evidence, graph_index, graphs = [], [], [], [], [], []
    x, last_speed = -78.0, 0.0
    for index in range(600):
        frame, t = 1000+index, index/20
        speed = speed_for(mode, t)
        x += speed/20
        acceleration = (speed-last_speed)*20 if index else 0.0
        last_speed = speed
        y = -1.75
        cameras = dict.fromkeys(CAMERAS, frame)
        raw.append({'frame': index, 'native_frame': frame,
                    'time_s': t, 'native_time_s': t,
                    'ego_actor_id': 1, 'ego_blueprint_id': 'vehicle.synthetic',
                    'ego_x_m': x, 'ego_y_m': y, 'ego_vx_mps': speed,
                    'ego_vy_mps': 0, 'ego_radius_m': 1.5,
                    'ego_accel_longitudinal_mps2': acceleration,
                    'ego_yaw_rate_radps': 0,
                    'person_actor_id': 2,
                    'person_blueprint_id': 'walker.pedestrian.synthetic',
                    'person_x_m': 4, 'person_y_m': -5.2,
                    'person_vx_mps': 0, 'person_vy_mps': 0,
                    'person_radius_m': .4,
                    'collision_sensor_contact': False,
                    'control_readback': {'throttle': .3 if speed > 2 else 0,
                                         'brake': .7 if acceleration < 0 else 0,
                                         'steer': 0}})
        frame_map.append({'video_frame': index, 'native_frame': frame,
                          'carla_frame': frame, 'time_s': t,
                          'camera_native_frames': cameras})
        ego_body = [[x+dx, y+dy, z] for dx in (-1.2, 1.2)
                    for dy in (-.6, .6) for z in (.2, 1.8)]
        person_body = [[4+dx, -5.2+dy, z] for dx in (-.25, .25)
                       for dy in (-.25, .25) for z in (0, 1.8)]
        trace.append({'frame': frame, 'time_s': t,
                      'position': {'x': x, 'y': y, 'z': 1.0},
                      'position_m': [x, y, 1.0], 'heading_deg': 0,
                      'speed_mps': speed, 'speed_mph': speed/.44704,
                      'velocity_mps': [speed, 0, 0],
                      'control': {'throttle': .3 if speed > 2 else 0,
                                  'brake': .7 if acceleration < 0 else 0,
                                  'steer': 0}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 1, 'recording_time_s': t,
                         'replay_simulation_time_s': t,
                         'ego': {'position_m': [x, y, 1.0], 'heading_deg': 0,
                                 'speed_mps': speed, 'body_vertices_m': ego_body,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'participants': {'2': {'role': 'synthetic roadside worker',
                                                'position_m': [4, -5.2, 1.0],
                                                'body_vertices_m': person_body}},
                         'world': {'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0},
                                   'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x+90}}})
        rel = f'graphs/base/{frame:08d}.adapter.json'
        graph_index.append({'frame': frame, 'simulation_time': t,
                            'base': rel, 'adapter_graph': rel, 'nodes': 2, 'edges': 0})
        graphs.append({'path': 'capture/native/' + rel,
                       'attributes': {'frame': frame, 'simulation_time_s': t,
                                      'source': 'synthetic C179799 person interaction fixture',
                                      'synthetic_diagnostic': True},
                       'nodes': [
                           {'id': 'ego', 'attributes': {'entity_id': 1, 'sem_class': 'ego',
                                                      'vertex': [x, y, 1.0],
                                                      'forward': [1, 0, 0],
                                                      'threedbbox': ego_body}},
                           {'id': 'worker', 'attributes': {'entity_id': 2,
                                                         'sem_class': 'pedestrian',
                                                         'vertex': [4, -5.2, 1.0],
                                                         'forward': [0, 1, 0],
                                                         'threedbbox': person_body}}],
                       'edges': []})
    trace_text = lines(trace)
    files = {'original-context-packet.json': wire(packet),
             'native-road-readback.json': wire(context),
             'native-person-interaction.jsonl': lines(raw),
             'video_frames.jsonl': lines(frame_map),
             'trace.jsonl': trace_text,
             'capture/evidence.jsonl': lines(evidence),
             'capture/native/frames.jsonl': lines(graph_index),
             'capture/manifest.json': wire({
                 'synthetic_diagnostic': True,
                 'extraction_confirmed': True, 'frames': 600,
                 'sources': {'trace.jsonl': sha(trace_text.encode()),
                             'road.xodr': sha(road.encode())}}),
             'capture/recorder_info.txt': (
                 'Synthetic C179799 diagnostic, no CARLA recorder.\n'
                 'Create 1: vehicle.synthetic (0)\n'
                 'Create 2: walker.pedestrian.synthetic (0)\n')}
    spec = {'files': files, 'graphs': graphs,
            'videos': [{'path': name+'.mkv', 'frames': 600,
                        'width': width, 'height': height,
                        'fps': 20, 'color': color}
                       for (name, width, height), color in zip(
                           (('overview', 1920, 1080), ('approach', 1280, 720),
                            ('reference_corner', 1280, 720),
                            ('driver_reference', 1280, 720)),
                           ('blue', 'green', 'white', 'red'))]}
    spec_path = folder / 'fixture-spec.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': 'work/'+ASSIGNMENT+'/cases/'+suffix+'/road.xodr',
                           'sha256': sha((folder/'road.xodr').read_bytes())}],
              'generator': {'source': 'work/'+ASSIGNMENT+'/cases/'+suffix+'/fixture-spec.json',
                            'sha256': sha(spec_path.read_bytes())}}
    (folder/'fixture-recipe.json').write_text(json.dumps(recipe, indent=2)+'\n')
    return {'case_id': case_id, 'spec_bytes': spec_path.stat().st_size,
            'minimum_speed_mps': min(speed_for(mode, i/20) for i in range(600))}


if __name__ == '__main__':
    print(json.dumps([make(suffix, mode) for suffix, mode in MODES.items()]))
