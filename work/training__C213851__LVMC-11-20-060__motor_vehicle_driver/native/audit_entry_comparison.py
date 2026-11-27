"""Independent source-bound comparison of the two roadway-return attempts."""

import hashlib
import json
from pathlib import Path

from measure_entry_return import measure_core_join
from measure_sidewalk import rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(yield_attempt, enter_attempt, assignment_id):
    attempts = [Path(yield_attempt), Path(enter_attempt)]
    policies = ['yield_to_approaching', 'enter_without_yield']
    case_ids = [assignment_id + '__' + policy for policy in policies]
    measured = [measure_core_join(path, case_id)
                for path, case_id in zip(attempts, case_ids)]
    sources = [rows(path / 'native-rows.jsonl') for path in attempts]
    site_files = ('road.xodr', 'original-site-review.json', 'site-review.json',
                  'original-entry-site-review.json')
    if any(sha(attempts[0] / name) != sha(attempts[1] / name)
           for name in site_files):
        raise ValueError('Roadway-return site context changed')
    fixed = ('pedestrian_world_xy_m', 'approaching_world_xy_m',
             'pedestrian_actor_id', 'approaching_actor_id', 'time_s')
    if any(a[key] != b[key] for a, b in zip(*sources) for key in fixed):
        raise ValueError('Roadway-return pedestrian or traffic context changed')
    if any(a['vehicle_world_xy_m'] != b['vehicle_world_xy_m']
           for a, b in zip(sources[0][:400], sources[1][:400])):
        raise ValueError('Road-exit phase changed')
    a, b = measured
    if (a['observed_pre_entry_stopped_frames'] <=
            b['observed_pre_entry_stopped_frames'] or
            a['first_entry_road_frame'] <= b['first_entry_road_frame']):
        raise ValueError('Requested entry dwell did not change observed timing')
    return {'format': 'c213851-roadway-return-comparison',
            'case_ids': case_ids, 'passed': True,
            'fixed_sources_sha256': {name: sha(attempts[0] / name)
                                     for name in site_files},
            'measurements': measured,
            'compared_variable': 'observed_pre_entry_stopped_frames',
            'source_scope': 'source-shaped CPU diagnostic',
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--yield-attempt', required=True)
    parser.add_argument('--enter-attempt', required=True)
    parser.add_argument('--assignment-id', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.yield_attempt, args.enter_attempt, args.assignment_id)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_ids': result['case_ids']}))
