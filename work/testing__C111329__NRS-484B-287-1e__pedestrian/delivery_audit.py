"""Independent saved-attempt gate for original diagonal pedestrian evidence.

Diagnostic mode exercises lifecycle joins only. A physical review must be made
against original video; this CPU module does not manufacture that review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from camera_media import CAMERAS, verify_media_receipt
from saved_crossing import CASE_STATES, process_saved


def _read_sealed(attempt, ref, name):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
        raise ValueError(name + ' source reference missing')
    original = attempt / ref['path']
    path = original.resolve()
    if not path.is_relative_to(attempt) or original.is_symlink() or not path.is_file():
        raise ValueError(name + ' source escapes attempt')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ref.get('sha256'):
        raise ValueError(name + ' source hash mismatch')
    return json.loads(data)


def audit_delivery(attempt_dir, case_id, *, physical_review_ref=None,
                   allow_diagnostic=False):
    attempt = Path(attempt_dir).resolve()
    if case_id not in CASE_STATES or not attempt.is_dir():
        raise ValueError('exact diagonal case and saved attempt required')
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    if acquisition.get('case_id') != case_id:
        raise ValueError('saved acquisition case mismatch')
    if acquisition.get('diagnostic') and not allow_diagnostic:
        raise ValueError('diagnostic attempt cannot pass delivery audit')
    measurement = process_saved(attempt, case_id, attempt / 'delivery-measurement.json',
                                allow_diagnostic=allow_diagnostic)
    if measurement['original_frames'] != 900:
        raise ValueError('complete 900 original frames required')
    if not measurement['full_video_decode']:
        raise ValueError('four original camera full decodes required')
    decoded = verify_media_receipt(
        attempt, acquisition.get('camera_media', {}),
        acquisition.get('camera_media_audit'), 900,
        diagnostic=bool(acquisition.get('diagnostic')))
    if acquisition.get('diagnostic'):
        return {'format': 'worker-delivery-audit', 'case_id': case_id,
                'diagnostic': True, 'software_checks_passed': True,
                'physical_completion': False, 'actual_pixels': False,
                'legal_conclusion': 'not_assessed'}
    review = _read_sealed(attempt, physical_review_ref, 'physical review')
    if (review.get('case_id') != case_id or review.get('source') != 'independent_original_video_review' or
            review.get('device_id') != measurement['measurement']['device_id'] or
            review.get('video_sha256') != {name: decoded['cameras'][name]['video_sha256']
                                           for name in CAMERAS} or
            review.get('crossing_frames') != measurement['measurement']['crossing_frames']):
        raise ValueError('physical review not bound to original crossing and cameras')
    if (not review.get('walker_route_completed') or
            not review.get('official_diagonal_device_visible') or
            not review.get('walker_visible_in_original_views') or
            review.get('reviewed_frame_ids') != [0, 450, 899]):
        raise ValueError('original physical visibility/completion review missing')
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'diagnostic': False, 'software_checks_passed': True,
            'physical_completion': True, 'actual_pixels': True,
            'legal_conclusion': 'not_assessed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--physical-review-ref', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    ref = json.loads(Path(args.physical_review_ref).read_text())
    result = audit_delivery(args.attempt, args.case, physical_review_ref=ref)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    main()
