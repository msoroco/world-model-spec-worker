"""Compare unexcepted left-half motion with engineered one-way sign context."""

import argparse
import json
from pathlib import Path

from excursion_comparison_audit import _case,_load
from one_way_measurement import measure_one_way


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__posted_one_way'


def audit(left_attempt,one_way_attempt):
    left_root,one_way_root=Path(left_attempt),Path(one_way_attempt)
    control=_case(left_root,'unexcepted_left')
    config=json.loads((one_way_root/'config.json').read_text())
    if config.get('selected_case_id')!=CASE:
        raise ValueError('One-way comparison exact case differs')
    for key,value in control['fixed'].items():
        if config.get(key)!=value:
            raise ValueError('One-way comparison fixed config differs: '+key)
    original=measure_one_way(one_way_root)
    left_rows,_=_load(left_root,'directed_roadway_footprints.jsonl')
    one_rows,_=_load(one_way_root,'one_way_roadway.jsonl')
    if len(left_rows)!=len(one_rows):
        raise ValueError('One-way comparison frame count differs')
    for baseline,candidate in zip(left_rows,one_rows):
        for key in ('frame','time_s','ego_id','ego_corners',
                    'roadway_center_point_xy','travel_tangent_xy',
                    'left_road_edge_xy','right_road_edge_xy'):
            if baseline[key]!=candidate[key]:
                raise ValueError('One-way comparison changed fixed original: '+key)
        if baseline['subject_road_id']!=candidate['road_id'] or (
                baseline['subject_lane_id']!=candidate['right_lane_id']):
            raise ValueError('One-way comparison route identity differs')
        if baseline['opposite_lane_id']==candidate['left_lane_id']:
            raise ValueError('One-way comparison did not change lane topology')
    if (left_root/'one_way_sign.jsonl').exists():
        raise ValueError('Unexcepted-left control has one-way sign source')
    return {'format':'worker-one-way-comparison-audit','comparison_id':'one-way',
            'case_ids':[control['case_id'],CASE],
            'source_bindings':{'left':control,'one_way':original['sources']},
            'changed_conditions':['left lane same-direction topology','one-way sign actor'],
            'fixed_conditions':list(control['fixed'])+['original subject body path','roadway width'],
            'designation_verified':False,'posting_authority_verified':False,
            'scope':'synthetic source-shaped diagnostic comparison',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--left-attempt',required=True)
    parser.add_argument('--one-way-attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior one-way comparison receipt')
    output.write_text(json.dumps(audit(args.left_attempt,args.one_way_attempt),indent=2)+'\n')


if __name__=='__main__':
    main()
