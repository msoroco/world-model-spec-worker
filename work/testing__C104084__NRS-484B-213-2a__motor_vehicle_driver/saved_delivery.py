"""Saved-only crest delivery join for exact original Native attempts.

This is a CPU integrity and observation receipt, not a visibility or legal call.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_media import audit as audit_media
from saved_crest import CASE_SUFFIXES, ONE_WAY_AUTHORITY, REQUIRED_SOURCES, measure


def process(attempt_dir, output_path, *, assignment_id, case_id,
            expected_frames=900, expected_dimensions=None):
    if case_id not in {f'{assignment_id}__{suffix}' for suffix in CASE_SUFFIXES}:
        raise ValueError('wrong exact crest case')
    attempt = Path(attempt_dir).resolve()
    output = Path(output_path)
    if output.exists():
        raise ValueError('retain prior saved delivery receipt')
    manifest = attempt / 'source-hashes.json'
    if manifest.is_symlink() or not manifest.is_file() or manifest.resolve().parent != attempt:
        raise ValueError('original source manifest missing or escapes attempt')
    manifest_bytes = manifest.read_bytes()
    hashes = json.loads(manifest_bytes)
    required = set(REQUIRED_SOURCES)
    if case_id.endswith('left_one_way_obstructed'):
        required.add(ONE_WAY_AUTHORITY)
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ValueError('original source manifest has wrong exact sources')
    observation = measure(attempt, hashes, case_id=case_id,
                          assignment_id=assignment_id,
                          expected_frames=expected_frames)
    media = audit_media(attempt, hashes, expected_frames=expected_frames,
                        expected_dimensions=expected_dimensions)
    if (observation['frame_count'] != expected_frames or
            any(item['frames_decoded'] != expected_frames or
                item['sha256'] != hashes[item['source']]
                for item in media['cameras'].values())):
        raise ValueError('saved observation and decoded media differ')
    result = {
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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
                      encoding='utf-8')
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--assignment', required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    result = process(args.attempt, args.output, assignment_id=args.assignment,
                     case_id=args.case)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
