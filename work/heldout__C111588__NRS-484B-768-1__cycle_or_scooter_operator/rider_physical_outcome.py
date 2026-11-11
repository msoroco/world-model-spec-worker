"""Source-based turn completion check; thresholds are engineering fixture criteria."""
import json
from math import atan2, cos, hypot, radians, sin
from pathlib import Path


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def assess(root):
    root = Path(root)
    sources = ['rider_motion.jsonl', 'trace.jsonl', 'video_frames.jsonl']
    method = 'joined rider heading change at least 65 degrees and planar path progress at least 2 metres'
    if any(not (root / name).is_file() for name in sources):
        return {'physical_checks': {'maneuver': {'status': 'unverified', 'method': method,
                 'sources': sources, 'reason': 'one or more original motion sources absent'}},
                'maneuver_completed': False, 'realized_observables': {},
                'provenance_kind': 'native', 'fixture_only': True,
                'actual_native_capture': False, 'physical_acceptance_claimed': False}
    motion, trace, mapping = (_rows(root / name) for name in sources)
    if len(motion) < 3 or len(motion) != len(trace) or len(trace) != len(mapping):
        raise ValueError('Motion/frame lengths differ')
    for i, (r, t, f) in enumerate(zip(motion, trace, mapping)):
        if (r['frame'], r['time_s']) != (t['frame'], t['time_s']) or (r['frame'], r['time_s']) != (f['carla_frame'], f['time_s']) or f['video_frame'] != i:
            raise ValueError('Motion/frame identities differ')
    delta = float(motion[-1]['rider_yaw_deg']) - float(motion[0]['rider_yaw_deg'])
    turn = abs(atan2(sin(radians(delta)), cos(radians(delta))) * 180 / 3.141592653589793)
    first, last = trace[0]['position_m'], trace[-1]['position_m']
    progress = hypot(float(last[0]) - float(first[0]), float(last[1]) - float(first[1]))
    status = 'met' if turn >= 65 and progress >= 2 else 'not_met'
    return {'physical_checks': {'maneuver': {'status': status, 'method': method,
             'sources': sources, 'net_turn_deg': turn, 'planar_progress_m': progress}},
            'maneuver_completed': status == 'met',
            'realized_observables': {'net_turn_deg': turn, 'planar_progress_m': progress},
            'provenance_kind': 'native', 'fixture_only': True,
            'actual_native_capture': False, 'physical_acceptance_claimed': False}
