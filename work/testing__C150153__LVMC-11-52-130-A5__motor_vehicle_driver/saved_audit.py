"""Independent hash-sealed original 20 Hz sidewalk-elevator history audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def audit_original_history(path: Path, expected_sha256: str, case_id: str,
                           site_sha256: str, frames: int = 900) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError('original history hash mismatch')
    try:
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('original history decode failed') from exc
    if len(rows) != frames:
        raise ValueError('original frame count mismatch')
    first = rows[0].get('original_frame')
    if type(first) is not int:
        raise ValueError('original frame identity missing')
    fixed_keys = ('ego_id', 'fixture_id', 'fixture_identity_sha256',
                  'fixture_geometry_sha256', 'fixture_blueprint_sha256',
                  'map_sha256', 'site_sha256', 'camera_plan_sha256',
                  'municipal_jurisdiction_sha256', 'sidewalk_sha256', 'curb_sha256',
                  'frame_map_sha256')
    fixed = {k: rows[0].get(k) for k in fixed_keys}
    if not all(fixed.values()) or fixed['site_sha256'] != site_sha256:
        raise ValueError('fixed original source missing or wrong site')
    previous_t = None
    intervals = []
    for index, row in enumerate(rows):
        if row.get('case_id') != case_id or row.get('original_frame') != first + index:
            raise ValueError('original frame or case join mismatch')
        if any(row.get(k) != v for k, v in fixed.items()):
            raise ValueError('fixed source changed in history')
        if not row.get('source_sha256') or not row.get('body_footprint_source_sha256'):
            raise ValueError('body or frame source missing')
        time_s = row.get('time_s')
        if type(time_s) not in (int, float) or (previous_t is not None and
            not (0.049 <= time_s - previous_t <= 0.051)):
            raise ValueError('20 Hz time join mismatch')
        previous_t = time_s
        west, east = row.get('body_west_x_m'), row.get('body_east_x_m')
        if type(west) not in (int, float) or type(east) not in (int, float) or east <= west:
            raise ValueError('body footprint invalid')
        if row.get('fixture_physically_present') is not True:
            raise ValueError('fixture presence readback missing')
        if row.get('activity_observation') not in ('moving', 'stopped', 'standing', 'parked'):
            raise ValueError('activity observation missing')
        if row.get('exception_kind') not in ('none', 'lawful_traffic_conflict',
                                             'police_direction', 'traffic_device_direction'):
            raise ValueError('exception classification source missing')
        if row['exception_kind'] != 'none' and not row.get('exception_source_sha256'):
            raise ValueError('exception source missing')
        intervals.append((west, east))
    return {'case_id': case_id, 'original_history_sha256': digest,
            'first_original_frame': first, 'last_original_frame': first + frames - 1,
            'frame_count': frames, 'source_identity': fixed,
            'observed_body_intervals_m': intervals, 'legal_judgment': None,
            'physical_visibility_verified': False}
