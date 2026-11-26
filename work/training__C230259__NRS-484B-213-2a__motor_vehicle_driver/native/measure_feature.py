"""Measure complete original source joins for the crest, curve and one-way cases.

The output is geometry and visibility evidence for review, not a statutory verdict.
"""
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(trace_path, road_path):
    road = json.loads(Path(road_path).read_text())
    rows = read_rows(trace_path)
    if len(rows) != FRAMES or [r.get('frame') for r in rows] != list(range(FRAMES)):
        raise ValueError('missing or disordered complete source trace')
    kind = road.get('feature_kind')
    if kind not in ('crest', 'curve') or road.get('feature_start_s_m') is None or road.get('feature_end_s_m') is None:
        raise ValueError('missing source feature geometry')
    start, end = float(road['feature_start_s_m']), float(road['feature_end_s_m'])
    if not 0 <= start < end or not road.get('road_geometry_sha256'):
        raise ValueError('invalid source feature interval or map binding')
    if kind == 'crest' and road.get('grade_profile_source') is None:
        raise ValueError('missing source grade profile')
    if kind == 'curve' and road.get('curvature_source') is None:
        raise ValueError('missing source curve profile')
    directionality = road.get('directionality')
    if directionality not in ('one_way', 'two_way') or road.get('centerline_source') is None:
        raise ValueError('missing source road directionality or centerline')
    approach, inside, left, obscured, opposing, sight = [], [], [], [], [], []
    for index, row in enumerate(rows):
        required = ('ego_id', 'ego_s_m', 'ego_forward_mps', 'ego_body_min_signed_m',
                    'ego_body_max_signed_m', 'sight_clear_m', 'sight_censored',
                    'camera_frame_ids', 'map_waypoint_source')
        if any(row.get(key) is None for key in required):
            raise ValueError('missing original ego, body, sightline or map source')
        if set(row['camera_frame_ids']) != set(CAMERAS) or any(row['camera_frame_ids'][name] != index for name in CAMERAS):
            raise ValueError('four-camera/source frame misjoin')
        s = float(row['ego_s_m'])
        if float(row['ego_forward_mps']) > 0 and s < start:
            approach.append(index)
        if start <= s <= end:
            inside.append(index)
        if float(row['ego_body_min_signed_m']) < 0:
            left.append(index)
        if row['sight_censored'] or float(row['sight_clear_m']) < float(row.get('available_forward_road_m', 1e9)):
            obscured.append(index)
        if row.get('other_vehicle_id') is not None:
            if row.get('other_vehicle_route_direction') not in ('opposing', 'same') or row.get('other_vehicle_s_m') is None:
                raise ValueError('missing other participant route source')
            if row['other_vehicle_route_direction'] == 'opposing':
                opposing.append(index)
        sight.append(float(row['sight_clear_m']))
    if directionality == 'one_way' and opposing:
        raise ValueError('one-way source contradicts opposing participant route')
    active = set(approach if kind == 'crest' else inside)
    overlap = sorted(active & set(left) & set(obscured))
    return {'format': 'worker-feature-source-measurement-v1',
            'trace_sha256': sha(trace_path), 'road_sha256': sha(road_path),
            'frames': FRAMES, 'rate_hz': 20, 'feature_kind': kind,
            'feature_start_s_m': start, 'feature_end_s_m': end,
            'road_directionality': directionality,
            'one_way_exception_context': directionality == 'one_way',
            'approach_frame_count': len(approach), 'feature_frame_count': len(inside),
            'left_of_center_frame_count': len(left), 'obscured_frame_count': len(obscured),
            'active_left_obscured_first_frame': overlap[0] if overlap else None,
            'active_left_obscured_frame_count': len(overlap),
            'sight_clear_min_m': min(sight), 'sight_clear_max_m': max(sight),
            'opposing_vehicle_observed_frames': len(opposing),
            'hazard_distance_legal_judgment': None,
            'physical_completion': None, 'legal_verdict': None}
