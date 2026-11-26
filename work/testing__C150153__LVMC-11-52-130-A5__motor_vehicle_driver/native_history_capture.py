"""Capture source-bound original elevator history from a Native frame adapter.

The adapter must return recorded observations, never commanded target values.
This module does not establish legal meaning or physical camera visibility.
"""
from __future__ import annotations

import hashlib
import json
import os
import math
from pathlib import Path

from parking import CASES, validate_site
from saved_audit import audit_original_history


def capture_original_history(adapter, site: dict, case, output: Path,
                             frames: int = 900, frame_hook=None) -> dict:
    """Tick a live adapter, seal its original observations and audit the result.

    `tick_and_sample()` returns a mapping with original_frame, time_s, actual
    vehicle body edges, fixture readback, activity, and source identities.
    The first frame may have any Native identity; subsequent frames must join.
    """
    validate_site(site)
    if case not in CASES or frames != 900:
        raise ValueError('exact case or 45-second capture duration missing')
    output = Path(output)
    if output.exists():
        raise ValueError('refusing to overwrite original capture')
    site_sha = site.get('site_sha256')
    if not site_sha:
        raise ValueError('site source hash missing')
    expected = {
        'fixture_identity_sha256': site['fixture_identity_sha256'],
        'fixture_geometry_sha256': site['fixture_geometry_sha256'],
        'fixture_blueprint_sha256': site['fixture_blueprint_sha256'],
        'map_sha256': site['map_sha256'],
        'site_sha256': site_sha,
        'camera_plan_sha256': site['camera_plan_sha256'],
        'municipal_jurisdiction_sha256': site['municipal_jurisdiction_sha256'],
        'sidewalk_sha256': site['sidewalk_sha256'],
        'curb_sha256': site['curb_sha256'],
    }
    source_key = {
        'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
        'police_direction': 'police_direction_source_sha256',
        'traffic_device_direction': 'traffic_device_source_sha256',
    }.get(case.exception)
    exception_sha = site.get(source_key) if source_key else None
    if source_key and not exception_sha:
        raise ValueError('exception source missing')
    temporary = output.with_name(output.name + '.incomplete')
    if temporary.exists():
        raise ValueError('incomplete capture already exists')
    first_frame = None
    first_time = None
    identities = None
    sha = hashlib.sha256()
    try:
        with temporary.open('xb') as stream:
            for index in range(frames):
                row = adapter.tick_and_sample()
                if not isinstance(row, dict):
                    raise ValueError('Native frame observation missing')
                if first_frame is None:
                    first_frame = row.get('original_frame')
                    first_time = row.get('time_s')
                    if type(first_frame) is not int or type(first_time) not in (int, float):
                        raise ValueError('original frame or time missing')
                    identities = (row.get('ego_id'), row.get('fixture_id'),
                                  row.get('frame_map_sha256'))
                    if not all(identities):
                        raise ValueError('actor or frame-map source missing')
                if row.get('case_id') != case.id or row.get('original_frame') != first_frame + index:
                    raise ValueError('exact case or original frame mismatch')
                t = row.get('time_s')
                if type(t) not in (int, float) or abs(t - (first_time + index / 20)) > 0.001:
                    raise ValueError('20 Hz original time mismatch')
                if (row.get('ego_id'), row.get('fixture_id'), row.get('frame_map_sha256')) != identities:
                    raise ValueError('actor or frame-map source changed')
                if any(row.get(key) != value for key, value in expected.items()):
                    raise ValueError('site or fixture source changed')
                if row.get('exception_kind') != case.exception or row.get('exception_source_sha256') != exception_sha:
                    raise ValueError('exception observation source mismatch')
                if row.get('fixture_physically_present') is not True:
                    raise ValueError('fixture presence readback missing')
                if not row.get('source_sha256') or not row.get('body_footprint_source_sha256'):
                    raise ValueError('original frame or body source missing')
                body_west, body_east = row.get('body_west_x_m'), row.get('body_east_x_m')
                if (type(body_west) not in (int, float) or type(body_east) not in (int, float)
                        or not body_west < body_east):
                    raise ValueError('observed vehicle body footprint invalid')
                if row.get('activity_observation') not in ('moving', 'stopped', 'standing', 'parked'):
                    raise ValueError('observed activity missing')
                for name in ('body_curb_gap_m', 'ego_speed_mps'):
                    value = row.get(name)
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise ValueError('observed ' + name + ' missing or invalid')
                encoded = (json.dumps(row, sort_keys=True, allow_nan=False,
                                      separators=(',', ':')) + '\n').encode('utf-8')
                if frame_hook is not None:
                    frame_hook(row, index)
                stream.write(encoded)
                sha.update(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        proof = audit_original_history(temporary, sha.hexdigest(), case.id, site_sha)
        os.replace(temporary, output)
        return {'path': str(output), 'sha256': sha.hexdigest(),
                'first_original_frame': proof['first_original_frame'],
                'last_original_frame': proof['last_original_frame'],
                'frame_count': proof['frame_count'], 'legal_judgment': None,
                'physical_visibility_verified': False}
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
