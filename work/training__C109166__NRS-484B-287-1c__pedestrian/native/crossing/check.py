"""Exact authored crossing request checker; no Native result is inferred."""
import argparse
import json
from pathlib import Path

from request import CASES, FRAMES, LAW, PLAN, PLAN_SHA, RATE, SOURCE, SOURCE_SHA, rows, sha


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    source = json.loads((bundle / 'assignment-source.json').read_text())
    plan = json.loads((bundle / 'case-plan.json').read_text())
    crossing = cfg['requested_crossing_location']
    if (crossing not in CASES or
            cfg['case_id'] != cfg['assignment_id'] + '__' + crossing or
            source['law']['text'] != LAW or plan['source_law_text'] != LAW or
            sha(SOURCE) != SOURCE_SHA or sha(PLAN) != PLAN_SHA or
            (bundle / 'assignment-source.json').read_bytes() != SOURCE.read_bytes() or
            (bundle / 'case-plan.json').read_bytes() != PLAN.read_bytes() or
            cfg['assignment_sha256'] != SOURCE_SHA or cfg['case_plan_sha256'] != PLAN_SHA or
            cfg['tracks_sha256'] != sha(bundle / 'requested-tracks.jsonl') or
            cfg['frames'] != FRAMES or cfg['rate_hz'] != RATE or cfg['duration_s'] != 30 or
            cfg['status'] != 'unselected_cpu_request' or cfg['legal_verdict'] is not None or
            any(cfg[k] is not False for k in
                ('adjacent_intersections_native_verified',
                 'official_devices_operating_verified',
                 'crosswalk_marking_native_verified', 'pedestrian_native_observed'))):
        raise ValueError('Crossing request source or unverified status changed')
    actual = [json.loads(line) for line in
              (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
    if actual != list(rows(crossing)):
        raise ValueError('Requested crossing track changed')
    entry = next(row for row in actual if row['requested_y_m'] >= -4)
    if (len(actual) != FRAMES or not 0 < entry['requested_x_m'] < 100 or
            entry['time_s'] <= 0 or actual[-1]['time_s'] != 30):
        raise ValueError('Crossing timing or geometry changed')
    return {'case_id': cfg['case_id'], 'frames': FRAMES, 'duration_s': 30,
            'requested_crossing_location': crossing,
            'roadway_entry_request_time_s': entry['time_s'],
            'pedestrian_native_observed': False, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=Path.cwd())
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.bundle)))
