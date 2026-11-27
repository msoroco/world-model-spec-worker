"""Measure sealed Native/Core roadway-return sources without deciding the law."""

import hashlib
import json
import math
from pathlib import Path

from measure_sidewalk import CAMERAS, SITE_SOURCES, number, rows


SOURCE_FILES = ('original-site-review.json', 'original-entry-site-review.json',
                'site-review.json', 'road.xodr', 'native-rows.jsonl',
                'video_frames.jsonl') + tuple(SITE_SOURCES.values()) + \
               tuple(name + '.mkv' for name in CAMERAS)
CORE_FILES = ('trace.jsonl', 'capture/evidence.jsonl',
              'capture/native/frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt, case_id):
    attempt = Path(attempt)
    suffix = case_id.rsplit('__', 1)[-1]
    if suffix not in ('yield_to_approaching', 'enter_without_yield'):
        raise ValueError('Unknown exact roadway-entry case')
    seal_path = attempt / 'captured-source-hashes.json'
    seal = json.loads(seal_path.read_text())
    if (seal.get('format') != 'original-native-sidewalk-source-seal' or
            seal.get('case_id') != case_id or
            seal.get('source_kind') != 'original_native_capture' or
            set(seal.get('sha256', {})) != set(SOURCE_FILES)):
        raise ValueError('Original roadway-entry source seal differs')
    for name in SOURCE_FILES:
        path = attempt / name
        if not path.is_file() or sha(path) != seal['sha256'][name]:
            raise ValueError('Original roadway-entry source missing or changed: ' + name)
    site = json.loads((attempt / 'site-review.json').read_text())
    original = json.loads((attempt / 'original-site-review.json').read_text())
    if any(site.get(key) != original.get(key) for key in original):
        raise ValueError('Original site review changed after capture')
    if (site.get('district') != 'residence' or
            site.get('route') != 'road_to_private_driveway' or
            site.get('road_xodr_sha256') != seal['sha256']['road.xodr'] or
            site.get('world_sidewalk_y_interval_m') != [-5.5, -3.5]):
        raise ValueError('Original driveway and sidewalk site context differs')
    for key, name in SITE_SOURCES.items():
        item = site.get(key)
        if (not isinstance(item, dict) or item.get('path') != name or
                item.get('sha256') != seal['sha256'][name]):
            raise ValueError('Original site source binding differs: ' + key)
    entry_site = json.loads((attempt / 'original-entry-site-review.json').read_text())
    if (entry_site.get('source_kind') != 'original_entry_site_review' or
            entry_site.get('authored_road_sha256') !=
            original.get('authored_road_sha256') or
            entry_site.get('district') != 'residence' or
            entry_site.get('roadway_connection_reviewed') is not True or
            entry_site.get('approaching_vehicle_lane_reviewed') is not True or
            entry_site.get('roadway_entry_reference_y_m') != -3.5 or
            entry_site.get('approaching_vehicle_lane_y_m') != -1.75):
        raise ValueError('Original roadway-entry site review differs')
    native = rows(attempt / 'native-rows.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    if len(native) != 1200 or len(frames) != 1200:
        raise ValueError('Original roadway-entry frame coverage incomplete')
    first_frame = native[0].get('native_frame')
    if type(first_frame) is not int:
        raise ValueError('Original first Native frame missing')
    actors = None
    first_exit_sidewalk = first_return_sidewalk = first_entry_road = None
    minimum_approach_distance = float('inf')
    pre_entry_stopped_frames = 0
    for index, (row, mapping) in enumerate(zip(native, frames)):
        frame = first_frame + index
        camera_join = {name: frame for name in CAMERAS}
        identity = (row.get('vehicle_actor_id'), row.get('pedestrian_actor_id'),
                    row.get('approaching_actor_id'))
        phase = ('road_exit' if index < 400 else
                 'private_driveway_dwell' if index < 560 else 'roadway_entry')
        if (row.get('source_kind') != 'original_native' or
                row.get('native_frame') != frame or
                row.get('video_frame') != index or
                row.get('phase') != phase or
                mapping.get('native_frame') != frame or
                mapping.get('video_frame') != index or
                row.get('source_cameras') != camera_join or
                mapping.get('camera_native_frames') != camera_join or
                not number(row.get('time_s')) or
                not number(mapping.get('time_s')) or
                abs(row['time_s'] - (index + 1) / 20) > .001 or
                abs(mapping['time_s'] - row['time_s']) > .001 or
                any(type(value) is not int for value in identity) or
                len(set(identity)) != 3):
            raise ValueError('Original roadway-entry frame join differs')
        if actors is None:
            actors = identity
        elif actors != identity:
            raise ValueError('Original roadway-entry actor identity changed')
        ego = row.get('vehicle_world_xy_m')
        traffic = row.get('approaching_world_xy_m')
        ped = row.get('pedestrian_world_xy_m')
        extent = row.get('vehicle_half_extent_m')
        speed = row.get('vehicle_speed_mps')
        traffic_speed = row.get('approaching_speed_mps')
        if (any(not isinstance(point, list) or len(point) != 2 or
                any(not number(value) for value in point)
                for point in (ego, traffic, ped)) or
                any(not number(value) for value in
                    (extent, speed, traffic_speed)) or
                extent <= 0 or speed < 0 or traffic_speed < 0 or
                abs(traffic[1] + 1.75) > 1.5):
            raise ValueError('Original roadway-entry position or speed differs')
        if index < 400 and first_exit_sidewalk is None and ego[1] - extent <= -3.5:
            first_exit_sidewalk = frame
        if index >= 560:
            if speed <= .1 and ego[1] + extent < -3.5:
                pre_entry_stopped_frames += 1
            if first_return_sidewalk is None and ego[1] + extent >= -5.5:
                first_return_sidewalk = frame
            if first_entry_road is None and ego[1] + extent >= -3.5:
                first_entry_road = frame
            minimum_approach_distance = min(
                minimum_approach_distance,
                math.hypot(ego[0] - traffic[0], ego[1] - traffic[1]))
    if (first_exit_sidewalk is None or first_return_sidewalk is None or
            first_entry_road is None or
            native[0]['vehicle_world_xy_m'][0] >= -3 or
            native[400]['vehicle_world_xy_m'][1] > -7 or
            native[-1]['vehicle_world_xy_m'][1] < -3.5):
        raise ValueError('Original roadway exit or return motion incomplete')
    return {
        'case_id': case_id,
        'source_seal_sha256': sha(seal_path),
        'source_kind': 'original_native_capture',
        'frame_count': 1200, 'rate_hz': 20,
        'first_exit_sidewalk_frame': first_exit_sidewalk,
        'first_return_sidewalk_frame': first_return_sidewalk,
        'first_entry_road_frame': first_entry_road,
        'observed_pre_entry_stopped_frames': pre_entry_stopped_frames,
        'minimum_observed_ego_approaching_center_distance_m':
            minimum_approach_distance,
        'district_or_right_of_way_legally_verified': False,
        'physical_completion': None,
        'legal_verdict': None,
    }


def measure_core_join(attempt, case_id):
    attempt = Path(attempt)
    measured = measure(attempt, case_id)
    for name in CORE_FILES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    native = rows(attempt / 'native-rows.jsonl')
    sources = [rows(attempt / name) for name in CORE_FILES]
    if any(len(source) != 1200 for source in sources):
        raise ValueError('Original Core roadway-entry frame coverage incomplete')
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
            raise ValueError('Original Native/Core roadway-entry join differs')
    measured['core_join'] = {
        'frames': 1200,
        'source_sha256': {name: sha(attempt / name) for name in CORE_FILES},
        'original_native_core_join_passed': True,
        'physical_or_legal_outcome_claimed': False,
    }
    return measured
