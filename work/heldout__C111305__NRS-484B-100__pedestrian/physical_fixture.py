"""Synthetic officer-direction outcome protocol using joined original-shaped packets.

This checks CPU logic only. It makes no Native communication or legal claim.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from math import hypot
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run(case_id,kind):
    if kind not in ('complete_motion','incomplete_motion','missing_evidence'):
        raise ValueError('unknown physical outcome')
    entries=json.loads((HERE/'provisional-manifest.json').read_text())['cases']
    entry=next((e for e in entries if e['case_id']==case_id),None)
    if entry is None:raise ValueError('unknown exact officer case')
    recipe=json.loads((ROOT/entry['fixture_recipe']).read_text())
    source=ROOT/recipe['generator']['source']
    if sha(source)!=recipe['generator']['sha256']:
        raise ValueError('diagnostic source hash changed')
    files=json.loads(source.read_text())['files']
    names=('officer_context.json','officer_direction.json','subject_motion_history.jsonl','video_frames.jsonl')
    source_hashes={name:hashlib.sha256(files[name].encode()).hexdigest() for name in names}
    if kind=='missing_evidence':
        source_hashes.pop('officer_direction.json')
    direction=None if kind=='missing_evidence' else json.loads(files['officer_direction.json'])
    rows=[json.loads(line) for line in files['subject_motion_history.jsonl'].splitlines()]
    video=[json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
    if len(rows)<3 or [r['frame'] for r in rows]!=[v['native_frame'] for v in video]:
        raise ValueError('subject/video original frame join failed')
    if direction is None:
        status='unverified';observables={}
    else:
        if direction['command'] not in ('stop','proceed') or not direction.get('exact_direction_text'):
            raise ValueError('exact officer direction source absent')
        if direction['subject_id']!=rows[0]['subject_id']:
            raise ValueError('officer direction recipient differs from subject')
        post=[r.copy() for r in rows if r['frame']>=direction['frame']]
        if len(post)<2:raise ValueError('no post-direction subject frames')
        suffix=case_id.rsplit('__',1)[-1]
        intended=('responds' if suffix in ('stop_responds','proceed_responds')
                  or suffix.startswith('stop_responds_timing_') else 'does_not_respond')
        # Stationary and walking are controlled synthetic outcomes; the source
        # packets remain joined by original frame identity and timestamps.
        should_walk=(direction['command']=='proceed')==(intended=='responds')
        if kind=='incomplete_motion':should_walk=not should_walk
        if should_walk:
            for i,row in enumerate(post):
                row['position_m']=list(row['position_m'])
                row['position_m'][0]=post[0]['position_m'][0]+1.5*i/(len(post)-1)
                row['speed_mps']=1.5
        else:
            for row in post:
                row['position_m']=list(post[0]['position_m'])
                row['speed_mps']=0.0
        transformed={row['frame']:row for row in post}
        synthetic_rows=[transformed.get(row['frame'],row) for row in rows]
        synthetic_bytes=''.join(json.dumps(row,sort_keys=True)+'\n' for row in synthetic_rows).encode()
        source_hashes['synthetic_subject_motion_history.jsonl']=hashlib.sha256(synthetic_bytes).hexdigest()
        displacement=hypot(*(post[-1]['position_m'][i]-post[0]['position_m'][i] for i in (0,1)))
        walking=displacement>=0.5 and post[-1]['speed_mps']>=0.5
        responded=walking if direction['command']=='proceed' else not walking
        status='met' if responded==(intended=='responds') else 'not_met'
        observables={'direction_frame':direction['frame'],'last_frame':post[-1]['frame'],
                     'post_direction_displacement_m':displacement,'last_speed_mps':post[-1]['speed_mps'],
                     'responded_to_direction':responded}
    expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
    if status!=expected:raise ValueError('fixture outcome differs: '+status)
    return {'case_id':case_id,'fixture_kind':kind,'diagnostic_fixture':True,
            'actual_native_capture':False,'provenance_kind':'synthetic_fixture',
            'physical_checks':{'maneuver':{'status':status,
                'method':'joined officer direction, recipient and post-direction subject frames; synthetic stop/proceed response criterion',
                'sources':source_hashes,'missing_evidence':['officer_direction.json'] if direction is None else []}},
            'maneuver_completed':status=='met','realized_observables':observables,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--kind',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();result=run(args.case,args.kind)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(args.case,args.kind,result['physical_checks']['maneuver']['status'],'synthetic_fixture_only')
