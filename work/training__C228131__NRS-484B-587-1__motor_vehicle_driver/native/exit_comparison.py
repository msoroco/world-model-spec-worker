"""Compare separately measured from-highway exits without assigning a verdict.

This unselected comparison is usable only after each candidate's saved source
auditor has produced its own exit facts. It does not bind an actor to C62507.
"""
from exit_finalize import AUTHORITY, observation


def compare_facts(indicated, outside):
    for label, facts in (('indicated', indicated), ('outside', outside)):
        if (facts.get('frame_count') != 600 or facts.get('four_camera_joins') != 2400
                or len(facts.get('exit_events', [])) != 1):
            raise ValueError(label + ' original exit measurement incomplete')
        if (facts.get('access_review_status') != facts.get('device_review_status')
                or facts.get('access_review_status') not in
                ('synthetic_diagnostic', 'independently_reviewed')):
            raise ValueError(label + ' access/device review mismatch')
        if facts.get('physical_completion_verified') is not False or facts.get('legal_result') is not None:
            raise ValueError(label + ' exit facts claim unverified acceptance')
    if indicated.get('source_kind') != outside.get('source_kind'):
        raise ValueError('Exit comparison mixes original and diagnostic sources')
    fixed = ('road.xodr', *AUTHORITY)
    for source in fixed:
        if (not indicated.get('source_sha256', {}).get(source)
                or indicated['source_sha256'][source] != outside.get('source_sha256', {}).get(source)):
            raise ValueError('Exit comparison fixed source differs: ' + source)
    first = indicated['exit_events'][0]
    second = outside['exit_events'][0]
    if first.get('within_indicated_exit') is not True or second.get('within_indicated_exit') is not False:
        raise ValueError('Exit comparison lacks indicated/outside contrast')
    if first.get('measured_center_x_m') == second.get('measured_center_x_m'):
        raise ValueError('Exit comparison lacks measured crossing difference')
    return {'format': 'nrs-484b-587-1-unselected-exit-comparison-v1',
            'source_kind': indicated['source_kind'], 'fixed_source_paths': list(fixed),
            'indicated_exit_event': first, 'outside_exit_event': second,
            'physical_completion_verified': False, 'legal_result': None,
            'selected_for_delivery': False}


def compare_attempts(indicated_root, outside_root):
    return compare_facts(observation(indicated_root), observation(outside_root))
