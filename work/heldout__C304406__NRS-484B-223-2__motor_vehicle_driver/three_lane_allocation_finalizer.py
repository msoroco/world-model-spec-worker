"""Saved-only allocation candidate measurement; legal posting stays unverified."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_finalizer import analyze as analyze_lanes, build_result as build_lane_result


def digest(path):
    path=Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+path.name)
    return sha256(path.read_bytes()).hexdigest()


def measure_allocation_sources(attempt):
    root=Path(attempt)
    names=('allocation_frames.jsonl','allocation_plan.json','three_lane_frames.jsonl',
           'three_lane_context.json','three_lane_map_readback.json','trace.jsonl','video_frames.jsonl')
    hashes={name:digest(root/name) for name in names}
    plan=json.loads((root/'allocation_plan.json').read_text())
    readback=json.loads((root/'three_lane_map_readback.json').read_text())
    config=json.loads((root/'config.json').read_text())
    posted=config['selected_case_id'].endswith('__center_allocated_posted')
    if (not config['selected_case_id'].endswith(('__center_allocated_posted','__center_allocated_unposted')) or
            plan.get('road_id')!=readback.get('road_id') or
            plan.get('center_lane_id')!=readback.get('lane_ids',{}).get('center') or
            plan.get('same_direction_map_readback') is not True or
            plan.get('posted_sign_candidate') is not posted or
            plan.get('allocation_authority_source') is not None or
            plan.get('sign_text_verified') is not None or
            plan.get('legal_allocation_verified') is not None):
        raise ValueError('Original allocation plan or map readback differs')
    rows=[json.loads(line) for line in (root/'allocation_frames.jsonl').read_text().splitlines() if line.strip()]
    lanes=[json.loads(line) for line in (root/'three_lane_frames.jsonl').read_text().splitlines() if line.strip()]
    if len(rows)<2 or len(rows)!=len(lanes):
        raise ValueError('Original allocation/lane frame count differs')
    for row,lane in zip(rows,lanes):
        if ((row.get('frame'),row.get('time_s'),row.get('ego_actor_id'))!=
                (lane.get('frame'),lane.get('time_s'),lane.get('ego_actor_id')) or
                row.get('same_direction_map_readback') is not True or
                row.get('posted_sign_candidate') is not posted or
                bool(row.get('sign_body_vertices_xyz')) is not posted or
                row.get('sign_actor_id')!=plan.get('sign_actor_id')):
            raise ValueError('Original allocation frame identity or candidate sign differs')
        if posted and (len(row['sign_body_vertices_xyz'])<4 or not all(
                len(v)==3 and all(type(a) in (int,float) for a in v)
                for v in row['sign_body_vertices_xyz'])):
            raise ValueError('Original candidate sign dimensions missing')
    return {'format':'worker-allocation-candidate-observation','sources':hashes,
            'frames':len(rows),'same_direction_map_readback':True,
            'posted_sign_candidate':posted,'sign_blueprint':plan.get('sign_blueprint'),
            'sign_text_verified':None,'legal_allocation_verified':None}


def analyze(attempt):
    report=analyze_lanes(attempt)
    measured=measure_allocation_sources(attempt)
    report['measurements']['allocation_observation']={
        'method':'measure_allocation_sources','value':measured,'sources':measured['sources']}
    return report


def build_result(attempt,report):
    result=build_lane_result(attempt,report)
    measured=report['measurements']['allocation_observation']['value']
    channel=Path(attempt)/'allocation_observation.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived allocation channel')
    rows=[json.loads(line) for line in (Path(attempt)/'allocation_frames.jsonl').read_text().splitlines() if line.strip()]
    channel.write_text(''.join(json.dumps({'frame':row['frame'],'time_s':row['time_s'],
        'value':int(row['posted_sign_candidate'])})+'\n' for row in rows))
    result['measured_values']['allocation_observation']=measured
    result['recording_evidence'].append({'name':'allocation_observation','unit':'indicator',
        'reference':channel.name,'sha256':digest(channel)})
    result['realized_observables']['allocation_observation']={
        'unit':'indicator','method':'original 20 Hz candidate prop and map source',
        'time_window':'all original frames','statistic':'candidate_posted_flag',
        'reference':channel.name,'value':int(measured['posted_sign_candidate']),
        'sample_window_s':[rows[0]['time_s'],rows[-1]['time_s']]}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior allocation analysis')
    report=analyze(args.attempt)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))


if __name__=='__main__':main()
