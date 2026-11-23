"""Source-gated crest and opposing-lane geometry for NRS 484B.213(2)(a).

The real capture must supply original map waypoint samples. Targets here are
engineering probes, not definitions of the statutory hazard judgment.
"""
from __future__ import annotations

import math


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_lanes(ego, opposite):
    """Require two original, opposite-direction lanes on the same road."""
    if not isinstance(ego, list) or not isinstance(opposite, list) or len(ego) < 3 or len(opposite) < 3:
        raise ValueError('original ego and opposing waypoint samples required')
    for lane in (ego, opposite):
        for point in lane:
            if not isinstance(point, dict) or not all(_number(point.get(k)) for k in ('s_m', 'x_m', 'y_m', 'road_z_m')):
                raise ValueError('finite original waypoint coordinates required')
            if not point.get('source_ref') or point.get('road_id') is None or point.get('lane_id') is None:
                raise ValueError('original waypoint provenance and road/lane IDs required')
        if any(b['s_m'] <= a['s_m'] for a, b in zip(lane, lane[1:])):
            raise ValueError('waypoint stations must increase')
        if len({p['road_id'] for p in lane}) != 1 or len({p['lane_id'] for p in lane}) != 1:
            raise ValueError('route changes road or lane')
    if ego[0]['road_id'] != opposite[0]['road_id'] or ego[0]['lane_id'] == opposite[0]['lane_id']:
        raise ValueError('opposing lane must be distinct on the same road')
    if ego[0].get('travel_direction') != 'increasing_s' or opposite[0].get('travel_direction') != 'decreasing_s':
        raise ValueError('original lane travel directions do not oppose')
    if any(p.get('travel_direction') != 'increasing_s' for p in ego) or any(p.get('travel_direction') != 'decreasing_s' for p in opposite):
        raise ValueError('inconsistent lane direction history')
    if any(abs(a['s_m'] - b['s_m']) > 0.1 for a, b in zip(ego, opposite)) or len(ego) != len(opposite):
        raise ValueError('opposing lane station coverage differs')
    if any(abs(a['road_z_m'] - b['road_z_m']) > 0.5 for a, b in zip(ego, opposite)):
        raise ValueError('lanes do not share a credible road grade')
    return True


def crest_occlusion(ego, opposite, *, observer_s_m, target_s_m, eye_height_m=1.4,
                     body_height_m=1.4):
    """Return sampled grade intersection, never a legal visibility conclusion."""
    validate_lanes(ego, opposite)
    if not all(_number(v) for v in (observer_s_m, target_s_m, eye_height_m, body_height_m)):
        raise ValueError('finite observer and target measurements required')
    if observer_s_m >= target_s_m or eye_height_m <= 0 or body_height_m <= 0:
        raise ValueError('observer must approach an opposing target in station order')
    points = {p['s_m']: p for p in ego}
    if observer_s_m not in points or target_s_m not in points:
        raise ValueError('observer and target require original waypoint samples')
    eye_z = points[observer_s_m]['road_z_m'] + eye_height_m
    target_z = points[target_s_m]['road_z_m'] + body_height_m
    blockers = []
    for p in ego:
        s = p['s_m']
        if observer_s_m < s < target_s_m:
            ray_z = eye_z + (target_z - eye_z) * (s - observer_s_m) / (target_s_m - observer_s_m)
            if p['road_z_m'] > ray_z:
                blockers.append({'s_m': s, 'excess_height_m': p['road_z_m'] - ray_z,
                                 'source_ref': p['source_ref']})
    return {'sampled_grade_blocks_proxy_ray': bool(blockers), 'blockers': blockers,
            'observer_s_m': observer_s_m, 'target_s_m': target_s_m,
            'proxy_limitations': 'Sampled road grade and virtual observer only; Native raycasts, actual bodies, pixels and hazard judgment remain unverified.'}
