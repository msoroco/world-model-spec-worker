"""Measure a sealed road-to-driveway Native trace without deciding the law."""

import hashlib
import json
import math
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SUFFIXES = ('stop_before_sidewalk', 'cross_without_stop')
SITE_SOURCES = {
    'district_source': 'site-sources/district.json',
    'private_driveway_source': 'site-sources/driveway.json',
    'sidewalk_source': 'site-sources/sidewalk.json',
    'pedestrian_route_source': 'site-sources/pedestrian.json',
}
SOURCE_FILES = ('original-site-review.json', 'site-review.json', 'road.xodr',
                'native-rows.jsonl', 'video_frames.jsonl') + \
               tuple(SITE_SOURCES.values()) + tuple(name + '.mkv' for name in CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(attempt, case_id):
    attempt = Path(attempt)
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in SUFFIXES:
        raise ValueError('Unknown exact sidewalk case')
    seal = json.loads((attempt / 'captured-source-hashes.json').read_text())
    if (seal.get('format') != 'original-native-sidewalk-source-seal' or
            seal.get('case_id') != case_id or
            seal.get('source_kind') != 'original_native_capture' or
            set(seal.get('sha256', {})) != set(SOURCE_FILES)):
        raise ValueError('Original sidewalk source seal differs')
    for name in SOURCE_FILES:
        path = attempt / name
        if not path.is_file() or sha(path) != seal['sha256'][name]:
            raise ValueError('Original sidewalk source missing or changed: ' + name)
    site = json.loads((attempt / 'site-review.json').read_text())
    if (site.get('source_kind') != 'original_site_review' or
            site.get('route') != 'road_to_private_driveway' or
            site.get('district') != 'residence' or
            site.get('road_xodr_sha256') != seal['sha256']['road.xodr'] or
            site.get('sidewalk_y_interval_m') != [0, 2] or
            site.get('world_sidewalk_y_interval_m') != [-5.5, -3.5] or
            site.get('route_frame') != 'road_east_then_driveway_south' or
            site.get('driveway_connection_reviewed') is not True or
            site.get('sidewalk_polygon_reviewed') is not True or
            site.get('pedestrian_route_reviewed') is not True):
        raise ValueError('Original district, driveway or sidewalk review missing')
    original = json.loads((attempt / 'original-site-review.json').read_text())
    if any(site.get(key) != original.get(key) for key in original):
        raise ValueError('Original site review changed after capture')
    for key, name in SITE_SOURCES.items():
        item = site.get(key)
        if (not isinstance(item, dict) or item.get('path') != name or
                item.get('sha256') != seal['sha256'][name]):
            raise ValueError('Original site source binding differs: ' + key)
    native = rows(attempt / 'native-rows.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    if len(native) != 600 or len(frames) != 600:
        raise ValueError('Original sidewalk frame coverage incomplete')
    ids = None
    first_body_cross = None
    prior_stop_frames = 0
    pedestrian_min_distance = float('inf')
    first_frame = native[0].get('native_frame')
    if type(first_frame) is not int:
        raise ValueError('Original Native first frame missing')
    previous_y = None
    for index, (row, mapping) in enumerate(zip(native, frames)):
        frame = first_frame + index
        identity = (row.get('vehicle_actor_id'), row.get('pedestrian_actor_id'))
        camera_join = {name: frame for name in CAMERAS}
        if (row.get('source_kind') != 'original_native' or
                row.get('native_frame') != frame or
                row.get('video_frame') != index or
                mapping.get('native_frame') != frame or
                mapping.get('video_frame') != index or
                row.get('source_cameras') != camera_join or
                mapping.get('camera_native_frames') != camera_join or
                not number(row.get('time_s')) or
                not number(mapping.get('time_s')) or
                abs(row['time_s'] - (index + 1) / 20) > .001 or
                abs(mapping['time_s'] - row['time_s']) > .001 or
                any(type(value) is not int for value in identity) or
                identity[0] == identity[1]):
            raise ValueError('Original Native sidewalk frame join differs')
        if ids is None:
            ids = identity
        elif identity != ids:
            raise ValueError('Original vehicle or pedestrian identity changed')
        ego = row.get('vehicle_xy_m')
        world_ego = row.get('vehicle_world_xy_m')
        ped = row.get('pedestrian_xy_m')
        world_ped = row.get('pedestrian_world_xy_m')
        extent = row.get('vehicle_half_extent_m')
        speed = row.get('vehicle_speed_mps')
        if (not isinstance(ego, list) or len(ego) != 2 or
                not isinstance(world_ego, list) or len(world_ego) != 2 or
                not isinstance(ped, list) or len(ped) != 2 or
                not isinstance(world_ped, list) or len(world_ped) != 2 or
                any(not number(v) for v in ego + world_ego + ped + world_ped) or
                not number(extent) or extent <= 0 or
                not number(speed) or speed < 0 or
                (previous_y is not None and ego[1] + .001 < previous_y) or
                abs(ego[0]) > 1.5 or
                abs(ped[1] - 1) > .5 or
                abs(world_ped[0] - ped[0]) > .1 or
                abs(world_ped[1] + 4.5) > .5):
            raise ValueError('Original road-to-driveway or pedestrian motion differs')
        expected_world = ([ego[1] + 1.75, -1.75] if ego[1] < -1.75
                          else [0.0, -3.5 - ego[1]])
        if (abs(world_ego[0] - expected_world[0]) > 1.5 or
                abs(world_ego[1] - expected_world[1]) > 1.5):
            raise ValueError('Original road-to-driveway local/world projection differs')
        previous_y = ego[1]
        if ego[1] + extent < 0 and speed <= .1:
            prior_stop_frames += 1
        if first_body_cross is None and ego[1] + extent >= 0:
            first_body_cross = frame
        pedestrian_min_distance = min(
            pedestrian_min_distance,
            math.hypot(ego[0] - ped[0], ego[1] - ped[1]))
    if (first_body_cross is None or native[0]['vehicle_xy_m'][1] >= 0 or
            native[-1]['vehicle_xy_m'][1] <= 2):
        raise ValueError('Original road-to-driveway sidewalk crossing absent')
    return {
        'case_id': case_id,
        'source_seal_sha256': sha(attempt / 'captured-source-hashes.json'),
        'source_kind': 'original_native_capture',
        'frame_count': 600,
        'rate_hz': 20,
        'route': 'road_to_private_driveway',
        'first_observed_body_sidewalk_cross_frame': first_body_cross,
        'observed_pre_sidewalk_stop_frames': prior_stop_frames,
        'minimum_observed_vehicle_pedestrian_center_distance_m': pedestrian_min_distance,
        'district_or_private_rights_legally_verified': False,
        'pedestrian_yield_legally_determined': False,
        'physical_completion': None,
        'legal_verdict': None,
    }


def measure_core_join(attempt, case_id):
    """Require saved Core and native source frames to describe the same motion."""
    attempt = Path(attempt)
    measured = measure(attempt, case_id)
    names = ('trace.jsonl', 'capture/evidence.jsonl',
             'capture/native/frames.jsonl')
    for name in names:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    native = rows(attempt / 'native-rows.jsonl')
    sources = [rows(attempt / name) for name in names]
    if any(len(source) != 600 for source in sources):
        raise ValueError('Original Core frame coverage incomplete')
    for row, (trace, evidence, frame) in zip(native, zip(*sources)):
        expected_frame = row['native_frame']
        expected_time = row['time_s']
        position = trace.get('position', {})
        ego = evidence.get('ego', {})
        ego_position = ego.get('position_m')
        if (trace.get('frame') != expected_frame or
                evidence.get('original_frame') != expected_frame or
                frame.get('frame') != expected_frame or
                not isinstance(ego_position, list) or len(ego_position) < 2 or
                any(not number(value) for value in (
                    position.get('x'), position.get('y'),
                    trace.get('speed_mps'), ego.get('speed_mps'),
                    ego_position[0], ego_position[1],
                    trace.get('time_s'), evidence.get('recording_time_s'),
                    frame.get('time_s'))) or
                any(abs(item - expected_time) > 1e-4 for item in (
                    trace['time_s'], evidence['recording_time_s'],
                    frame['time_s'])) or
                abs(position['x'] - row['vehicle_world_xy_m'][0]) > 1e-3 or
                abs(position['y'] - row['vehicle_world_xy_m'][1]) > 1e-3 or
                abs(ego_position[0] - row['vehicle_world_xy_m'][0]) > 1e-3 or
                abs(ego_position[1] - row['vehicle_world_xy_m'][1]) > 1e-3 or
                abs(trace['speed_mps'] - row['vehicle_speed_mps']) > 1e-3 or
                abs(ego['speed_mps'] - row['vehicle_speed_mps']) > 1e-3):
            raise ValueError('Original Native/Core sidewalk source join differs')
    measured['core_join'] = {
        'frames': 600,
        'source_sha256': {name: sha(attempt / name) for name in names},
        'original_native_core_join_passed': True,
        'physical_or_legal_outcome_claimed': False,
    }
    return measured
