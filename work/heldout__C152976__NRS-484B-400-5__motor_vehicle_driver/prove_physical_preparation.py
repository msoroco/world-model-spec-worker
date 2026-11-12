"""Prove source-driven physical outcomes and saved processing lifecycle on CPU fixtures."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import math

folder=Path(__file__).resolve().parent
repo=folder.parents[1]
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,_closure

def sha(path):return sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')

def run(case):
    manifest=json.loads((folder/'execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==case)
    branch=case.removeprefix(folder.name+'__').replace('__','-')
    cfg=json.loads(next(f['content'] for f in json.loads((folder/entry['construction']).read_text())['files'] if f['path']=='config.json'))
    fixtures=[]
    for kind in ('complete_motion','incomplete_motion','missing_evidence'):
        with tempfile.TemporaryDirectory(prefix='c152976-motion-',dir=repo/'.runtime-work') as temporary:
            root=Path(temporary)
            put(root/'config.json',cfg)
            frames=[{'video_frame':i,'carla_frame':1000+i,'time_s':round(i/20,5)} for i in range(160)]
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
            trace=[];motion=[]
            (root/'native').mkdir()
            for i in range(160):
                theta=math.pi*i/(2*159) if kind=='complete_motion' else 0.0
                x=-10+10*math.cos(theta);y=10*math.sin(theta)
                time_s=round(i/20,5)
                trace.append({'frame':1000+i,'time_s':time_s,
                              'position_m':[x,y,0.0], 'heading_deg':90+math.degrees(theta)})
                if kind!='missing_evidence':
                    corners=[[x-0.7,y-0.7],[x+0.7,y-0.7],[x+0.7,y+0.7],[x-0.7,y+0.7]]
                    motion.append({'frame':1000+i,'time_s':time_s,'body_vertices_m':corners,
                                   'heading_deg':90+math.degrees(theta),'road_id':2 if i>80 else 1})
            (root/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in trace))
            if motion:
                (root/'native/turn_motion.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in motion))
            assessed=assess_physical(root,cfg)
            status=assessed['physical_checks']['maneuver']['status']
            expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
            if status!=expected:raise ValueError(f'Physical source assessor {kind}: {status}')
            result={'case_id':case,'fixture_kind':kind,'diagnostic_fixture':True,
                    'provenance_kind':'native' if kind=='complete_motion' else 'diagnostic',
                    'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
                    'physical_checks':assessed['physical_checks'],
                    'maneuver_completed':assessed['maneuver_completed'],
                    'realized_observables':assessed['realized_observables']}
            result_name=f'{branch}-physical-{kind}.json';log_name=f'{branch}-physical-{kind}.log'
            put(folder/result_name,result)
            (folder/log_name).write_text(f'{case} {kind} source_assessment={status} frames=160 criterion=turn\n')
            fixtures.append({'kind':kind,
                'command':f'.venv-cpu/bin/python work/{folder.name}/prove_physical_preparation.py --case {case}',
                'exit_code':0,'log':log_name,'log_sha256':sha(folder/log_name),
                'result':result_name,'result_sha256':sha(folder/result_name)})
    with tempfile.TemporaryDirectory(prefix='c152976-lifecycle-',dir=repo/'.runtime-work') as temporary:
        attempt=Path(temporary);(attempt/'construction.json').write_bytes((folder/entry['construction']).read_bytes())
        (attempt/'runner.py').write_bytes((folder/'runner.py').read_bytes())
        seal={'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{},'native_revision':{'construction_sha256':sha(attempt/'construction.json'),
                                               'runner_sha256':sha(attempt/'runner.py')}}
        put(attempt/'capture-seal.json',seal)
        try:acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        except ValueError as error:
            if 'has not exited' not in str(error):raise
        else:raise AssertionError('Owner release accepted before Native exit')
        exit_receipt=record_native_exit(attempt)
        if exit_receipt['event']!='native_exit':raise AssertionError('Missing Native exit')
        owner=acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        if owner['event']!='owner_released':raise AssertionError('Missing owner release')
        _closure(attempt,attempt/'owner-release.json','native',False)
        events=seal['events']+['native_exit','owner_released','saved_processing_started']
        log_name=f'{branch}-physical-lifecycle.log'
        (folder/log_name).write_text(' -> '.join(events)+'\nRejected owner release before Native exit; closure accepted after owner release.\n')
    proof={'format':'worker-physical-preparation-proof','case_id':case,
           'construction_sha256':entry['construction_sha256'],'fixtures':fixtures,
           'lifecycle':{'events':events,'exit_code':0,'log':log_name,'log_sha256':sha(folder/log_name)}}
    receipt_name=f'{branch}-physical-preparation.json';put(folder/receipt_name,proof)
    entry['physical_preparation']={'receipt':receipt_name,'sha256':sha(folder/receipt_name)}
    (folder/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(case,'physical_preparation_passed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    args=parser.parse_args();run(args.case)
