"""Compare original left-excursion and engineered narrow-road diagnostics."""

import argparse
import json
from pathlib import Path

from excursion_comparison_audit import _case, _load
from width_envelope_measurement import measure_width


def audit(left_attempt, narrow_attempt):
    left_root,narrow_root=Path(left_attempt),Path(narrow_attempt)
    left=_case(left_root,'unexcepted_left')
    narrow=_case(narrow_root,'insufficient_width')
    if left['fixed'] != narrow['fixed']:
        raise ValueError('Width comparison fixed config conditions differ')
    for key in ('frame_count','road_id','lane_id','ego_id'):
        if left[key] != narrow[key]:
            raise ValueError('Width comparison fixed identity differs: '+key)
    original=measure_width(narrow_root/'directed_roadway_footprints.jsonl')
    if not narrow['minimum_road_width_m'] < left['minimum_road_width_m']:
        raise ValueError('Narrow-road candidate is not narrower than control')
    left_rows,_=_load(left_root,'directed_roadway_footprints.jsonl')
    narrow_rows,_=_load(narrow_root,'directed_roadway_footprints.jsonl')
    for control,candidate in zip(left_rows,narrow_rows):
        for key in ('frame','time_s','ego_id','ego_corners','subject_road_id',
                    'subject_lane_id','opposite_lane_id','travel_tangent_xy',
                    'roadway_center_point_xy'):
            if control[key] != candidate[key]:
                raise ValueError('Width comparison changed non-width original: '+key)
    return {'format':'worker-right-half-width-comparison-audit',
            'comparison_id':'width','case_ids':[left['case_id'],narrow['case_id']],
            'source_bindings':[left,narrow],
            'measured_roadway_width_m':{'left':left['minimum_road_width_m'],
                                         'narrow':narrow['minimum_road_width_m']},
            'narrow_envelope':original,
            'changed_conditions':['original road edges','mapped lane widths'],
            'fixed_conditions':list(left['fixed'])+['original subject body path'],
            'scope':'synthetic source-shaped width comparison',
            'legal_sufficiency_decided':False,'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--left-attempt',required=True)
    parser.add_argument('--narrow-attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior width comparison receipt')
    output.write_text(json.dumps(audit(args.left_attempt,args.narrow_attempt),indent=2)+'\n')


if __name__=='__main__':
    main()
