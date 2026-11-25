"""Independent engineering comparison of original 307(9)(b) attempt summaries."""

PAIRS = {
    'complete_cycle_count': ('two_cycles_clear', 'one_cycle_entry', 'full_cycles_after_stop', (2, 1)),
    'complete_cycle_count_above': ('two_cycles_clear', 'three_cycles_clear', 'full_cycles_after_stop', (2, 3)),
    'stopping_event': ('two_cycles_clear', 'rolling_entry', 'stopped_frame', ('present', 'absent')),
    'causal_record': ('two_cycles_clear', 'no_causal_record', 'unchanged_signal_cause', ('failed_detection', 'not_established')),
    'crosswalk_yield': ('two_cycles_clear', 'pedestrian_crosswalk', 'other_user_region', ('clear', 'adjacent_crosswalk')),
    'intersection_yield': ('two_cycles_clear', 'lawful_traffic', 'other_user_region', ('clear', 'intersection')),
}


class ComparisonError(ValueError):
    pass


def audit_pair(name, left, right):
    if name not in PAIRS:
        raise ComparisonError('unknown comparison')
    ls, rs, variable, values = PAIRS[name]
    if (left.get('case_suffix'), right.get('case_suffix')) != (ls, rs):
        raise ComparisonError('wrong exact case pair')
    fixed = ('map_sha256', 'route_sha256', 'signal_sha256', 'stop_sha256',
             'crosswalk_sha256', 'camera_profile_sha256', 'duration_frames',
             'official_head_id', 'ego_approach_id', 'actor_type_id')
    for key in fixed:
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError('fixed condition differs: ' + key)
    for record in (left, right):
        if record.get('initial_composite_phase') is not True:
            raise ComparisonError('official red plus arrow source missing')
        if record.get('entry_frame') is None:
            raise ComparisonError('entry event missing')
        if record.get('legal_permission_verdict') is not None or record.get('right_of_way_verdict') is not None:
            raise ComparisonError('unsupported legal finding')
        if not record.get('original_sources'):
            raise ComparisonError('original source references missing')
    if variable == 'stopped_frame':
        actual = ('present' if left.get(variable) is not None else 'absent',
                  'present' if right.get(variable) is not None else 'absent')
    else:
        actual = (left.get(variable), right.get(variable))
    if actual != values:
        raise ComparisonError('declared difference not measured: ' + variable)
    return {'comparison_id': name, 'fixed_conditions_checked': len(fixed),
            'measured_difference': variable, 'legal_verdict': None,
            'physical_acceptance': False}
