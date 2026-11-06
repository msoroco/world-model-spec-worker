"""Exercise all eight exact synthetic positive/negative v1 packages."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON=ROOT/'.venv-cpu/bin/python'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    env=dict(os.environ)
    env['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+env.get('LD_LIBRARY_PATH','')
    results=[]
    for case in ('condition_a','condition_b'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            log=HERE/'native'/f'package-{case}-{candidate}.log'
            command=[str(PYTHON),str(HERE/'probe-package.py'),
                     '--case',case,'--candidate',candidate]
            completed=subprocess.run(command,cwd=ROOT,env=env,text=True,
                                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
            log.write_text(completed.stdout)
            record={'case':case,'candidate':candidate,'exit_code':completed.returncode,
                    'log':str(log.relative_to(HERE)),'log_sha256':sha(log),
                    'scope':'synthetic v1 software diagnostic; no selected delivery proof'}
            results.append(record)
            print(case,candidate,'exit',completed.returncode,flush=True)
            if completed.returncode:
                break
        if results[-1]['exit_code']:
            break
    (HERE/'package-probes-summary.json').write_text(json.dumps({
        'format':'c110919-unselected-v1-package-diagnostics','results':results},indent=2)+'\n')
    if len(results)!=8 or any(item['exit_code'] for item in results):raise SystemExit(1)

if __name__=='__main__':run()
