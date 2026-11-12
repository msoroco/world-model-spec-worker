"""CPU proof of source-bound station reversal and Native ownership closure."""
import argparse
from hashlib import sha256
import json
from math import cos,pi,sin
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.native_output import assess_physical
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,_closure


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def prove(entry):
    case=entry['case_id'];short=case.rsplit('__',1)[-1]
    construction=json.loads((HERE/entry['construction']).read_text())
    cfg=json.loads(next(item['content'] for item in construction['files']
                        if item['path']=='config.json'))
    if (cfg.get('physical_completion',{}).get('criterion')!='turn' or
            cfg['physical_completion'].get('turn_degrees')!=180 or
            cfg['physical_completion'].get('motion_source')!='subject_original.jsonl'):
        raise ValueError('Authored original station-turn criterion missing')
    fixtures=[]
    for kind in ('complete_motion','incomplete_motion','missing_evidence'):
        with tempfile.TemporaryDirectory(prefix='c111706-physical-',dir=ROOT/'.runtime-work') as temp:
            root=Path(temp)
            put(root/'config.json',cfg)
            put(root/'station_survey.json',cfg['station_survey'])
            n=round(cfg['duration_s']*cfg['rate_hz'])
            frames=[{'video_frame':i,'carla_frame':1000+i,'time_s':round(i/20,5)}
                    for i in range(n)]
            (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
            if kind!='missing_evidence':
                rows=[];subject=[]
                for i in range(n):
                    fraction=i/(n-1)
                    angle=pi*fraction if kind=='complete_motion' else 0.0
                    position=[10*sin(angle),10*(1-cos(angle)),0.0] if kind=='complete_motion' else [10*fraction,0.0,0.0]
                    rows.append({'frame':1000+i,'time_s':round(i/20,5),
                                 'position_m':position,'heading_deg':180*fraction if kind=='complete_motion' else 0.0})
                    x,y=position[:2]
                    subject.append({'frame':1000+i,'time_s':round(i/20,5),
                                    'center_xy':[x,y],
                                    'body_corners_xy':[[x-1,y-.5],[x+1,y-.5],
                                                       [x+1,y+.5],[x-1,y+.5]],
                                    'heading_deg':180*fraction if kind=='complete_motion' else 0.0})
                (root/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                (root/'subject_original.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in subject))
            else:
                (root/'trace.jsonl').write_text(''.join(json.dumps({
                    'frame':1000+i,'time_s':round(i/20,5),'position_m':[i/20,0,0]})+'\n'
                    for i in range(n)))
            assessed=assess_physical(root,cfg)
            expected={'complete_motion':'met','incomplete_motion':'not_met',
                      'missing_evidence':'unverified'}[kind]
            actual=assessed['physical_checks']['maneuver']['status']
            if actual!=expected:
                raise ValueError(f'Source-based station-turn assessor {kind}: {actual}')
            result={'case_id':case,'fixture_kind':kind,'diagnostic_fixture':True,
                    'provenance_kind':'native' if kind=='complete_motion' else 'diagnostic',
                    'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,
                    'physical_checks':assessed['physical_checks'],
                    'maneuver_completed':assessed['maneuver_completed'],
                    'realized_observables':assessed['realized_observables']}
            result_name=short+'-physical-'+kind+'.json'
            log_name=short+'-physical-'+kind+'.log'
            put(HERE/result_name,result)
            (HERE/log_name).write_text(f'{case} {kind} source_assessment={actual} frames={n}\n')
            fixtures.append({'kind':kind,
                'command':f'.venv-cpu/bin/python work/{HERE.name}/prove_physical_preparation.py --case {case}',
                'exit_code':0,'log':log_name,'log_sha256':digest(HERE/log_name),
                'result':result_name,'result_sha256':digest(HERE/result_name)})
    with tempfile.TemporaryDirectory(prefix='c111706-lifecycle-',dir=ROOT/'.runtime-work') as temp:
        attempt=Path(temp)
        (attempt/'construction.json').write_bytes((HERE/entry['construction']).read_bytes())
        (attempt/'runner.py').write_bytes((HERE/'runner.py').read_bytes())
        seal={'events':['capture_finished','encoders_closed','restoration_verified'],
              'sources':{},'native_revision':{
                  'construction_sha256':digest(attempt/'construction.json'),
                  'runner_sha256':digest(attempt/'runner.py')}}
        put(attempt/'capture-seal.json',seal)
        try:
            acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        except ValueError as error:
            if 'has not exited' not in str(error):raise
        else:
            raise AssertionError('Owner release accepted before Native exit')
        exit_receipt=record_native_exit(attempt)
        if exit_receipt['event']!='native_exit':raise AssertionError('Missing Native exit')
        owner=acknowledge_owner_release(attempt,attempt/'owner-release.json',True)
        if owner['event']!='owner_released':raise AssertionError('Missing owner release')
        _closure(attempt,attempt/'owner-release.json','native',False)
        events=seal['events']+['native_exit','owner_released','saved_processing_started']
        log_name=short+'-physical-lifecycle.log'
        (HERE/log_name).write_text(' -> '.join(events)+'\nRejected early owner release; accepted closure after release.\n')
    # Keep one exact per-case log with all three measured outcomes and lifecycle.
    original_logs=[item['log'] for item in fixtures]+[log_name]
    combined_name=short+'-physical-controls.log'
    (HERE/combined_name).write_text(''.join(
        f'[{name}]\n'+(HERE/name).read_text() for name in original_logs))
    combined_sha=digest(HERE/combined_name)
    for item in fixtures:
        item['log']=combined_name
        item['log_sha256']=combined_sha
    log_name=combined_name
    for name in original_logs:
        (HERE/name).unlink()
    proof={'format':'worker-physical-preparation-proof','case_id':case,
           'construction_sha256':entry['construction_sha256'],'fixtures':fixtures,
           'lifecycle':{'events':events,'exit_code':0,'log':log_name,
                        'log_sha256':combined_sha}}
    receipt_name=short+'-physical-preparation.json'
    put(HERE/receipt_name,proof)
    entry['physical_preparation']={'receipt':receipt_name,
                                   'sha256':digest(HERE/receipt_name)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case');args=parser.parse_args()
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        if args.case and entry['case_id']!=args.case:continue
        prove(entry)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
