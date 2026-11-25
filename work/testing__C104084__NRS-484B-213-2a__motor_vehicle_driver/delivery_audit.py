"""Independent saved crest delivery integrity join; no physical acceptance claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_media import audit as audit_media
from derived_audit import audit as audit_derived
from saved_crest import CASE_SUFFIXES, ONE_WAY_AUTHORITY, REQUIRED_SOURCES, measure, source_inventory


def audit(attempt_dir, receipt_path, *, assignment_id, case_id,
          expected_frames=900, expected_dimensions=None):
    if case_id not in {f'{assignment_id}__{suffix}' for suffix in CASE_SUFFIXES}:
        raise ValueError('wrong exact crest case')
    attempt = Path(attempt_dir).resolve()
    receipt_file = Path(receipt_path)
    if receipt_file.is_symlink() or not receipt_file.is_file():
        raise ValueError('saved delivery receipt missing or linked')
    receipt_bytes = receipt_file.read_bytes()
    receipt = json.loads(receipt_bytes)
    manifest = attempt / 'source-hashes.json'
    if not manifest.exists():
        provenance = attempt / 'acquisition-provenance.json'
        if (provenance.is_file() and
                json.loads(provenance.read_text()).get('diagnostic_fixture') is True):
            manifest = attempt / 'original-hashes.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('sealed original source manifest missing')
    manifest_bytes = manifest.read_bytes()
    hashes = json.loads(manifest_bytes)
    source_inventory(hashes, case_id, expected_frames)
    observation = measure(attempt, hashes, assignment_id=assignment_id,
                          case_id=case_id, expected_frames=expected_frames)
    media = audit_media(attempt, hashes, expected_frames=expected_frames,
                        expected_dimensions=expected_dimensions)
    derived = audit_derived(attempt, assignment_id=assignment_id,
                            case_id=case_id, expected_frames=expected_frames)
    expected = {
        'format': 'c104084-crest-saved-delivery-v1',
        'assignment_id': assignment_id,
        'case_id': case_id,
        'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'observation': observation,
        'media': media,
        'physical_visibility_reviewed': False,
        'public_highway_authority_verified': False,
        'hazard_distance_judgment': 'unresolved',
        'legal_judgment': 'unresolved',
    }
    if receipt != expected:
        raise ValueError('saved delivery receipt differs from sealed originals')
    if (derived['source_manifest_sha256'] != expected['source_manifest_sha256'] or
            derived['verified_frames'] != expected_frames):
        raise ValueError('derived and saved original frame joins differ')
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != expected['source_manifest_sha256']:
        raise ValueError('sealed source manifest changed during delivery audit')
    return {
        'format': 'c104084-crest-independent-delivery-audit-v1',
        'case_id': case_id,
        'source_manifest_sha256': expected['source_manifest_sha256'],
        'saved_receipt_sha256': hashlib.sha256(receipt_bytes).hexdigest(),
        'derived_sha256': derived['derived_sha256'],
        'decoded_media_sha256': {name: row['sha256'] for name, row in media['cameras'].items()},
        'verified_frames': expected_frames,
        'source_join_passed': True,
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Audit one saved original crest delivery without legal or physical acceptance')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--assignment', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.expected_frames != 900:
        provenance = Path(args.attempt) / 'acquisition-provenance.json'
        if not provenance.is_file() or json.loads(provenance.read_text()).get('diagnostic_fixture') is not True:
            raise ValueError('short delivery audit requires explicit diagnostic provenance')
    result = audit(args.attempt, args.receipt, assignment_id=args.assignment,
                   case_id=args.case, expected_frames=args.expected_frames)
    output = Path(args.output)
    if output.exists():
        raise ValueError('retain prior independent delivery audit')
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'source_join_passed': result['source_join_passed'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
