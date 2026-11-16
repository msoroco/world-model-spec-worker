"""Run exact current public compatibility and saved processing on draft candidates."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'draft-execution-manifest.json'
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
    output=ROOT/'.runtime-work'/('c111256-matrix-'+key)
    saved=ROOT/'.runtime-work'/('c111256-matrix-saved-'+key)
    logs=ROOT/'.runtime-work'/('c111256-matrix-'+key+'-command.log')
    env=dict(os.environ)
    env['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    case_id=HERE.name+'__'+case
    common=['--manifest',str(MANIFEST),'--case',case_id,'--library',str(LIBRARY),'--validator',str(VALIDATOR)]
    with logs.open('w') as log:
        command=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'compatibility',*common,
                 '--candidate',candidate,'--output',str(output)]
        completed=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        if completed.returncode:
            return {'case':case,'candidate':candidate,'passed':False,'stage':'compatibility',
                    'exit_code':completed.returncode,'error_tail':'\n'.join(logs.read_text().splitlines()[-12:])}
        command=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'process-saved',*common,
                 '--attempt',str(output),'--output',str(saved)]
        completed=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        if completed.returncode:
            return {'case':case,'candidate':candidate,'passed':False,'stage':'process-saved',
                    'exit_code':completed.returncode,'error_tail':'\n'.join(logs.read_text().splitlines()[-12:])}
    a=json.loads((output/'compatibility.json').read_text())
    path=saved/'v0001/processing.json';b=json.loads(path.read_text())
    assert a['passed'] and REQUIRED<=set(a['checks']) and a['negative_removed']=='road_geometry.json'
    assert b['passed'] and not b['missing_evidence'] and b['originals_preserved']
    assert b['timestamp_joins']['frames']==480 and b['final_video_checks']['passed']
    return {'case':case,'candidate':candidate,'passed':True,
            'compatibility_receipt_sha256':sha(output/'compatibility.json'),
            'saved_receipt_sha256':sha(path),'frames':480,
            'negative_removed':a['negative_removed'],'originals_preserved':True,
            'scope':'synthetic diagnostic only; no CARLA or acceptance'}

def main():
    pending=[(case,candidate) for case in CASES for candidate in CANDIDATES
             if (case,candidate) not in (('witness_1','primary'),('exception_1_2','primary'))]
    results=[]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures={executor.submit(run,c,k):(c,k) for c,k in pending}
        for future in as_completed(futures):
            case,candidate=futures[future]
            try:record=future.result()
            except Exception as error:record={'case':case,'candidate':candidate,'passed':False,
                'stage':'orchestration','error':repr(error)}
            results.append(record)
            print(case,candidate,'PASS' if record['passed'] else 'FAIL',flush=True)
            (HERE/'public-matrix-summary.json').write_text(json.dumps({'format':'c111256-public-runtime-matrix',
                'results':sorted(results,key=lambda v:(v['case'],v['candidate']))},indent=2)+'\n')
    if any(not x['passed'] for x in results):raise SystemExit(1)

if __name__=='__main__':main()
