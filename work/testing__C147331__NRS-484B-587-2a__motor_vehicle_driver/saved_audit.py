"""Independent hash-bound audit of saved C147331 Native frame histories."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


def audit_history(path: Path, expected_sha256: str, expected_case: str,
                  expected_map_sha256: str, expected_frames: int = 900) -> dict:
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError('Native history hash mismatch')
    try:
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Native history decode failed') from exc
    if len(rows) != expected_frames:
        raise ValueError('Native history frame count mismatch')
    first = rows[0].get('original_frame')
    if type(first) is not int:
        raise ValueError('original frame missing')
    fixed = ('ego_id', 'map_sha256', 'lane_marking_source_sha256',
             'legal_controlled_access_source_sha256', 'public_highway_boundary_source_sha256',
             'camera_plan_sha256', 'vehicle_class', 'approach', 'route_class',
             'sign_source_sha256', 'emergency_record_source_sha256',
             'subsection3_authorization_source_sha256')
    baseline = {key: rows[0].get(key) for key in fixed}
    if any(not value for value in baseline.values()) or baseline['map_sha256'] != expected_map_sha256:
        raise ValueError('fixed Native source missing or wrong map')
    for offset, row in enumerate(rows):
        if row.get('case') != expected_case or row.get('original_frame') != first+offset:
            raise ValueError('case/original-frame join mismatch')
        if any(row.get(key) != value for key, value in baseline.items()):
            raise ValueError('fixed Native source changed')
        if not row.get('source_sha256') or not row.get('capture_packet_sha256'):
            raise ValueError('original capture packet source missing')
        for key in ('sign_permits_shoulder', 'emergency_required', 'subsection3_authorized'):
            if type(row.get(key)) is not bool or row[key] != rows[0][key]:
                raise ValueError(f'{key} source changed or missing')
    return {'case': expected_case, 'original_history_sha256': digest,
            'first_original_frame': first, 'last_original_frame': first+expected_frames-1,
            'frame_count': expected_frames, 'fixed': baseline,
            'physical_visibility_verified': False, 'legal_judgment': None}
