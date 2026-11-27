"""Independent comparison checks over source-bound original observations."""

import argparse
import json
from pathlib import Path

from interference import require


ASSIGNMENT = 'testing__C147344__NRS-484B-270-7a__cycle_or_scooter_operator'
PAIRS = {
    'merge_effect': ('planned_merge_braking', 'planned_merge_no_braking'),
    'intent_source': ('planned_merge_braking', 'ordinary_merge_braking'),
    'merge_presence': ('ordinary_merge_braking', 'hold_lane_braking'),
}


def audit(comparison_id, left, right):
    """Reject lost fixed conditions and missing original observation sources."""
    require(comparison_id in PAIRS, 'unknown exact comparison')
    expected = [ASSIGNMENT + '__' + slug for slug in PAIRS[comparison_id]]
    require([left.get('case_id'), right.get('case_id')] == expected,
            'comparison exact cases differ')
    a = left.get('observation')
    b = right.get('observation')
    require(isinstance(a, dict) and isinstance(b, dict),
            'source-bound original observations missing')
    require(a.get('case_id') == PAIRS[comparison_id][0] and
            b.get('case_id') == PAIRS[comparison_id][1] and
            a.get('frame_count') == b.get('frame_count') == 600,
            'original sample identities differ')
    for field in ('bicycle_id', 'motor_vehicle_id',
                  'reviewed_road_source_sha256',
                  'electric_bicycle_classification_source_sha256',
                  'motor_vehicle_classification_source_sha256'):
        require(a.get(field) and a[field] == b.get(field),
                'fixed original source differs: ' + field)
    for report in (left, right):
        require(report.get('original_sources_sha256') and
                report.get('physical_acceptance_claimed') is False and
                report.get('legal_judgment') is None,
                'original source seal or review separation missing')
    if comparison_id == 'merge_effect':
        require(a['requested_bicycle_path'] == b['requested_bicycle_path']
                == 'merge' and
                a['requested_motor_response'] == 'brake' and
                b['requested_motor_response'] == 'continue' and
                a['route_geometry_source_sha256'] ==
                b['route_geometry_source_sha256'] and
                a['declared_intention'] == b['declared_intention'],
                'motor-response contrast lost fixed bicycle path or intent')
    elif comparison_id == 'intent_source':
        require(a['requested_bicycle_path'] == b['requested_bicycle_path']
                == 'merge' and
                a['requested_motor_response'] ==
                b['requested_motor_response'] == 'brake' and
                a['route_geometry_source_sha256'] ==
                b['route_geometry_source_sha256'] and
                a['declared_intention'] is not None and
                b['declared_intention'] is None,
                'authored-intent contrast lost fixed physical request')
    else:
        require(a['requested_bicycle_path'] == 'merge' and
                b['requested_bicycle_path'] == 'hold' and
                a['requested_motor_response'] ==
                b['requested_motor_response'] == 'brake' and
                a['declared_intention'] is None and
                b['declared_intention'] is None,
                'merge-presence contrast lost fixed motor response')
    return {'format': 'worker-c147344-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': expected,
            'original_source_hashes': [left['original_sources_sha256'],
                                       right['original_sources_sha256']],
            'fixed_conditions_checked': True,
            'deliberate_difference_checked': True,
            'physical_acceptance_claimed': False,
            'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'retain prior comparison audit')
    result = audit(args.comparison, json.loads(args.left.read_text()),
                   json.loads(args.right.read_text()))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
