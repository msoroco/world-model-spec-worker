"""Exact-case diagnostic delivery protocol, without real-source acceptance."""
import argparse
import json
import tempfile
from pathlib import Path

from delivery_audit import audit_delivery
from saved_crossing import CASE_STATES


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--case', required=True, choices=CASE_STATES)
    p.add_argument('--negative', action='store_true')
    args = p.parse_args()
    if args.negative:
        scratch = Path(__file__).resolve().parents[2] / '.runtime-work/c111329-delivery-probe'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            root = Path(temp)
            (root / 'acquisition.json').write_text(json.dumps({'case_id': args.case,
                                                               'diagnostic': True}) + '\n')
            audit_delivery(root, args.case)
        raise AssertionError('diagnostic attempt accepted for production')
    receipt = json.loads((Path(__file__).resolve().parent /
                          'diagnostic-lifecycle-receipts.json').read_text())
    suffix = args.case.rsplit('__', 1)[-1]
    case = receipt['cases'][suffix]
    assert case['case_id'] == args.case
    assert case['delivery_software_checks_passed'] is True
    assert case['four_original_views_full_decoded'] is True
    assert case['physical_completion'] is False
    assert receipt['official_diagonal_device_verified'] is False
    print('exact diagnostic delivery checks passed:', args.case)
    print('physical_completion=false; official_diagonal_device_verified=false')


if __name__ == '__main__':
    main()
