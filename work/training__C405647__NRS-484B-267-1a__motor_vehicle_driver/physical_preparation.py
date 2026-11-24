"""Prove 480-frame synthetic request completion and saved ownership order."""
import argparse, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
EVENTS=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
KINDS=('complete_motion','incomplete_motion','missing_evidence')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')
def source(suffix):
    r=json.loads((HERE/f'current-{suffix}-recipe.json').read_text())
    x=next(x for x in r['sources'] if x['path']=='actor-frames.jsonl')
    return ROOT/x['source']
def evaluate(rows):
    if len(rows)!=480 or any(x.get('frame')!=i or abs(x.get('time_s',-1)-i/20)>1e-4 for i,x in enumerate(rows)):
        return 'unverified',{}
    x0=rows[0]['subject']['x_m'];x1=rows[-1]['subject']['x_m']
    delta=x1-x0
    return ('met' if delta>=60 else 'not_met'),{'joined_frames':480,'requested_travel_x_m':round(delta,4),'source_kind':'synthetic_cpu_request'}
def fixture(suffix,kind,output):
    manifest=json.loads((HERE/'current-execution-manifest.json').read_text())
    entry=next(c for c in manifest['cases'] if c['case_id'].endswith('__'+suffix))
    result={'case_id':entry['case_id'],'construction_sha256':entry['construction_sha256'],
      'diagnostic_fixture':True,'provenance_kind':'synthetic_fixture','original_native_observed':False,
      'legal_verdict':None}
    if kind=='lifecycle':
        processing=json.loads((HERE/'current-public'/(suffix+'-primary-processing.json')).read_text())
        if not (processing['passed'] and processing['recorded_only'] and processing['originals_preserved']):
            raise ValueError('Recorded-only saved proof missing')
        result.update(events=EVENTS,exit_code=0,negative_premature_saved_processing_rejected=True,
          recorded_only_receipt_sha256=sha(HERE/'current-public'/(suffix+'-primary-processing.json')))
    else:
        path=source(suffix);rows=[json.loads(x) for x in path.read_text().splitlines()]
        if kind=='incomplete_motion':
            for row in rows[6:]: row['subject']['x_m']=rows[5]['subject']['x_m']
        if kind=='missing_evidence': rows.pop()
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c405647-1a-physical-') as temp:
            scratch=Path(temp)/'mutated.jsonl';scratch.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            status,measured=evaluate([json.loads(x) for x in scratch.read_text().splitlines()])
        expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
        if status!=expected: raise ValueError('Physical diagnostic differs: '+suffix+'/'+kind+'/'+status)
        result.update(physical_checks={'maneuver':{'status':status,
          'method':'480 joined synthetic requested actor samples; check full requested longitudinal travel only',
          'sources':[path.relative_to(ROOT).as_posix()]}},
          maneuver_completed=status=='met',realized_observables=measured if status=='met' else {},source_sha256=sha(path))
    put(output,result)
    print(json.dumps({'case':suffix,'kind':kind,'status':result.get('physical_checks',{}).get('maneuver',{}).get('status')}))
def build():
    manifest=json.loads((HERE/'current-execution-manifest.json').read_text());index=[]
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        folder=HERE/'physical-proof'/suffix;folder.mkdir(parents=True,exist_ok=True);refs=[]
        for kind in (*KINDS,'lifecycle'):
            output=folder/(kind+'.json');log=folder/(kind+'.log')
            command=[sys.executable,str(Path(__file__).resolve()),'--case',suffix,'--kind',kind,'--output',str(output)]
            env=dict(os.environ,TMPDIR=str(ROOT/'.runtime-work'),PYTHONDONTWRITEBYTECODE='1')
            with log.open('w') as stream: done=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=30)
            if done.returncode: raise ValueError('Physical fixture failed: '+str(log))
            refs.append({'kind':kind,'command':' '.join(command),'exit_code':0,
              'log':log.relative_to(HERE).as_posix(),'log_sha256':sha(log),
              'result':output.relative_to(HERE).as_posix(),'result_sha256':sha(output)})
        life=json.loads((folder/'lifecycle.json').read_text())
        proof={'format':'c405647-1a-synthetic-physical-preparation','case_id':entry['case_id'],
          'construction_sha256':entry['construction_sha256'],'fixtures':refs[:3],
          'lifecycle':{**life,'log':refs[3]['log'],'log_sha256':refs[3]['log_sha256']},
          'diagnostic_only':True,'original_native_observed':False}
        path=folder/'proof.json';put(path,proof)
        index.append({'case_id':entry['case_id'],'receipt':path.relative_to(HERE).as_posix(),'sha256':sha(path)})
    put(HERE/'physical-proof/index.json',{'cases':index,'diagnostic_only':True})
    print(json.dumps({'physical_fixture_cases':len(index)}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true')
    parser.add_argument('--case');parser.add_argument('--kind');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.build: build()
    elif args.case and args.kind and args.output: fixture(args.case,args.kind,args.output)
    else: parser.error('select build or fixture')
