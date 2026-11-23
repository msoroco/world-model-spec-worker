"""Independent source-bound comparison of crossing facts, not legal outcomes."""
from __future__ import annotations

PAIRS = {
    'marked_vs_unmarked': ('marked_cross', 'unmarked_cross', 'marked', 'unmarked', 'none', 'none', True, True),
    'contrary_device_choice': ('other_device_stop', 'other_device_cross', 'marked', 'marked', 'DONT_WALK', 'DONT_WALK', False, True),
    'crosswalk_boundary': ('marked_cross', 'outside_cross', 'marked', 'marked', 'none', 'none', True, False),
}


class ComparisonError(ValueError):
    pass


def audit_pair(comparison_id, left, right):
    if comparison_id not in PAIRS:
        raise ComparisonError('unknown comparison')
    ln, rn, lk, rk, ld, rd, le, re = PAIRS[comparison_id]
    if (left.get('case_suffix'), right.get('case_suffix')) != (ln, rn):
        raise ComparisonError('wrong exact cases')
    for key in ('map_source_sha256', 'signal_source_sha256', 'device_inventory_source_sha256',
                'highway_polygon_source_sha256', 'camera_profile_sha256', 'duration_frames'):
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError('fixed condition differs: ' + key)
    for row, kind, device, entry, name in ((left, lk, ld, le, ln), (right, rk, rd, re, rn)):
        if row.get('crosswalk_kind') != kind:
            raise ComparisonError('crosswalk kind mismatch: ' + name)
        if row.get('green_alone_frames') != row['duration_frames']:
            raise ComparisonError('circular green alone not evidenced throughout: ' + name)
        observed = row.get('first_highway_entry')
        if (observed is not None) != entry:
            raise ComparisonError('highway entry mismatch: ' + name)
        if observed:
            if observed.get('other_device_indication') != device:
                raise ComparisonError('other device state mismatch: ' + name)
            if observed.get('in_crosswalk') is not (name != 'outside_cross'):
                raise ComparisonError('crosswalk location mismatch: ' + name)
        elif row.get('device_indication_while_waiting') != device:
            raise ComparisonError('device state while waiting mismatch: ' + name)
    return {'comparison_id': comparison_id, 'fixed_conditions_checked': 6,
            'legal_verdict': None, 'physical_acceptance': False}
