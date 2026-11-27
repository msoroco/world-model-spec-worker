"""Exercise recorded-only processing of every case against pinned diagnostics."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
SCRATCH=REPO/'.runtime-work/c412974-nov26/saved'
VALIDATOR=REPO/'.runtime-work/c229455-validator/.lake/build/bin/adapterCheck'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(cmd,log):
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',
      SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
      MPLCONFIGDIR=str(SCRATCH/'mpl'))
    (SCRATCH/'mpl').mkdir(parents=True,exist_ok=True)
    p=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True)
    log.write_text(((p.stdout+p.stderr).rstrip() or 'saved-only command exited '+str(p.returncode))+'\n',encoding='utf-8')
    if p.returncode:raise ValueError(shlex.join(cmd)+' failed: '+str(log))

def main():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    path=ROOT/'execution-manifest.json';manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        cid=entry['case_id'];suffix=cid.removeprefix(ROOT.name+'__')
        attempt=SCRATCH/('attempt-'+suffix);output=SCRATCH/('processed-'+suffix)
        if attempt.exists():shutil.rmtree(attempt)
        if output.exists():shutil.rmtree(output)
        run([sys.executable,'runtime.py','compatibility','--manifest',str(path),
             '--case',cid,'--candidate','primary','--output',str(attempt),
             '--library','runtime/library','--validator',str(VALIDATOR)],
             SCRATCH/('source-'+suffix+'.log'))
        cmd=[sys.executable,'runtime.py','process-saved','--manifest',str(path),
             '--case',cid,'--attempt',str(attempt),'--output',str(output),
             '--library','runtime/library','--validator',str(VALIDATOR)]
        log=ROOT/('proof-saved-'+suffix+'.log');run(cmd,log)
        receipt=json.loads((output/'v0001/processing.json').read_text())
        if (receipt.get('case_id')!=cid or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or receipt.get('missing_evidence')):
            raise ValueError('saved-only proof not bound to selected case')
        entry['post_capture']={'recorded_only':True,
          'command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+ROOT.name+
            '/execution-manifest.json --case '+cid+' --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR',
          'feedback_command':'.venv-cpu/bin/python runtime.py process-saved --manifest work/'+ROOT.name+
            '/execution-manifest.json --case '+cid+' --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR',
          'test_log':log.name,'test_log_sha256':sha(log),'test_exit_code':0,
          'scope':'synthetic saved-only software replay; original designation, pixels and physical review pending'}
        path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print(suffix,'saved-only',flush=True)
if __name__=='__main__':main()
