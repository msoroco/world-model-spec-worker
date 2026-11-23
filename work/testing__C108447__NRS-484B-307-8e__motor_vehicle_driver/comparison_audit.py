"""Independent fixed-condition checks for property-bypass comparison packets."""
from __future__ import annotations


def audit(left: dict, right: dict, variable: str) -> dict:
    allowed = {'parcel_class', 'route_class', 'approach_state', 'destination_state', 'purpose'}
    if variable not in allowed:
        raise ValueError('undeclared comparison variable')
    common = ('map_id', 'actor_id', 'capture_profile', 'duration_frames', 'approach_device_id', 'destination_device_id')
    for field in common:
        if not left.get(field) or not right.get(field) or left[field] != right[field]:
            raise ValueError(f'fixed condition differs or absent: {field}')
    for field in allowed - {variable}:
        if field not in left or field not in right or left[field] != right[field]:
            raise ValueError(f'undeclared difference or absent condition: {field}')
    if variable not in left or variable not in right or left[variable] == right[variable]:
        raise ValueError('deliberate difference missing')
    for side in (left, right):
        if not side.get('trace_sha256') or not side.get('map_source_sha256') or not side.get('frame_map_sha256'):
            raise ValueError('source/trace/frame seals required')
        if side.get('map_source_sha256') != left.get('map_source_sha256'):
            raise ValueError('original map/property source differs')
    return {'comparison_variable': variable, 'fixed_conditions_checked': list(common) + sorted(allowed - {variable}), 'source_seals_checked': True, 'deliberate_difference_observed': True, 'legal_judgment': None}
