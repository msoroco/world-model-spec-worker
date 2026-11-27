"""Source-shaped CPU positives and negatives for roadway-return measurement."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from build_entry_return import AID, POLICIES, ROOT, target
from measure_entry_return import (CAMERAS, CORE_FILES, SITE_SOURCES,
                                  SOURCE_FILES, measure_core_join)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def bbox(x, y, half_x, half_y):
    return [[x + dx, y + dy, z] for dx in (-half_x, half_x)
            for dy in (-half_y, half_y) for z in (.2, 1.8)]


def fixture(folder, policy):
    case_id = AID + '__' + policy
    road = folder / 'road.xodr'
    road.write_bytes((ROOT / 'native/road/road.xodr').read_bytes())
    source_refs = {}
    for key, name in SITE_SOURCES.items():
        write_json(folder / name, {'fixture_only': True, 'review_item': key})
        source_refs[key] = {'path': name, 'sha256': sha(folder / name)}
    review = {
        'source_kind': 'original_site_review',
        'route': 'road_to_private_driveway', 'district': 'residence',
        'road_xodr_sha256': sha(road),
        'authored_road_sha256': sha(road),
        'sidewalk_y_interval_m': [0, 2],
        'world_sidewalk_y_interval_m': [-5.5, -3.5],
        'route_frame': 'road_east_then_driveway_south',
        'driveway_connection_reviewed': True,
        'sidewalk_polygon_reviewed': True,
        'pedestrian_route_reviewed': True,
        'fixture_only': True, **source_refs,
    }
    write_json(folder / 'original-site-review.json', review)
    write_json(folder / 'site-review.json', review)
    write_json(folder / 'original-entry-site-review.json', {
        'source_kind': 'original_entry_site_review',
        'authored_road_sha256': sha(road),
        'district': 'residence',
        'roadway_connection_reviewed': True,
        'approaching_vehicle_lane_reviewed': True,
        'roadway_entry_reference_y_m': -3.5,
        'approaching_vehicle_lane_y_m': -1.75,
        'fixture_only': True,
    })
    for name in CAMERAS:
        (folder / (name + '.mkv')).write_text('CPU camera marker ' + name + '\n')
    native = []
    mappings = []
    for index in range(1200):
        row = target(index, policy)
        frame = 1100 + index
        camera_join = {name: frame for name in CAMERAS}
        ego = row['requested_ego_world_xy_m']
        traffic = row['requested_approaching_world_xy_m']
        ped = row['requested_pedestrian_world_xy_m']
        native.append({
            'source_kind': 'original_native',
            'native_frame': frame, 'video_frame': index,
            'time_s': row['time_s'], 'source_cameras': camera_join,
            'vehicle_actor_id': 101, 'pedestrian_actor_id': 202,
            'approaching_actor_id': 303,
            'vehicle_xy_m': ego, 'vehicle_world_xy_m': ego,
            'vehicle_half_extent_m': 1.2,
            'vehicle_speed_mps': row['requested_ego_speed_mps'],
            'pedestrian_xy_m': ped, 'pedestrian_world_xy_m': ped,
            'approaching_world_xy_m': traffic,
            'approaching_speed_mps': row['requested_approaching_speed_mps'],
            'phase': row['phase'],
        })
        mappings.append({
            'native_frame': frame, 'carla_frame': frame,
            'video_frame': index, 'time_s': row['time_s'],
            'camera_native_frames': camera_join,
        })
    write_rows(folder / 'native-rows.jsonl', native)
    write_rows(folder / 'video_frames.jsonl', mappings)
    write_rows(folder / 'trace.jsonl', [
        {'frame': row['native_frame'], 'time_s': row['time_s'],
         'position': {'x': row['vehicle_world_xy_m'][0],
                      'y': row['vehicle_world_xy_m'][1], 'z': 1.0},
         'position_m': [*row['vehicle_world_xy_m'], 1.0],
         'heading_deg': 0.0 if row['phase'] == 'road_exit' else 90.0,
         'speed_mps': row['vehicle_speed_mps'],
         'speed_mph': row['vehicle_speed_mps'] / .44704,
         'velocity_mps': [row['vehicle_speed_mps'], 0, 0],
         'control': {'diagnostic': True}}
        for row in native])
    write_rows(folder / 'capture/evidence.jsonl', [
        {'original_frame': row['native_frame'], 'recording_time_s': row['time_s'],
         'actor_id': row['vehicle_actor_id'],
         'replay_frame': row['native_frame'],
         'replay_simulation_time_s': row['time_s'],
         'ego': {'position_m': [*row['vehicle_world_xy_m'], 1.0],
                 'speed_mps': row['vehicle_speed_mps'],
                 'body_vertices_m': bbox(*row['vehicle_world_xy_m'], 1.2, .8),
                 'heading_deg': 0.0 if row['phase'] == 'road_exit' else 90.0,
                 'speed_provenance': 'synthetic_native_sample',
                 'synthetic_diagnostic': True},
         'other_actors': [
             {'actor_id': row['pedestrian_actor_id'],
              'sem_class': 'pedestrian',
              'body_vertices_m': bbox(*row['pedestrian_world_xy_m'], .3, .3)},
             {'actor_id': row['approaching_actor_id'],
              'sem_class': 'vehicle',
              'body_vertices_m': bbox(*row['approaching_world_xy_m'], 1.2, .8)}],
         'world': {'road_projection': {'road_id': 1, 'section_id': 0,
                                       'lane_id': -1, 's_m': 0.0},
                   'weather': {'cloudiness': 0, 'fog_density': 0,
                               'precipitation': 0, 'wetness': 0}}}
        for row in native])
    write_rows(folder / 'capture/native/frames.jsonl', [
        {'frame': row['native_frame'], 'time_s': row['time_s'],
         'simulation_time': row['time_s'],
         'base': f'graphs/base/{index:08d}.adapter.json',
         'adapter_graph': f'graphs/base/{index:08d}.adapter.json',
         'nodes': 3, 'edges': 0}
        for index, row in enumerate(native)])
    write_json(folder / 'captured-source-hashes.json', {
        'format': 'original-native-sidewalk-source-seal',
        'case_id': case_id,
        'source_kind': 'original_native_capture',
        'sha256': {name: sha(folder / name) for name in SOURCE_FILES},
        'fixture_only': True,
    })
    return case_id


def rejected(folder, case_id, expected):
    try:
        measure_core_join(folder, case_id)
    except ValueError as error:
        if expected not in str(error):
            raise
        return str(error)
    raise AssertionError('Source mutation accepted: ' + expected)


def main():
    scratch = Path(os.environ.get('TMPDIR', '.runtime-work')).resolve()
    if '.runtime-work' not in scratch.parts:
        raise ValueError('Temporary source fixture must stay under .runtime-work')
    positives, negatives = [], []
    with tempfile.TemporaryDirectory(prefix='c213851-return-', dir=scratch) as name:
        root = Path(name)
        for policy in POLICIES:
            folder = root / policy
            folder.mkdir()
            case_id = fixture(folder, policy)
            result = measure_core_join(folder, case_id)
            if (result['frame_count'] != 1200 or
                    result['first_entry_road_frame'] is None or
                    result['legal_verdict'] is not None):
                raise AssertionError('Expected bounded synthetic measurement missing')
            positives.append({'case_id': case_id,
                              'first_entry_road_frame': result['first_entry_road_frame'],
                              'stopped_frames':
                                  result['observed_pre_entry_stopped_frames']})
            missing = folder / 'original-entry-site-review.json'
            original = missing.read_bytes()
            missing.unlink()
            negatives.append(rejected(folder, case_id, 'missing or changed'))
            missing.write_bytes(original)
            core = folder / CORE_FILES[0]
            original = core.read_bytes()
            core.unlink()
            negatives.append(rejected(folder, case_id, 'Missing required source'))
            core.write_bytes(original)
            native_path = folder / 'native-rows.jsonl'
            original = native_path.read_bytes()
            rows = [json.loads(line) for line in original.splitlines()]
            rows[802]['source_cameras']['overview'] = 9999
            write_rows(native_path, rows)
            seal_path = folder / 'captured-source-hashes.json'
            seal = json.loads(seal_path.read_text())
            seal['sha256']['native-rows.jsonl'] = sha(native_path)
            write_json(seal_path, seal)
            negatives.append(rejected(folder, case_id, 'frame join differs'))
    proof = {
        'format': 'roadway-entry-return-source-shape-cpu-proof',
        'passed': True, 'positive_count': len(positives),
        'negative_count': len(negatives),
        'positives': positives, 'negative_errors': negatives,
        'original_native_capture_observed': False,
        'physical_or_legal_acceptance': False,
    }
    path = ROOT / 'native/entry_return/measurement-proof.json'
    write_json(path, proof)
    return {'passed': True, 'positive_count': len(positives),
            'negative_count': len(negatives), 'proof_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main()))
