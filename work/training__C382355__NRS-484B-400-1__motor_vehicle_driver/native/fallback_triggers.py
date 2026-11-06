"""Evaluate fallback conditions from saved sources; never infer physical success."""
import hashlib
import json
import math
from pathlib import Path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value):
    if (not isinstance(value, list) or len(value) != 2 or
        any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('Invalid route or Native point')
    return value


def _distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        raise ValueError('Degenerate requested route segment')
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def evaluate(samples_path, map_audit_path, pixel_audit_path, video_path, requested_route_xy_m):
    """Return three independently measured triggers for one original attempt.

    ``map_audit`` is an independently reviewed Native map readback, and
    ``pixel_audit`` is an independently reviewed original camera annotation.
    Synthetic inputs exercise this logic but cannot establish those origins.
    """
    paths = [Path(p) for p in (samples_path, map_audit_path, pixel_audit_path, video_path)]
    if any(not p.is_file() for p in paths):
        raise ValueError('Missing trigger source')
    samples = [json.loads(line) for line in paths[0].read_text().splitlines() if line.strip()]
    if len(samples) < 4:
        raise ValueError('Too few original Native samples')
    mapping = json.loads(paths[1].read_text())
    pixels = json.loads(paths[2].read_text())
    if mapping.get('source_kind') != 'native_map_readback':
        raise ValueError('Native map readback provenance missing')
    if mapping.get('native_samples_sha256') != _sha(paths[0]):
        raise ValueError('Native sample hash mismatch')
    if type(mapping.get('connected_right_turn_lane_link')) is not bool:
        raise ValueError('Native connector observation missing')
    if pixels.get('source_kind') != 'original_camera_pixels':
        raise ValueError('Original pixel provenance missing')
    if pixels.get('video_sha256') != _sha(paths[3]) or pixels.get('native_samples_sha256') != _sha(paths[0]):
        raise ValueError('Pixel audit source hash mismatch')
    visible, total = pixels.get('full_body_and_lane_marking_visible_frames'), pixels.get('approach_frames')
    if type(visible) is not int or type(total) is not int or total < 1 or not 0 <= visible <= total:
        raise ValueError('Invalid pixel visibility counts')
    route = [_point(p) for p in requested_route_xy_m]
    if len(route) < 2:
        raise ValueError('Requested route is incomplete')
    errors = []
    completed = False
    last_frame, last_time = -1, -math.inf
    for row in samples:
        frame, time = row.get('native_frame'), row.get('time_s')
        if (type(frame) is not int or frame <= last_frame or type(time) not in (int, float)
            or not math.isfinite(time) or time <= last_time):
            raise ValueError('Native frame/time sequence invalid')
        last_frame, last_time = frame, time
        center = _point(row.get('native_center_xy_m'))
        body = row.get('native_body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Complete Native body missing')
        body = [_point(p) for p in body]
        if -10 <= center[0] <= 0:
            errors.append(min(_distance(center, a, b) for a, b in zip(route, route[1:])))
        if (time <= 24 and max(p[1] for p in body) < -7 and
            row.get('native_road_id') == 4 and row.get('native_lane_id') == -2):
            completed = True
    if not errors:
        raise ValueError('No observed turn-entry tracking window')
    maximum = max(errors)
    fraction = visible / total
    return {
        'fallback1': not mapping['connected_right_turn_lane_link'] or not completed,
        'fallback2': maximum > 0.35,
        'fallback3': fraction < 0.95,
        'metrics': {'connected_right_turn_lane_link': mapping['connected_right_turn_lane_link'],
                    'full_body_destination_exit_observed_by_24s': completed,
                    'maximum_turn_entry_route_error_m': maximum,
                    'approach_pixel_visible_fraction': fraction},
        'source_hashes': {p.name: _sha(p) for p in paths},
        'scope': 'Source-bound trigger logic; synthetic values are not physical observations'
    }
