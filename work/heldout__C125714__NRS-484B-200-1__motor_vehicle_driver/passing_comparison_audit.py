"""Compare original left-excursion and proposed passing diagnostic sources."""

import argparse
import json
from pathlib import Path

from excursion_comparison_audit import _case, _load
from passing_source_audit import audit as audit_passing


def audit(left_attempt, passing_attempt):
    left_root, passing_root = Path(left_attempt), Path(passing_attempt)
    left = _case(left_root, 'unexcepted_left')
    passing = _case(passing_root, 'passing_same_direction')
    if left['fixed'] != passing['fixed']:
        raise ValueError('Passing comparison fixed conditions differ')
    for key in ('frame_count', 'road_id', 'lane_id', 'ego_id'):
        if left[key] != passing[key]:
            raise ValueError('Passing comparison route/frame/subject identity differs: ' + key)
    if abs(left['minimum_road_width_m']-passing['minimum_road_width_m']) > .01:
        raise ValueError('Passing comparison roadway width differs')
    if left['first_crossing_frame'] is None or passing['first_crossing_frame'] is None:
        raise ValueError('Passing comparison requires original left-half crossing')
    if (left_root/'passing_actors.jsonl').exists():
        raise ValueError('Unexcepted-left control contains passing actor source')
    original = audit_passing(passing_root)
    left_road, _ = _load(left_root, 'directed_roadway_footprints.jsonl')
    pass_road, _ = _load(passing_root, 'directed_roadway_footprints.jsonl')
    for baseline, candidate in zip(left_road, pass_road):
        for key in ('subject_road_id','subject_lane_id','opposite_lane_id',
                    'subject_lane_width_m','opposite_lane_width_m',
                    'roadway_center_point_xy','travel_tangent_xy',
                    'left_road_edge_xy','right_road_edge_xy'):
            if baseline[key] != candidate[key]:
                raise ValueError('Passing comparison original roadway condition differs: '+key)
    return {'format':'worker-right-half-passing-comparison-audit',
            'comparison_id':'passing', 'case_ids':[left['case_id'],passing['case_id']],
            'source_bindings':[left,passing], 'passing_source':original,
            'fixed_conditions':list(left['fixed'])+['original directed roadway geometry'],
            'changed_conditions':['same-direction lead actor','subject longitudinal pass path'],
            'scope':'synthetic source-shaped diagnostic comparison',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--left-attempt',required=True)
    parser.add_argument('--passing-attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior passing comparison receipt')
    output.write_text(json.dumps(audit(args.left_attempt,args.passing_attempt),indent=2)+'\n')


if __name__=='__main__':
    main()
