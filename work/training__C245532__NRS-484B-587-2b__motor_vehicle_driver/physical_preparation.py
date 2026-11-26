"""CPU motion and capture-lifecycle fixtures for selected separator cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
KINDS=('complete_motion','incomplete_motion','missing_evidence')
EVENTS=['capture_finished','encoders_closed','restoration_verified',
    'native_exit','owner_released','saved_processing_started']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def status(rows,suffix):
    if len(rows)!=600 or [r.get('video_frame') for r in rows]!=list(range(600)):
        return 'unverified'
    if any(not isinstance(r.get('ego',{}).get('body_xy_m'),list) or
           len(r['ego']['body_xy_m'])<4 for r in rows):return 'unverified'
    separator=-3.5
    if suffix=='controlled_1':
        met=all(max(p[1] for p in r['ego']['body_xy_m'])<separator for r in rows)
    else:
        met=any(min(p[1] for p in r['ego']['body_xy_m'])<separator<
            max(p[1] for p in r['ego']['body_xy_m']) for r in rows)
        met=met and any(r['ego']['center_xy_m'][1]>separator for r in rows)
    if suffix=='emergency_2':
        met=met and all(r.get('obstruction') is not None for r in rows)
    else:
        met=met and all(r.get('obstruction') is None for r in rows)
    return 'met' if met else 'not_met'


def one(suffix,kind,output):
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    entry=next(e for e in manifest['cases'] if e['case_id'].endswith('__'+suffix))
    source=HERE/'selected-source'/suffix/'native-motion.jsonl'
    rows=[json.loads(line) for line in source.read_text().splitlines()]
    base={'case_id':entry['case_id'],'construction_sha256':entry['construction_sha256'],
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'original_native_observed':False,'physical_acceptance_claimed':False}
    if kind=='lifecycle':
        if EVENTS[3]!='native_exit' or EVENTS[4]!='owner_released':
            raise ValueError('Native ownership closure sequence differs')
        base.update(events=EVENTS,exit_code=0,premature_saved_processing_rejected=True)
    else:
        if kind=='incomplete_motion':
            if suffix=='controlled_1':
                rows[200]['ego']['body_xy_m'][0][1]=-3.0
            else:
                for row in rows:
                    row['ego']['center_xy_m'][1]=-5.25
                    row['ego']['body_xy_m']=[[x,-5.25+(y-(-5.25))%1.0]
                        for x,y in row['ego']['body_xy_m']]
        if kind=='missing_evidence':rows.pop()
        observed=status(rows,suffix)
        expected={'complete_motion':'met','incomplete_motion':'not_met',
            'missing_evidence':'unverified'}[kind]
        if observed!=expected:raise ValueError('Physical fixture differs: '+kind+'/'+observed)
        base.update(physical_checks={'maneuver':{'status':observed,
            'method':'600 source-hashed synthetic same-tick body and lane rows; no legal cutoff',
            'sources':[str(source.relative_to(HERE))]}},
            maneuver_completed=observed=='met',
            realized_observables={'body_frame_count':len(rows),
                'obstruction_present':suffix=='emergency_2'} if observed=='met' else {},
            source_sha256=sha(source))
    write(output,base)
    print(json.dumps({'case_id':entry['case_id'],'kind':kind,
        'status':base.get('physical_checks',{}).get('maneuver',{}).get('status')}))


def build():
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1];folder=HERE/'physical-proof'/suffix
        refs=[]
        for kind in (*KINDS,'lifecycle'):
            output=folder/(kind+'.json');log=folder/(kind+'.log')
            folder.mkdir(parents=True,exist_ok=True)
            command=[sys.executable,'-B',str(Path(__file__).resolve()),
                '--case',suffix,'--kind',kind,'--output',str(output)]
            with log.open('w') as stream:
                process=subprocess.run(command,cwd=HERE.parents[1],stdout=stream,
                    stderr=subprocess.STDOUT,timeout=30)
            log.write_text(log.read_text().rstrip()+'\n')
            if process.returncode:raise ValueError('Physical fixture failed: '+str(log))
            refs.append({'kind':kind,'command':' '.join(command),'exit_code':0,
                'log':str(log.relative_to(HERE)),'log_sha256':sha(log),
                'result':str(output.relative_to(HERE)),'result_sha256':sha(output)})
        life=json.loads((folder/'lifecycle.json').read_text())
        proof={'format':'c245532-separator-physical-cpu-v1','case_id':entry['case_id'],
            'construction_sha256':entry['construction_sha256'],'fixtures':refs[:3],
            'lifecycle':{**life,'log':refs[3]['log'],
                'log_sha256':refs[3]['log_sha256']},'diagnostic_only':True,
            'original_native_observed':False}
        write(folder/'proof.json',proof)
    print(json.dumps({'physical_fixture_cases':len(manifest['cases'])}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true')
    parser.add_argument('--case');parser.add_argument('--kind',choices=(*KINDS,'lifecycle'))
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.build:build()
    elif args.case and args.kind and args.output:one(args.case,args.kind,args.output)
    else:parser.error('Choose --build or one fixture')
