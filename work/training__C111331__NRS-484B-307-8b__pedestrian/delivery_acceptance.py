"""Independent exact-case source audit; synthetic fixtures never pass physical acceptance."""

import argparse
import hashlib
import json
from pathlib import Path

from finalize import measure
from source_join import audit_attempt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case_id, diagnostic=False, owner_receipt=None, processing_receipt=None):
    attempt = Path(attempt)
    config_path = attempt / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing delivery source: config.json')
    config = json.loads(config_path.read_text())
    if config['case_id'] != case_id:
        raise ValueError('Wrong exact delivery case')
    if not diagnostic:
        for name in ('capture-seal.json', 'native-capture-report.json'):
            if not (attempt / name).is_file():
                raise ValueError('Missing delivery source: ' + name)
        for path, label in ((owner_receipt, 'owner release'), (processing_receipt, 'saved processing')):
            if not path or not Path(path).is_file():
                raise ValueError('Missing ' + label + ' receipt')
        original = audit_attempt(attempt, config)
        if not original['join'].get('original_source_join_passed'):
            raise ValueError('Original source audit incomplete')
    report = measure(attempt)
    joined = report['join']
    if not joined['original_source_join_passed'] or not joined['trace_evidence_join_passed']:
        raise ValueError('Delivery source join incomplete')
    evidence = {'config.json': sha(config_path), **report['source_hashes']}
    result = {'format': 'c111331-independent-delivery-audit-v1',
              'case_id': case_id, 'checks': ['native_source', 'all_participants',
                  'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
              'source_hashes': evidence, 'frames': joined['frames'],
              'diagnostic_fixture': diagnostic, 'original_native_observed': not diagnostic,
              'display_pixels_reviewed': False, 'governing_device_verified': False,
              'physical_acceptance': False, 'legal_verdict': None}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--owner-receipt')
    parser.add_argument('--processing-receipt')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic, args.owner_receipt, args.processing_receipt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_fixture': args.diagnostic,
                      'source_join_passed': True}))
