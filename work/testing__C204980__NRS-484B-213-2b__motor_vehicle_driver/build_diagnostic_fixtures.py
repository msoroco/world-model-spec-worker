"""Generate compact 900-frame source-shaped CPU fixtures, never physical evidence."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from rail_left import CASES, FOOT_M, validate_scene

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
BASE = REPO / 'work/testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver'
SCRATCH = REPO / '.runtime-work/c204980-owner-nov26'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n'
                            for row in rows))


def video_hashes(spec):
    scratch = SCRATCH / 'diagnostic-video-hash'
    scratch.mkdir(parents=True, exist_ok=True)
    output = {}
    for video in spec['videos']:
        target = scratch / video['path']
        if not target.is_file():
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-n', '-f', 'lavfi', '-i',
                f"color=c={video['color']}:s={video['width']}x{video['height']}:r={video['fps']}",
                '-frames:v', str(video['frames']), '-an', '-c:v', 'ffv1',
                '-threads', '1', '-fflags', '+bitexact', '-flags:v', '+bitexact',
                str(target)], check=True, timeout=180)
        output[video['path']] = sha(target.read_bytes())
    return output


def make_case(case, road, movies):
    cid = AID + '__' + case.case_id
    root = HERE / 'diagnostics' / case.case_id
    root.mkdir(parents=True, exist_ok=True)
    (root / 'road.xodr').write_text(road)
    map_sha = sha(road.encode())
    source_data = {
        'highway': {'public_highway': True, 'one_way_highway': case.one_way,
                    'centerline_present': True, 'centerline_point_xy': [0, 0],
                    'centerline_heading_xy': [1, 0]},
        'railroad': {'stationary_rail_carrier_person_or_property': True,
                     'streetcar_rail': False},
        'crossing': {'at_grade': True, 'crossing_near_station_m': 0,
                     'crossing_far_station_m': 5,
                     'route_xy': [[-60, 0], [-30, 0], [10, 0]]},
        'vehicle': {'ordinary_motor_vehicle': True, 'driver_actual_control': True},
    }
    source_hashes = {}
    for kind, values in source_data.items():
        path = root / f'reviewed-{kind}.json'
        write(path, {'source_kind': kind, 'case_id': cid,
                     'map_opendrive_sha256': map_sha,
                     'source_citation': 'synthetic:rail-software-fixture',
                     'diagnostic_fixture': True, **values})
        source_hashes[kind] = sha(path.read_bytes())
    scene = {'cell_id': 'C204980', 'actor': 'motor_vehicle_driver',
             'rail_grade_crossing': True,
             'stationary_rail_carrier_person_or_property': True,
             'streetcar_rail': False, 'one_way_highway': case.one_way,
             **{k: source_data['crossing'][k] for k in
                ('crossing_near_station_m', 'crossing_far_station_m', 'route_xy')},
             'centerline_point_xy': [0, 0], 'centerline_heading_xy': [1, 0],
             'map_opendrive_sha256': map_sha,
             'reviewed_source_sha256': source_hashes}
    mapping = {'jurisdiction': 'highway', 'highway_status': 'highway',
               'one_way_status': 'highway', 'centerline': 'highway',
               'vehicle': 'vehicle', 'driver_control': 'vehicle',
               'body_reference': 'vehicle', 'rail_carrier': 'railroad',
               'streetcar_exclusion': 'railroad', 'rail_grade': 'crossing',
               'crossing_near_edge': 'crossing', 'crossing_far_edge': 'crossing',
               'route': 'crossing'}
    scene.update({key + '_source_sha256': source_hashes[kind]
                  for key, kind in mapping.items()})
    validate_scene(scene, case)
    y = 3.5 if case.left_side else -3.5
    x_at_100 = -case.target_leading_distance_ft * FOOT_M - 2.4
    frames, trace, evidence, frame_map, graph_frames, videos = [], [], [], [], [], []
    for i in range(900):
        frame, t = i + 1, i / 20
        x = -60 + (x_at_100 + 60) * i / 100 if i <= 100 else x_at_100 + (10 - x_at_100) * (i - 100) / 799
        speed = (x_at_100 + 60) / 5 if i <= 100 else (10 - x_at_100) / (799 / 20)
        body = [[x + dx, y + dy, z] for dx in (-2.4, 2.4)
                for dy in (-.9, .9) for z in (0, 1.5)]
        source = sha(json.dumps([frame, x, y, speed], sort_keys=True).encode())
        frames.append({'original_frame': frame, 'time_s': t,
            'source_sha256': source, 'body_geometry_sha256': source,
            'motion_sha256': source,
            'crossing_geometry_sha256': source_hashes['crossing'],
            'centerline_sha256': source_hashes['highway'],
            'highway_classification_sha256': source_hashes['highway'],
            'rail_carrier_sha256': source_hashes['railroad'],
            'crossing_near_edge_source_sha256': source_hashes['crossing'],
            'centerline_source_sha256': source_hashes['highway'],
            'one_way_highway': case.one_way, 'ego_id': 'fixture-ego',
            'leading_body_station_m': x + 2.4,
            'trailing_body_station_m': x - 2.4,
            'body_leftmost_lateral_m': y + .9,
            'body_rightmost_lateral_m': y - .9,
            'ego_speed_mps': speed})
        trace.append({'frame': frame, 'time_s': t,
            'position': {'x': x, 'y': y, 'z': 0},
            'position_m': [x, y, 0], 'heading_deg': 0,
            'speed_mps': speed, 'speed_mph': speed / .44704,
            'velocity_mps': [speed, 0, 0],
            'control': {'throttle': .2, 'brake': 0.0, 'hand_brake': False},
            'source_frame': frame, 'physical_acceptance_claimed': False})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
            'actor_id': 1, 'recording_time_s': t,
            'replay_simulation_time_s': t,
            'ego': {'position_m': [x, y, 0], 'heading_deg': 0,
                    'speed_mps': speed,
                    'speed_provenance': 'synthetic_native_sample',
                    'body_vertices_m': body},
            'world': {'weather': {}}, 'visibility': None})
        frame_map.append({'video_frame': i, 'carla_frame': frame,
                          'native_frame': frame, 'time_s': t})
        graph_frames.append({'frame': frame, 'simulation_time': t,
                             'adapter_graph': f'graphs/base/{frame:08d}.adapter.json'})
        videos.append(frame)
    jsonl(root / 'rail-frames.jsonl', frames)
    jsonl(root / 'trace.jsonl', trace)
    jsonl(root / 'capture/evidence.jsonl', evidence)
    jsonl(root / 'video_frames.jsonl', frame_map)
    jsonl(root / 'capture/native/frames.jsonl', graph_frames)
    write(root / 'frame-map.json', {'frames': videos,
                                   'camera_frames': {name: videos for name in CAMERAS}})
    write(root / 'rail-context.json', {'case_id': cid, 'scene': scene,
                                       'reviewed_map_sha256': map_sha,
                                       'physical_acceptance_claimed': False,
                                       'diagnostic_fixture': True})
    write(root / 'capture/manifest.json', {'acquisition': 'synthetic_fixture',
        'case_id': cid, 'extraction_confirmed': True, 'frames': 900,
        'required_observations': [], 'sources': {'road.xodr': sha((root / 'road.xodr').read_bytes()),
            'trace.jsonl': sha((root / 'trace.jsonl').read_bytes())},
        'status': 'diagnostic'})
    (root / 'capture/recorder_info.txt').write_text('Create 1: vehicle.tesla.model3\n')
    write(root / 'acquisition-provenance.json', {'diagnostic_fixture': True,
        'case_id': cid, 'physical_acceptance_claimed': False})
    write(root / 'fixture-provenance.json', {'diagnostic_fixture': True,
        'case_id': cid, 'physical_acceptance_claimed': False,
        'scope': '900-frame source-shaped software fixture, no original rail qualification or pixels'})
    sealed = ('rail-frames.jsonl', 'frame-map.json', 'rail-context.json',
              *(f'reviewed-{kind}.json' for kind in source_data))
    hashes = {name: sha((root / name).read_bytes()) for name in sealed}
    hashes.update(movies)
    write(root / 'source-hashes.json', hashes)
    write(root / 'original-hashes.json', hashes)
    files = [path for path in root.rglob('*') if path.is_file() and path.name != 'recipe.json']
    assignment = REPO / 'inputs' / AID / 'assignment.json'
    refs = [{'path': str(path.relative_to(root)),
             'source': str(path.relative_to(REPO)), 'sha256': sha(path.read_bytes())}
            for path in files]
    refs.append({'path': 'diagnostic-input.json',
                 'source': str(assignment.relative_to(REPO)),
                 'sha256': sha(assignment.read_bytes())})
    graph = HERE / 'diagnostic-graph.json'
    recipe = {'format': 'worker-fixture-recipe', 'sources': refs,
              'generator': {'source': str(graph.relative_to(REPO)),
                            'sha256': sha(graph.read_bytes())}}
    write(root / 'recipe.json', recipe)
    return root / 'recipe.json'


def main():
    spec = json.loads((BASE / 'diagnostic.json').read_text())
    if spec['files'] or len(spec['graphs']) != 900 or any(v['frames'] != 900 for v in spec['videos']):
        raise ValueError('pinned compact 900-frame diagnostic graph shape changed')
    graph = HERE / 'diagnostic-graph.json'
    write(graph, spec)
    road = (BASE / 'diagnostics/freight_loading/road.xodr').read_text()
    movies = video_hashes(spec)
    for case in CASES:
        path = make_case(case, road, movies)
        print(case.case_id, path.stat().st_size, flush=True)


if __name__ == '__main__':
    main()
