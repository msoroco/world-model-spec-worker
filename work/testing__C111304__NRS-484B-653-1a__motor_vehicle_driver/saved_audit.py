"""Independent saved-only source checks for C111304 original actor histories.

No legal conclusion or physical camera claim is made from a CPU fixture.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


def audit_history(path: Path, expected_sha256: str, expected_case_id: str,
                  expected_site_sha256: str, expected_frames: int = 900) -> dict:
    source = path.read_bytes()
    actual_sha256 = hashlib.sha256(source).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError('original history hash mismatch')
    try:
        rows = [json.loads(line) for line in source.decode('utf-8').splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('original history decode failed') from exc
    if len(rows) != expected_frames:
        raise ValueError('original history frame count mismatch')
    first = rows[0].get('original_frame')
    if type(first) is not int:
        raise ValueError('original frame identity missing')
    fixed = ('ego_id', 'crossing_vehicle_id', 'occupant_id', 'property_id',
             'ego_blueprint', 'crossing_blueprint', 'property_blueprint',
             'map_sha256', 'public_access_basis', 'site_sha256', 'camera_plan_sha256')
    baseline = {key: rows[0].get(key) for key in fixed}
    if any(not value for value in baseline.values()):
        raise ValueError('original fixed source missing')
    if baseline['site_sha256'] != expected_site_sha256:
        raise ValueError('site source mismatch')
    for offset, row in enumerate(rows):
        if row.get('case_id') != expected_case_id or row.get('original_frame') != first + offset:
            raise ValueError('case or original frame join mismatch')
        if any(row.get(key) != value for key, value in baseline.items()):
            raise ValueError('fixed source changed within recording')
        if row.get('occupant_vehicle_id') != baseline['crossing_vehicle_id']:
            raise ValueError('occupancy join mismatch')
        if not row.get('source_sha256') or not row.get('control_command_source_sha256'):
            raise ValueError('original control source missing')
    return {'case_id': expected_case_id, 'original_history_sha256': actual_sha256,
            'site_sha256': baseline['site_sha256'], 'map_sha256': baseline['map_sha256'],
            'first_original_frame': first, 'last_original_frame': first + expected_frames - 1,
            'frame_count': expected_frames, 'fixed': baseline,
            'physical_visibility_verified': False, 'legal_judgment': None}


def audit_comparison(left: Mapping, right: Mapping, difference: str) -> dict:
    if left.get('frame_count') != 900 or right.get('frame_count') != 900:
        raise ValueError('comparison original history incomplete')
    if not left.get('original_history_sha256') or not right.get('original_history_sha256'):
        raise ValueError('comparison source hash missing')
    fixed = ('map_sha256', 'site_sha256', 'public_access_basis',
             'ego_blueprint', 'crossing_blueprint', 'property_blueprint',
             'camera_plan_sha256')
    for key in fixed:
        if key not in left or key not in right or left[key] != right[key]:
            raise ValueError(f'comparison fixed source changed: {key}')
    if difference not in left or difference not in right or left[difference] == right[difference]:
        raise ValueError('comparison deliberate difference missing')
    if left.get('case_id') == right.get('case_id'):
        raise ValueError('comparison duplicates case')
    return {'left_case_id': left['case_id'], 'right_case_id': right['case_id'],
            'difference': difference, 'source_hashes': [left['original_history_sha256'],
                                                         right['original_history_sha256']],
            'legal_judgment': None}
