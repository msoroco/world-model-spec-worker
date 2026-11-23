"""Independent comparison of source-measured arrow-turn attempts."""
from __future__ import annotations


class ComparisonError(ValueError):
    pass


PAIRS = {
    'pedestrian_yield': ('yield_pedestrian', 'continue_pedestrian'),
    'pedestrian_presence': ('clear_crosswalk_turn', 'yield_pedestrian'),
    'arrow_movement': ('clear_crosswalk_turn', 'wrong_movement'),
    'other_traffic_yield': ('yield_other_traffic', 'continue_other_traffic'),
}


def audit_pair(comparison_id, left, right):
    if comparison_id not in PAIRS:
        raise ComparisonError('unknown comparison')
    if (left.get('case_suffix'), right.get('case_suffix')) != PAIRS[comparison_id]:
        raise ComparisonError('wrong case pair')
    fixed = ('map_sha256', 'ego_signal_sha256', 'opposing_signal_sha256',
             'crosswalk_sha256', 'camera_profile_sha256', 'duration_frames',
             'arrow_direction', 'pedestrian_permission_sha256')
    for key in fixed:
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError('fixed source differs: ' + key)
    for row in (left, right):
        if row.get('original_signal_frames') != row['duration_frames']:
            raise ComparisonError('red plus arrow or opposing red incomplete')
        if not row.get('first_ego_entry'):
            raise ComparisonError('ego entry not measured')
    if comparison_id == 'pedestrian_yield':
        for row in (left, right):
            if not row.get('pedestrian_lawfully_inside_at_approach'):
                raise ComparisonError('pedestrian comparison lacks lawful crosswalk occupant')
        if not left.get('held_until_clear') or right.get('held_until_clear'):
            raise ComparisonError('yield difference not observed')
    elif comparison_id == 'pedestrian_presence':
        if left.get('pedestrian_lawfully_inside_at_approach') or not right.get('pedestrian_lawfully_inside_at_approach'):
            raise ComparisonError('crosswalk occupancy difference not observed')
        if left.get('actual_route') != 'arrow_turn' or right.get('actual_route') != 'arrow_turn':
            raise ComparisonError('turn movement not fixed')
    elif comparison_id == 'arrow_movement':
        if left.get('actual_route') != 'arrow_turn' or right.get('actual_route') != 'straight':
            raise ComparisonError('movement difference not observed')
        if left.get('pedestrian_lawfully_inside_at_approach') or right.get('pedestrian_lawfully_inside_at_approach'):
            raise ComparisonError('pedestrian condition not fixed')
    else:
        for row in (left, right):
            if not row.get('other_traffic_lawfully_in_intersection_at_approach'):
                raise ComparisonError('lawful other traffic not observed')
            if row.get('pedestrian_lawfully_inside_at_approach'):
                raise ComparisonError('pedestrian condition not fixed')
        if not left.get('held_until_clear') or right.get('held_until_clear'):
            raise ComparisonError('other traffic yield difference not observed')
    return {'comparison_id': comparison_id, 'fixed_sources_checked': len(fixed),
            'physical_acceptance': False, 'legal_verdict': None}
