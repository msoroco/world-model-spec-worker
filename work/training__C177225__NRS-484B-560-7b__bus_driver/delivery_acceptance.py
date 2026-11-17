"""Exact-case independent delivery audit orchestration.

Diagnostic success exercises code and source joins, never accepts a recording.
Native acceptance also requires sealed motion completion, visual review, and
source-bound closure/owner-release/saved-processing receipts.
"""
import argparse
import json
from pathlib import Path

from audit_delivery import audit
from lifecycle_preparation import inspect
from physical_outcome import assess


def check(attempt, case_id, *, diagnostic, owner_receipt=None, processing_receipt=None):
    attempt = Path(attempt)
    if not diagnostic and (owner_receipt is None or processing_receipt is None):
        raise ValueError('Original delivery requires owner release and saved processing receipts')
    visual = audit(attempt, case_id, diagnostic=diagnostic)
    physical = assess(attempt, case_id)
    status = physical['physical_checks']['maneuver']['status']
    if diagnostic:
        if visual['delivery_accepted'] or physical['provenance_kind'] != 'synthetic_fixture':
            raise ValueError('Diagnostic source cannot receive Native acceptance')
        return {
            'format': 'c177225-delivery-acceptance-diagnostic-v1',
            'case_id': case_id, 'diagnostic_passed': True, 'delivery_accepted': False,
            'physical_status': status, 'lifecycle_verified': False,
            'checks_exercised': visual['checks_verified'],
            'checks_pending': ['original_native_source', 'actual_physical_completion',
                               'operator_owner_release', 'saved_processing_order']
        }
    if status != 'met' or physical['provenance_kind'] != 'native':
        raise ValueError('Original Native physical completion not established')
    lifecycle = inspect(attempt, owner_receipt, processing_receipt)
    if not visual['delivery_accepted']:
        raise ValueError('Independent visual audit did not accept original delivery')
    return {
        'format': 'c177225-delivery-acceptance-v1', 'case_id': case_id,
        'diagnostic_passed': False, 'delivery_accepted': True,
        'physical_status': status, 'lifecycle_verified': True,
        'checks_verified': visual['checks_verified'],
        'source_sha256': visual['source_sha256'],
        'lifecycle_events': lifecycle['events'],
        'legal_verdict_claimed': False
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--owner-receipt', type=Path)
    parser.add_argument('--processing-receipt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(args.attempt, args.case, diagnostic=args.diagnostic,
                   owner_receipt=args.owner_receipt, processing_receipt=args.processing_receipt)
    if args.output.exists():
        raise ValueError('Retain prior delivery audit result')
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'case_id': args.case, 'delivery_accepted': result['delivery_accepted'],
                      'physical_status': result['physical_status']}))


if __name__ == '__main__':
    main()
