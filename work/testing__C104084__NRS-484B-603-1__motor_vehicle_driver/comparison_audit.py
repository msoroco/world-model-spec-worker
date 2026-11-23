"""Independent physical comparison of two source-bound crest speed packets."""
from __future__ import annotations

from crest_speed import measure


FIXED = ('map_source_sha256', 'ego_route_source_sha256',
         'other_route_source_sha256', 'other_motion_source_sha256',
         'highway_context_source_sha256', 'prescribed_limit_source_sha256',
         'camera_contract_sha256', 'duration_s', 'initial_speed_mps')


def compare(left, right, *, expected_profiles):
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError('two original capture packets required')
    if [left.get('profile'), right.get('profile')] != list(expected_profiles):
        raise ValueError('exact comparison profiles differ')
    for field in FIXED:
        if left.get(field) is None or left.get(field) != right.get(field):
            raise ValueError(f'fixed condition differs or is missing: {field}')
    if left.get('capture_id') == right.get('capture_id') or not all(
            packet.get('capture_id') for packet in (left, right)):
        raise ValueError('two distinct original captures required')
    measured = [measure(packet.get('waypoints'), packet.get('frames'),
                        approach_start_m=packet.get('approach_start_m'))
                for packet in (left, right)]
    if any(m['initial_speed_mps'] != packet['initial_speed_mps']
           for m, packet in zip(measured, (left, right))):
        raise ValueError('declared initial speed differs from original motion')
    if measured[0]['crest_station_m'] != measured[1]['crest_station_m']:
        raise ValueError('measured crest station differs')
    if measured[0]['speed_change_mps'] == measured[1]['speed_change_mps'] and \
            measured[0]['first_speed_decrease_frame_id'] == measured[1]['first_speed_decrease_frame_id']:
        raise ValueError('declared speed-profile difference was not measured')
    return {'comparison_profiles': list(expected_profiles),
            'capture_ids': [left['capture_id'], right['capture_id']],
            'physical_measurements': measured,
            'legal_limit': 'No conclusion on necessary decrease, due care or compliance.'}
