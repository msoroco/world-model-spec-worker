"""Independent hash-bound audit of saved C3997 Native frame histories."""
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
             'lane_function_source_sha256', 'vehicle_class_source_sha256',
             'vehicle_class',
             'paved_shoulder_source_sha256',
             'lawful_shoulder_sign_source_sha256',
             'legal_controlled_access_source_sha256', 'public_highway_boundary_source_sha256',
             'camera_plan_sha256', 'direction_source_sha256', 'approach',
             'origin', 'destination', 'route_id', 'separator_kind',
             'separator_source_sha256', 'emergency_record_source_sha256',
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
        if row.get('separator_kind') != 'solid_white':
            raise ValueError('original solid-white separator missing')
        for key in ('ego_speed_mps', 'center_signed_m', 'body_min_signed_m',
                    'body_max_signed_m', 'center_segment_fraction',
                    'body_min_segment_fraction', 'body_max_segment_fraction'):
            if type(row.get(key)) not in (int, float):
                raise ValueError('original body/line measurement missing: '+key)
        if not row['body_min_signed_m'] <= row['center_signed_m'] <= row['body_max_signed_m']:
            raise ValueError('original body footprint misses center')
        if not row['body_min_segment_fraction'] <= row['center_segment_fraction'] <= row['body_max_segment_fraction']:
            raise ValueError('original body longitudinal footprint misses center')
        for key in ('emergency_required', 'subsection3_shoulder_authorized',
                    'shoulder_paved', 'lawful_sign_permits_shoulder'):
            if type(row.get(key)) is not bool or row[key] != rows[0][key]:
                raise ValueError(f'{key} source changed or missing')
        if row['subsection3_shoulder_authorized'] and not (
                row['shoulder_paved'] and row['lawful_sign_permits_shoulder']):
            raise ValueError('subsection 3 paving or lawful sign source missing')
    return {'case': expected_case, 'original_history_sha256': digest,
            'first_original_frame': first, 'last_original_frame': first+expected_frames-1,
            'frame_count': expected_frames, 'fixed': baseline,
            'physical_visibility_verified': False, 'legal_judgment': None}
