"""In-memory audit unit fixtures; never an original capture or acceptance report."""
from __future__ import annotations

import copy

from comparison_audit import AID, PAIRS, audit_pair


def report(suffix):
    design = {'power': 'combustion', 'wheel_count': 4,
              'designed_for_wheel_count': 4}
    if suffix.startswith('electric_three_wheel_'):
        design = {'power': 'solely_electric', 'wheel_count': 3,
                  'designed_for_wheel_count': 3}
    role = {'electric_three_wheel_emergency': 'emergency',
            'electric_three_wheel_law_officer': 'law_officer',
            'electric_three_wheel_security_guard': 'security_guard'}.get(suffix, 'ordinary')
    entrance = {'permanent_driveway_crossing': 'permanent_driveway',
                'temporary_driveway_crossing': 'temporary_driveway',
                'alley_entrance_crossing': 'alley_entrance'}.get(suffix)
    return {'format': 'worker-delivery-audit', 'passed': True,
            'protocol_fixture_checked': False, 'physical_acceptance_claimed': True,
            'case_id': AID + '__' + suffix, 'frame_count': 900,
            'comparison_record': {
                'source_kind': 'original_native_capture', 'fixed_source_sha256': {'map': 'unit-only'},
                'camera_plan': ['four-view-unit-only'], 'duration_s': 45,
                'frame_count': 900, 'requested_relation': suffix,
                'maximum_sidewalk_body_overlap_m2': 0 if suffix == 'ordinary_road_travel' else 2,
                'maximum_entrance_body_overlap_m2': {
                    name: 1 if name == entrance else 0 for name in
                    ('permanent_driveway', 'temporary_driveway', 'alley_entrance')},
                'vehicle_design': design,
                'body_geometry_source_sha256': 'three-wheel' if design['wheel_count'] == 3 else 'four-wheel',
                'operator_context': {'role': role,
                                     'authorized': role != 'ordinary',
                                     'on_official_duty': role in ('law_officer', 'security_guard'),
                                     'operated_as_authorized_emergency_vehicle': role == 'emergency'}}}


def main():
    for comparison_id, suffixes in PAIRS.items():
        reports = {AID + '__' + suffix: report(suffix) for suffix in suffixes}
        result = audit_pair(comparison_id, reports)
        if not result['physical_comparison_passed'] or result['legal_verdict_claimed']:
            raise ValueError('comparison unit fixture misclassified')
        changed = copy.deepcopy(reports)
        changed[AID + '__' + suffixes[1]]['comparison_record']['fixed_source_sha256']['map'] = 'changed'
        try:
            audit_pair(comparison_id, changed)
        except ValueError as error:
            if 'changed fixed original condition' not in str(error):
                raise
        else:
            raise ValueError('changed fixed map source accepted')
        changed = copy.deepcopy(reports)
        changed[AID + '__' + suffixes[1]]['passed'] = False
        try:
            audit_pair(comparison_id, changed)
        except ValueError as error:
            if 'original accepted report required' not in str(error):
                raise
        else:
            raise ValueError('nonaccepted report accepted')
        print(comparison_id, 'positive_unit_fixture', 'changed_fixed_source_rejected',
              'nonaccepted_report_rejected')


if __name__ == '__main__':
    main()
