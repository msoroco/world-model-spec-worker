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
    bounds = history.get('crossing_bounds_xy_m')
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError('crossing geometry absent')
    entered = {'ego': None, 'other': None}
    cleared = {'ego': None, 'other': None}
    prior_t = -math.inf
    prior_inside = {'ego': False, 'other': False}
    states = set()
    for i, row in enumerate(rows):
        if row.get('frame') != i or not isinstance(row.get('time_s'), (int, float)) or not math.isfinite(row['time_s']) or row['time_s'] <= prior_t:
            raise ValueError('frame/time discontinuity')
        prior_t = row['time_s']
        light = row.get('ego_light_readback')
        if light not in {'Red', 'Yellow', 'Green'}:
            raise ValueError('signal readback absent')
        states.add(light)
        for party in ('ego', 'other'):
            actor = row.get(party)
            if not isinstance(actor, dict) or actor.get('actor_id') != history.get(f'{party}_actor_id') or actor.get('alive') is not True:
                raise ValueError(f'{party} Native actor absent or replaced')
            pos = actor.get('xy_m')
            if not isinstance(pos, list) or len(pos) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in pos):
                raise ValueError(f'{party} position absent')
            inside = _inside(pos, bounds)
            if inside and not prior_inside[party] and entered[party] is None:
                entered[party] = i
            if not inside and prior_inside[party] and cleared[party] is None:
                cleared[party] = i
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
            'signal_states_observed': sorted(states), 'physical_review_pending': True}


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
