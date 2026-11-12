"""Independent center-no-exception versus constructed-target source comparison."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from audit_lane_occupancy_comparison import source_case, digest
from audit_center_passing_delivery import audit as audit_passing


def audit(center_attempt, center_processing, passing_attempt, passing_processing):
    center = source_case(center_attempt, center_processing, 'center_no_exception')
    passing = source_case(passing_attempt, passing_processing, 'center_pass_clear')
    passed = audit_passing(passing_attempt, passing_processing)
    fixed = ('three_lane_context.json', 'three_lane_map_readback.json',
             'three_lane_frames.jsonl', 'trace.jsonl', 'video_frames.jsonl')
    for name in fixed:
        if digest(center['attempt']/name) != digest(passing['attempt']/name):
            raise ValueError('Passing comparison fixed source changed: '+name)
    c = json.loads((center['attempt']/'config.json').read_text())
    p = json.loads((passing['attempt']/'config.json').read_text())
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s',
                'travel_direction','cameras','required_atoms','source_packets','lane_role'):
        if c.get(key) != p.get(key):
            raise ValueError('Passing comparison fixed config changed: '+key)
    center_obs = center['observation']['observations']
    pass_obs = passing['observation']['observations']
    if (len(center_obs) != len(pass_obs) or
            any(a['body_lane_overlap_fraction'] != b['body_lane_overlap_fraction']
                for a,b in zip(center_obs,pass_obs)) or
            not all(row['body_lane_overlap_fraction']['center'] > .95 for row in pass_obs)):
        raise ValueError('Passing comparison center subject occupancy changed')
    if ((center['attempt']/'passing_frames.jsonl').exists() or
            not (passing['attempt']/'passing_frames.jsonl').is_file()):
        raise ValueError('Passing comparison target source absent or present in baseline')
    return {'format':'worker-center-passing-comparison-audit',
            'comparison_id':'center_pass_clear',
            'center_case':center['report']['case_id'],
            'passing_case':passing['report']['case_id'],
            'center_processing_sha256':digest(center_processing),
            'passing_processing_sha256':digest(passing_processing),
            'passing_source_audit_sha256':sha256(json.dumps(passed,sort_keys=True).encode()).hexdigest(),
            'fixed_original_sources':{name:digest(center['attempt']/name) for name in fixed},
            'frames':len(pass_obs),'target_source_added':True,
            'fixed_conditions_passed':True,'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('center-attempt','center-processing','passing-attempt','passing-processing','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=audit(args.center_attempt,args.center_processing,args.passing_attempt,args.passing_processing)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
