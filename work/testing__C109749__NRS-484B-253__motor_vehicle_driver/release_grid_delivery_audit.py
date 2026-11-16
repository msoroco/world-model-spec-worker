"""Exact release-grid entry point for the existing independent C109749 audits.

The original far and yielding audit implementations remain unchanged so their
selected-case source hashes stay valid. This CLI runs one exact case per process.
"""
import argparse
import json

import far_delivery_audit as far
import approaching_delivery_audit as approaching

PREFIX = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__'
FAR_CASE = PREFIX + 'approaching_release_3s'
YIELD_CASE = PREFIX + 'approaching_release_5s'


def audit_attempt(attempt, case_id, job_id, attempt_number, recording_id,
                  pixel_review, output, decode_receipt, *, diagnostic_selftest=False):
    if case_id == FAR_CASE:
        original = far.CASE
        try:
            far.CASE = FAR_CASE
            return far.audit_attempt(attempt, case_id, job_id, attempt_number,
                                     recording_id, pixel_review, output,
                                     decode_receipt,
                                     diagnostic_selftest=diagnostic_selftest)
        finally:
            far.CASE = original
    if case_id == YIELD_CASE:
        try:
            approaching.APPROACHING_BRANCHES[YIELD_CASE] = 'yield'
            return approaching.audit_attempt(attempt, case_id, job_id,
                                             attempt_number, recording_id,
                                             pixel_review, output, decode_receipt,
                                             diagnostic_selftest=diagnostic_selftest)
        finally:
            approaching.APPROACHING_BRANCHES.pop(YIELD_CASE, None)
    raise ValueError('Exact 3 s or 5 s release-grid case required')


def main():
    parser = argparse.ArgumentParser()
    for name in ('case', 'attempt', 'job-id', 'recording-id', 'pixel-review',
                 'output', 'decode-receipt'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--attempt-number', type=int, required=True)
    parser.add_argument('--diagnostic-selftest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit_attempt(
        args.attempt, args.case, args.job_id, args.attempt_number,
        args.recording_id, args.pixel_review, args.output,
        args.decode_receipt, diagnostic_selftest=args.diagnostic_selftest),
        sort_keys=True))


if __name__ == '__main__':
    main()
