"""Run each exact current-runtime offline construction and bind its log."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path,text):
    SCRATCH.mkdir(parents=True,exist_ok=True)
    stage = SCRATCH/(path.name+'.stage')
    stage.write_text(text.rstrip()+'\n')
    os.replace(stage,path)


def main():
    manifest = ROOT/'selected-preflight-manifest.json'
    entries = json.loads(manifest.read_text())['cases']
    rows = []
    for entry in entries:
        case = entry['case_id']
        suffix = case.rsplit('__',1)[-1]
        attempt = SCRATCH/'offline-batch'/suffix
        if attempt.exists():
            raise ValueError('Retain prior offline attempt: '+suffix)
        command = [str(REPO/'.venv-cpu/bin/python'),'-B',str(REPO/'runtime.py'),
                   'offline','--manifest',str(manifest),'--case',case,
                   '--output',str(attempt),'--python',str(REPO/'.venv-cpu/bin/python')]
        env = dict(os.environ)
        env['TMPDIR'] = str(SCRATCH)
        subprocess.run(command,cwd=REPO,env=env,check=True,
                       stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        destination = ROOT/'selected-offline'/(suffix+'.log')
        destination.parent.mkdir(parents=True,exist_ok=True)
        atomic(destination,(attempt/'offline.log').read_text())
        rows.append({'case_id':case,'construction_sha256':entry['construction_sha256'],
                     'command':' '.join(command),'exit_code':0,
                     'log':str(destination.relative_to(ROOT)),
                     'log_sha256':sha(destination)})
        print(json.dumps({'case':suffix,'offline':'passed'}),flush=True)
    index = ROOT/'selected-offline/index.json'
    atomic(index,json.dumps({'format':'c132924-selected-offline-v1','checks':rows},indent=2))
    print(json.dumps({'selected_offline_passed':len(rows),'index_sha256':sha(index)}))


if __name__=='__main__':
    main()
