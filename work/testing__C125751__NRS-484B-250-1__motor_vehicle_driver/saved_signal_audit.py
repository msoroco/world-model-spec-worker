"""Independent original-frame median-crossing evidence audit.

This consumes a sealed Native packet after capture; authored signal settings are
never substituted for per-frame readback or legal device review.
"""
from __future__ import annotations

import hashlib
import json
import math
import argparse
from pathlib import Path
from signal_crossing import _inside


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c):
    return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))


def _segments_touch(a, b, c, d):
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)
    if ab_c * ab_d < 0 and cd_a * cd_b < 0:
        return True
    return ((ab_c == 0 and _on_segment(a, b, c)) or
            (ab_d == 0 and _on_segment(a, b, d)) or
            (cd_a == 0 and _on_segment(c, d, a)) or
            (cd_b == 0 and _on_segment(c, d, b)))


def _point_in_polygon(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if _orientation(a, b, point) == 0 and _on_segment(a, b, point):
            return True
        if (a[1] > y) != (b[1] > y):
            crossing_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing_x:
                inside = not inside
    return inside


def _body_overlaps(body, box):
    if not isinstance(body, list) or len(body) < 3:
        raise ValueError('Native body outline absent')
    if any(not isinstance(p, list) or len(p) != 2 or
           any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p)
           for p in body):
        raise ValueError('Native body outline invalid')
    poly = [tuple(p) for p in body]
    if abs(sum(a[0] * b[1] - b[0] * a[1]
               for a, b in zip(poly, poly[1:] + poly[:1]))) < 1e-8:
        raise ValueError('Native body outline degenerate')
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if any(_inside(p, box) for p in poly) or any(_point_in_polygon(p, poly) for p in corners):
        return True
    return any(_segments_touch(a, b, c, d)
               for a, b in zip(poly, poly[1:] + poly[:1])
               for c, d in zip(corners, corners[1:] + corners[:1]))


def audit(packet: dict, payload: bytes, expected_case: str, expected_source_sha: str):
    if hashlib.sha256(payload).hexdigest() != packet.get('payload_sha256'):
        raise ValueError('Native history seal mismatch')
    if packet.get('case_id') != expected_case or packet.get('review_sha256') != expected_source_sha:
        raise ValueError('case or reviewed source differs')
    history = json.loads(payload)
    rows = history.get('frames', [])
    if len(rows) != packet.get('expected_frames') or len(rows) < 2:
        raise ValueError('original-frame history absent or duration incomplete')
    if history.get('map_sha256') != packet.get('map_sha256'):
        raise ValueError('Native map source differs')
    if packet.get('duration_frames') != packet.get('expected_frames'):
        raise ValueError('duration and original frame count differ')
    if history.get('crossing_id') != packet.get('crossing_id'):
        raise ValueError('Native crossing identity differs')
    bounds = history.get('crossing_bounds_xy_m')
    if (not isinstance(bounds, list) or len(bounds) != 4 or
            any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in bounds) or
            bounds[0] >= bounds[2] or bounds[1] >= bounds[3]):
        raise ValueError('crossing geometry absent')
    entered = {'ego': None, 'other': None}
    cleared = {'ego': None, 'other': None}
    prior_t = None
    prior_inside = {'ego': False, 'other': False}
    states = set()
    transitions = []
    previous_light = None
    for i, row in enumerate(rows):
        if row.get('frame') != i or not isinstance(row.get('time_s'), (int, float)) or not math.isfinite(row['time_s']) or (prior_t is not None and (row['time_s'] <= prior_t or abs(row['time_s'] - prior_t - .05) > .01)):
            raise ValueError('frame/time discontinuity')
        prior_t = row['time_s']
        light = row.get('ego_light_readback')
        if light not in {'Red', 'Yellow', 'Green'}:
            raise ValueError('signal readback absent')
        states.add(light)
        if light != previous_light:
            transitions.append({'frame': i, 'state': light})
        previous_light = light
        for party in ('ego', 'other'):
            actor = row.get(party)
            if not isinstance(actor, dict) or actor.get('actor_id') != history.get(f'{party}_actor_id') or actor.get('alive') is not True:
                raise ValueError(f'{party} Native actor absent or replaced')
            pos = actor.get('xy_m')
            if not isinstance(pos, list) or len(pos) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in pos):
                raise ValueError(f'{party} position absent')
            inside = _body_overlaps(actor.get('body_vertices_xy_m'), bounds)
            if i == 0 and inside:
                raise ValueError(f'{party} begins inside crossing')
            if inside and not prior_inside[party] and entered[party] is None:
                entered[party] = i
            if not inside and prior_inside[party] and cleared[party] is None:
                cleared[party] = i
            if inside and cleared[party] is not None:
                raise ValueError(f'{party} reenters crossing after clearance')
            prior_inside[party] = inside
    if any(v is None for v in entered.values()) or any(v is None for v in cleared.values()):
        raise ValueError('crossing entry and clearance unobserved')
    fixed = ('map_sha256', 'review_sha256', 'crossing_id', 'ego_route_sha256',
             'other_route_sha256', 'camera_plan_sha256', 'duration_frames',
             'ego_blueprint', 'other_blueprint')
    if any(not packet.get(key) for key in fixed):
        raise ValueError('comparison source or fixed condition absent')
    return {'case_id': expected_case, 'source_sha256': expected_source_sha,
            **{key: packet[key] for key in fixed},
            'ego_entry_frame': entered['ego'], 'other_entry_frame': entered['other'],
            'ego_clear_frame': cleared['ego'], 'other_clear_frame': cleared['other'],
            'other_entered_first': entered['other'] < entered['ego'],
            'signal_states_observed': sorted(states),
            'signal_initial_state': rows[0]['ego_light_readback'],
            'signal_transition_frames': transitions,
            'physical_review_pending': True}


def main():
    parser = argparse.ArgumentParser(description='Audit sealed original Native frames')
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.packet.read_text()), args.payload.read_bytes(),
                   args.case, args.source_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
