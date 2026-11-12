"""Independent clear-versus-occluded original-source comparison."""

import argparse
import json
from pathlib import Path

from audit_lane_occupancy_comparison import source_case, digest
from audit_center_passing_delivery import audit as audit_clear
from audit_center_passing_occluded_delivery import audit as audit_occluded


def audit(clear_attempt, clear_processing, occluded_attempt, occluded_processing):
    clear=source_case(clear_attempt,clear_processing,'center_passing_clear')
    occluded=source_case(occluded_attempt,occluded_processing,'center_passing_occluded')
    audit_clear(clear_attempt,clear_processing)
    audit_occluded(occluded_attempt,occluded_processing)
    fixed=('passing_frames.jsonl','three_lane_frames.jsonl','three_lane_context.json',
           'three_lane_map_readback.json','trace.jsonl','video_frames.jsonl')
    for name in fixed:
        if digest(clear['attempt']/name)!=digest(occluded['attempt']/name):
            raise ValueError('Occluded comparison fixed source changed: '+name)
    c=json.loads((clear['attempt']/'config.json').read_text())
    o=json.loads((occluded['attempt']/'config.json').read_text())
    for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s',
                'travel_direction','cameras','required_atoms','source_packets',
                'lane_role','target_ahead_m','clear_target_m',
                'ego_target_speed_mps','target_blueprint'):
        if c.get(key)!=o.get(key):
            raise ValueError('Occluded comparison fixed config changed: '+key)
    if ((clear['attempt']/'occluder_frames.jsonl').exists() or
            not (occluded['attempt']/'occluder_frames.jsonl').is_file()):
        raise ValueError('Occluded comparison static source not isolated')
    return {'format':'worker-occluded-passing-comparison-audit',
            'comparison_id':'center_passing_occluded',
            'clear_processing_sha256':digest(clear_processing),
            'occluded_processing_sha256':digest(occluded_processing),
            'fixed_original_sources':{name:digest(clear['attempt']/name) for name in fixed},
            'occluder_original_sha256':digest(occluded['attempt']/'occluder_frames.jsonl'),
            'static_occluder_source_added':True,
            'physical_sight_occlusion_confirmed':False,
            'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('clear-attempt','clear-processing','occluded-attempt','occluded-processing','output'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=audit(args.clear_attempt,args.clear_processing,
                 args.occluded_attempt,args.occluded_processing)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
