"""Source-bound kinematic observations for NRS 484B.210(1)(a).

This records physical events; it never decides whether a pass is lawful. Input is
an original native per-tick trace, sealed separately from this measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def load_sealed_trace(path: Path, expected_sha256: str) -> dict:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise ValueError('source trace sha256 mismatch')
    data = json.loads(raw)
    if data.get('source_kind') != 'original_native_actor_trace':
        raise ValueError('source must be an original native actor trace')
    return data


def observe(data: dict) -> dict:
    frames = data.get('frames', [])
    if len(frames) < 8:
        raise ValueError('at least eight source frames required')
    if data.get('fps') != 20 or data.get('ego_id') == data.get('target_id'):
        raise ValueError('wrong clock or actor binding')
    road = data.get('road', {})
    if not road.get('public_highway_observed') or not road.get('two_way_observed'):
        raise ValueError('road status and direction need native source confirmation')
    interval = road.get('intersection_s_m')
    if not isinstance(interval, list) or len(interval) != 2 or interval[0] >= interval[1]:
        raise ValueError('missing original intersection bounds')
    prev = None
    events = []
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('t_s', -1) - i / 20) > 1e-6:
            raise ValueError('noncontinuous original 20 Hz trace')
        for key in ('ego_s_m', 'target_s_m', 'ego_lateral_m', 'target_lateral_m',
                    'ego_speed_mps', 'target_speed_mps', 'target_left_signal',
                    'target_heading_deg', 'ego_paved', 'target_paved'):
            if key not in frame:
                raise ValueError('missing native actor field: ' + key)
        for key in ('ego_s_m', 'target_s_m', 'ego_lateral_m', 'target_lateral_m',
                    'ego_speed_mps', 'target_speed_mps', 'target_heading_deg'):
            if not math.isfinite(frame[key]):
                raise ValueError('nonfinite native field: ' + key)
        if not frame['ego_paved'] or not frame['target_paved']:
            raise ValueError('actor leaves observed paved surface')
        if prev is not None and frame['ego_s_m'] < prev['ego_s_m']:
            raise ValueError('ego progress reverses')
        prev = frame
    # A right pass requires both a trailing and an ahead sample after warmup,
    # and source-derived lateral ordering throughout the crossing window.
    trailing = [f for f in frames[2:] if f['ego_s_m'] + 1.0 < f['target_s_m']]
    ahead = [f for f in frames[2:] if f['ego_s_m'] > f['target_s_m'] + 1.0]
    if not trailing or not ahead or trailing[-1]['frame'] >= ahead[0]['frame']:
        raise ValueError('no completed right-pass order in original trace')
    start, end = trailing[-1]['frame'], ahead[0]['frame']
    crossing = frames[start:end + 1]
    if any(f['ego_lateral_m'] <= f['target_lateral_m'] + 1.0 for f in crossing):
        raise ValueError('ego was not to target right throughout pass')
    signal = any(f['target_left_signal'] is True for f in crossing)
    # Leftward target motion is a measured heading/lateral change, not a signal
    # alias. The 0.5 m and 10 degree values are detection tolerances only.
    left_motion = (crossing[-1]['target_lateral_m'] - crossing[0]['target_lateral_m'] < -0.5
                   and crossing[-1]['target_heading_deg'] - crossing[0]['target_heading_deg'] < -10.0)
    near_intersection = any(interval[0] <= f['ego_s_m'] <= interval[1] for f in crossing)
    if not near_intersection:
        raise ValueError('pass not at source-bound intersection')
    events.append({'frame': start, 'kind': 'last_trailing_sample'})
    events.append({'frame': end, 'kind': 'first_ahead_sample'})
    return {
        'source_kind': data['source_kind'], 'ego_id': data['ego_id'],
        'target_id': data['target_id'], 'pass_frames': [start, end],
        'pass_distance_m': frames[end]['ego_s_m'] - frames[start]['ego_s_m'],
        'target_left_signal_during_pass': signal,
        'target_left_motion_during_pass': left_motion,
        'intersection_crossed_during_pass': near_intersection,
        'right_pass_observed': True,
        'paragraph_a_condition_observed': bool(signal or left_motion),
        'other_permission_alternatives': 'unresolved_requires_separate_geometry_review',
        'legal_outcome': 'unresolved', 'events': events,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = observe(load_sealed_trace(args.trace, args.sha256))
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
