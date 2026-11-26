"""Audit the fixed taxi stop and one declared loading-subject difference."""
import argparse
import hashlib
import json
from pathlib import Path

PREFIX = 'training__C394327__LVMC-11-60-040__taxi_driver'
COMPARISON = PREFIX + '__comparison'


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(comparison, passenger, merchandise):
    require(comparison == COMPARISON, 'Wrong exact taxi comparison')
    roots = [Path(passenger).resolve(), Path(merchandise).resolve()]
    configs = [read(root / 'config.json') for root in roots]
    expected_cases = [PREFIX + '__probe_a', PREFIX + '__probe_b']
    require([c.get('selected_case_id') for c in configs] == expected_cases,
            'Comparison case identity differs')
    fixed = ('law_id', 'cell_id', 'actor', 'duration_s', 'rate_hz', 'frames',
             'taxi_stop_x_m', 'road_sha256', 'cameras', 'required_atoms',
             'source_packets', 'requested_activity_window_frames')
    require(all(configs[0].get(k) == configs[1].get(k) for k in fixed),
            'Fixed taxi construction condition differs')
    require(configs[0].get('law_id') == 'LVMC-11-60-040' and
            configs[0].get('cell_id') == 'C394327' and
            configs[0].get('actor') == 'taxi_driver' and
            configs[0].get('duration_s') == 30 and
            configs[0].get('rate_hz') == 20 and
            configs[0].get('frames') == 600,
            'Taxi comparison fixed identity or time differs')
    require([c.get('requested_activity') for c in configs] ==
            ['passenger_loading', 'merchandise_loading'],
            'Declared loading-subject difference missing')
    require(all(read(root / 'construction.json').get('case_id') == case
                for root, case in zip(roots, expected_cases)),
            'Comparison construction identity differs')
    original = []
    for root, case in zip(roots, expected_cases):
        native = root / 'observed-activity.jsonl'
        review = root / 'participant-activity-review.json'
        require(native.is_file() and review.is_file(),
                'Missing original taxi comparison source')
        lines = [json.loads(line) for line in native.read_text().splitlines() if line]
        require(len(lines) == 600 and all(row['video_frame'] == i
                    for i, row in enumerate(lines)),
                'Taxi comparison frame join differs')
        require(read(review).get('source_basis'),
                'Taxi comparison participant review lacks source basis')
        original.append({'case_id': case, 'activity_sha256': sha(native),
                         'review_sha256': sha(review)})
    require(original[0]['activity_sha256'] != original[1]['activity_sha256'],
            'Taxi comparison activity sources are identical')
    return {'format': 'worker-taxi-comparison-audit',
            'comparison_id': comparison, 'passed': True,
            'fixed_conditions': list(fixed),
            'declared_difference': 'loading_subject_and_occupant_transition',
            'cases': original, 'original_native_accepted': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--passenger', required=True)
    parser.add_argument('--merchandise', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.passenger,
                           args.merchandise), allow_nan=False))
