"""Independent source-bound comparison of crossing facts, not legal outcomes."""
from __future__ import annotations

PAIRS = {
    'marked_vs_unmarked': ('marked_cross', 'unmarked_cross', 'marked', 'unmarked', 'none', 'none', True, True),
    'contrary_device_choice': ('other_device_stop', 'other_device_cross', 'marked', 'marked', 'DONT_WALK', 'DONT_WALK', False, True),
    'crosswalk_boundary': ('marked_cross', 'outside_cross', 'marked', 'marked', 'none', 'none', True, True),
}

DEVICE_ALTERNATIVES = {
    'device_alternative_walk_cross': ('walk_cross', 'walk', True),
    'device_alternative_flashing_countdown_cross':
        ('flashing_countdown_cross', 'flashing_countdown', True),
    'device_alternative_flashing_no_countdown_wait':
        ('flashing_no_countdown_wait', 'flashing_no_countdown', False),
    'device_alternative_walk_then_flash_continue':
        ('walk_then_flash_continue', 'walk', True),
    'device_alternative_walk_then_steady_continue':
        ('walk_then_steady_continue', 'walk', True),
}


class ComparisonError(ValueError):
    pass


def audit_pair(comparison_id, left, right):
    if comparison_id in DEVICE_ALTERNATIVES:
        return audit_device_alternative(comparison_id, left, right)
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


def audit_device_alternative(comparison_id, left, right):
    suffix, mode, enters = DEVICE_ALTERNATIVES[comparison_id]
    if (left.get('case_suffix'), right.get('case_suffix')) != ('marked_cross', suffix):
        raise ComparisonError('wrong exact device alternative cases')
    fixed = ('map_source_sha256', 'signal_source_sha256',
             'device_inventory_source_sha256', 'highway_polygon_source_sha256',
             'camera_profile_sha256', 'duration_frames')
    for key in fixed:
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError('fixed condition differs: ' + key)
    for row in (left, right):
        if row.get('crosswalk_kind') != 'marked' or row.get('green_alone_frames') != row['duration_frames']:
            raise ComparisonError('marked crosswalk or circular green observation missing')
        if row.get('source_bound') is not True:
            raise ComparisonError('original device timeline source binding missing')
    baseline = left.get('first_highway_entry')
    if not isinstance(baseline, dict) or baseline.get('in_crosswalk') is not True or baseline.get('other_device_indication') != 'none':
        raise ComparisonError('baseline entry facts missing')
    timeline = right.get('device_timeline')
    if not isinstance(timeline, dict) or timeline.get('format') != 'c111125-saved-device-timeline-v1':
        raise ComparisonError('saved original device timeline missing')
    if timeline.get('original_last_frame') - timeline.get('original_first_frame') + 1 != right['duration_frames']:
        raise ComparisonError('device timeline frame span differs')
    if (timeline.get('entry_frame') is not None) != enters or timeline.get('entry_device_mode') != (mode if enters else None):
        raise ComparisonError('device alternative entry mode differs')
    if enters:
        if timeline.get('entry_within_crosswalk') is not True or timeline.get('clearance_frame') is None:
            raise ComparisonError('device alternative crossing or clearance missing')
    elif right.get('first_highway_entry') is not None or right.get('device_indication_while_waiting') != 'DONT_WALK':
        raise ComparisonError('device alternative wait was not observed')
    if suffix == 'flashing_countdown_cross' and timeline.get('cleared_before_countdown_zero_observed') is not True:
        raise ComparisonError('countdown clearance before zero not observed')
    if suffix == 'walk_then_flash_continue' and timeline.get('cleared_before_steady_observed') is not True:
        raise ComparisonError('flashing continuation before steady not observed')
    if suffix == 'walk_then_steady_continue' and timeline.get('first_steady_frame') is None:
        raise ComparisonError('steady transition not observed')
    if timeline.get('legal_verdict') is not None or timeline.get('physical_acceptance') is not False:
        raise ComparisonError('device timeline makes unsupported acceptance claim')
    return {'comparison_id': comparison_id, 'fixed_conditions_checked': len(fixed),
            'device_mode_checked': mode, 'legal_verdict': None,
            'physical_acceptance': False}
