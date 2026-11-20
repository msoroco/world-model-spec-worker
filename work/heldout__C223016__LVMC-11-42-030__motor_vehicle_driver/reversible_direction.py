"""Source-bound direction measurements for prospective C223016 captures.

This module measures a device designation and a vehicle's travel direction.
It does not infer municipal authorization, visual legibility or a legal finding.
"""

from datetime import datetime
from math import hypot, isfinite


CASE_SUFFIXES = frozenset({
    'morning_east_with', 'morning_west_against',
    'evening_west_with', 'evening_east_against',
    'sign_east_with', 'sign_west_against',
    'marking_east_with', 'marking_west_against',
    'signal_east_with', 'signal_west_against',
    'centerline_east_with', 'centerline_west_against',
})
SOURCE_KINDS = frozenset({'sign', 'marking', 'barrier', 'lane_control_signal'})


def _unit(vector, label):
    if not isinstance(vector, (list, tuple)) or len(vector) != 2:
        raise ValueError(label + ' requires two source coordinates')
    if any(type(value) not in (int, float) or not isfinite(value) for value in vector):
        raise ValueError(label + ' coordinates must be finite')
    length = hypot(*vector)
    if length < 1e-6:
        raise ValueError(label + ' direction is unresolved')
    return [value / length for value in vector]


def measure_direction(rows, *, case_suffix, lane_id):
    """Join source frames and return observed alignment, without a legal label.

    Each row must contain original frame/time, civil-time provenance, measured
    actor velocity, lane ID and a same-frame device observation with source
    identity, governed lane, kind, designated vector and effective period.
    """
    if case_suffix not in CASE_SUFFIXES:
        raise ValueError('Unknown exact reversible-lane case')
    if type(lane_id) is not int or lane_id == 0:
        raise ValueError('Mapped travel lane identity required')
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError('Continuous original frame window required')
    result = []
    previous = None
    source_identity = None
    designation_identity = None
    previous_civil = None
    for row in rows:
        frame, stamp = row.get('frame'), row.get('time_s')
        if type(frame) is not int or frame < 0 or type(stamp) not in (int, float) or not isfinite(stamp):
            raise ValueError('Original frame/time unavailable')
        if previous is not None and (frame != previous[0] + 1 or stamp <= previous[1]):
            raise ValueError('Original frame/time join is discontinuous')
        previous = frame, stamp
        if row.get('lane_id') != lane_id:
            raise ValueError('Subject left the governed source lane')
        civil = row.get('civil_time')
        if not isinstance(civil, dict) or not civil.get('source') or not civil.get('iso8601'):
            raise ValueError('Civil-time source and timestamp required')
        try:
            civil_stamp = datetime.fromisoformat(civil['iso8601'])
        except (TypeError, ValueError) as error:
            raise ValueError('Civil-time timestamp is invalid') from error
        if civil_stamp.tzinfo is None or civil_stamp.utcoffset() is None:
            raise ValueError('Civil-time offset required')
        if previous_civil is not None and civil_stamp <= previous_civil:
            raise ValueError('Civil-time source did not advance with original frames')
        previous_civil = civil_stamp
        device = row.get('device')
        if not isinstance(device, dict) or device.get('kind') not in SOURCE_KINDS:
            raise ValueError('Original direction device source required')
        if device.get('governs_lane_id') != lane_id or not device.get('source_id'):
            raise ValueError('Device identity or lane governance unavailable')
        if not device.get('period_id') or device.get('effective') is not True:
            raise ValueError('Effective designation period must be source-observed')
        identity = device['source_id'], device['kind']
        designation = _unit(device.get('direction_xy'), 'Device designation')
        designation_key = device['period_id'], tuple(round(x, 8) for x in designation)
        if source_identity is None:
            source_identity = identity
        elif identity != source_identity:
            raise ValueError('Device source changed within comparison window')
        if designation_identity is None:
            designation_identity = designation_key
        elif designation_key != designation_identity:
            raise ValueError('Effective designation changed within comparison window')
        travel = _unit(row.get('subject_velocity_xy'), 'Subject velocity')
        dot = sum(a * b for a, b in zip(travel, designation))
        result.append({
            'frame': frame, 'time_s': stamp,
            'civil_time': civil['iso8601'], 'civil_time_source': civil['source'],
            'period_id': device['period_id'], 'device_source_id': device['source_id'],
            'device_kind': device['kind'], 'lane_id': lane_id,
            'travel_alignment': dot,
            'observed_direction': 'with_designation' if dot >= .95 else
                                  'against_designation' if dot <= -.95 else 'oblique',
            'legal_judgment': None,
        })
    return result
