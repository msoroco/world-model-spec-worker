"""Independent source-presence and fixed-condition checks for crest comparisons.

This checker verifies recorded packet isolation only. It does not adjudicate the
statutory hazard-distance phrase or certify physical capture quality.
"""
import json
from pathlib import Path

REQUIRED = ('case_id', 'source_ref', 'law_id', 'actor', 'map_source', 'camera_profile',
            'duration_frames', 'crest_grade_sha256', 'ego_route_sha256',
            'other_route_sha256', 'other_timing_sha256', 'lane_allocation',
            'ego_left_side_observed', 'sampled_grade_blocks_proxy_ray')
COMPARISONS = {
    'left_side_motion': {
        'suffixes': ('right_crest_obstructed', 'left_crest_obstructed'),
        'fixed': ('law_id', 'actor', 'map_source', 'camera_profile', 'duration_frames',
                  'crest_grade_sha256', 'other_route_sha256', 'other_timing_sha256',
                  'lane_allocation', 'sampled_grade_blocks_proxy_ray'),
        'difference': ('ego_left_side_observed',),
    },
    'crest_view_obstruction': {
        'suffixes': ('left_crest_obstructed', 'left_crest_clear'),
        'fixed': ('law_id', 'actor', 'camera_profile', 'duration_frames',
                  'ego_route_sha256', 'other_route_sha256', 'other_timing_sha256',
                  'lane_allocation', 'ego_left_side_observed'),
        'difference': ('crest_grade_sha256', 'sampled_grade_blocks_proxy_ray'),
    },
    'one_way_exception': {
        'suffixes': ('left_crest_obstructed', 'left_one_way_obstructed'),
        'fixed': ('law_id', 'actor', 'camera_profile', 'duration_frames',
                  'ego_left_side_observed', 'sampled_grade_blocks_proxy_ray'),
        'difference': ('lane_allocation',),
    },
}


def audit(comparison_id, first, second, assignment_id):
    spec = COMPARISONS[comparison_id]
    for packet, suffix in zip((first, second), spec['suffixes']):
        if not isinstance(packet, dict) or any(k not in packet or packet[k] is None for k in REQUIRED):
            raise ValueError('missing source-bound comparison packet field')
        if packet['case_id'] != f'{assignment_id}__{suffix}' or not packet['source_ref']:
            raise ValueError('wrong exact case or missing original source')
        if packet['law_id'] != 'NRS-484B-213-2a' or packet['actor'] != 'motor_vehicle_driver':
            raise ValueError('law or actor drift')
        if packet['lane_allocation'] not in ('two_way', 'one_way') or type(packet['ego_left_side_observed']) is not bool or type(packet['sampled_grade_blocks_proxy_ray']) is not bool:
            raise ValueError('invalid observed lane or body state')
    for field in spec['fixed']:
        if first[field] != second[field]:
            raise ValueError(f'confounded fixed condition: {field}')
    for field in spec['difference']:
        if first[field] == second[field]:
            raise ValueError(f'missing deliberate difference: {field}')
    if comparison_id != 'one_way_exception' and any(p['lane_allocation'] != 'two_way' for p in (first, second)):
        raise ValueError('two-way comparison lacks opposing lane')
    if comparison_id == 'left_side_motion' and (first['ego_left_side_observed'], second['ego_left_side_observed']) != (False, True):
        raise ValueError('left-side motion order wrong')
    if comparison_id == 'crest_view_obstruction' and (first['sampled_grade_blocks_proxy_ray'], second['sampled_grade_blocks_proxy_ray']) != (True, False):
        raise ValueError('crest proxy-ray comparison order wrong')
    if comparison_id == 'one_way_exception' and (first['lane_allocation'], second['lane_allocation']) != ('two_way', 'one_way'):
        raise ValueError('one-way exception order wrong')
    return {'comparison_id': comparison_id, 'passed': True,
            'scope': 'source-packet field isolation only; physical and legal review pending'}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True, choices=COMPARISONS)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--assignment', required=True)
    args = parser.parse_args()
    result = audit(args.comparison, json.loads(Path(args.first).read_text()),
                   json.loads(Path(args.second).read_text()), args.assignment)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
