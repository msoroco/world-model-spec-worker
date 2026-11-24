"""Saved-only exact-case crossing and original PNG source join.

Observed diagonal device states are not a legal authorization finding. The
NRS 484B.290 exception and physical visibility remain independent reviews.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_measurement import measure_acquisition
from saved_media_audit import audit_camera_sources

ASSIGNMENT = 'testing__C111329__NRS-484B-287-1d__pedestrian'
CASES = {
    'adjacent_no_diagonal_authority': ('adjacent', False),
    'diagonal_no_authority': ('opposite', False),
    'diagonal_authorized': ('opposite', True),
    'adjacent_authorized_device': ('adjacent', True),
}


def _read(root: Path, ref: dict):
    relative = ref.get('path')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('saved source path invalid')
    source = root / relative
    if source.is_symlink():
        raise ValueError('saved source symlinked')
    path = source.resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('saved source outside attempt')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise ValueError('saved source hash mismatch')
    return json.loads(raw)


def process(attempt: Path, site_ref: dict, native_ref: dict, camera_ref: dict,
            case_id: str, output: Path, *, expected_frames: int = 900,
            allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    output = Path(output)
    if output.exists():
        raise ValueError('saved crossing receipt already exists')
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('foreign exact crossing case')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if suffix not in CASES:
        raise ValueError('unknown exact crossing case')
    site, packet, camera_manifest = (_read(attempt, ref) for ref in
                                      (site_ref, native_ref, camera_ref))
    route_kind, authorization = CASES[suffix]
    measured = measure_acquisition(site, packet, case_id=case_id,
                                   route_kind=route_kind, authorization=authorization,
                                   expected_frames=expected_frames,
                                   allow_diagnostic=allow_diagnostic)
    media = audit_camera_sources(packet, camera_manifest, attempt,
                                 allow_diagnostic=allow_diagnostic)
    if (measured['native_rows_sha256'] != media['native_rows_sha256'] or
            measured['case_id'] != media['case_id'] or
            packet['frame_count'] != media['frame_count'] or
            media['decoded_png_count'] != 4 * expected_frames):
        raise ValueError('saved crossing and camera source join mismatch')
    result = {'format': 'c111329-saved-process-v1', 'case_id': case_id,
              'site_source_sha256': site_ref['sha256'],
              'native_source_sha256': native_ref['sha256'],
              'camera_manifest_source_sha256': camera_ref['sha256'],
              'measurement': measured, 'media_audit': media,
              'physical_visibility': 'requires_independent_review',
              'exception_484B_290': 'unresolved', 'legal_verdict': None}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
                      encoding='utf-8')
    return result
