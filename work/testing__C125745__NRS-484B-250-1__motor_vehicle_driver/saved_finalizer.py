"""Saved-only exact precedence result from source-sealed original histories."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_history_capture import CAMERAS, _retained_file, audit_media
from saved_crossing import ASSIGNMENT, SOURCES, measure


def finalize(attempt, output, *, expected_manifest_sha256, case_id):
    attempt, output = Path(attempt), Path(output)
    if case_id not in (ASSIGNMENT + '__precedence', ASSIGNMENT + '__advance'):
        raise ValueError('unknown exact precedence case')
    manifest_path = _retained_file(attempt, 'source-manifest.json')
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise ValueError('original source manifest hash mismatch')
    manifest = json.loads(manifest_bytes)
    if not set(SOURCES + ('camera-frame-map.jsonl', 'video_frames.jsonl')).issubset(manifest):
        raise ValueError('original body and four-camera source manifest incomplete')
    timing = measure(attempt)
    if timing['case_id'] != case_id:
        raise ValueError('saved original case identity differs')
    site = json.loads(_retained_file(attempt, 'site-context.json').read_text(encoding='utf-8'))
    dimensions = site.get('camera_dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('source-bound four-camera dimensions required')
    media = audit_media(attempt, camera_dimensions=dimensions)
    if media['joined_original_frames'] != timing['original_frame_count']:
        raise ValueError('saved camera/body frame count differs')
    diagnostic = (site.get('review_status') != 'reviewed_original' or
                  timing['original_frame_count'] != 900)
    result = {
        'format': 'worker-c125745-2501-saved-v1',
        'assignment_id': ASSIGNMENT,
        'case_id': case_id,
        'source_manifest_sha256': expected_manifest_sha256,
        'source_sha256': timing['source_sha256'],
        'original_frame_count': timing['original_frame_count'],
        'camera_audit': media,
        'crossing_measurement': timing,
        'diagnostic_fixture': diagnostic,
        'legal_applicability': 'unresolved_official_device_exception_and_subsection_4',
        'physical_acceptance': False,
        'legal_verdict_claimed': False,
    }
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result
