"""Run all eight unselected constructions through the pinned runtime offline path."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPOSITORY=ROOT.parents[1]
MANIFEST=ROOT/'draft-current-runtime-manifest.json'
BASE=ROOT/'.runtime-work'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

matrix=[]
for witness in ('reference','contrast'):
    case=ROOT.name+'__'+witness
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        output=BASE/('update015-'+witness+'-'+candidate+'-'+sha(MANIFEST)[:12])
        command=[sys.executable,str(REPOSITORY/'runtime.py'),'offline',
                 '--manifest',str(MANIFEST),'--case',case,
                 '--candidate',candidate,'--output',str(output)]
        result=subprocess.run(command,cwd=REPOSITORY,capture_output=True,text=True)
        log=ROOT/('update015-current-offline-'+witness+'-'+candidate+'.log')
        log.write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError('Pinned offline failed: '+str(log))
        receipt=json.loads(result.stdout)
        if (receipt.get('offline_passed') is not True or
                receipt.get('simulation_started') is not False or
                receipt.get('case_id')!=case or
                receipt.get('candidate_id')!=candidate or
                'OK' not in (output/'offline.log').read_text()):
            raise ValueError('Pinned offline receipt differs: '+candidate)
        matrix.append({'case_id':case,'candidate_id':candidate,
                       'command':' '.join(command),'exit_code':0,
                       'log':log.name,'log_sha256':sha(log),
                       'runtime_offline_log_sha256':sha(output/'offline.log'),
                       'construction_sha256':sha(output/'construction.json')})
proof={'format':'c132497-unselected-current-runtime-offline-v1',
       'manifest_sha256':sha(MANIFEST),'passed':True,
       'constructions':matrix,'count':len(matrix),
       'compatibility_passed':False,'process_saved_passed':False,
       'original_native_observed':False,'delivery_ready':False}
path=ROOT/'update015-current-offline-matrix.json'
path.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'passed':True,'count':len(matrix),'sha256':sha(path)}))
