"""Independent saved-source audit for original C111329 Native crossing attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_process import CASES, ASSIGNMENT, _read
from saved_measurement import measure_acquisition
from saved_media_audit import audit_camera_sources


def audit(attempt: Path, case_id: str, site_ref: dict, native_ref: dict,
          camera_ref: dict, saved_ref: dict, *, expected_frames: int = 900,
          allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    if not case_id.startswith(ASSIGNMENT + '__') or case_id.removeprefix(ASSIGNMENT + '__') not in CASES:
        raise ValueError('unknown exact C111329 case')
    route, authority = CASES[case_id.removeprefix(ASSIGNMENT + '__')]
    site, native, camera, saved = (_read(attempt, ref) for ref in
                                   (site_ref, native_ref, camera_ref, saved_ref))
    if saved.get('format') != 'c111329-saved-process-v1' or saved.get('case_id') != case_id:
        raise ValueError('saved crossing receipt identity mismatch')
    if (saved.get('site_source_sha256') != site_ref['sha256'] or
            saved.get('native_source_sha256') != native_ref['sha256'] or
            saved.get('camera_manifest_source_sha256') != camera_ref['sha256']):
        raise ValueError('saved crossing receipt source binding mismatch')
    measurement = measure_acquisition(site, native, case_id=case_id,
                                      route_kind=route, authorization=authority,
                                      expected_frames=expected_frames,
                                      allow_diagnostic=allow_diagnostic)
    media = audit_camera_sources(native, camera, attempt,
                                 allow_diagnostic=allow_diagnostic)
    if saved.get('measurement') != json.loads(json.dumps(measurement)) or saved.get('media_audit') != json.loads(json.dumps(media)):
        raise ValueError('saved crossing measurement or full-pixel audit changed')
    if media['decoded_png_count'] != 4 * expected_frames or media['frame_count'] != expected_frames:
        raise ValueError('full original four-camera decode incomplete')
    if saved.get('legal_verdict') is not None or saved.get('exception_484B_290') != 'unresolved':
        raise ValueError('unsupported legal or exception finding')
    return {'format': 'c111329-independent-delivery-audit-v1', 'case_id': case_id,
            'site_sha256': site_ref['sha256'], 'native_sha256': native_ref['sha256'],
            'camera_manifest_sha256': camera_ref['sha256'],
            'saved_receipt_sha256': saved_ref['sha256'],
            'frame_count': expected_frames, 'decoded_png_count': media['decoded_png_count'],
            'decoded_pixel_sha256': media['decoded_pixel_sha256'],
            'diagnostic': native.get('diagnostic'),
            'physical_visibility': 'requires_independent_review',
            'exception_484B_290': 'unresolved', 'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--site-ref', type=Path, required=True)
    parser.add_argument('--native-ref', type=Path, required=True)
    parser.add_argument('--camera-ref', type=Path, required=True)
    parser.add_argument('--saved-ref', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('independent delivery audit already exists')
    refs = [json.loads(p.read_text(encoding='utf-8')) for p in
            (args.site_ref, args.native_ref, args.camera_ref, args.saved_ref)]
    result = audit(args.attempt, args.case, *refs)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
