"""NRS 484B.450(1)(o) construction and original-source checks.

Every output is an observation for review, never a legal verdict. Native scene
and authority evidence must be supplied by the local adapter, not inferred from
an authored device category.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class SourceError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise SourceError(message)


def sealed_json(ref, root=None):
    base = Path(root).resolve() if root is not None else None
    path = (base / ref['path']).resolve() if base else Path(ref['path']).resolve()
    require(base is None or path.is_relative_to(base), 'source escapes root')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'source hash mismatch')
    return json.loads(raw)


def validate_sources(site_ref, device_ref, vehicle_ref, case):
    site, device, vehicle = (sealed_json(ref) for ref in (site_ref, device_ref, vehicle_ref))
    require(site['cell_id'] == 'C229439' and site['layout'] == 'road', 'wrong road cell')
    require(site['map_name'] and site['approach_waypoints'] and site['parking_polygon'], 'missing mapped parking site')
    require(len(site['approach_waypoints']) >= 2 and len(site['parking_polygon']) >= 3, 'incomplete site geometry')
    require(all(len(point) == 2 and all(math.isfinite(float(v)) for v in point) for point in site['parking_polygon']), 'invalid parking polygon')
    require(device['device_id'] and device['exact_instruction'] and device['authority_source'], 'official device content or authority missing')
    require(device['placement_source'] and device['traffic_purpose_source'] and device['legal_consistency_source'], 'device placement/legal context missing')
    require(device['governed_polygon'] == site['parking_polygon'], 'device does not govern planned parking place')
    require(device['effective_intervals'] and device['prohibited_actions'], 'device effective rule missing')
    require(set(device['prohibited_actions']) <= {'stop', 'stand', 'park'}, 'unknown device action')
    require(device['exact_instruction'] == case['exact_instruction'], 'case-specific device instruction mismatch')
    require(case['halt_action'] in device['prohibited_actions'], 'device does not prohibit selected halt action')
    require(vehicle['blueprint'] and vehicle['driver_identity_source'] and vehicle['vehicle_class_source'], 'driver or vehicle source missing')
    require(case['halt_action'] in {'stop', 'stand', 'park'}, 'unknown halt action')
    require(case['exception'] in {'none', 'traffic_conflict', 'law', 'police_direction', 'device_direction'}, 'unknown exception')
    require(case['device_mode'] in {'effective', 'not_effective'}, 'unknown device mode')
    return site, device, vehicle


def construct_case(adapter, site_ref, device_ref, vehicle_ref, case):
    """Use an injected Native adapter; source/readback mismatch aborts before motion."""
    site, device, vehicle = validate_sources(site_ref, device_ref, vehicle_ref, case)
    observed = adapter.verify_site(site)
    require(observed['map_name'] == site['map_name'] and observed['parking_polygon'] == site['parking_polygon'], 'Native site readback mismatch')
    observed_device = adapter.install_and_read_device(device)
    require(observed_device['device_id'] == device['device_id'], 'Native device identity mismatch')
    require(observed_device['exact_instruction'] == device['exact_instruction'], 'Native device instruction mismatch')
    require(observed_device['governed_polygon'] == site['parking_polygon'], 'Native device governed area mismatch')
    adapter.configure_effective_window(device['device_id'], case['device_mode'], device['effective_intervals'])
    require(adapter.read_device_effective(device['device_id']) == (case['device_mode'] == 'effective'), 'Native effective-window readback mismatch')
    ego = adapter.spawn_driver_vehicle(vehicle, site['approach_waypoints'][0])
    require(ego['actor_id'] and ego['blueprint'] == vehicle['blueprint'], 'Native driver vehicle readback mismatch')
    adapter.configure_parking_route(ego['actor_id'], site['approach_waypoints'], site['parking_polygon'], case['halt_action'])
    adapter.configure_exception_cause(ego['actor_id'], case['exception'])
    require(adapter.read_exception_cause(ego['actor_id']) == case['exception'], 'Native exception-cause readback mismatch')
    return {'case_id': case['case_id'], 'map_name': site['map_name'], 'device_id': device['device_id'], 'subject_id': ego['actor_id'], 'halt_action': case['halt_action']}


def _inside_polygon(point, polygon):
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def measure_original_history(rows, expected):
    """Measure original 20 Hz source rows, including actual stop and device state."""
    require(len(rows) == expected['frame_count'] and len(rows) >= 2, 'incomplete frame count')
    stopped, governed, prohibited, exceptions = [], [], [], []
    polygon = expected['parking_polygon']
    for i, row in enumerate(rows):
        require(row['frame'] == expected['first_frame'] + i, 'frame gap')
        require(row['case_id'] == expected['case_id'] and row['subject_id'] == expected['subject_id'], 'case or actor mismatch')
        require(row['device_id'] == expected['device_id'] and row['device_instruction'] == expected['device_instruction'], 'device source mismatch')
        require(math.isfinite(float(row['time_s'])), 'invalid time')
        if i:
            require(abs(row['time_s'] - rows[i-1]['time_s'] - 0.05) <= 0.001, 'not contiguous 20 Hz')
        require(isinstance(row['device_effective'], bool), 'device effective readback missing')
        require(isinstance(row['traffic_conflict'], bool) and isinstance(row['police_direction'], bool), 'exception source missing')
        require(isinstance(row['law_direction'], bool) and isinstance(row['device_direction'], bool), 'direction source missing')
        require(row['speed_mps'] >= 0 and math.isfinite(row['speed_mps']), 'invalid speed')
        require(row['halt_activity'] in {'stop', 'stand', 'park', 'travel'}, 'actual halt activity missing')
        require(len(row['body_corners_xy']) == 4, 'body footprint missing')
        stopped.append(row['speed_mps'] < 0.1)
        governed.append(all(_inside_polygon(p, polygon) for p in row['body_corners_xy']))
        prohibited.append(row['device_effective'] and expected['halt_action'] in row['prohibited_actions'])
        exceptions.append(any(row[key] for key in ('traffic_conflict', 'police_direction', 'law_direction', 'device_direction')))
    active = [i for i in range(len(rows)) if stopped[i] and governed[i] and rows[i]['halt_activity'] == expected['halt_action']]
    return {'case_id': expected['case_id'], 'source_frame_count': len(rows),
            'halt_inside_frames': len(active), 'effective_prohibition_during_halt_frames': sum(prohibited[i] for i in active),
            'exception_source_during_halt_frames': sum(exceptions[i] for i in active),
            'first_time_s': rows[0]['time_s'], 'last_time_s': rows[-1]['time_s'], 'legal_judgment': None}


def audit_comparison(left, right, fixed_keys, deliberate_keys):
    require(left['case_id'] != right['case_id'], 'duplicate case')
    require(all(left[key] == right[key] for key in fixed_keys), 'fixed condition changed')
    require(any(left[key] != right[key] for key in deliberate_keys), 'declared difference absent')
    return {'case_ids': [left['case_id'], right['case_id']], 'fixed_checked': list(fixed_keys), 'differences_checked': list(deliberate_keys)}


def audit_saved_attempt(attempt, root):
    """Independent original-row and four-camera source audit; pixel decode is separate."""
    require(attempt['source_format'] == 'native_original' and attempt['fps'] == 20 and attempt['frame_count'] == 900, 'capture profile mismatch')
    require(set(attempt['cameras']) == {'front', 'rear', 'left', 'right'}, 'missing camera')
    rows = sealed_json(attempt['actor_rows'], root)
    frame_map = sealed_json(attempt['frame_map'], root)
    require(len(frame_map) == 900, 'frame map incomplete')
    require(all(frame_map[i]['frame'] == rows[i]['frame'] and frame_map[i]['time_s'] == rows[i]['time_s'] for i in range(900)), 'frame map join mismatch')
    camera_hashes = {}
    for name, ref in attempt['cameras'].items():
        path = (Path(root).resolve() / ref['path']).resolve()
        require(path.is_relative_to(Path(root).resolve()), 'camera source escapes root')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'camera source hash mismatch')
        require(ref['frame_count'] == 900 and ref['fps'] == 20, 'camera profile mismatch')
        camera_hashes[name] = ref['sha256']
    expected = {key: attempt[key] for key in ('frame_count', 'first_frame', 'case_id', 'subject_id', 'device_id', 'device_instruction', 'parking_polygon', 'halt_action')}
    measurement = measure_original_history(rows, expected)
    return {'format': 'official-parking-device-source-audit', 'measurement': measurement, 'camera_hashes': camera_hashes,
            'full_video_decode': 'pending_pinned_media_auditor', 'actual_pixels': 'pending_physical_review'}
