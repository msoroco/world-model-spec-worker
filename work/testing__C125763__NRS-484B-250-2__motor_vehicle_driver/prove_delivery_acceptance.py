"""Exact-case diagnostic proof of the independent acceptance audit boundary."""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_acceptance import CASE_IDS, CHECKS, verify_physical  # noqa: E402
from worker_exchange.common import sha  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    if args.case not in CASE_IDS or len(CHECKS) != 6:
        raise ValueError('Acceptance auditor case/check inventory differs')
    entries = json.loads((HERE / 'execution-manifest.json').read_text())['cases']
    entry = next(row for row in entries if row['case_id'] == args.case)
    construction = HERE / entry['construction']
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Exact construction source changed')
    files = json.loads(construction.read_text())['files']
    config = json.loads(next(row['content'] for row in files if row['path'] == 'config.json'))
    criterion = config['physical_completion']
    if (criterion['criterion'] != 'intersection_clearance' or
            criterion['body_key'] != 'ego.body_vertices_xy_m' or
            criterion['motion_source'] != 'crossing_history.jsonl'):
        raise ValueError('Exact physical criterion differs')
    if args.mode == 'positive':
        suite = unittest.defaultTestLoader.discover(str(HERE / 'tests'),
                                                     pattern='test_delivery_acceptance.py')
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            raise ValueError('Independent acceptance boundary tests failed')
    with tempfile.TemporaryDirectory(prefix='c125763-acceptance-') as temporary:
        attempt = Path(temporary)
        source = attempt / 'crossing_history.jsonl'
        source.write_text('{"diagnostic":true}\n')
        check = {'status': 'met', 'method': 'source-bound diagnostic check',
                 'sources': {'crossing_history.jsonl': sha(source)}}
        physical = {'physical_acceptance_claimed': False,
                    'setup_confirmed': True, 'behavior_attempted': True,
                    'maneuver_completed': True,
                    'physical_checks': {name: check for name in ('setup', 'target', 'maneuver')}}
        verify_physical(physical, attempt)
        if args.mode == 'negative':
            source.write_text('{"tampered":true}\n')
            verify_physical(physical, attempt)
            raise AssertionError('Tampered source incorrectly accepted')
    print(json.dumps({'case_id': args.case, 'mode': args.mode,
                      'auditor_checks': CHECKS, 'diagnostic_only': True,
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
