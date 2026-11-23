"""Exact-case CPU diagnostic of the C125714 delivery audit boundary."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(REPO / '.runtime-work' / 'c125714-delivery-proof'))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from delivery_audit import audit_delivery  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((row for row in manifest['cases'] if row['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Unselected exact case')
    construction = HERE / entry['construction']
    if hashlib.sha256(construction.read_bytes()).hexdigest() != entry['construction_sha256']:
        raise ValueError('Selected construction source changed')
    if args.mode == 'positive':
        suite = unittest.defaultTestLoader.discover(str(HERE / 'tests'), pattern='test_precedence.py')
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            raise ValueError('C125714 source and audit CPU tests failed')
        print(json.dumps({'case_id': args.case, 'cpu_boundary_passed': True,
                          'native_source_accepted': False, 'physical_acceptance_claimed': False}))
    else:
        with tempfile.TemporaryDirectory(prefix='c125714-audit-negative-') as temp:
            audit_delivery(Path(temp), HERE)
        raise AssertionError('Missing original Native media incorrectly accepted')


if __name__ == '__main__':
    main()
