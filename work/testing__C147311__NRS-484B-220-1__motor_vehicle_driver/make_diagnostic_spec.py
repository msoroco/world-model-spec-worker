"""Bounded synthetic four-camera converter packets for one-way CPU proof."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one_way_direction import CASES

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False)


def lines(rows):
    return ''.join(compact(row) + '\n' for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')


def build(case):
    suffix = case.name
    case_id = ASSIGNMENT + '__' + suffix
    sign = 1 if case.direction == 'designated' else -1
    source = 'a' * 64
    scene = {'cell_id': 'C147311', 'actor': 'motor_vehicle_driver',
             'motor_vehicle': True, 'driver_in_physical_control': True,
             'public_highway': True, 'highway_dedicated': True,
             'one_way_designated': True, 'lane_count': 2, 'lane_ids': [1, 2],
             'lane': case.lane, 'direction': case.direction,
             'sign_authorized': True, 'signposted': True,
             'sign_governs_route': True, 'designated_unit_xy': [1, 0],
             'sign_xy': [0, 0], 'ego_route_xy': [[0, float(case.lane)],
                                                    [sign * 225, float(case.lane)]],
             'diagnostic_fixture': True}
    scene.update({name + '_source_sha256': source for name in
                  ('highway', 'vehicle', 'driver_control', 'lane_inventory',
                   'one_way_designation', 'sign_authority', 'sign_message',
                   'sign_orientation', 'sign_placement', 'sign_governance', 'ego_route')})
    fields = ('frame', 'ego_motion', 'ego_position', 'driver_control',
              'lane_inventory', 'one_way_designation', 'sign_authority',
              'sign_message', 'sign_orientation', 'sign_governance')
    motion = []
    for i in range(900):
        row = {'original_frame': i, 'time_s': i / 20,
               'ego_id': 'synthetic-ego', 'position_xy': [sign * i * .25, float(case.lane)],
               'velocity_xy': [sign * 5.0, 0.0], 'lane': case.lane,
               'sign_governs_route': True, 'diagnostic_fixture': True}
        row.update({field + '_source_sha256': source for field in fields})
        motion.append(row)
    y = -1.75 if case.lane == 1 else -5.25
    trace = [{'frame': i, 'time_s': i / 20,
              'position_m': [sign * i * .25, y, 0],
              'position': {'x': sign * i * .25, 'y': y, 'z': 0},
              'speed_mps': 5.0, 'speed_mph': 5.0 / .44704,
              'velocity_mps': [sign * 5.0, 0, 0],
              'heading_deg': 0 if sign == 1 else 180, 'control': {}}
             for i in range(900)]
    frame_map = [{'video_frame': i, 'carla_frame': i, 'native_frame': i,
                  'time_s': i / 20} for i in range(900)]
    evidence = [{'original_frame': i, 'replay_frame': i, 'actor_id': 11,
                 'recording_time_s': i / 20, 'replay_simulation_time_s': i / 20,
                 'world': {'weather': {}},
                 'ego': {'position_m': trace[i]['position_m'],
                         'heading_deg': trace[i]['heading_deg'],
                         'speed_mps': 5.0,
                         'speed_provenance': 'synthetic_native_sample',
                         'body_vertices_m': [[sign * i * .25 + dx, y + dy, z]
                                             for dx, dy, z in ((-2,-1,0),(-2,-1,1.5),
                                                                (2,-1,0),(2,-1,1.5),
                                                                (-2,1,0),(-2,1,1.5),
                                                                (2,1,0),(2,1,1.5))]},
                 'original_observations': {'frame': i, 'time_s': i / 20,
                                           'participants': [],
                                           'map_context': {'declared_public_way_road_ids': []}}}
                for i in range(900)]
    graphs = [{'path': f'capture/native/graphs/base/{i:08d}.adapter.json',
               'attributes': {'frame': i, 'time_s': i / 20,
                              'observed_evidence': evidence[i]['original_observations']},
               'nodes': [], 'edges': []} for i in range(900)]
    native_frames = [{'frame': i, 'simulation_time': i / 20,
                      'adapter_graph': f'graphs/base/{i:08d}.adapter.json'}
                     for i in range(900)]
    map_sha = sha(ROOT / 'diagnostic-map.xodr')
    motion_path = ROOT / f'cases/{suffix}/diagnostic-motion.jsonl'
    motion_path.write_text(lines(motion), encoding='utf-8')
    file_map = {'site-source.json': compact(scene) + '\n',
                'trace.jsonl': lines(trace),
                'video_frames.jsonl': lines(frame_map),
                'capture/evidence.jsonl': lines(evidence),
                'capture/native/frames.jsonl': lines(native_frames),
                'capture/recorder_info.txt': 'Create 11: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n',
                'capture/manifest.json': compact({'status': 'draft',
                  'acquisition': 'synthetic_cpu_fixture', 'case_id': case_id,
                  'frames': 900, 'extraction_confirmed': True,
                  'complete_driving_lanes': False,
                  'sources': {'road.xodr': map_sha,
                              'trace.jsonl': hashlib.sha256(lines(trace).encode()).hexdigest()}}) + '\n',
                'acquisition-provenance.json': compact({'provenance_kind': 'synthetic_fixture',
                                                         'diagnostic_fixture': True}) + '\n'}
    videos = [{'path': name + '.mkv', 'frames': 900, 'width': size[0],
               'height': size[1], 'fps': 20, 'color': 'black'}
              for name, size in (('overview', (1920, 1080)),
                                 ('approach', (1280, 720)),
                                 ('reference_corner', (1280, 720)),
                                 ('driver_reference', (1280, 720)))]
    spec_rel = f'cases/{suffix}/diagnostic-spec.json'
    write(ROOT / spec_rel, {'files': file_map, 'graphs': graphs, 'videos': videos})
    recipe_rel = f'cases/{suffix}/diagnostic-recipe.json'
    write(ROOT / recipe_rel, {'format': 'worker-fixture-recipe',
          'sources': [{'path': 'road.xodr',
                       'source': str((ROOT / 'diagnostic-map.xodr').relative_to(ROOT.parent.parent)),
                       'sha256': map_sha},
                      {'path': 'native-frames.jsonl',
                       'source': str(motion_path.relative_to(ROOT.parent.parent)),
                       'sha256': sha(motion_path)}],
          'generator': {'source': str((ROOT / spec_rel).relative_to(ROOT.parent.parent)),
                        'sha256': sha(ROOT / spec_rel)}})
    return recipe_rel, (ROOT / spec_rel).stat().st_size


if __name__ == '__main__':
    for case in CASES:
        print(case.name, *build(case))
