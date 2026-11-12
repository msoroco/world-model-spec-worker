"""Compare original two-lane left excursion with three-lane diagnostic context."""

import argparse
import json
from pathlib import Path

from excursion_comparison_audit import _case,_load
from three_lane_measurement import measure_three_lane


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__three_lane'


def audit(left_attempt,three_lane_attempt):
    left_root,three_root=Path(left_attempt),Path(three_lane_attempt)
    control=_case(left_root,'unexcepted_left')
    config=json.loads((three_root/'config.json').read_text())
    if config.get('selected_case_id')!=CASE:
        raise ValueError('Three-lane comparison exact case differs')
    for key,value in control['fixed'].items():
        if config.get(key)!=value:
            raise ValueError('Three-lane comparison fixed config differs: '+key)
    measured=measure_three_lane(three_root)
    if measured['minimum_roadway_width_m']<=control['minimum_road_width_m']:
        raise ValueError('Three-lane comparison did not add a traffic lane')
    baseline,_=_load(left_root,'directed_roadway_footprints.jsonl')
    candidate,_=_load(three_root,'three_lane_roadway.jsonl')
    if len(baseline)!=len(candidate):
        raise ValueError('Three-lane comparison frame count differs')
    for a,b in zip(baseline,candidate):
        for key in ('frame','time_s','ego_id','ego_corners',
                    'roadway_center_point_xy','travel_tangent_xy'):
            if a[key]!=b[key]:
                raise ValueError('Three-lane comparison changed fixed original: '+key)
        if a['subject_road_id']!=b['road_id'] or a['subject_lane_id']!=b['right_lane_id']:
            raise ValueError('Three-lane comparison selected route differs')
        if a['opposite_lane_id']==b['center_lane_id'] or (
                b['applicable_lane_rule_verified'] is not False):
            raise ValueError('Three-lane comparison topology/rule claim differs')
    return {'format':'worker-three-lane-comparison-audit','comparison_id':'three-lane',
            'case_ids':[control['case_id'],CASE],
            'source_bindings':{'two_lane':control,'three_lane':measured['sources']},
            'fixed_conditions':list(control['fixed'])+['original subject body path'],
            'changed_conditions':['third traffic lane','center lane same-direction topology','roadway width'],
            'applicable_lane_rule_verified':False,
            'scope':'synthetic source-shaped diagnostic comparison',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--left-attempt',required=True)
    parser.add_argument('--three-lane-attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise ValueError('Retain prior three-lane comparison receipt')
    output.write_text(json.dumps(audit(args.left_attempt,args.three_lane_attempt),indent=2)+'\n')


if __name__=='__main__':main()
