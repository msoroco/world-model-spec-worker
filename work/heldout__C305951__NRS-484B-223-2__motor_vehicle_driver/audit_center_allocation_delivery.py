"""Bind saved allocation candidate sources and posted/unposted comparison."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

SOURCES=('allocation_frames.jsonl','allocation_plan.json','three_lane_frames.jsonl',
         'three_lane_context.json','three_lane_map_readback.json','trace.jsonl','video_frames.jsonl')
FIXED=('three_lane_frames.jsonl','three_lane_context.json','three_lane_map_readback.json',
       'trace.jsonl','video_frames.jsonl')
PREFIX='heldout__C305951__NRS-484B-223-2__motor_vehicle_driver__'


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def source_case(attempt,processing,suffix):
    attempt,processing=Path(attempt),Path(processing)
    case=PREFIX+suffix
    receipt=json.loads(processing.read_text())
    if (receipt.get('case_id')!=case or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False or
            receipt.get('physical_acceptance_claimed') is not False or
            receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved allocation receipt differs: '+suffix)
    report=json.loads((processing.parent/'analysis/analysis-report.json').read_text())
    result=json.loads((processing.parent/'analysis/result.json').read_text())
    measure=report.get('measurements',{}).get('allocation_observation')
    if (report.get('case_id')!=case or result.get('case_id')!=case or
            not isinstance(measure,dict) or
            result.get('measured_values',{}).get('allocation_observation')!=measure.get('value')):
        raise ValueError('Saved allocation measurement differs: '+suffix)
    hashes=measure.get('sources')
    if not isinstance(hashes,dict) or set(hashes)!=set(SOURCES):
        raise ValueError('Saved allocation inventory differs: '+suffix)
    for name in SOURCES:
        path=attempt/name
        if not path.is_file() or digest(path)!=hashes[name]:
            raise ValueError('Saved allocation original source differs: '+name)
    posted=suffix.endswith('signed') and not suffix.endswith('unsigned')
    value=measure['value']
    lanes=report['measurements']['three_lane_observation']['value']['observations']
    if (value.get('posted_sign_candidate') is not posted or
            value.get('same_direction_map_readback') is not True or
            value.get('sign_text_verified') is not None or
            value.get('legal_allocation_verified') is not None or
            len(lanes)!=value.get('frames') or
            not all(row['body_lane_overlap_fraction']['center']>.95 for row in lanes)):
        raise ValueError('Saved allocation candidate, occupancy or limitations differ')
    return {'attempt':attempt,'processing':processing,'sources':hashes,'posted':posted,
            'value':value,'config':json.loads((attempt/'config.json').read_text())}


def audit(center_attempt,center_processing,posted_attempt,posted_processing,unposted_attempt,unposted_processing):
    center_attempt,center_processing=Path(center_attempt),Path(center_processing)
    center_receipt=json.loads(center_processing.read_text())
    if center_receipt.get('case_id')!=PREFIX+'center_no_exception' or center_receipt.get('passed') is not True:
        raise ValueError('Center-default comparison receipt differs')
    posted=source_case(posted_attempt,posted_processing,'center_allocated_signed')
    unposted=source_case(unposted_attempt,unposted_processing,'center_allocated_unsigned')
    for name in FIXED:
        a=digest(center_attempt/name)
        if posted['sources'][name]!=a or unposted['sources'][name]!=a:
            raise ValueError('Fixed original changed across allocation comparison: '+name)
    cfg=json.loads((center_attempt/'config.json').read_text())
    for other in (posted,unposted):
        for key in ('law_id','cell_id','actor','rate_hz','frames','duration_s',
                    'travel_direction','cameras','required_atoms','source_packets','lane_role'):
            if cfg.get(key)!=other['config'].get(key):
                raise ValueError('Fixed allocation configuration changed: '+key)
    p=json.loads((posted['attempt']/'allocation_plan.json').read_text())
    u=json.loads((unposted['attempt']/'allocation_plan.json').read_text())
    for key in ('allocation_claim','allocation_authority_source','same_direction_map_readback',
                'center_lane_id','road_id','sign_text_verified','legal_allocation_verified'):
        if p.get(key)!=u.get(key):
            raise ValueError('Fixed allocation plan changed: '+key)
    if not p['posted_sign_candidate'] or u['posted_sign_candidate'] or not p['sign_actor_id'] or u['sign_actor_id']:
        raise ValueError('Posted versus unposted candidate contrast missing')
    return {'format':'worker-allocation-source-and-comparison-audit',
            'center_processing_sha256':digest(center_processing),
            'posted_processing_sha256':digest(posted_processing),
            'unposted_processing_sha256':digest(unposted_processing),
            'fixed_original_sources':{name:digest(center_attempt/name) for name in FIXED},
            'posted_original_sources':posted['sources'],'unposted_original_sources':unposted['sources'],
            'posted_candidate_only_difference':True,'sign_text_verified':False,
            'legal_allocation_verified':False,'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('center-attempt','center-processing','posted-attempt','posted-processing',
                 'unposted-attempt','unposted-processing','output'):
        parser.add_argument('--'+name,required=True)
    a=parser.parse_args()
    result=audit(a.center_attempt,a.center_processing,a.posted_attempt,a.posted_processing,
                 a.unposted_attempt,a.unposted_processing)
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
