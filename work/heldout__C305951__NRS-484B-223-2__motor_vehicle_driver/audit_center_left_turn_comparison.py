"""Independent center-default versus left-turn preparation source comparison."""

import argparse
import json
from pathlib import Path

from audit_lane_occupancy_comparison import source_case,digest
from audit_center_left_turn_delivery import audit as audit_turn


def audit(center_attempt,center_processing,turn_attempt,turn_processing):
    center=source_case(center_attempt,center_processing,'center_no_exception')
    turn=source_case(turn_attempt,turn_processing,'center_prepare_left')
    audit_turn(turn_attempt,turn_processing)
    fixed=('three_lane_frames.jsonl','three_lane_context.json',
           'three_lane_map_readback.json','trace.jsonl','video_frames.jsonl')
    for name in fixed:
        if digest(center['attempt']/name)!=digest(turn['attempt']/name):
            raise ValueError('Left-turn comparison fixed source changed: '+name)
    c=json.loads((center['attempt']/'config.json').read_text())
    t=json.loads((turn['attempt']/'config.json').read_text())
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s',
                'travel_direction','cameras','required_atoms','source_packets','lane_role'):
        if c.get(key)!=t.get(key):
            raise ValueError('Left-turn comparison fixed config changed: '+key)
    for name in ('left_turn_frames.jsonl','left_turn_plan.json'):
        if (center['attempt']/name).exists() or not (turn['attempt']/name).is_file():
            raise ValueError('Left-turn plan/source not isolated: '+name)
    return {'format':'worker-left-turn-comparison-audit',
            'comparison_id':'center_prepare_left',
            'center_processing_sha256':digest(center_processing),
            'turn_processing_sha256':digest(turn_processing),
            'fixed_original_sources':{name:digest(center['attempt']/name) for name in fixed},
            'turn_plan_and_indicator_sources_added':True,
            'physical_turn_completed':False,
            'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('center-attempt','center-processing','turn-attempt','turn-processing','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=audit(args.center_attempt,args.center_processing,args.turn_attempt,args.turn_processing)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
