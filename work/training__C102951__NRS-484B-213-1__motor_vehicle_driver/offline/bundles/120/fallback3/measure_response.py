"""Saved approaching/overtaken response metrics during a completed pass.

These kinematics describe observed motion. They do not assign causation,
interference, a statutory sufficient distance or a legal verdict.
"""
import argparse
import json
import math
from pathlib import Path

from measure_pass import measure

WINDOW = 5
HARD_DECEL_MPS2 = -3.0


def median(values):
    ordered = sorted(values)
    n = len(ordered)
    return (ordered[(n-1)//2]+ordered[n//2])/2


def measure_response(folder, expected_hashes=None):
    folder = Path(folder)
    passing = measure(folder, expected_hashes)
    rows = [json.loads(line) for line in (folder/'native-observed.jsonl').read_text().splitlines()]
    start = passing['first_left_of_center_frame']
    finish = passing['first_return_after_pass_frame']
    if start < 20 or finish+WINDOW >= len(rows):
        raise ValueError('Saved response lacks 20-frame baseline or post-pass window')
    response = {}
    for actor in ('oncoming', 'overtaken'):
        key = actor+'_speed_mps'
        baseline = median([row[key] for row in rows[:20]])
        phase = [row[key] for row in rows[start:finish+1]]
        accelerations = []
        for i in range(start, finish+1):
            if i < WINDOW:
                continue
            t = rows[i]['time_s']-rows[i-WINDOW]['time_s']
            if not math.isfinite(t) or abs(t-WINDOW/20) > 1e-4:
                raise ValueError('Saved response time window differs')
            accelerations.append((i, (rows[i][key]-rows[i-WINDOW][key])/t))
        if not accelerations:
            raise ValueError('Saved response acceleration window absent')
        minimum_frame, minimum_accel = min(accelerations, key=lambda item: (item[1], item[0]))
        hard_frames = [i for i, value in accelerations if value < HARD_DECEL_MPS2]
        response[actor] = {
            'prepass_median_speed_mps': round(baseline, 3),
            'minimum_left_phase_speed_mps': round(min(phase), 3),
            'maximum_left_phase_speed_drop_mps': round(max(0, baseline-min(phase)), 3),
            'minimum_five_frame_acceleration_mps2': round(minimum_accel, 3),
            'minimum_acceleration_frame': minimum_frame,
            'five_frame_hard_deceleration_count': len(hard_frames),
            'first_five_frame_hard_deceleration_frame': hard_frames[0] if hard_frames else None,
        }
    return {
        'format': 'c102951-saved-response-measurement-v1',
        'source_kind': passing['source_kind'],
        'source_hashes': passing['source_hashes'],
        'pass_entry_frame': start, 'pass_return_frame': finish,
        'sampling_rate_hz': 20, 'acceleration_window_frames': WINDOW,
        'engineering_hard_deceleration_threshold_mps2': HARD_DECEL_MPS2,
        'response': response,
        'caused_by_passing_judgment': None,
        'interference_judgment': None,
        'safe_distance_judgment': None,
        'legal_verdict': None,
        'delivery_ready': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    print(json.dumps(measure_response(args.folder), indent=2))
