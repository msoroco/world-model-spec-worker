"""Independent source binding for center-lane left-turn preparation."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import PREFIX

CASE=PREFIX+'center_left_turn'
SOURCES=('left_turn_frames.jsonl','left_turn_plan.json','three_lane_frames.jsonl',
         'three_lane_context.json','three_lane_map_readback.json',
         'trace.jsonl','video_frames.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt,processing):
    attempt,processing=Path(attempt),Path(processing)
    receipt=json.loads(processing.read_text())
    if (receipt.get('case_id')!=CASE or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved left-turn receipt differs')
    report=json.loads((processing.parent/'analysis/analysis-report.json').read_text())
    result=json.loads((processing.parent/'analysis/result.json').read_text())
    measure=report.get('measurements',{}).get('left_turn_observation')
    if (report.get('case_id')!=CASE or result.get('case_id')!=CASE or
            not isinstance(measure,dict) or
            result.get('measured_values',{}).get('left_turn_observation')!=measure.get('value')):
        raise ValueError('Saved left-turn measurement differs')
    hashes=measure.get('sources')
    if not isinstance(hashes,dict) or set(hashes)!=set(SOURCES):
        raise ValueError('Saved left-turn original inventory differs')
    for name in SOURCES:
        path=attempt/name
        if not path.is_file() or digest(path)!=hashes[name]:
            raise ValueError('Saved left-turn original source differs: '+name)
    observations=measure['value']['observations']
    if (len(observations)<2 or not all(row['left_indicator_readback'] is True
            and row['distance_to_approach_end_m']>=0 for row in observations) or
            not 45<=measure['value']['mapped_turn_angle_deg']<=135):
        raise ValueError('Original left-turn preparation geometry or signal missing')
    lane=report['measurements']['three_lane_observation']['value']['observations']
    if len(lane)!=len(observations) or not all(
            row['body_lane_overlap_fraction']['center']>.95 for row in lane):
        raise ValueError('Original center-lane preparation occupancy missing')
    return {'format':'worker-left-turn-source-audit','case_id':CASE,
            'processing_sha256':digest(processing),'original_sources':hashes,
            'frames':len(observations),'mapped_turn_angle_deg':measure['value']['mapped_turn_angle_deg'],
            'source_binding_passed':True,'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('attempt','processing','output'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=audit(args.attempt,args.processing)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
