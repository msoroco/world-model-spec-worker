"""Regenerate all exact offline and compatibility CPU receipts after bundle changes."""
import json
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
repo=root.parents[1]
manifest=root/'execution-manifest.json'
data=json.loads(manifest.read_text())
for entry in data['cases']:
    case=entry['case_id']
    if '_speed_probe__' not in case: continue
    branch=case.removeprefix(root.name+'__').replace('__','-')
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        stem=f'{branch}-{candidate}'
        for mode in ('offline','compatibility'):
            suffix='offline' if mode=='offline' else 'compat'
            output=repo/'.runtime-work'/f'c136529-{stem}-{suffix}-v7'
            if output.exists():
                raise ValueError('Retain previous exact proof output: '+str(output))
            command=[sys.executable,str(repo/'runtime.py'),mode,'--manifest',str(manifest),
                     '--case',case,'--candidate',candidate,'--output',str(output)]
            if mode=='offline':command+=['--python',sys.executable]
            else:command+=['--library',str(repo/'runtime/library'),
                            '--validator',str(repo/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
            process=subprocess.run(command,cwd=repo,text=True,capture_output=True)
            (root/f'{stem}-{mode}-v7.log').write_text(process.stdout+process.stderr)
            if process.returncode:
                raise ValueError(f'{mode} failed for {stem}: {process.stderr[-900:]}')
            print(stem,mode,'PASS',flush=True)
