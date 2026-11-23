"""Independent original-frame and controlled-pair audits for the trail cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


FIXED = ('cell_id', 'map_sha256', 'corridor_source_sha256', 'route_sha256',
         'vehicle_blueprint', 'operator_source_sha256', 'camera_plan_sha256',
         'duration_frames')
CONDITIONS = ('official_plan_designation', 'city_trail_dedication',
              'prohibits_motor_vehicles', 'emergency_use', 'maintenance_use')


def audit_history(path: Path, expected_sha256: str, case_id: str,
                  expected_frames: int = 900) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError('original history hash mismatch')
    try:
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('original history decode failed') from exc
    if len(rows) != expected_frames:
        raise ValueError('original history frame count mismatch')
    first = rows[0]
    if type(first.get('original_frame')) is not int:
        raise ValueError('original frame identity missing')
    baseline = {key: first.get(key) for key in FIXED + CONDITIONS +
                ('sign_face_sha256', 'governed_access_sha256',
                 'official_plan_source_sha256', 'dedication_source_sha256',
                 'exception_status_source_sha256')}
    if any(value is None or value == '' for value in baseline.values()):
        raise ValueError('fixed or administrative source missing')
    if baseline['cell_id'] != 'C143687' or baseline['duration_frames'] != expected_frames:
        raise ValueError('wrong cell or capture duration')
    entered = False
    sign_readback = False
    for index, row in enumerate(rows):
        if row.get('case_id') != case_id or row.get('original_frame') != first['original_frame'] + index:
            raise ValueError('case or original frame join mismatch')
        if any(row.get(key) != value for key, value in baseline.items()):
            raise ValueError('fixed source changed during capture')
        if not row.get('native_packet_sha256') or not row.get('vehicle_id') or not row.get('operator_id'):
            raise ValueError('Native actor source missing')
        if row.get('vehicle_id') != first.get('vehicle_id') or row.get('operator_id') != first.get('operator_id'):
            raise ValueError('actor identity changed')
        if type(row.get('vehicle_inside_corridor')) is not bool or type(row.get('sign_face_visible')) is not bool:
            raise ValueError('corridor or sign readback missing')
        entered |= row['vehicle_inside_corridor']
        sign_readback |= row['sign_face_visible']
    if not entered:
        raise ValueError('vehicle never entered trail corridor')
    if not sign_readback:
        raise ValueError('sign face was never read back')
    return {'case_id': case_id, 'original_history_sha256': digest,
            'frame_count': len(rows), 'entered_corridor': entered,
            'sign_face_readback': sign_readback, **baseline,
            'legal_judgment': None, 'physical_video_visibility_verified': False}


def audit_pair(left: Mapping, right: Mapping, deliberate_difference: str) -> dict:
    if deliberate_difference not in CONDITIONS:
        raise ValueError('undeclared comparison variable')
    for side in (left, right):
        if side.get('frame_count') != 900 or not side.get('original_history_sha256') or not side.get('entered_corridor'):
            raise ValueError('comparison original evidence incomplete')
    source_fields = ('governed_access_sha256', 'sign_face_sha256',
                     'official_plan_source_sha256', 'dedication_source_sha256',
                     'exception_status_source_sha256')
    variable_source = {
        'official_plan_designation': 'official_plan_source_sha256',
        'city_trail_dedication': 'dedication_source_sha256',
        'prohibits_motor_vehicles': 'sign_face_sha256',
        'emergency_use': 'exception_status_source_sha256',
        'maintenance_use': 'exception_status_source_sha256',
    }[deliberate_difference]
    for key in FIXED + tuple(x for x in CONDITIONS if x != deliberate_difference) + tuple(
            x for x in source_fields if x != variable_source):
        if key not in left or key not in right or left[key] != right[key]:
            raise ValueError(f'fixed condition changed: {key}')
    if deliberate_difference not in left or deliberate_difference not in right or left[deliberate_difference] == right[deliberate_difference]:
        raise ValueError('deliberate difference absent')
    if left.get('case_id') == right.get('case_id'):
        raise ValueError('same exact case twice')
    return {'case_ids': [left['case_id'], right['case_id']],
            'difference': deliberate_difference,
            'source_hashes': [left['original_history_sha256'], right['original_history_sha256']],
            'legal_judgment': None}
