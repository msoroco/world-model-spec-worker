"""Re-run every hash-bound CPU-selected candidate with the current pinned runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=HERE/'selected-cpu-manifest.json'
PYTHON=ROOT/'.venv-cpu/bin/python'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    receipts=[]
    for case_index,case in enumerate(manifest['cases'],1):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            body=case if candidate=='primary' else next(x for x in case['candidates'] if x['id']==candidate)
            path=HERE/body['construction']
            if sha(path)!=body['construction_sha256']:
                raise ValueError('Construction hash mismatch: '+str(path))
            output=ROOT/'.runtime-work'/f'c329610-400-selected-{case_index}-{candidate}'
            command=[str(PYTHON),str(ROOT/'runtime.py'),'offline','--manifest',str(MANIFEST),
                '--case',case['case_id'],'--candidate',candidate,'--output',str(output),'--python',str(PYTHON)]
            run=subprocess.run(command,cwd=ROOT,env=os.environ.copy(),text=True,capture_output=True,timeout=300)
            if run.returncode:
                raise RuntimeError(f'{case_index}/{candidate} pinned offline failed: '+run.stdout+run.stderr)
            result=json.loads(run.stdout)
            if result.get('offline_passed') is not True or result.get('simulation_started') is not False:
                raise ValueError('Offline receipt status differs')
            receipts.append({'case_id':case['case_id'],'candidate_id':candidate,
                'construction_sha256':body['construction_sha256'],
                'offline_log_sha256':sha(output/'offline.log'),'simulation_started':False})
            print(case_index,candidate,'passed',flush=True)
    (HERE/'selected-cpu-offline-summary.json').write_text(json.dumps({
        'format':'selected-cpu-offline-summary-v1','manifest_sha256':sha(MANIFEST),
        'receipts':receipts,'physical_acceptance_claimed':False},indent=2)+'\n')


if __name__=='__main__':main()
