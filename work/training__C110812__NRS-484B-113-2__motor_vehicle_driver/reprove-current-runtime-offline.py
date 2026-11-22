"""Run every preserved selected construction against the currently pinned runtime."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'current-runtime-reproof-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    current = sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    if manifest['runtime_manifest_sha256'] != current:
        raise ValueError('Reproof manifest is stale')
    results = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__',1)[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            chosen = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            source = HERE/chosen['construction']
            if sha(source) != chosen['construction_sha256']:
                raise ValueError('Selected construction changed: '+str(source))
            stem = 'current-runtime-reproof-'+suffix+'-'+candidate
            log = HERE/(stem+'-offline.log')
            output = ROOT/'.runtime-work'/('c110812-'+stem)
            command = [sys.executable,str(ROOT/'runtime.py'),'offline',
                       '--manifest',str(MANIFEST),'--case',entry['case_id'],
                       '--candidate',candidate,'--output',str(output)]
            with log.open('w') as file:
                status = subprocess.run(command,cwd=ROOT,stdout=file,stderr=subprocess.STDOUT).returncode
            results.append({'case_id':entry['case_id'],'candidate_id':candidate,
                            'construction_sha256':chosen['construction_sha256'],
                            'exit_code':status,'log':log.name,'log_sha256':sha(log)})
            if status:
                raise RuntimeError('Offline current-runtime reproof failed: '+str(log))
    return {'format':'c110812-current-runtime-offline-reproof-v1',
            'assignment_id':HERE.name,'runtime_manifest_sha256':current,
            'manifest_sha256':sha(MANIFEST),'passed':True,'candidate_count':len(results),
            'results':results,'compatibility_and_saved_reproof_pending':True}


if __name__=='__main__':
    print(json.dumps(main(),indent=2,sort_keys=True))
