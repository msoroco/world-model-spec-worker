"""Check modeled CPU lifecycle ordering; no original Native release is claimed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--capture-tests', type=Path, required=True)
    parser.add_argument('--saved-receipt', type=Path, required=True)
    args = parser.parse_args()
    log = args.capture_tests.read_text()
    saved = json.loads(args.saved_receipt.read_text())
    if ('test_source_sealed_capture_restores_world' not in log or
            not log.rstrip().endswith('OK') or
            saved.get('case_id') != args.case or
            saved.get('source_kind') != 'synthetic_diagnostic_fixture' or
            saved.get('recorded_only') is not True or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('passed') is not True or
            saved.get('physical_acceptance_claimed') is not False):
        raise ValueError('synthetic cleanup or recorded-only proof missing')
    print(json.dumps({'case_id': args.case, 'modeled_events': EVENTS,
                      'source_kind': 'synthetic_cpu_lifecycle_model',
                      'capture_test_log_sha256': sha(args.capture_tests),
                      'saved_receipt_sha256': sha(args.saved_receipt),
                      'original_native_release_observed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
