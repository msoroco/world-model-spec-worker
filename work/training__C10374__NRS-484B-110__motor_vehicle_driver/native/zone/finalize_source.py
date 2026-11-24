"""Finalize retained safety-zone measurements without a legal designation claim.

This is a source-only CPU component. The public process-saved path and physical
designation audit remain separate prerequisites for selected delivery.
"""
import argparse
import hashlib
import json
from pathlib import Path

from saved import SAVED, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(bundle, saved, raw=None):
    bundle, saved = Path(bundle), Path(saved)
    measurement = measure(bundle, saved)
    receipt = json.loads((saved / 'preparation-receipt.json').read_text())
    if receipt['source_kind'] != measurement['source_kind']:
        raise ValueError('saved source kind changed')
    if receipt['original_native_observed'] or measurement['original_native_observed']:
        raise ValueError('original Native claim requires independent capture audit')
    if measurement['authored_rectangle_is_designated_zone'] or measurement['legal_verdict'] is not None:
        raise ValueError('authored rectangle cannot establish official safety zone')
    if set(receipt['saved_hashes']) != set(SAVED):
        raise ValueError('saved source inventory changed')
    if len(receipt.get('raw_hashes', {})) != 5:
        raise ValueError('retained raw source inventory incomplete')
    if raw is not None:
        raw = Path(raw)
        for name, expected in receipt['raw_hashes'].items():
            if not (raw / name).is_file() or sha(raw / name) != expected:
                raise ValueError('retained raw source changed: ' + name)
        for name, expected in receipt.get('media_hashes', {}).items():
            if not (raw / name).is_file() or sha(raw / name) != expected:
                raise ValueError('retained camera source changed: ' + name)
    return {
        'format': 'c10374-zone-source-finalization-v1',
        'case_id': measurement['case_id'],
        'candidate_id': measurement['candidate_id'],
        'measurement': measurement,
        'source_bindings': {
            'preparation_receipt_sha256': sha(saved / 'preparation-receipt.json'),
            'saved_hashes': {name: sha(saved / name) for name in SAVED},
            'raw_hashes': receipt['raw_hashes'],
            'raw_source_reverified': raw is not None,
            'config_sha256': sha(bundle / 'config.json'),
        },
        'target_check': {
            'metric': 'moving_body_rectangle_overlap_frames',
            'measured': measurement['moving_body_rectangle_overlap_frames'],
            'requested_route_intersects_authored_rectangle': measurement['requested_zone_route'],
            'physical_zone_designation_confirmed': False,
            'legal_outcome_claimed': False,
        },
        'source_kind': measurement['source_kind'],
        'public_process_saved_passed': False,
        'physical_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--saved', required=True)
    parser.add_argument('--raw')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = finalize(args.bundle, args.saved, args.raw)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'],
                      'overlap_frames': result['target_check']['measured'],
                      'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
