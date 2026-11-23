"""Independent pair checks against exact controlled-difference declarations."""
from crossing_geometry import validate_scene


ALLOWED = {
    'right_angle_vs_neither': {'route_xy_m', 'construction_intent', 'case_id'},
    'shortest_vs_neither': {'route_xy_m', 'construction_intent', 'case_id'},
    'outside_vs_crosswalk_exception': {'crosswalk_boundaries_xy_m', 'crosswalk_context',
                                       'construction_intent', 'case_id'},
}


def audit_pair(comparison_id, left, right):
    validate_scene(left)
    validate_scene(right)
    if comparison_id not in ALLOWED:
        raise ValueError('unknown comparison')
    if left['case_id'] == right['case_id']:
        raise ValueError('comparison needs distinct cases')
    changed = {key for key in set(left) | set(right) if left.get(key) != right.get(key)}
    unreviewed = changed - ALLOWED[comparison_id]
    if unreviewed:
        raise ValueError('unreviewed comparison changes: ' + ', '.join(sorted(unreviewed)))
    required = ALLOWED[comparison_id] - {'construction_intent', 'case_id'}
    if not changed & required:
        raise ValueError('declared comparison variable did not change')
    return {'comparison_id': comparison_id, 'changed_fields': sorted(changed),
            'fixed_fields_checked': sorted(set(left) & set(right) - changed),
            'legal_judgment': 'unresolved', 'physical_realization': 'unconfirmed'}
