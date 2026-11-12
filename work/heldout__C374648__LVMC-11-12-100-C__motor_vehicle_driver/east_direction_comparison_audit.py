"""Independent original-source comparison of east/west center-lane left turns."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from turn_origin_comparison_audit import PREFIX, _source


def audit(east_root, west_root, *, decode_video=True):
    east = _source(east_root, PREFIX+'left_center_east', decode_video=decode_video)
    west = _source(west_root, PREFIX+'left_center_west', decode_video=decode_video)
    a, b = east['measurement'], west['measurement']
    if not a['origin_matches_center_lane'] or not b['origin_matches_center_lane']:
        raise ValueError('Both original origins must be candidate center lanes')
    if (a['approach_road_id'] != b['approach_road_id'] or
            a['approach_lane_id'] != -b['approach_lane_id'] or
            a['center_turn_lane_id'] != -b['center_turn_lane_id'] or
            a['maximum_left_deflection_deg'] != b['maximum_left_deflection_deg']):
        raise ValueError('East/west original lane or left-turn motion differs')
    if (east['rows'][0]['ego_forward_xy'][0] <= 0 or
            west['rows'][0]['ego_forward_xy'][0] >= 0):
        raise ValueError('Original approach direction did not change east to west')
    fixed = ('requested_maneuver', 'designation_authority_verified',
             'target_exit_road_id')
    if any(east['context'].get(key) != west['context'].get(key) for key in fixed):
        raise ValueError('East/west authored fixed condition differs')
    if ([(r['is_junction'], r['time_s']-east['rows'][0]['time_s']) for r in east['rows']] !=
            [(r['is_junction'], r['time_s']-west['rows'][0]['time_s']) for r in west['rows']]):
        raise ValueError('East/west original junction/time schedule differs')
    if [c['name'] for c in east['config']['cameras']] != [
            c['name'] for c in west['config']['cameras']]:
        raise ValueError('East/west four-camera contract differs')
    return {'format': 'worker-independent-comparison-audit',
            'comparison_id': 'east_direction',
            'east_case_id': PREFIX+'left_center_east',
            'west_case_id': PREFIX+'left_center_west',
            'east_source_hashes': east['hashes'],
            'west_source_hashes': west['hashes'],
            'fixed_conditions': ['candidate center origin, left-turn intent and exit road',
                                 'original junction/time schedule and four camera sources'],
            'observed_difference': {'east_origin_lane_id': a['approach_lane_id'],
                                    'west_origin_lane_id': b['approach_lane_id'],
                                    'east_heading_x': east['rows'][0]['ego_forward_xy'][0],
                                    'west_heading_x': west['rows'][0]['ego_forward_xy'][0]},
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--east', required=True)
    parser.add_argument('--west', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior east/west comparison proof')
    output.write_text(json.dumps(audit(args.east, args.west), indent=2)+'\n')
