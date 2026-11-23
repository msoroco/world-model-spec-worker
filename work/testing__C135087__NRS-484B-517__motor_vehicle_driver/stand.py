"""Source-gated taxicab-stand construction and original-history measurements.

The outputs describe observations, not NRS 484B.517 legal conclusions.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise SourceError(message)


def _sealed_object(ref):
    path = Path(ref['path'])
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'source hash mismatch')
    return json.loads(raw)


def validate_source(site_ref, vehicle_ref, case):
    site = _sealed_object(site_ref)
    vehicles = _sealed_object(vehicle_ref)
    _require(site['kind'] == 'taxicab_stand' and site['cell_id'] == 'C135087', 'wrong stand or cell')
    _require(site['highway_status_source'] and site['designation_source'] and site['sign_source'], 'stand designation/sign source missing')
    _require(site['map_name'] and site['lane_id'] and site['curb_polygon'], 'stand geometry missing')
    _require(len(site['curb_polygon']) >= 3, 'curb polygon incomplete')
    _require(all(len(p) == 2 and all(math.isfinite(float(x)) for x in p) for p in site['curb_polygon']), 'invalid curb geometry')
    _require(site['approach_lane_id'] and site['access_waypoints'], 'entrant approach path missing')
    _require(len(site['access_waypoints']) >= 2, 'entrant approach path incomplete')
    _require(vehicles['subject']['kind'] == 'passenger_vehicle', 'subject passenger vehicle source missing')
    _require(not vehicles['subject']['compensated_taxicab_use'], 'subject taxicab exclusion missing')
    _require(vehicles['subject']['driver_identity_source'], 'driver identity missing')
    entrant = vehicles['entrant']
    _require(entrant['kind'] == 'motor_vehicle' and entrant['design_capacity_including_driver'] <= 6, 'entrant capacity/class missing')
    _require(entrant['compensated_passenger_use_source'], 'entrant compensated use source missing')
    _require(case['entrant_mode'] in {'about_to_enter', 'waiting_to_enter', 'no_entrant'}, 'unknown entrant mode')
    _require(case['loading_mode'] in {'active', 'ceased'}, 'unknown loading mode')
    _require(case['access_mode'] in {'open', 'constrained'}, 'unknown access mode')
    return site, vehicles


def construct_case(adapter, site_ref, vehicle_ref, case):
    """Adapter methods perform Native spawn/marking/readback; reject absent readback."""
    site, vehicles = validate_source(site_ref, vehicle_ref, case)
    observed = adapter.verify_site(site)
    _require(observed['map_name'] == site['map_name'], 'Native map readback mismatch')
    _require(observed['sign_visible'] and observed['sign_id'] == site['sign_id'], 'Native sign readback missing')
    _require(observed['curb_polygon'] == site['curb_polygon'], 'Native curb readback mismatch')
    ego = adapter.spawn_subject(vehicles['subject'], site['stand_waypoint'])
    _require(ego['actor_id'] and ego['blueprint'] == vehicles['subject']['blueprint'], 'subject readback mismatch')
    entrant = adapter.spawn_entrant(vehicles['entrant'], site['access_waypoints'], case['entrant_mode'])
    _require(entrant['actor_id'] and entrant['blueprint'] == vehicles['entrant']['blueprint'], 'entrant readback mismatch')
    passenger = adapter.spawn_passenger(site['passenger_waypoint'])
    _require(passenger['actor_id'], 'passenger readback missing')
    adapter.configure_loading(ego['actor_id'], passenger['actor_id'], case['loading_mode'])
    adapter.configure_access(entrant['actor_id'], site['access_waypoints'], case['access_mode'])
    return {'site': site, 'subject_id': ego['actor_id'], 'entrant_id': entrant['actor_id'], 'passenger_id': passenger['actor_id'], 'case_id': case['case_id']}


def measure_original_history(rows, expected):
    """Measure every original synchronized frame; missing actors or frames fail closed."""
    _require(len(rows) == expected['frame_count'] and len(rows) >= 2, 'incomplete frame count')
    loading = []
    stopped = []
    entrance = []
    access = []
    for index, row in enumerate(rows):
        _require(row['frame'] == expected['first_frame'] + index, 'frame gap')
        _require(row['case_id'] == expected['case_id'], 'case mismatch')
        _require(row['map_name'] == expected['map_name'], 'map mismatch')
        _require(row['subject_id'] == expected['subject_id'] and row['entrant_id'] == expected['entrant_id'] and row['passenger_id'] == expected['passenger_id'], 'actor identity mismatch')
        _require(math.isfinite(float(row['time_s'])), 'nonfinite time')
        if index:
            _require(row['time_s'] > rows[index-1]['time_s'], 'time discontinuity')
        _require(row['subject_speed_mps'] >= 0 and row['entrant_speed_mps'] >= 0, 'invalid speed')
        _require(isinstance(row['passenger_loading_active'], bool), 'loading readback missing')
        _require(isinstance(row['entrant_waiting'], bool) and isinstance(row['entrant_about_to_enter'], bool), 'entrant status missing')
        _require(isinstance(row['access_obstructed'], bool), 'access readback missing')
        loading.append(row['passenger_loading_active'])
        stopped.append(row['subject_speed_mps'] < 0.1)
        entrance.append(row['entrant_waiting'] or row['entrant_about_to_enter'])
        access.append(row['access_obstructed'])
    active_stop_frames = [i for i, value in enumerate(stopped) if value]
    return {
        'case_id': expected['case_id'], 'source_frame_count': len(rows),
        'stopped_frames': len(active_stop_frames),
        'stop_duration_s': (rows[active_stop_frames[-1]]['time_s'] - rows[active_stop_frames[0]]['time_s']) if active_stop_frames else 0.0,
        'loading_during_stop_frames': sum(loading[i] for i in active_stop_frames),
        'entrant_waiting_or_about_during_stop_frames': sum(entrance[i] for i in active_stop_frames),
        'access_obstructed_during_stop_frames': sum(access[i] for i in active_stop_frames),
        'first_time_s': rows[0]['time_s'], 'last_time_s': rows[-1]['time_s'],
        'legal_judgment': None,
    }


def audit_comparison(left, right, fixed_keys, deliberate_keys):
    _require(left['case_id'] != right['case_id'], 'duplicate case')
    _require(all(left[k] == right[k] for k in fixed_keys), 'fixed condition changed')
    _require(any(left[k] != right[k] for k in deliberate_keys), 'declared difference absent')
    return {'case_ids': [left['case_id'], right['case_id']], 'fixed_checked': list(fixed_keys), 'differences_checked': list(deliberate_keys)}


def audit_saved_attempt(attempt, capture_root):
    """Independent original-source inventory and 900-frame observation audit.

    Media decode and pixel visibility require the separate pinned media auditor;
    this function does not claim either.
    """
    root = Path(capture_root).resolve()
    _require(attempt['source_format'] == 'native_original', 'non-original capture source')
    _require(attempt['frame_count'] == 900 and attempt['fps'] == 20, 'duration/profile mismatch')
    _require(set(attempt['cameras']) == {'front', 'rear', 'left', 'right'}, 'four camera sources required')
    def source(ref):
        p = (root / ref['path']).resolve()
        _require(p.is_relative_to(root), 'source escapes attempt root')
        raw = p.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'saved source hash mismatch')
        return raw
    rows = json.loads(source(attempt['actor_rows']).decode('utf-8'))
    frame_map = json.loads(source(attempt['frame_map']).decode('utf-8'))
    _require(len(frame_map) == 900, 'frame map incomplete')
    _require(len(rows) == 900, 'incomplete frame count')
    _require(all(frame_map[i]['frame'] == rows[i]['frame'] and frame_map[i]['time_s'] == rows[i]['time_s'] for i in range(900)), 'frame map and actor rows disagree')
    camera_hashes = {}
    for name, ref in attempt['cameras'].items():
        source(ref)
        _require(ref['frame_count'] == 900 and ref['fps'] == 20, 'camera frame/profile mismatch')
        camera_hashes[name] = ref['sha256']
    expected = {key: attempt[key] for key in ('case_id', 'map_name', 'subject_id', 'entrant_id', 'passenger_id', 'frame_count', 'first_frame')}
    measurement = measure_original_history(rows, expected)
    return {'format': 'taxicab-stand-saved-source-audit', 'case_id': attempt['case_id'], 'measurement': measurement,
            'source_sha256': {'actor_rows': attempt['actor_rows']['sha256'], 'frame_map': attempt['frame_map']['sha256'], 'cameras': camera_hashes},
            'full_video_decode': 'pending_pinned_media_auditor', 'actual_pixels': 'pending_physical_review'}
