"""Independent original-source outer-lane maneuver control."""

import argparse
import json
from pathlib import Path

from turn_origin_comparison_audit import PREFIX, _source as turn_source
from center_use_comparison_audit import _source as straight_source


def audit(left_root, straight_root, *, decode_video=True):
    left = turn_source(left_root, PREFIX+'left_outer_east', decode_video=decode_video)
    straight = straight_source(straight_root, PREFIX+'straight_outer_east',
                               decode_video=decode_video)
    a, b = left['measurement'], straight['measurement']
    if a['origin_matches_center_lane'] or b['origin_matches_center_lane']:
        raise ValueError('Outer-lane control entered candidate center lane')
    fixed = ('approach_road_id', 'approach_lane_id', 'center_turn_lane_id',
             'designation_source', 'center_marking_source_ids')
    if any(a.get(key) != b.get(key) for key in fixed):
        raise ValueError('Outer-lane original fixed source condition differs')
    if (left['context'].get('requested_maneuver') != 'left turn' or
            straight['context'].get('requested_maneuver') != 'straight' or
            a['maximum_left_deflection_deg'] < 60 or
            not b['straight_motion_observed']):
        raise ValueError('Outer-lane maneuver difference not observed')
    if ([(r['is_junction'], r['time_s']-left['rows'][0]['time_s']) for r in left['rows']] !=
            [(r['is_junction'], r['time_s']-straight['rows'][0]['time_s']) for r in straight['rows']]):
        raise ValueError('Outer-lane original junction/time schedule differs')
    if [c['name'] for c in left['config']['cameras']] != [
            c['name'] for c in straight['config']['cameras']]:
        raise ValueError('Outer-lane four-camera contract differs')
    return {'format': 'worker-independent-comparison-audit',
            'comparison_id': 'outer_nonapplicability',
            'left_case_id': PREFIX+'left_outer_east',
            'straight_case_id': PREFIX+'straight_outer_east',
            'left_source_hashes': left['hashes'],
            'straight_source_hashes': straight['hashes'],
            'fixed_conditions': ['outer lane, candidate center marking sources',
                                 'original junction/time schedule and four camera sources'],
            'observed_difference': {
                'left_maneuver': left['context']['requested_maneuver'],
                'straight_maneuver': straight['context']['requested_maneuver'],
                'left_deflection_deg': a['maximum_left_deflection_deg'],
                'straight_deflection_deg': b['maximum_deflection_deg']},
            'outer_lane_outside_candidate_center_in_both': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--straight', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior outer-lane comparison proof')
    output.write_text(json.dumps(audit(args.left, args.straight), indent=2)+'\n')
