"""Run pinned runtime.py offline for all eight unselected C146314 bundles."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
MANIFEST=CASE/'draft-execution-manifest.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest=json.loads(MANIFEST.read_text())
    run=uuid.uuid4().hex[:12]
    entries=[]
    for witness in ('witness_1','witness_2'):
        case_id=CASE.name+'__'+witness
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            output=ROOT/'.runtime-work'/f'c146314-pinned-{run}-{witness}-{candidate}'
            command=[sys.executable,str(ROOT/'runtime.py'),'offline',
                '--manifest',str(MANIFEST),'--case',case_id,
                '--candidate',candidate,'--output',str(output)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,
                                  text=True,timeout=330)
            if result.returncode:
                raise RuntimeError('Pinned offline failed: '+
                                   result.stdout+result.stderr)
            response=json.loads(result.stdout)
            log=output/'offline.log'
            if (response['offline_passed'] is not True or
                response['simulation_started'] is not False or
                log.read_text().count('Ran 3 tests')!=1 or
                'OK' not in log.read_text()):
                raise ValueError('Pinned offline receipt/test log differs')
            selected=json.loads((output/'candidate-selection.json').read_text())
            entries.append({'case_id':case_id,'candidate_id':candidate,
                'construction_sha256':selected['construction_sha256'],
                'materialized_dir':str(output.relative_to(ROOT)),
                'log_sha256':sha(log),'tests':3,'exit_code':result.returncode,
                'simulation_started':False})
    proof={'format':'c146314-pinned-runtime-offline-diagnostic-v1',
        'manifest_sha256':sha(MANIFEST),'entries':entries,
        'passed':True,'original_native_observed':False,
        'delivery_ready':False}
    path=CASE/'offline'/'pinned-runtime-proof.json'
    path.write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    x=prove();print(json.dumps({'pinned_offline_passes':len(x['entries']),
                                'tests':sum(e['tests'] for e in x['entries'])}))
