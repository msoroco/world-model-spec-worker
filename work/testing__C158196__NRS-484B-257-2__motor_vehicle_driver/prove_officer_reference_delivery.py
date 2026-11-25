"""Run exact independent officer/reference delivery diagnostics on retained CPU sources."""

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def run(case_id, mode, attempt):
    private = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    allowed = (REPO / '.runtime-work').resolve()
    if private != allowed and allowed not in private.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    if mode not in ('positive', 'negative'):
        raise ValueError('Choose positive or negative diagnostic')
    if not case_id.startswith('testing__C158196__NRS-484B-257-2__motor_vehicle_driver__'):
        raise ValueError('Wrong exact assignment case')
    sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
    sys.path.insert(0, str(ROOT))
    from officer_reference_delivery_audit import audit_delivery
    if mode == 'negative':
        missing = private / ('missing-' + case_id.rsplit('__', 1)[-1])
        missing.mkdir(parents=True, exist_ok=True)
        (missing / 'config.json').write_bytes((Path(attempt) / 'config.json').read_bytes())
        audit_delivery(missing, ROOT, case_id, diagnostic_fixture=True)
        raise AssertionError('Missing original capture unexpectedly accepted')
    result = audit_delivery(attempt, ROOT, case_id, diagnostic_fixture=True,
                            receipt_dir=private / ('audited-' + case_id.rsplit('__', 1)[-1]))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--mode', required=True, choices=('positive', 'negative'))
    parser.add_argument('--attempt', required=True, type=Path)
    args = parser.parse_args()
    run(args.case, args.mode, args.attempt)
