"""Source-bound sidewalk occupancy; legal and visual review remain separate."""
import argparse
import json
import math
from pathlib import Path

COVERED = {'human_propelled_bicycle', 'electric_bicycle', 'electric_scooter'}
SIGN = 'NO BICYCLES, ELECTRIC BICYCLES OR ELECTRIC SCOOTERS ON SIDEWALK'


def inside(point, polygon):
    x, y = point
    found = False
    for i, (ax, ay) in enumerate(polygon):
        bx, by = polygon[i - 1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            found = not found
    return found


def measure(poses_path, context_path, frame_map_path):
    rows = [json.loads(line) for line in Path(poses_path).read_text().splitlines()]
    mapping = [json.loads(line) for line in Path(frame_map_path).read_text().splitlines()]
    context = json.loads(Path(context_path).read_text())
    if len(rows) != 600 or len(mapping) != 600 or [r['video_frame'] for r in rows] != list(range(600)):
        raise ValueError('missing original 600-frame source')
    if not all(rows[i]['native_frame'] < rows[i + 1]['native_frame'] for i in range(599)):
        raise ValueError('nonmonotonic Native frame identity')
    if not all(abs(r['time_s'] - i / 20) < .005 for i, r in enumerate(rows)):
        raise ValueError('missing original 20 Hz timing')
    for row, frame in zip(rows, mapping):
        if row['native_frame'] != frame.get('native_frame') or abs(row['time_s'] - frame.get('time_s', -999)) > .005:
            raise ValueError('pose/frame map source join failed')
        cameras = frame.get('camera_native_frames', {})
        if set(cameras) != {'overview', 'sign_approach', 'sign_face', 'sidewalk_use'} or any(v != row['native_frame'] for v in cameras.values()):
            raise ValueError('four source camera frame join failed')
    if context.get('street_name') != 'Fremont Street' or context.get('west_boundary') != 'Main Street' or context.get('east_boundary') != 'Seventh Street':
        raise ValueError('named segment source missing')
    if not context.get('native_sidewalk_survey') or not context.get('sidewalk_xy_m'):
        raise ValueError('Native sidewalk geometry source missing')
    if context.get('sign_text') != SIGN or context.get('sign_id') != '100' or not context.get('native_sign_survey'):
        raise ValueError('posted three-class sign source missing')
    if context.get('rider_class') not in COVERED or not context.get('blueprint_id'):
        raise ValueError('covered machine class source missing')
    for row in rows:
        if row.get('rider_blueprint_id') != context['blueprint_id'] or row.get('machine_class') != context['rider_class']:
            raise ValueError('machine class source join failed')
        point = row.get('rider_xy_m')
        velocity = row.get('velocity_xy_mps')
        if not point or not velocity or len(point) != 2 or len(velocity) != 2 or not all(math.isfinite(v) for v in point + velocity):
            raise ValueError('original pose or velocity source missing')
        if row.get('mounted_posture') not in {'mounted', 'dismounted', 'unverified'}:
            raise ValueError('operator posture source missing')
    positions = [r['rider_xy_m'] for r in rows]
    occupied = [inside(p, context['sidewalk_xy_m']) for p in positions]
    moving = [math.hypot(*r['velocity_xy_mps']) > .25 for r in rows]
    mounted = [r['mounted_posture'] == 'mounted' for r in rows]
    dismounted = [r['mounted_posture'] == 'dismounted' for r in rows]
    uncertainty = sum(r['mounted_posture'] == 'unverified' for r in rows)
    return {'frames': 600, 'sidewalk_occupied_frames': sum(occupied),
            'moving_sidewalk_frames': sum(a and b for a, b in zip(occupied, moving)),
            'mounted_moving_sidewalk_frames': sum(a and b and c for a, b, c in zip(occupied, moving, mounted)),
            'dismounted_moving_sidewalk_frames': sum(a and b and c for a, b, c in zip(occupied, moving, dismounted)),
            'posture_unverified_frames': uncertainty,
            'path_length_m': sum(math.dist(a, b) for a, b in zip(positions, positions[1:])),
            'geographic_identity_verified': bool(context.get('geographic_identity_verified')),
            'sign_posting_observed_in_native_map': True,
            'sign_face_pixels_verified': bool(context.get('physical_sign_pixels_verified')),
            'riding_prohibition_conditional_on_sign': False,
            'legal_conclusion': None, 'physical_review_required': True}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--poses', required=True)
    p.add_argument('--context', required=True)
    p.add_argument('--frame-map', required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.poses, a.context, a.frame_map), sort_keys=True))
