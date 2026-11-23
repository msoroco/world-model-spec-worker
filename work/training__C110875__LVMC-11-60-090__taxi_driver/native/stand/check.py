"""Check the exact copied taxi request and controlled first-turn difference."""
import argparse
import hashlib
import json
from pathlib import Path

from request import CASES, FRAMES, LAW, PLAN, PLAN_SHA, RATE, SOURCE, SOURCE_SHA, route


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    source = json.loads((bundle / 'assignment-source.json').read_text())
    plan = json.loads((bundle / 'case-plan.json').read_text())
    suffix = cfg['case_id'].split('__')[-1]
    if (suffix not in CASES or source['law']['text'] != LAW or
            plan['source_law_text'] != LAW or
            (bundle / 'assignment-source.json').read_bytes() != SOURCE.read_bytes() or
            (bundle / 'case-plan.json').read_bytes() != PLAN.read_bytes() or
            cfg['assignment_sha256'] != sha(SOURCE) or sha(SOURCE) != SOURCE_SHA or
            cfg['case_plan_sha256'] != sha(PLAN) or sha(PLAN) != PLAN_SHA or
            cfg['tracks_sha256'] != sha(bundle / 'requested-tracks.jsonl') or
            cfg['requested_first_turn'] != CASES[suffix] or
            cfg['rate_hz'] != RATE or cfg['frames'] != FRAMES or
            cfg['duration_s'] != 30 or
            any(cfg[key] is not False for key in
                ('stand_designation_verified', 'posted_notice_verified',
                 'taxi_license_verified', 'first_intersection_native_verified',
                 'original_native_observed')) or cfg['legal_verdict'] is not None or
            cfg['status'] != 'unselected_cpu_request'):
        raise ValueError('Taxi source, requested route or unverified status changed')
    actual = [json.loads(line) for line in
              (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
    if actual != route(CASES[suffix]) or len(actual) != FRAMES:
        raise ValueError('First-intersection route changed')
    if (actual[0]['cab_stand_departure_station_m'] != 5 or
            any(row['first_intersection_station_m'] != 80 or
                row['next_intersection_station_m'] != 130 for row in actual) or
            any(row['requested_x_m'] > 80 for row in actual)
                if CASES[suffix] == 'right' else
            not any(row['requested_x_m'] > 80 for row in actual)):
        raise ValueError('First versus later intersection distinction changed')
    return {'case_id': cfg['case_id'], 'requested_first_turn': CASES[suffix],
            'frames': FRAMES, 'duration_s': 30,
            'stand_designation_verified': False, 'posted_notice_verified': False,
            'original_native_observed': False, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, default=Path.cwd())
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.bundle)))
