"""Join original roundabout sources without deciding statutory impeding."""

import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing retained source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def polar(actor, center):
    return (math.hypot(actor['x_m'] - center[0], actor['y_m'] - center[1]),
            math.atan2(actor['y_m'] - center[1], actor['x_m'] - center[0]))


def lane(radius, geometry):
    outer = geometry['outer_right_lane_radius_m']
    inner = geometry['inner_left_lane_radius_m']
    if outer[0] <= radius < outer[1]:
        return 'extreme_right'
    if inner[0] <= radius < inner[1]:
        return 'inner_left'
    return 'outside_or_straddling'


def measure(config_path, native_path, frame_path, geometry_path):
    config = json.loads(Path(config_path).read_text())
    geometry = json.loads(Path(geometry_path).read_text())
    native, frames = lines(native_path), lines(frame_path)
    if config.get('frames') != FRAMES or config.get('rate_hz') != RATE or len(native) != FRAMES or len(frames) != FRAMES:
        raise ValueError('Exact 30-second source contract differs')
    if geometry.get('source_kind') not in ('synthetic_native_sample', 'original_native'):
        raise ValueError('Roundabout geometry provenance missing')
    outer, inner = geometry.get('outer_right_lane_radius_m'), geometry.get('inner_left_lane_radius_m')
    if (geometry.get('direction') != 'counterclockwise' or
            not isinstance(outer, list) or not isinstance(inner, list) or
            len(outer) != 2 or len(inner) != 2 or
            not 0 < inner[0] < inner[1] <= outer[0] < outer[1] or
            not geometry.get('same_direction_marked_lanes_source')):
        raise ValueError('Two marked same-direction roundabout lanes unverified')
    center = geometry.get('center_xy_m')
    if not isinstance(center, list) or len(center) != 2 or not all(isinstance(x, (int, float)) for x in center):
        raise ValueError('Roundabout center source missing')
    counts = {'extreme_right': 0, 'inner_left': 0, 'outside_or_straddling': 0,
              'follower_behind': 0, 'ego_slower_than_follower': 0,
              'slower_vehicle_ahead': 0, 'pass_in_progress': 0,
              'after_pass_right': 0, 'after_pass_left': 0}
    previous_frame = None
    first_clearance = None
    first_pass = None
    for i, (row, frame) in enumerate(zip(native, frames)):
        fid = row.get('native_frame')
        if type(fid) is not int or (previous_frame is not None and fid != previous_frame + 1):
            raise ValueError('Native frame sequence differs')
        previous_frame = fid
        t = i / RATE
        if (frame.get('native_frame') != fid or frame.get('video_frame') != i or
                any(not isinstance(x, (int, float)) or abs(x - t) > 1e-4 for x in (row.get('time_s'), frame.get('time_s')))):
            raise ValueError('Original Native/video frame-time join differs')
        if row.get('source_kind') != geometry['source_kind'] or set(row.get('actors', {})) < {'ego', 'follower'}:
            raise ValueError('Original ego/follower source missing')
        ego, follower = row['actors']['ego'], row['actors']['follower']
        if any(not isinstance(actor.get(key), (int, float)) or not math.isfinite(actor[key]) for actor in (ego, follower) for key in ('x_m', 'y_m', 'speed_mps')):
            raise ValueError('Original actor position or speed missing')
        if ego['speed_mps'] < 0 or follower['speed_mps'] < 0:
            raise ValueError('Original negative source speed')
        body = ego.get('body_vertices_native_m')
        if not isinstance(body, list) or len(body) < 4 or any(
                not isinstance(v, list) or len(v) < 2 for v in body):
            raise ValueError('Original ego body vertices missing')
        ego_radius, ego_angle = polar(ego, center)
        follow_radius, follow_angle = polar(follower, center)
        body_lanes = {lane(math.hypot(v[0]-center[0], v[1]-center[1]), geometry) for v in body}
        occupied = body_lanes.pop() if len(body_lanes) == 1 else 'outside_or_straddling'
        counts[occupied] += 1
        arc = (ego_angle - follow_angle) % (2 * math.pi)
        if 0 < arc < math.pi and abs(follow_radius - ego_radius) < 4.0:
            counts['follower_behind'] += 1
        if ego['speed_mps'] < follower['speed_mps']:
            counts['ego_slower_than_follower'] += 1
        pass_source = row.get('pass_observation')
        if pass_source is not None:
            if not isinstance(pass_source, dict) or not isinstance(pass_source.get('slower_vehicle_ahead'), bool) or not isinstance(pass_source.get('slower_vehicle_cleared'), bool):
                raise ValueError('Original pass observation incomplete')
            if pass_source['slower_vehicle_ahead']:
                counts['slower_vehicle_ahead'] += 1
            if pass_source['slower_vehicle_ahead'] and not pass_source['slower_vehicle_cleared'] and occupied == 'inner_left':
                counts['pass_in_progress'] += 1
                if first_pass is None:
                    first_pass = i
            if pass_source['slower_vehicle_cleared']:
                if first_clearance is None:
                    first_clearance = i
                counts['after_pass_right' if occupied == 'extreme_right' else 'after_pass_left'] += 1
    return {'format': 'c132924-source-roundabout-measurement-v1',
            'case_id': config['case_id'], 'frames': FRAMES, 'rate_hz': RATE,
            'counts': counts, 'first_pass_frame': first_pass,
            'first_clearance_frame': first_clearance,
            'source_hashes': {'config': sha(config_path), 'native': sha(native_path),
                              'frame_map': sha(frame_path), 'geometry': sha(geometry_path)},
            'impeding_judgment': None, 'passing_necessity_judgment': None,
            'physical_legal_verdict': None, 'original_pixels_verified': False}
