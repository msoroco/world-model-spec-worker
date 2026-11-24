"""Saved-only source and physical-completion protocol for exact pedestrian cases.

This CPU protocol does not establish visibility, legal permission, or acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_capture import ASSIGNMENT
from native_crossing import source
from pedestrian_control import ENTER_CASES, WAIT_CASES
from saved_measurement import build_sealed
from saved_media_audit import audit as audit_media
from device_timeline import observe_timeline


def audit(attempt_root, site_ref, case_suffix):
    if case_suffix not in ENTER_CASES | WAIT_CASES:
        raise ValueError('unknown exact case')
    root = Path(attempt_root).resolve()
    receipt_path = root / 'capture-receipt.json'
    receipt_ref = {'path': receipt_path.name,
                   'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
    receipt = json.loads(source(receipt_ref, root).read_text())
    case_id = ASSIGNMENT + '__' + case_suffix
    if receipt.get('case_id') != case_id:
        raise ValueError('original capture case mismatch')
    event_ref = receipt['original_frames']
    measured = build_sealed(site_ref, event_ref, receipt_ref, root)
    media = audit_media(root)
    if media['case_id'] != case_id or media['frame_count'] != measured['facts']['frame_count']:
        raise ValueError('saved measurement and camera source join mismatch')
    facts = measured['facts']['measurements']
    timeline = observe_timeline(measured['facts'])
    entry = measured['facts']['first_highway_entry']
    if case_suffix in WAIT_CASES:
        if entry is not None:
            raise ValueError('waiting pedestrian entered highway')
    else:
        if entry is None:
            raise ValueError('pedestrian did not enter highway')
        entry_index = next(i for i, row in enumerate(facts) if row['in_highway'])
        if not any(not row['in_highway'] for row in facts[entry_index + 1:]):
            raise ValueError('pedestrian highway clearance missing')
        if case_suffix == 'outside_cross':
            if entry['in_crosswalk']:
                raise ValueError('outside-cross case entered crosswalk')
        elif not entry['in_crosswalk']:
            raise ValueError('crosswalk entry not observed')
    if case_suffix == 'walk_cross' and timeline['entry_device_mode'] != 'walk':
        raise ValueError('WALK entry mode not observed')
    if case_suffix == 'flashing_countdown_cross':
        if (timeline['entry_device_mode'] != 'flashing_countdown' or
                timeline['cleared_before_countdown_zero_observed'] is not True):
            raise ValueError('countdown entry and clearance before zero not observed')
    if case_suffix == 'flashing_no_countdown_wait':
        if not any(row['other_device_mode'] == 'flashing_no_countdown' for row in facts):
            raise ValueError('flashing without countdown not observed')
    if case_suffix in ('walk_then_flash_continue', 'walk_then_steady_continue'):
        if timeline['entry_device_mode'] != 'walk' or timeline['first_steady_frame'] is None:
            raise ValueError('WALK entry and later steady transition not observed')
        if case_suffix == 'walk_then_flash_continue' and (
                not any(row['other_device_mode'] == 'flashing_no_countdown' for row in facts) or
                timeline['cleared_before_steady_observed'] is not True):
            raise ValueError('flashing continuation and clearance before steady not observed')
    return {'format': 'worker-pedestrian-delivery-protocol',
            'assignment_id': ASSIGNMENT, 'case_id': case_id,
            'capture_receipt_sha256': receipt_ref['sha256'],
            'site_source_sha256': measured['site_source_sha256'],
            'frame_count': media['frame_count'],
            'decoded_images': media['decoded_images'],
            'first_highway_entry_frame': entry['frame'] if entry else None,
            'device_timeline': timeline,
            'source_join_passed': True, 'physical_completion_protocol_passed': True,
            'physical_acceptance': False, 'legal_verdict': None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', required=True)
    parser.add_argument('--site-ref', required=True)
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    site_ref = json.loads(Path(args.site_ref).read_text())
    result = audit(args.attempt_root, site_ref, args.case_suffix)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
