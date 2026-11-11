"""Case-specific CPU proof for the independent delivery audit contract.

The positive path tests source and decode mechanics on synthetic samples. The
negative path must fail when those samples are offered as original Native rows.
Neither path emits an accepted recording receipt.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--reject-synthetic', action='store_true')
    args = parser.parse_args()
    if args.case not in (ASSIGNMENT+'__reference', ASSIGNMENT+'__contrast'):
        raise ValueError('Unknown exact delivery case')
    audit = load('c132497_contract_audit', ROOT/'native/delivery_audit.py')
    tests = load('c132497_contract_tests', ROOT/'tests/test_delivery_audit.py')
    lane = -2 if args.case.endswith('__reference') else -1
    raw, frames, trace = tests.sample(lane)
    if args.reject_synthetic:
        audit.validate_rows(raw, frames, trace, args.case, 'primary')
        raise AssertionError('Production accepted synthetic rows as original Native')
    suite = unittest.TestSuite()
    for name in ('test_delivery_audit.py', 'test_original_motion_assessment.py',
                 'test_original_pair.py'):
        module = load('c132497_'+name.replace('.', '_'), ROOT/'tests'/name)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    run = unittest.TextTestRunner(verbosity=1).run(suite)
    if not run.wasSuccessful():
        raise ValueError('Independent audit CPU mechanics failed')
    observed = audit.validate_rows(raw, frames, trace, args.case, 'primary',
                                   'synthetic_native_sample')
    assert observed['frames'] == 240 and observed['exit_lane_id'] == lane
    print(json.dumps({'case_id': args.case, 'candidate_id': 'primary',
        'cpu_audit_mechanics_passed': True, 'unit_tests_run': run.testsRun,
        'synthetic_sample_only': True, 'original_native_observed': False,
        'accepted_recording': False, 'checks_exercised': list(audit.CHECKS)}))


if __name__ == '__main__':
    main()
