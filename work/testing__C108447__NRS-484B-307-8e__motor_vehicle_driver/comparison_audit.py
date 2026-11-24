"""Independent fixed-condition checks for property-bypass comparison packets."""
from __future__ import annotations

PREFIX = 'testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__'
PAIRS = {
    'public_vs_private_property': ('public_bypass', 'parcel_class', 'private', 'public'),
    'property_vs_roadway_route': ('ordinary_crossing', 'route_class', 'property', 'roadway'),
    'approach_signal_activation': ('no_approach_red', 'approach_state', 'red_alone', ('green', 'yellow', 'dark')),
    'destination_signal_condition': ('destination_red', 'destination_state', ('green', 'yellow', 'dark'), ('red_alone', 'red_combined')),
    'avoidance_purpose': ('other_purpose', 'purpose', 'avoid_red', 'other'),
}


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


def audit_planned(reference: dict, contrast: dict, comparison_id: str) -> dict:
    """Bind the fixed-condition audit to one of the five exact planned pairs."""
    if comparison_id not in PAIRS:
        raise ValueError('unknown exact comparison')
    suffix, variable, reference_value, contrast_value = PAIRS[comparison_id]
    if reference.get('case_id') != PREFIX + 'private_bypass' or contrast.get('case_id') != PREFIX + suffix:
        raise ValueError('exact comparison case pair differs')
    expected_reference = reference_value if isinstance(reference_value, tuple) else (reference_value,)
    expected_contrast = contrast_value if isinstance(contrast_value, tuple) else (contrast_value,)
    if reference.get(variable) not in expected_reference or contrast.get(variable) not in expected_contrast:
        raise ValueError('planned observed comparison values differ')
    result = audit(reference, contrast, variable)
    return {'format': 'property-comparison-audit-v1', 'comparison_id': comparison_id,
            'case_ids': [reference['case_id'], contrast['case_id']], **result}
