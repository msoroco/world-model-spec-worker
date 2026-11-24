"""Run recorded-only saved processing for all selected diagnostic candidates."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PUBLIC=HERE/'current-public'
VALIDATOR=ROOT/'.runtime-work/c329610-decoder/.lake/build/bin/adapterCheck'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def run(item):
    branch,suffix,candidate=item
    name=suffix+'-'+candidate
    attempt=ROOT/'.runtime-work'/('c405647-1a-'+name+'-public')
    output=ROOT/'.runtime-work'/('c405647-1a-'+name+'-saved-final')
    if output.exists(): shutil.rmtree(output)
    command=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'process-saved',
       '--manifest',str(HERE/('current-'+branch+'-manifest.json')),
       '--case',HERE.name+'__'+suffix,'--attempt',str(attempt),'--output',str(output),
       '--library',str(ROOT/'runtime/library'),'--validator',str(VALIDATOR)]
    env=dict(os.environ,TMPDIR=str(ROOT/'.runtime-work'),PYTHONDONTWRITEBYTECODE='1',
             SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT/'.runtime-work/c405647-1a-runtime-import'))
    done=subprocess.run(command,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=900)
    log=PUBLIC/(name+'-saved-command.log')
    log.write_text(done.stdout.rstrip()+'\n')
    result={'branch':branch,'case':suffix,'candidate':candidate,'exit_code':done.returncode,
            'log':log.relative_to(HERE).as_posix(),'log_sha256':sha(log)}
    if done.returncode:
        result['error']=done.stdout[-1200:]
    else:
        target=PUBLIC/(name+'-processing.json')
        shutil.copyfile(output/'v0001/processing.json',target)
        result['receipt']=target.relative_to(HERE).as_posix()
        result['receipt_sha256']=sha(target)
    return result

def main():
    items=[(branch,suffix,candidate)
      for branch,cases in [('witness',('witness_1','witness_2')),
                           ('exception',('exception_1_1','exception_1_2')),
                           ('official',('official_1','official_2'))]
      for suffix in cases for candidate in ('primary','fallback1','fallback2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(run,items))
    (PUBLIC/'all-selected-saved-summary.json').write_text(json.dumps({'results':rows},indent=2)+'\n')
    for row in rows:
        print(row['case'],row['candidate'],row['exit_code'],flush=True)
        if row['exit_code']: print(row['error'],flush=True)
    if any(row['exit_code'] for row in rows): raise SystemExit(1)

if __name__=='__main__': main()
