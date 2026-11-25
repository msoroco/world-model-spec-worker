"""Independent original-frame and controlled-pair audits for the trail cases."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Mapping


FIXED = ('cell_id', 'map_sha256', 'corridor_source_sha256', 'route_sha256',
         'vehicle_blueprint', 'operator_source_sha256', 'camera_plan_sha256',
         'duration_frames')
CONDITIONS = ('official_plan_designation', 'city_trail_dedication',
              'prohibits_motor_vehicles', 'emergency_use', 'maintenance_use')
CASE_CONDITIONS = {
    'all_prerequisites': (True, True, True, False, False),
    'not_designated': (False, True, True, False, False),
    'not_dedicated': (True, False, True, False, False),
    'no_prohibition_sign': (True, True, False, False, False),
    'emergency_vehicle': (True, True, True, True, False),
    'maintenance_vehicle': (True, True, True, False, True),
}
ASSIGNMENT_ID = 'testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver'


def _case_suffix(case_id: str) -> str:
    prefix = ASSIGNMENT_ID + '__'
    if not isinstance(case_id, str) or not case_id.startswith(prefix):
        raise ValueError('foreign exact case')
    suffix = case_id[len(prefix):]
    if suffix not in CASE_CONDITIONS:
        raise ValueError('unknown exact case')
    return suffix


def audit_history(path: Path, expected_sha256: str, case_id: str,
                  expected_frames: int = 900) -> dict:
    suffix = _case_suffix(case_id)
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
    observed = tuple(baseline[key] for key in CONDITIONS)
    if any(type(value) is not bool for value in observed) or observed != CASE_CONDITIONS[suffix]:
        raise ValueError('recorded conditions differ from exact case')
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
        suffix = _case_suffix(side.get('case_id'))
        if tuple(side.get(key) for key in CONDITIONS) != CASE_CONDITIONS[suffix]:
            raise ValueError('comparison conditions differ from exact case')
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
    if left[variable_source] == right[variable_source]:
        raise ValueError('difference has no distinct source')
    if left.get('case_id') == right.get('case_id'):
        raise ValueError('same exact case twice')
    return {'case_ids': [left['case_id'], right['case_id']],
            'difference': deliberate_difference,
            'source_hashes': [left['original_history_sha256'], right['original_history_sha256']],
            'legal_judgment': None}


def audit_packet_join(history_path, history_sha256, packet_path, packet_sha256,
                      corridor_box, case_id):
    """Independently bind every observed trail row to its original tick packet."""
    history_path, packet_path = Path(history_path), Path(packet_path)
    if hashlib.sha256(history_path.read_bytes()).hexdigest() != history_sha256:
        raise ValueError('original history hash mismatch')
    packet_bytes = packet_path.read_bytes()
    if hashlib.sha256(packet_bytes).hexdigest() != packet_sha256:
        raise ValueError('original packet stream hash mismatch')
    history = [json.loads(line) for line in history_path.read_text().splitlines() if line]
    packets = packet_bytes.splitlines(keepends=True)
    if len(history) != len(packets) or len(history) != 900:
        raise ValueError('original packet/history frame count mismatch')
    if (not isinstance(corridor_box, list) or len(corridor_box) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in corridor_box) or
            corridor_box[0] >= corridor_box[2] or corridor_box[1] >= corridor_box[3]):
        raise ValueError('reviewed corridor geometry missing')
    previous = None
    for index, (row, raw) in enumerate(zip(history, packets)):
        if hashlib.sha256(raw).hexdigest() != row.get('native_packet_sha256'):
            raise ValueError('history/packet hash join mismatch')
        packet = json.loads(raw)
        if (row.get('case_id') != case_id or row.get('original_frame') != packet.get('frame') or
                row.get('time_s') != packet.get('time_s') or
                row.get('vehicle_id') != packet.get('vehicle_id') or
                row.get('sign_face_visible') != packet.get('sign_face_visible')):
            raise ValueError('history/original packet identity or clock mismatch')
        point = packet.get('location_xy')
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
            raise ValueError('original packet location missing')
        inside = (corridor_box[0] <= point[0] <= corridor_box[2] and
                  corridor_box[1] <= point[1] <= corridor_box[3])
        if row.get('vehicle_inside_corridor') is not inside:
            raise ValueError('history/original packet corridor observation mismatch')
        frame, time_s = packet['frame'], packet['time_s']
        if previous is not None and (frame != previous[0] + 1 or
                                     not .049 <= time_s - previous[1] <= .051):
            raise ValueError('original packet 20 Hz clock discontinuity')
        previous = frame, time_s
    audited = audit_history(history_path, history_sha256, case_id)
    return {'case_id': case_id, 'original_history_sha256': history_sha256,
            'original_packets_sha256': packet_sha256, 'joined_frames': len(history),
            'entered_corridor': audited['entered_corridor'],
            'physical_video_visibility_verified': False, 'legal_judgment': None}
