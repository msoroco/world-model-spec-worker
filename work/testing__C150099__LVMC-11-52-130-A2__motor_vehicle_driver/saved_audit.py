"""Independent sealed original-frame audit; fixture data is not physical evidence."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from fire_lane import CASES


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
    fixed_keys = ('ego_id', 'sign_id', 'site_sha256', 'map_sha256',
                  'jurisdiction_sha256', 'fire_code_designation_sha256',
                  'posting_authority_sha256', 'posted_extent_sha256',
                  'sign_identity_sha256', 'sign_appearance_sha256',
                  'property_source_sha256', 'curb_geometry_sha256',
                  'route_sha256', 'weather_sha256',
                  'camera_plan_sha256', 'frame_map_sha256')
    fixed = {k: rows[0].get(k) for k in fixed_keys}
    if not all(fixed.values()) or fixed['site_sha256'] != site_sha256:
        raise ValueError('fixed original source missing or wrong site')
    first = rows[0].get('original_frame')
    if type(first) is not int:
        raise ValueError('original frame identity missing')
    previous_t = None
    overlap_frames = 0
    camera_keys = ('overview', 'approach', 'reference_corner', 'driver_reference')
    for index, row in enumerate(rows):
        if row.get('case_id') != case_id or row.get('original_frame') != first + index:
            raise ValueError('original frame or case join mismatch')
        if any(row.get(k) != value for k, value in fixed.items()):
            raise ValueError('fixed original source changed')
        t = row.get('time_s')
        if type(t) not in (int, float) or (previous_t is not None and not 0.049 <= t - previous_t <= 0.051):
            raise ValueError('20 Hz time join mismatch')
        previous_t = t
        if not row.get('source_sha256') or not row.get('body_footprint_source_sha256'):
            raise ValueError('original body source missing')
        if row.get('sign_physically_present') is not True or row.get('sign_text_readback') != 'FIRE LANE':
            raise ValueError('fire-lane sign readback missing')
        if row.get('activity_observation') not in ('moving', 'stopped', 'standing', 'parked'):
            raise ValueError('activity observation missing')
        if type(row.get('attended_observation')) is not bool or row.get('property_kind') not in ('public', 'private'):
            raise ValueError('attendance or property observation missing')
        bounds = row.get('posted_interval_m')
        body = row.get('body_interval_m')
        if (not isinstance(bounds, list) or len(bounds) != 2 or
            not isinstance(body, list) or len(body) != 2 or
            any(type(v) not in (int, float) for v in bounds + body) or
            bounds[1] <= bounds[0] or body[1] <= body[0]):
            raise ValueError('posted interval or body footprint invalid')
        overlap_frames += min(bounds[1], body[1]) > max(bounds[0], body[0])
        cameras = row.get('camera_frames')
        if not isinstance(cameras, dict) or set(cameras) != set(camera_keys):
            raise ValueError('four-camera frame source missing')
        for camera in camera_keys:
            packet = cameras[camera]
            if (not isinstance(packet, dict) or
                packet.get('original_frame') != first + index or
                not isinstance(packet.get('source_sha256'), str) or
                len(packet['source_sha256']) != 64 or
                any(c not in '0123456789abcdef' for c in packet['source_sha256'])):
                raise ValueError('four-camera original frame/source join invalid')
        kind = row.get('exception_kind')
        if kind not in ('none', 'lawful_traffic_conflict', 'police_direction', 'traffic_device_direction'):
            raise ValueError('exception kind unsupported')
        if kind != 'none' and not row.get('exception_source_sha256'):
            raise ValueError('exception source missing')
    return {'case_id': case_id, 'original_history_sha256': digest,
            'frame_count': frames, 'first_original_frame': first,
            'last_original_frame': first + frames - 1,
            'overlap_frames': overlap_frames, 'fixed_sources': fixed,
            'legal_judgment': None, 'physical_visibility_verified': False}


def audit_planned_case(path: Path, expected_sha256: str, full_case_id: str,
                       site_sha256: str, frames: int = 900) -> dict:
    """Check a sealed history against the planned variation using original rows.

    The final 100 frames are a measurement window, not a legal threshold. It
    prevents startup transit from masquerading as a stopped/parked observation.
    """
    matches = [case for case in CASES if full_case_id.endswith('__' + case.id)]
    if len(matches) != 1:
        raise ValueError('planned case identity missing')
    case = matches[0]
    report = audit_original_history(path, expected_sha256, full_case_id,
                                    site_sha256, frames=frames)
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line]
    tail = rows[-min(100, frames):]
    expected_activity = {'stop': 'stopped', 'stand': 'standing', 'park': 'parked'}[case.activity]
    if not all(row.get('activity_observation') == expected_activity for row in tail):
        raise ValueError('planned activity absent from original hold')
    if not all(row.get('attended_observation') is case.attended for row in tail):
        raise ValueError('planned attendance absent from original hold')
    if not all(row.get('property_kind') == case.property_kind for row in rows):
        raise ValueError('planned property source changed')
    if not all(row.get('exception_kind') == case.exception for row in tail):
        raise ValueError('planned exception source absent from original hold')
    overlaps = [min(row['posted_interval_m'][1], row['body_interval_m'][1]) >
                max(row['posted_interval_m'][0], row['body_interval_m'][0]) for row in tail]
    if case.target_region == 'inside' and not all(overlaps):
        raise ValueError('planned inside target absent from original hold')
    if case.target_region == 'outside' and any(overlaps):
        raise ValueError('planned outside target absent from original hold')
    report['observed'] = {
        'attended': case.attended, 'property_kind': case.property_kind,
        'activity': case.activity, 'target_region': case.target_region,
        'exception': case.exception, 'hold_frame_count': len(tail),
        'hold_overlap_frames': sum(overlaps),
    }
    return report
