"""Run pinned runtime.py offline over all eight paragraph (a) candidates."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

BRANCH=Path(__file__).resolve().parent
CASE=BRANCH.parent.parent
ROOT=CASE.parents[1]
MANIFEST=BRANCH/'draft-execution-manifest.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def prove():
    run=uuid.uuid4().hex[:12];entries=[]
    for witness in ('exception_1_1','exception_1_2'):
        case_id=CASE.name+'__'+witness
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            output=ROOT/'.runtime-work'/f'c146314-a-{run}-{witness}-{candidate}'
            result=subprocess.run([sys.executable,str(ROOT/'runtime.py'),'offline',
                '--manifest',str(MANIFEST),'--case',case_id,
                '--candidate',candidate,'--output',str(output)],
                cwd=ROOT,capture_output=True,text=True,timeout=330)
            if result.returncode:
                raise RuntimeError('paragraph (a) pinned offline: '+result.stdout+result.stderr)
            response=json.loads(result.stdout);log=output/'offline.log'
            if (not response['offline_passed'] or response['simulation_started'] or
                    'Ran 5 tests' not in log.read_text() or
                    '\nOK\n' not in log.read_text()):
                raise ValueError('paragraph (a) offline receipt')
            choice=json.loads((output/'candidate-selection.json').read_text())
            entries.append({'case_id':case_id,'candidate_id':candidate,
                'construction_sha256':choice['construction_sha256'],
                'materialized_dir':str(output.relative_to(ROOT)),
                'log_sha256':sha(log),'tests':5,'exit_code':0,
                'simulation_started':False})
    proof={'format':'c146314-paragraph-a-pinned-offline-v1',
        'manifest_sha256':sha(MANIFEST),'entries':entries,'passed':True,
        'original_native_observed':False,'delivery_ready':False}
    (BRANCH/'offline/pinned-runtime-proof.json').write_text(
        json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    p=prove();print(json.dumps({'passes':len(p['entries']),
                                'tests':sum(x['tests'] for x in p['entries'])}))
