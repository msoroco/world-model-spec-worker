"""Independent clear versus near center traffic original-source comparison."""

import argparse
import json
from pathlib import Path

from audit_lane_occupancy_comparison import source_case, digest
from audit_center_passing_delivery import audit as audit_clear
from audit_center_passing_near_delivery import audit as audit_near


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(clear_attempt, clear_processing, near_attempt, near_processing):
    clear = source_case(clear_attempt, clear_processing, 'center_passing_clear')
    near = source_case(near_attempt, near_processing, 'center_passing_near_traffic')
    audit_clear(clear_attempt, clear_processing)
    audit_near(near_attempt, near_processing)
    fixed = ('three_lane_context.json','three_lane_map_readback.json',
             'three_lane_frames.jsonl','trace.jsonl','video_frames.jsonl')
    for name in fixed:
        if digest(clear['attempt']/name) != digest(near['attempt']/name):
            raise ValueError('Near-traffic comparison fixed source changed: '+name)
    a, b = rows(clear['attempt']/'passing_frames.jsonl'), rows(near['attempt']/'passing_frames.jsonl')
    if not a or len(a) != len(b):
        raise ValueError('Near-traffic comparison frame count differs')
    for first, second in zip(a,b):
        for key in ('frame','time_s','ego_actor_id','target_actor_id','ego_center_xy',
                    'target_center_xy','target_corners_xy','right_lane_center_xy',
                    'center_lane_center_xy','clear_target_m'):
            if first.get(key) != second.get(key):
                raise ValueError('Near-traffic comparison fixed passing source changed: '+key)
        base = first['other_vehicle_bodies']
        altered = second['other_vehicle_bodies']
        if len(altered) != len(base)+1 or any(x not in altered for x in base):
            raise ValueError('Near-traffic comparison center blocker not isolated')
    c, n = (json.loads((x['attempt']/'config.json').read_text()) for x in (clear,near))
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s','travel_direction','cameras',
                'required_atoms','source_packets','lane_role','target_ahead_m',
                'clear_target_m','ego_target_speed_mps','target_blueprint'):
        if c.get(key) != n.get(key):
            raise ValueError('Near-traffic comparison fixed config changed: '+key)
    return {'format':'worker-near-traffic-comparison-audit',
            'comparison_id':'center_passing_near_traffic',
            'clear_processing_sha256':digest(clear_processing),
            'near_processing_sha256':digest(near_processing),
            'fixed_original_sources':{name:digest(clear['attempt']/name) for name in fixed},
            'frames':len(a),'added_center_actor_each_frame':True,
            'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('clear-attempt','clear-processing','near-attempt','near-processing','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=audit(args.clear_attempt,args.clear_processing,args.near_attempt,args.near_processing)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
