"""Run exact source-gated offline checks for all primary and fallback bundles."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PYTHON=str(REPO/'.venv-cpu/bin/python')
SCRATCH=REPO/'.runtime-work/c135705-owner/offline'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest_path=HERE/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    SCRATCH.mkdir(parents=True,exist_ok=True)
    for entry in manifest['cases']:
        slug=entry['case_id'].removeprefix(HERE.name+'__')
        for candidate in ('primary','fallback1'):
            tag=slug+'-'+candidate
            output=SCRATCH/tag
            if output.exists():
                raise ValueError('scratch attempt already exists: '+str(output))
            command=[PYTHON,str(REPO/'runtime.py'),'offline','--manifest',str(manifest_path),
                     '--case',entry['case_id'],'--output',str(output),'--python',PYTHON]
            if candidate!='primary':command+=['--candidate',candidate]
            completed=subprocess.run(command,cwd=REPO,env=os.environ,capture_output=True,text=True)
            if completed.returncode:
                raise RuntimeError('offline failed: '+tag+' '+completed.stderr[-1500:])
            log=HERE/('cpu-offline-'+tag+'.log')
            log.write_text((output/'offline.log').read_text().rstrip()+'\n')
            target=entry if candidate=='primary' else entry['candidates'][0]
            target['offline']={'command':' '.join(command),'construction_sha256':target['construction_sha256'],
                               'log':log.name,'log_sha256':sha(log),'exit_code':0}
            print('offline',tag,'passed',flush=True)
    manifest_path.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':prove()
