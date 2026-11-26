"""Source-shaped physical destination-stop check, independent of legal judgment."""

from __future__ import annotations

import math

from designated_stop import FRAMES, RATE_HZ, REST_SPEED_MPS, measure


def motion(rows):
    if not isinstance(rows, list) or len(rows) != FRAMES:
        raise ValueError('Incomplete original physical motion source')
    points, speeds = [], []
    for index, row in enumerate(rows):
        point = row.get('position_m')
        speed = row.get('observed_speed_mps')
        if not isinstance(point, list) or len(point) != 3 or any(
                type(value) not in (int, float) or not math.isfinite(value)
                for value in point):
            raise ValueError('Original finite vehicle position missing')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original finite vehicle speed missing')
        points.append(point)
        speeds.append(speed)
    progress = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    stationary = [index for index, speed in enumerate(speeds)
                  if speed <= REST_SPEED_MPS]
    longest, current = 0, 0
    for speed in speeds:
        current = current + 1 if speed <= REST_SPEED_MPS else 0
        longest = max(longest, current)
    return {'sampled_path_m': round(progress, 4),
            'rest_frames': len(stationary),
            'longest_continuous_rest_frames': longest,
            'approach_observed': progress >= 0.25,
            'rest_observed': longest >= 80,
            'engineering_tolerances_not_legal': True}


def assess(packet):
    measured = measure(packet)
    observed = motion(packet['rows'])
    status = 'met' if observed['approach_observed'] and \
        observed['rest_observed'] else 'not_met'
    return {'format': 'worker-designated-stop-physical-check',
            'criterion': 'observed_approach_then_destination_rest',
            'status': status, 'frames': FRAMES, 'rate_hz': RATE_HZ,
            'observation': observed,
            'body_overlap_at_any_rest_frame': measured['body_overlap_at_any_rest_frame'],
            'source_hashes': measured['source_hashes'],
            'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False}
