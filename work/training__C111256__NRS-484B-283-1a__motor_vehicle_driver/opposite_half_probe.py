"""Source-shaped opposite-half geometry probe without a legal danger cutoff.

This is a CPU construction probe, not a CARLA capture or selected delivery case.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

CASES = ('opposite_half_near', 'opposite_half_farther')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
BASE = {'route_tracking_lookahead_m': 5.0, 'yield_clearance_margin_s': 1.0,
        'overview_fov_deg': 90.0}
CHANGES = {'primary': {}, 'fallback1': {'route_tracking_lookahead_m': 3.0},
           'fallback2': {'yield_clearance_margin_s': 2.0},
           'fallback3': {'overview_fov_deg': 105.0}}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_rows(case):
    if case not in CASES:
        raise ValueError('Unknown opposite-half case')
    target_x = -0.35 if case == 'opposite_half_near' else -2.15
    rows = []
    for frame in range(480):
        time_s = frame / 20
        ego_y = -40 + min(frame, 240) * 0.16
        walker_x = -4 + (target_x + 4) * min(frame, 160) / 160
        rows.append({'native_frame': frame + 100, 'time_s': time_s,
                     'ego_body_xy_m': [[0.8, ego_y - 2.6], [2.7, ego_y - 2.6],
                                       [2.7, ego_y + 2.6], [0.8, ego_y + 2.6]],
                     'pedestrian_body_xy_m': [[walker_x - .2, -11.2],
                                               [walker_x + .2, -11.2],
                                               [walker_x + .2, -10.8],
                                               [walker_x - .2, -10.8]],
                     'ego_directional_lane_ids': [-1],
                     'pedestrian_directional_lane_ids': [1],
                     'official_device_actors_present': False,
                     'marked_crosswalk_geometry_present': True})
    return {'format': 'c111256-opposite-half-source-v1', 'case': case,
            'source_kind': 'synthetic_native_sample', 'rate_hz': 20,
            'frames': rows, 'legal_danger_threshold': None,
            'original_native_observed': False}


def interval_distance(a_low, a_high, b_low, b_high):
    return max(a_low - b_high, b_low - a_high, 0.0)


def measure(source, case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    record = json.loads(source.read_text())
    if record.get('source_kind') != 'synthetic_native_sample' or record.get('case') != case:
        raise ValueError('Wrong or unsourced opposite-half sample')
    rows = record.get('frames')
    if not isinstance(rows, list) or len(rows) != 480:
        raise ValueError('Exact 480-frame source required')
    distances = []
    for index, row in enumerate(rows):
        if row.get('native_frame') != index + 100 or abs(row.get('time_s', -1) - index / 20) > 1e-9:
            raise ValueError('Frame join differs')
        if row.get('ego_directional_lane_ids') != [-1] or row.get('pedestrian_directional_lane_ids') != [1]:
            raise ValueError('Pedestrian is not on the opposite directional half')
        if row.get('official_device_actors_present') is not False or row.get('marked_crosswalk_geometry_present') is not True:
            raise ValueError('Uncontrolled marked-crosswalk source missing')
        ego = row['ego_body_xy_m']; ped = row['pedestrian_body_xy_m']
        ex = [point[0] for point in ego]; ey = [point[1] for point in ego]
        px = [point[0] for point in ped]; py = [point[1] for point in ped]
        if max(px) >= 0 or min(ex) <= 0:
            raise ValueError('Synthetic body crossed directional-half boundary')
        distance = math.hypot(interval_distance(min(ex), max(ex), min(px), max(px)),
                              interval_distance(min(ey), max(ey), min(py), max(py)))
        distances.append(distance)
    closest = min(range(480), key=lambda i: distances[i])
    return {'format': 'c111256-opposite-half-measurement-v1', 'case': case,
            'candidate': candidate, 'source_sha256': sha(source),
            'source_kind': 'synthetic_native_sample', 'frames_joined': 480,
            'minimum_body_clearance_m': round(distances[closest], 6),
            'minimum_clearance_frame': closest + 100,
            'minimum_clearance_time_s': closest / 20,
            'pedestrian_remained_opposite_half': True,
            'legal_danger_threshold': None, 'legal_danger_judgment': None,
            'physical_acceptance_claimed': False,
            'knobs': BASE | CHANGES[candidate]}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--candidate', choices=CANDIDATES, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = measure(a.source, a.case, a.candidate)
    if a.output.exists():
        raise ValueError('Retain previous probe output')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case': a.case, 'candidate': a.candidate,
                      'minimum_body_clearance_m': result['minimum_body_clearance_m'],
                      'legal_danger_judgment': None}))
