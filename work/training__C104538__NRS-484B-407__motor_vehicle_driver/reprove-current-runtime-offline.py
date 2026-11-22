"""Recheck preserved selected sightline constructions with the current runtime."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'current-runtime-reproof-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    doc = json.loads(MANIFEST.read_text())
    current = sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    if doc['runtime_manifest_sha256'] != current:
        raise ValueError('Current runtime binding differs')
    rows = []
    for entry in doc['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            selected = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            if sha(HERE/selected['construction']) != selected['construction_sha256']:
                raise ValueError('Preserved construction changed: '+suffix+' '+candidate)
            log = HERE/f'current-runtime-{suffix}-{candidate}-offline.log'
            if not log.is_file() or '"offline_passed": true' not in log.read_text():
                output = ROOT/'.runtime-work'/f'c104538-current-{suffix}-{candidate}-offline-{time.time_ns()}'
                command = [sys.executable,str(ROOT/'runtime.py'),'offline','--manifest',str(MANIFEST),
                           '--case',entry['case_id'],'--candidate',candidate,'--output',str(output),
                           '--python',sys.executable]
                with log.open('w') as stream:
                    status = subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT).returncode
                if status != 0:
                    raise RuntimeError('Current-runtime offline failed: '+str(log))
            proof = json.loads(log.read_text())
            if not proof.get('offline_passed') or proof['case_id'] != entry['case_id'] or proof['candidate_id'] != candidate:
                raise ValueError('Offline receipt identity differs')
            rows.append({'case_id':entry['case_id'],'candidate_id':candidate,
                         'construction_sha256':selected['construction_sha256'],
                         'log':log.name,'log_sha256':sha(log)})
            print(suffix,candidate,'offline passed',flush=True)
    path=HERE/'current-runtime-offline-reproof.json'
    path.write_text(json.dumps({'format':'c104538-current-runtime-offline-v1',
        'runtime_manifest_sha256':current,'manifest_sha256':sha(MANIFEST),'rows':rows},indent=2)+'\n')


if __name__ == '__main__':
    main()
