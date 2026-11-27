"""Bind CPU positive and negative independent delivery predicate tests."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
repo=root.parents[1]
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
script=root/'delivery_audit.py'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
    folder=root/'delivery-proofs';folder.mkdir(exist_ok=True)
    base=[sys.executable,'-B',str(script),'--case',case,'--self-test']
    commands={'test':base,'negative':base+['--negative']}
    runs={}
    for kind,command in commands.items():
        run=subprocess.run(command,cwd=repo,text=True,capture_output=True,
                           env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        log=folder/(suffix+'-'+kind+'.log')
        log.write_text(run.stdout+run.stderr)
        runs[kind]={'command':' '.join(command),'exit_code':run.returncode,
                    'log':str(log.relative_to(root)),'log_sha256':sha(log)}
    assert runs['test']['exit_code']==0 and runs['negative']['exit_code']!=0
    assert 'Missing original source: exact original Native result' in (root/runs['negative']['log']).read_text()
    entry['delivery_acceptance']={'case_id':case,'sets':['full-train'],
        'checks':['native_source','all_participants','time_join','full_video_decode',
                  'actual_pixels','physical_completion'],
        'script':'delivery_audit.py','script_sha256':sha(script),
        'command':runs['test']['command'],'test_exit_code':0,
        'test_log':runs['test']['log'],'test_log_sha256':runs['test']['log_sha256'],
        'negative_command':runs['negative']['command'],
        'negative_exit_code':runs['negative']['exit_code'],
        'negative_expected_error':'Missing original source: exact original Native result',
        'negative_log':runs['negative']['log'],
        'negative_log_sha256':runs['negative']['log_sha256'],
        'scope':'CPU predicates only; original Native capture pending'}
manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
