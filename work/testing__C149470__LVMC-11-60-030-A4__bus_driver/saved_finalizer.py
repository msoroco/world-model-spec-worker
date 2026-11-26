"""Recorded-only C149470 saved measurement; rejects synthetic sources."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit_attempt


def finalize(attempt: Path, site: Path, case: str) -> dict:
    result = audit_attempt(site, attempt, case)
    if result['source_kind'] != 'original_native_capture':
        raise ValueError('saved analysis requires recorded original capture')
    return {'format': 'c149470-recorded-saved-finalizer-v1',
            'case_id': result['case_id'],
            'source_kind': result['source_kind'],
            'reviewed_site_sha256': result['reviewed_site_sha256'],
            'frames_sha256': result['frames_sha256'],
            'camera_hashes': result['camera_hashes'],
            'camera_frame_map_sha256': result['camera_frame_map_sha256'],
            'camera_archive_hashes': result['camera_archive_hashes'],
            'measurement': result['measurement'],
            'legal_status': 'unresolved',
            'physical_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior saved output; choose a fresh path')
    args.output.write_text(json.dumps(finalize(args.attempt, args.site, args.case),
                                      indent=2) + '\n', encoding='utf-8')
