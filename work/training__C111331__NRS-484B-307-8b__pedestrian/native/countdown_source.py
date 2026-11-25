"""Synthetic 283(1)(d)(2) countdown request, separate from Native evidence."""

import json
import math
from pathlib import Path

from native_red import BOUNDARY_Y, FRAMES, countdown_program, plan, requested_speed, sha

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'diagnostic-red-entry' / 'exception_countdown.jsonl'


def requested():
    config = plan('exception_countdown')
    y = config['walker_start_xy_m'][1]
    rows = []
    for frame in range(FRAMES):
        y -= requested_speed('exception_countdown', frame) / 20
        program = countdown_program(frame)
        flashing, remaining = program['flashing'], program['countdown_seconds']
        feet = [[x, round(y + dy, 4)] for x, dy in
                ((7.8, -.2), (7.8, .2), (8.2, -.2), (8.2, .2))]
        rows.append({'frame': frame, 'time_s': frame / 20,
                     'walker_footprint_xy_m': feet,
                     'traffic_head': 'steady_red_alone',
                     'other_device': 'flashing_dont_walk_countdown' if flashing else 'steady_dont_walk',
                     'countdown_seconds': remaining,
                     'source_kind': 'synthetic_scene_request',
                     'original_native_observed': False,
                     'legal_verdict': None})
    return rows


def measure(rows):
    if len(rows) != FRAMES:
        raise ValueError('Countdown source incomplete')
    first_entry = None
    for index, row in enumerate(rows):
        if row.get('frame') != index or row.get('time_s') != index / 20 or \
                row.get('traffic_head') != 'steady_red_alone' or \
                row.get('source_kind') != 'synthetic_scene_request' or \
                row.get('original_native_observed') is not False or \
                row.get('legal_verdict') is not None:
            raise ValueError('Countdown original-source status changed')
        flashing = countdown_program(index)['flashing']
        expected_device = 'flashing_dont_walk_countdown' if flashing else 'steady_dont_walk'
        expected_timer = math.ceil((380 - index) / 20) if flashing else None
        if row.get('other_device') != expected_device or row.get('countdown_seconds') != expected_timer:
            raise ValueError('Countdown display request changed')
        feet = row.get('walker_footprint_xy_m')
        if not isinstance(feet, list) or len(feet) != 4 or any(len(point) != 2 for point in feet):
            raise ValueError('Countdown walker footprint absent')
        if any(point[1] < BOUNDARY_Y for point in feet) and first_entry is None:
            first_entry = index
    if first_entry is None or rows[first_entry]['countdown_seconds'] is None or \
            rows[first_entry]['countdown_seconds'] <= 0:
        raise ValueError('Entry-before-zero contrast absent')
    return {'first_entry_frame': first_entry,
            'countdown_at_entry_s': rows[first_entry]['countdown_seconds'],
            'native_display_constructed': False,
            'original_pixels_reviewed': False,
            'legal_verdict_claimed': False}


def main():
    import copy
    rows = requested()
    SOURCE.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    positive = measure(rows)
    negatives = 0
    for altered, expected in (
            ((220, 'countdown_seconds', None), 'Countdown display request changed'),
            ((220, 'other_device', 'steady_dont_walk'), 'Countdown display request changed'),
            ((220, 'walker_footprint_xy_m', None), 'Countdown walker footprint absent')):
        damaged = copy.deepcopy(rows)
        index, key, value = altered
        damaged[index][key] = value
        try:
            measure(damaged)
        except ValueError as exc:
            if expected not in str(exc):
                raise
            negatives += 1
        else:
            raise AssertionError('Missing countdown source rejection')
    receipt = {'format': 'c111331-countdown-source-cpu-proof-v1',
               'source_path': str(SOURCE.relative_to(HERE.parent)),
               'source_sha256': sha(SOURCE), 'positive': positive,
               'negative_checks': negatives,
               'native_display_constructed': False,
               'physical_permission_verified': False}
    target = HERE.parent / 'countdown-source-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'receipt_sha256': sha(target), 'negative_checks': negatives,
                      'first_entry_frame': positive['first_entry_frame']}))


if __name__ == '__main__':
    main()
