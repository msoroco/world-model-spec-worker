"""Exact selected offline, public compatibility and saved CPU diagnostics."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,json,os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MANIFEST=HERE/'execution-manifest.json'
LIBRARY=ROOT/'runtime/pipeline/library'
VALIDATOR=ROOT/'.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'
CASES=('witness_1','witness_2','exception_1_1','exception_1_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
REQUIRED={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
 'render','final_decode','acquisition_unchanged','derived_outputs_rebuilt',
 'four_camera_sources','selected_measurements','negative_case_source'}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run(case,candidate):
    key=f'{case}-{candidate}'
    prefix=ROOT/'.runtime-work'/('c111256-selected-'+key)
    offline=Path(str(prefix)+'-offline');output=Path(str(prefix)+'-compat');saved=Path(str(prefix)+'-saved')
    log=Path(str(prefix)+'-command.log')
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    case_id=HERE.name+'__'+case
    common=['--manifest',str(MANIFEST),'--case',case_id,'--candidate',candidate]
    commands=[
      [str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'offline',*common,
       '--output',str(offline),'--python',str(ROOT/'.venv-cpu/bin/python')],
      [str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'compatibility',*common,
       '--output',str(output),'--library',str(LIBRARY),'--validator',str(VALIDATOR)],
      [str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'process-saved',
       '--manifest',str(MANIFEST),'--case',case_id,'--attempt',str(output),
       '--output',str(saved),'--library',str(LIBRARY),'--validator',str(VALIDATOR)] ]
    with log.open('w') as stream:
        for stage,command in zip(('offline','compatibility','process-saved'),commands):
            stream.write('\nSTAGE '+stage+'\n');stream.flush()
            completed=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
            if completed.returncode:
                return {'case':case,'candidate':candidate,'passed':False,'stage':stage,
                        'exit_code':completed.returncode,'error_tail':'\n'.join(log.read_text().splitlines()[-12:])}
    a=json.loads((output/'compatibility.json').read_text())
    path=saved/'v0001/processing.json';b=json.loads(path.read_text())
    assert a['passed'] and REQUIRED<=set(a['checks']) and a['negative_removed']=='road_geometry.json'
    assert b['passed'] and not b['missing_evidence'] and b['originals_preserved']
    assert b['timestamp_joins']['frames']==480 and b['final_video_checks']['passed']
    return {'case':case,'candidate':candidate,'passed':True,
        'offline_log_sha256':sha(offline/'offline.log'),
        'compatibility_receipt_sha256':sha(output/'compatibility.json'),
        'saved_receipt_sha256':sha(path),'frames':480,'negative_removed':'road_geometry.json',
        'originals_preserved':True,'scope':'selected CPU diagnostic only; no original CARLA or acceptance'}

def main():
    pending=[(c,k) for c in CASES for k in CANDIDATES if (c,k)!=('witness_1','primary')]
    results=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(run,c,k):(c,k) for c,k in pending}
        for future in as_completed(futures):
            c,k=futures[future]
            try:r=future.result()
            except Exception as error:r={'case':c,'candidate':k,'passed':False,'stage':'orchestration','error':repr(error)}
            results.append(r)
            print(c,k,'PASS' if r['passed'] else 'FAIL',flush=True)
            (HERE/'selected-matrix-summary.json').write_text(json.dumps({'format':'c111256-selected-runtime-matrix',
                'results':sorted(results,key=lambda x:(x['case'],x['candidate']))},indent=2)+'\n')
    if any(not x['passed'] for x in results):raise SystemExit(1)
if __name__=='__main__':main()
