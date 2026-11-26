"""Saved-source bicycle roadway-use measurements, not a legal verdict."""
import argparse
import json
import math
from pathlib import Path


def inside(p, polygon):
    x, y = p
    result = False
    for i, (ax, ay) in enumerate(polygon):
        bx, by = polygon[i - 1]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            result = not result
    return result


def measure(pose_path, context_path):
    rows = [json.loads(line) for line in Path(pose_path).read_text().splitlines()]
    c = json.loads(Path(context_path).read_text())
    if len(rows) != 600 or [r['video_frame'] for r in rows] != list(range(600)):
        raise ValueError('missing original bicycle frames')
    if not all(rows[i]['native_frame'] < rows[i+1]['native_frame'] for i in range(599)):
        raise ValueError('nonmonotonic Native frame identities')
    if not all(abs(r['time_s'] - i / 20) < .005 for i, r in enumerate(rows)):
        raise ValueError('missing original 20 Hz timing')
    if c.get('rider_class') != 'human_propelled_bicycle' or not c.get('blueprint_id'):
        raise ValueError('original bicycle actor source missing')
    if c.get('sign_text') != 'BICYCLES PROHIBITED ON ROADWAY' or c.get('sign_id') != '100':
        raise ValueError('exact bicycle sign source missing')
    if not c.get('native_sign_survey') or not c.get('native_roadway_survey') or not c.get('native_shoulder_survey'):
        raise ValueError('Native sign or roadway survey source missing')
    if c.get('target_surface') not in ('roadway', 'shoulder') or c.get('case_id', '').rsplit('__', 1)[-1] not in ('probe_01', 'probe_02'):
        raise ValueError('exact case and surface source missing')
    if (c['target_surface'] == 'roadway') != c['case_id'].endswith('__probe_02'):
        raise ValueError('case surface source mismatch')
    polygon = c['roadway_xy_m']
    points = [r['rider_xy_m'] for r in rows]
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
        raise ValueError('invalid original rider position')
    occupied = [inside(p, polygon) for p in points]
    path = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    return {'frames': 600, 'roadway_occupied_frames': sum(occupied),
            'roadway_occupied_after_sign_frames': sum(v and p[0] >= c['sign_x_m'] for v, p in zip(occupied, points)),
            'path_length_m': path, 'longitudinal_displacement_m': points[-1][0]-points[0][0],
            'lateral_displacement_m': points[-1][1]-points[0][1],
            'target_surface': c['target_surface'],
            'wheel_characteristics_reviewed': bool(c.get('wheel_characteristics_reviewed')),
            'physical_sign_pixels_verified': bool(c.get('physical_sign_pixels_verified')),
            'legal_conclusion': None, 'official_designation_verified': bool(c.get('city_traffic_engineer_designation_verified')),
            'physical_review_required': True}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--poses', required=True)
    p.add_argument('--context', required=True)
    a = p.parse_args()
    print(json.dumps(measure(a.poses, a.context), sort_keys=True))
