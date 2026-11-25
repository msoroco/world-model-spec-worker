"""Independent saved-source and physical-review checks for C111304 delivery.

The CPU self-test exercises rejection and joins. It does not accept a recording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CAMERAS = ('front', 'rear', 'left', 'right')


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt: Path, report: dict, review: dict, case_id: str) -> dict:
    """Bind independently reviewed pixels to a complete original Native attempt."""
    from saved_audit import audit_native_acquisition
    from media_audit import audit_media

    receipt_path = attempt / 'native-receipt.json'
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError('original Native receipt missing')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('case_id') != case_id or report.get('case_id') != case_id:
        raise ValueError('exact delivery case mismatch')
    if report.get('native_receipt_sha256') != _sha(receipt_path):
        raise ValueError('saved report Native source binding mismatch')
    source = audit_native_acquisition(attempt, receipt)
    if source['frame_count'] != 900 or receipt.get('original_fps') != 20:
        raise ValueError('original 900-frame, 20 Hz source required')
    inventory_path = attempt / 'camera-media-inventory.json'
    plan_path = attempt / 'camera-plan.json'
    if not inventory_path.is_file() or not plan_path.is_file():
        raise ValueError('saved camera source inventory missing')
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    camera_plan = json.loads(plan_path.read_text(encoding='utf-8'))
    decoded = audit_media(attempt, receipt, inventory, camera_plan)
    if decoded.get('source_kind') != 'original_encoded':
        raise ValueError('original encoded pixels required')
    if (review.get('case_id') != case_id or
            review.get('native_receipt_sha256') != _sha(receipt_path) or
            review.get('media_inventory_sha256') != _sha(inventory_path) or
            review.get('frame_map_sha256') != receipt.get('original_frame_map_sha256')):
        raise ValueError('physical review source binding mismatch')
    if review.get('review_kind') != 'independent_original_pixels' or review.get('reviewer') in (None, ''):
        raise ValueError('independent original-pixel review missing')
    visible = review.get('visible', {})
    if set(visible) != set(CAMERAS) or any(visible[camera] is not True for camera in CAMERAS):
        raise ValueError('actual four-camera participant visibility unconfirmed')
    if review.get('physical_completion') is not True:
        raise ValueError('physical completion unconfirmed')
    return {'format': 'c111304-independent-delivery-check', 'case_id': case_id,
            'native_receipt_sha256': _sha(receipt_path),
            'media_inventory_sha256': _sha(inventory_path),
            'frame_count': 900, 'original_fps': 20,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'legal_judgment': None}


def _self_test(case_id: str, tamper: bool) -> None:
    """Test the pure physical-review gate without presenting fixture as evidence."""
    def check_review(row: dict) -> None:
        if row['case_id'] != case_id:
            raise ValueError('exact delivery case mismatch')
        if row['frame_count'] != 900 or row['fps'] != 20:
            raise ValueError('original frame contract mismatch')
        if set(row['visible']) != set(CAMERAS) or not all(row['visible'].values()):
            raise ValueError('actual four-camera participant visibility unconfirmed')
        if not row['physical_completion']:
            raise ValueError('physical completion unconfirmed')

    row = {'case_id': case_id, 'frame_count': 900, 'fps': 20,
           'visible': dict.fromkeys(CAMERAS, True), 'physical_completion': True}
    if tamper:
        row['visible']['right'] = False
    check_review(row)
    print('CPU physical-review checker passed for ' + case_id + '; no recording accepted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--tamper', action='store_true')
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    if args.self_test:
        _self_test(args.case, args.tamper)
    else:
        if not all((args.attempt, args.report, args.review)):
            parser.error('attempt, report and review required')
        result = audit(args.attempt, json.loads(args.report.read_text()),
                       json.loads(args.review.read_text()), args.case)
        print(json.dumps(result, sort_keys=True))
