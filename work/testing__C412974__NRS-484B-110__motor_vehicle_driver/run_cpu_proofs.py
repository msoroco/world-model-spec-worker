"""Run and bind each exact primary/fallback offline and compatibility proof."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SCRATCH=REPO/'.runtime-work/c412974-nov26'
VALIDATOR=REPO/'.runtime-work/c229455-validator/.lake/build/bin/adapterCheck'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def clean_copy(source,destination):
    content=Path(source).read_text(encoding='utf-8').rstrip()
    Path(destination).write_text(content+'\n' if content else '',encoding='utf-8')
def save(manifest):
    (ROOT/'execution-manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def run(command,log):
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',
      SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
      MPLCONFIGDIR=str(SCRATCH/'mpl'))
    (SCRATCH/'mpl').mkdir(parents=True,exist_ok=True)
    with log.open('w',encoding='utf-8') as out:
        process=subprocess.run(command,cwd=REPO,env=env,stdout=out,stderr=subprocess.STDOUT,text=True)
    if process.returncode:
        raise ValueError(shlex.join(command)+' failed: '+str(log))

def main():
    if not VALIDATOR.is_file():raise ValueError('local Lean decoder absent')
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        cid=entry['case_id'];suffix=cid.removeprefix(ROOT.name+'__')
        folder=ROOT/'cases'/suffix;folder.mkdir(parents=True,exist_ok=True)
        for candidate in ('primary','fallback1'):
            target=entry if candidate=='primary' else entry['candidates'][0]
            output=SCRATCH/('offline-'+suffix+'-'+candidate)
            if output.exists():shutil.rmtree(output)
            cmd=[sys.executable,'runtime.py','offline','--manifest',str(ROOT/'execution-manifest.json'),
                 '--case',cid,'--candidate',candidate,'--output',str(output)]
            run(cmd,SCRATCH/('offline-stdout-'+suffix+'-'+candidate+'.log'))
            log=folder/('proof-offline-'+candidate+'.log')
            clean_copy(output/'offline.log',log)
            target['offline']={'command':shlex.join(cmd),'exit_code':0,
              'construction_sha256':target['construction_sha256'],
              'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)}
            save(manifest)
            print(suffix,candidate,'offline',flush=True)
            output=SCRATCH/('compat-'+suffix+'-'+candidate)
            if output.exists():shutil.rmtree(output)
            cmd=[sys.executable,'runtime.py','compatibility','--manifest',str(ROOT/'execution-manifest.json'),
                 '--case',cid,'--candidate',candidate,'--output',str(output),
                 '--library','runtime/library','--validator',str(VALIDATOR)]
            run(cmd,SCRATCH/('compat-stdout-'+suffix+'-'+candidate+'.log'))
            receipt=json.loads((output/'compatibility.json').read_text())
            if (receipt['case_id']!=cid or receipt['candidate_id']!=candidate or
                receipt['construction_sha256']!=target['construction_sha256'] or
                receipt['passed'] is not True):
                raise ValueError('compatibility receipt binds different source')
            receipt_path=folder/('proof-compatibility-'+candidate+'.json')
            positive=folder/('proof-compatibility-'+candidate+'-analysis.log')
            negative=folder/('proof-compatibility-'+candidate+'-negative.log')
            clean_copy(output/'compatibility.json',receipt_path)
            clean_copy(output/'compatibility-analysis.log',positive)
            clean_copy(output/'negative-analysis.log',negative)
            target['compatibility']={'receipt':str(receipt_path.relative_to(ROOT)),
              'sha256':sha(receipt_path),'log':str(positive.relative_to(ROOT)),
              'negative_log':str(negative.relative_to(ROOT))}
            if candidate=='primary':entry['negative']={'log':str(negative.relative_to(ROOT))}
            save(manifest)
            print(suffix,candidate,'compatibility',flush=True)
if __name__=='__main__':main()
