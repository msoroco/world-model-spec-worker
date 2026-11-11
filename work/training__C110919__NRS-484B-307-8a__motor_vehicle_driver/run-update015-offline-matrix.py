"""Run eight current source-bound offline construction checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
MANIFEST=HERE/'draft-execution-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest=json.loads(MANIFEST.read_text())
    rows=[]
    for case in manifest['cases']:
        suffix=case['case_id'].split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            folder=HERE/'update015-offline-logs-v2'/suffix
            folder.mkdir(parents=True,exist_ok=True)
            log=folder/(candidate+'.log')
            output=REPO/'.runtime-work/c110919-update015-offline-v2'/suffix/candidate
            command=[sys.executable,str(REPO/'runtime.py'),'offline','--manifest',str(MANIFEST),
                     '--case',case['case_id'],'--candidate',candidate,'--output',str(output)]
            result=subprocess.run(command,cwd=REPO,capture_output=True,text=True)
            log.write_text(result.stdout+result.stderr)
            if result.returncode:raise ValueError('Current right-turn offline failed: '+str(log))
            rows.append({'case_id':case['case_id'],'candidate_id':candidate,
                         'construction_sha256':case['construction_sha256'] if candidate=='primary'
                             else next(row['construction_sha256'] for row in case['candidates'] if row['id']==candidate),
                         'log':log.relative_to(HERE).as_posix(),'log_sha256':sha(log),'exit_code':0})
            print(json.dumps({'case':suffix,'candidate':candidate,'passed':True}),flush=True)
    summary={'format':'c110919-update015-unselected-offline-matrix',
             'manifest_sha256':sha(MANIFEST),
             'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
             'rows':rows,'passed':len(rows),'selected':False}
    path=HERE/'update015-offline-summary.json'
    path.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'summary_sha256':sha(path),'passed':len(rows)}))


if __name__=='__main__':run()
