"""Measure a sealed road-to-driveway Native trace without deciding the law."""

import hashlib
import json
import math
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SUFFIXES = ('stop_before_sidewalk', 'cross_without_stop')
SOURCE_FILES = ('site-review.json', 'road.xodr', 'native-rows.jsonl',
                'video_frames.jsonl') + tuple(name + '.mkv' for name in CAMERAS)


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
            site.get('driveway_connection_reviewed') is not True or
            site.get('sidewalk_polygon_reviewed') is not True or
            site.get('pedestrian_route_reviewed') is not True):
        raise ValueError('Original district, driveway or sidewalk review missing')
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
        ped = row.get('pedestrian_xy_m')
        extent = row.get('vehicle_half_extent_m')
        speed = row.get('vehicle_speed_mps')
        if (not isinstance(ego, list) or len(ego) != 2 or
                not isinstance(ped, list) or len(ped) != 2 or
                any(not number(v) for v in ego + ped) or
                not number(extent) or extent <= 0 or
                not number(speed) or speed < 0 or
                (previous_y is not None and ego[1] + .001 < previous_y) or
                abs(ego[0]) > 1.5 or
                abs(ped[1] - 1) > .5):
            raise ValueError('Original road-to-driveway or pedestrian motion differs')
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
