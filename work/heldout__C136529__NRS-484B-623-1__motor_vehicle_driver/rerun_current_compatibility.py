"""Refresh exact compatibility receipts after semantic sweep proposal changes."""
import json
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent;repo=root.parents[1]
manifest=root/'execution-manifest.json';data=json.loads(manifest.read_text())
for entry in data['cases']:
    case=entry['case_id'];slug=case.removeprefix(root.name+'__').replace('__','-')
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        stem=f'{slug}-{candidate}'
        output=repo/'.runtime-work'/f'c136529-{stem}-compat-v8'
        if output.exists():raise ValueError('Retain previous exact compatibility output: '+str(output))
        command=[sys.executable,str(repo/'runtime.py'),'compatibility',
          '--manifest',str(manifest),'--case',case,'--candidate',candidate,
          '--output',str(output),'--library',str(repo/'runtime/library'),
          '--validator',str(repo/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
        process=subprocess.run(command,cwd=repo,text=True,capture_output=True)
        (root/f'{stem}-compatibility-v8.log').write_text(process.stdout+process.stderr)
        if process.returncode:raise ValueError(f'Compatibility failed for {stem}: {process.stderr[-1200:]}')
        print(stem,'compatibility PASS',flush=True)
