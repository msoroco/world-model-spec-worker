"""Independent saved-only source checks for C111304 original actor histories.

No legal conclusion or physical camera claim is made from a CPU fixture.
"""
from __future__ import annotations

import hashlib
import json
import math
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


def audit_native_acquisition(attempt: Path, receipt: Mapping) -> dict:
    """Rejoin sealed original source packets, actor rows and camera readbacks."""
    from encounter import CASES
    from native_acquisition import ASSIGNMENT

    expected_case = next((case for case in CASES
                          if receipt.get('case_id') == f'{ASSIGNMENT}__{case.case_id}'), None)
    if expected_case is None:
        raise ValueError('native receipt exact case unknown')
    for key, value in (('ego_target_speed_mps', expected_case.ego_speed_mps),
                       ('crossing_target_speed_mps', expected_case.crossing_speed_mps),
                       ('crossing_release_s', expected_case.crossing_release_s)):
        if receipt.get(key) != value:
            raise ValueError(f'native receipt {key} differs from exact case')
    expected = ('original-history.jsonl', 'original-packets.jsonl', 'original-cameras.jsonl',
                'trace.jsonl', 'video_frames.jsonl')
    keys = ('original_history_sha256', 'original_packets_sha256', 'original_cameras_sha256',
            'original_trace_sha256', 'original_frame_map_sha256')
    tables = []
    for name, key in zip(expected, keys):
        path = attempt / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'{name} missing or redirected')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt.get(key):
            raise ValueError(f'{name} hash mismatch')
        try:
            tables.append([json.loads(line) for line in raw.decode('utf-8').splitlines() if line])
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'{name} decode failed') from exc
    histories, packets, cameras, traces, frame_maps = tables
    count = receipt.get('frame_count')
    if count != 900 or any(len(table) != count for table in tables):
        raise ValueError('original acquisition frame count mismatch')
    first = receipt.get('first_original_frame')
    if type(first) is not int or receipt.get('last_original_frame') != first + count - 1:
        raise ValueError('original acquisition frame range mismatch')
    for offset, (row, packet, camera) in enumerate(zip(histories, packets, cameras)):
        frame = first + offset
        if any(item.get('original_frame') != frame for item in (row, packet, camera)):
            raise ValueError('original acquisition frame join mismatch')
        source = json.dumps(packet, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if row.get('source_sha256') != hashlib.sha256(source).hexdigest():
            raise ValueError('actor source packet mismatch')
        controls = packet.get('control')
        if not isinstance(controls, dict):
            raise ValueError('control source packet missing')
        for key in ('ego_target_speed_mps', 'crossing_target_speed_mps', 'crossing_release_s'):
            if controls.get(key) != receipt[key]:
                raise ValueError(f'original {key} control differs from exact case')
        control_source = json.dumps(controls, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if row.get('control_command_source_sha256') != hashlib.sha256(control_source).hexdigest():
            raise ValueError('control source packet mismatch')
        for role, key in (('ego', 'ego_id'), ('crossing_vehicle', 'crossing_vehicle_id'),
                          ('occupant', 'occupant_id'), ('property', 'property_id')):
            actor = packet.get('actors', {}).get(role, {})
            if str(actor.get('id')) != row.get(key):
                raise ValueError(f'{role} original actor join mismatch')
            if role in ('ego', 'occupant', 'property') and actor.get('xy') != row.get(role + '_xy'):
                raise ValueError(f'{role} original position join mismatch')
            if role in ('ego', 'crossing_vehicle') and actor.get('speed_mps') != row.get('ego_speed_mps' if role == 'ego' else 'crossing_speed_mps'):
                raise ValueError(f'{role} original speed join mismatch')
            if role in ('ego', 'crossing_vehicle', 'property') and actor.get('blueprint') != row.get('crossing_blueprint' if role == 'crossing_vehicle' else role + '_blueprint'):
                raise ValueError(f'{role} original blueprint join mismatch')
        if str(packet['actors']['occupant'].get('vehicle_id')) != row.get('occupant_vehicle_id'):
            raise ValueError('occupant original vehicle join mismatch')
        if row.get('map_sha256') != receipt.get('map_sha256') or row.get('camera_plan_sha256') != receipt.get('camera_plan_sha256'):
            raise ValueError('map or camera plan source mismatch')
        if abs(row.get('elapsed_seconds', float('nan')) - histories[0].get('elapsed_seconds', float('nan')) - offset / 20) > 0.001:
            raise ValueError('original elapsed-time join mismatch')
        camera_hashes = camera.get('camera_sha256')
        if not isinstance(camera_hashes, dict) or set(camera_hashes) != {'front', 'rear', 'left', 'right'} or not all(isinstance(h, str) and len(h) == 64 for h in camera_hashes.values()):
            raise ValueError('four original camera hashes missing')
        if row.get('case_id') != receipt.get('case_id') or row.get('site_sha256') != receipt.get('site_sha256'):
            raise ValueError('case or site source mismatch')
        ego = packet['actors']['ego']
        elapsed = row['elapsed_seconds'] - histories[0]['elapsed_seconds']
        expected_trace = {
                'frame': frame, 'time_s': elapsed,
                'position_m': [*ego['xy'], ego.get('z')],
                'position': {'x': ego['xy'][0], 'y': ego['xy'][1], 'z': ego.get('z')},
                'heading_deg': ego.get('heading_deg'), 'speed_mps': ego['speed_mps'],
                'speed_mph': ego['speed_mps'] / .44704}
        if any(traces[offset].get(key) != value for key, value in expected_trace.items()):
            raise ValueError('original trace source join mismatch')
        if frame_maps[offset] != {'video_frame': offset, 'carla_frame': frame, 'time_s': elapsed}:
            raise ValueError('original frame map source join mismatch')
    return {'case_id': receipt['case_id'], 'frame_count': count,
            'original_history_sha256': receipt['original_history_sha256'],
            'original_cameras_sha256': receipt['original_cameras_sha256'],
            'full_video_decode': False, 'actual_pixels': False,
            'physical_completion': False, 'legal_judgment': None}


def finalize_saved_measurements(attempt: Path, case) -> dict:
    """Measure original packets only after independent sealed-source rejoin."""
    from encounter import CASES, measure_history
    from native_acquisition import ASSIGNMENT

    if case not in CASES:
        raise ValueError('unknown exact case')
    receipt_path = attempt / 'native-receipt.json'
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError('native receipt missing or redirected')
    try:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('native receipt decode failed') from exc
    if (receipt.get('assignment_id') != ASSIGNMENT or
            receipt.get('case_id') != f'{ASSIGNMENT}__{case.case_id}'):
        raise ValueError('native receipt exact case mismatch')
    source = audit_native_acquisition(attempt, receipt)
    rows = [json.loads(line) for line in (attempt / 'original-history.jsonl').read_text(
        encoding='utf-8').splitlines() if line]
    measured = measure_history(rows, case)
    if measured['frame_count'] != source['frame_count']:
        raise ValueError('measurement source count mismatch')
    return {'assignment_id': ASSIGNMENT, 'case_id': receipt['case_id'],
            'original_history_sha256': source['original_history_sha256'],
            'native_receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            'source_audit': source, 'measurements': measured,
            'actual_pixels': False, 'physical_completion': False, 'legal_judgment': None}


def audit_saved_timing_pair(left_attempt: Path, right_attempt: Path,
                            comparison_id: str) -> dict:
    """Reopen both original attempts before a declared timing comparison.

    Distances describe physical trajectories only. They cannot establish a
    willful or wanton state or a statutory spacing threshold.
    """
    from encounter import CASES

    pairs = {
        'highway_person_north_timing': ('person_north_early', 'person_north_late'),
        'highway_person_south_timing': ('person_south_early', 'person_south_late'),
        'premises_person_timing': ('premises_person_early', 'premises_person_late'),
    }
    if comparison_id not in pairs:
        raise ValueError('unsupported exact timing comparison')
    by_id = {case.case_id: case for case in CASES}
    early_id, late_id = pairs[comparison_id]
    early = finalize_saved_measurements(left_attempt, by_id[early_id])
    late = finalize_saved_measurements(right_attempt, by_id[late_id])
    first = json.loads((left_attempt / 'native-receipt.json').read_text(encoding='utf-8'))
    second = json.loads((right_attempt / 'native-receipt.json').read_text(encoding='utf-8'))
    fixed = ('site_sha256', 'map_sha256', 'camera_plan_sha256',
             'public_access_basis', 'ego_target_speed_mps',
             'crossing_target_speed_mps', 'frame_count', 'original_fps')
    for key in fixed:
        if first.get(key) != second.get(key):
            raise ValueError(f'comparison fixed condition changed: {key}')
    # The actor blueprints are in the sealed original histories, not receipts.
    with (left_attempt / 'original-history.jsonl').open(encoding='utf-8') as source:
        first_row = json.loads(source.readline())
    with (right_attempt / 'original-history.jsonl').open(encoding='utf-8') as source:
        second_row = json.loads(source.readline())
    for key in ('ego_blueprint', 'crossing_blueprint', 'property_blueprint'):
        if first_row.get(key) != second_row.get(key):
            raise ValueError(f'comparison fixed condition changed: {key}')
    if first['crossing_release_s'] >= second['crossing_release_s']:
        raise ValueError('comparison release order missing')
    a = early['measurements']['min_ego_occupant_center_distance_m']
    b = late['measurements']['min_ego_occupant_center_distance_m']
    if abs(a - b) <= 1e-6:
        raise ValueError('comparison measured encounter difference missing')
    return {'comparison_id': comparison_id,
            'case_ids': [early['case_id'], late['case_id']],
            'original_history_sha256': [early['original_history_sha256'],
                                        late['original_history_sha256']],
            'native_receipt_sha256': [early['native_receipt_sha256'],
                                      late['native_receipt_sha256']],
            'crossing_release_s': [first['crossing_release_s'], second['crossing_release_s']],
            'min_ego_occupant_center_distance_m': [a, b],
            'actual_pixels': False, 'physical_completion': False,
            'legal_judgment': None}


def audit_saved_property_pair(near_attempt: Path, far_attempt: Path) -> dict:
    """Reopen both sealed captures for the declared property-position pair.

    This compares measured center distances, without inferring damage, risk,
    visibility, or the driver's state of mind from position alone.
    """
    from encounter import CASES

    by_id = {case.case_id: case for case in CASES}
    near = finalize_saved_measurements(near_attempt, by_id['property_near'])
    far = finalize_saved_measurements(far_attempt, by_id['property_far'])
    receipts = [json.loads((path / 'native-receipt.json').read_text(encoding='utf-8'))
                for path in (near_attempt, far_attempt)]
    fixed_receipt = ('site_sha256', 'map_sha256', 'camera_plan_sha256',
                     'public_access_basis', 'ego_target_speed_mps',
                     'crossing_target_speed_mps', 'crossing_release_s',
                     'frame_count', 'original_fps')
    for key in fixed_receipt:
        if receipts[0].get(key) != receipts[1].get(key):
            raise ValueError(f'comparison fixed condition changed: {key}')
    first_rows = []
    for path in (near_attempt, far_attempt):
        with (path / 'original-history.jsonl').open(encoding='utf-8') as source:
            first_rows.append(json.loads(source.readline()))
    fixed_actor = ('ego_blueprint', 'crossing_blueprint', 'property_blueprint',
                   'ego_id', 'crossing_vehicle_id', 'occupant_id',
                   'occupant_vehicle_id', 'ego_xy', 'occupant_xy')
    for key in fixed_actor:
        if first_rows[0].get(key) != first_rows[1].get(key):
            raise ValueError(f'comparison fixed condition changed: {key}')
    if first_rows[0].get('property_xy') == first_rows[1].get('property_xy'):
        raise ValueError('comparison property position difference missing')
    a = near['measurements']['min_ego_property_center_distance_m']
    b = far['measurements']['min_ego_property_center_distance_m']
    if not a < b:
        raise ValueError('comparison measured near/far property order missing')
    return {'comparison_id': 'highway_property_position',
            'case_ids': [near['case_id'], far['case_id']],
            'original_history_sha256': [near['original_history_sha256'],
                                        far['original_history_sha256']],
            'native_receipt_sha256': [near['native_receipt_sha256'],
                                      far['native_receipt_sha256']],
            'first_property_xy': [first_rows[0]['property_xy'],
                                  first_rows[1]['property_xy']],
            'min_ego_property_center_distance_m': [a, b],
            'actual_pixels': False, 'physical_completion': False,
            'legal_judgment': None}


def audit_saved_approach_pair(north_attempt: Path, south_attempt: Path) -> dict:
    """Reopen sealed highway attempts and compare observed ego approach vectors.

    Opposite motion is a measured contrast only. It does not establish that
    either maneuver was physically safe or legally willful or wanton.
    """
    from encounter import CASES

    by_id = {case.case_id: case for case in CASES}
    north = finalize_saved_measurements(north_attempt, by_id['person_north_early'])
    south = finalize_saved_measurements(south_attempt, by_id['person_south_early'])
    receipts = [json.loads((path / 'native-receipt.json').read_text(encoding='utf-8'))
                for path in (north_attempt, south_attempt)]
    fixed_receipt = ('site_sha256', 'map_sha256', 'camera_plan_sha256',
                     'public_access_basis', 'ego_target_speed_mps',
                     'crossing_target_speed_mps', 'crossing_release_s',
                     'frame_count', 'original_fps')
    for key in fixed_receipt:
        if receipts[0].get(key) != receipts[1].get(key):
            raise ValueError(f'comparison fixed condition changed: {key}')
    if receipts[0].get('public_access_basis') != 'highway':
        raise ValueError('approach comparison requires sourced highway context')
    endpoints = []
    for path in (north_attempt, south_attempt):
        with (path / 'original-history.jsonl').open(encoding='utf-8') as source:
            rows = [json.loads(line) for line in source]
        endpoints.append((rows[0], rows[-1]))
    fixed_actor = ('ego_blueprint', 'crossing_blueprint', 'property_blueprint',
                   'ego_id', 'crossing_vehicle_id', 'occupant_id',
                   'occupant_vehicle_id', 'property_id', 'occupant_xy', 'property_xy')
    for key in fixed_actor:
        if endpoints[0][0].get(key) != endpoints[1][0].get(key):
            raise ValueError(f'comparison fixed condition changed: {key}')
    vectors = []
    for first, last in endpoints:
        a, b = first['ego_xy'], last['ego_xy']
        vector = (b[0] - a[0], b[1] - a[1])
        length = math.hypot(*vector)
        if length <= 1.0:
            raise ValueError('comparison original ego approach motion missing')
        vectors.append((vector, length))
    cosine = sum(a * b for a, b in zip(vectors[0][0], vectors[1][0])) / (
        vectors[0][1] * vectors[1][1])
    if cosine >= -0.5:
        raise ValueError('comparison observed approach directions not opposed')
    return {'comparison_id': 'highway_person_approach_direction',
            'case_ids': [north['case_id'], south['case_id']],
            'original_history_sha256': [north['original_history_sha256'],
                                        south['original_history_sha256']],
            'native_receipt_sha256': [north['native_receipt_sha256'],
                                      south['native_receipt_sha256']],
            'ego_displacement_xy_m': [list(vectors[0][0]), list(vectors[1][0])],
            'direction_cosine': cosine, 'actual_pixels': False,
            'physical_completion': False, 'legal_judgment': None}
