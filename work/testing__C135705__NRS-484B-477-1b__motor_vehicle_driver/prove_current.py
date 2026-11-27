"""Bind exact current-hash offline, compatibility and saved-only CPU proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
MANIFEST=HERE/'execution-manifest.json'
PYTHON=str(REPO/'.venv-cpu/bin/python')
SCRATCH=REPO/'.runtime-work/c135705-owner/current'
VALIDATOR=REPO/'.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def call(command):
    completed=subprocess.run(command,cwd=REPO,env=os.environ,capture_output=True,text=True)
    if completed.returncode:
        raise RuntimeError('proof failed: '+' '.join(command)+'\n'+completed.stderr[-3000:])
    return completed.stdout


def save(name,source):
    path=HERE/name
    path.write_text(Path(source).read_text().rstrip()+'\n')
    return path


def prove():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        slug=entry['case_id'].removeprefix(HERE.name+'__')
        for candidate in ('primary','fallback1'):
            tag=slug+'-'+candidate
            offline=SCRATCH/('offline-'+tag)
            command=[PYTHON,str(REPO/'runtime.py'),'offline','--manifest',str(MANIFEST),
                     '--case',entry['case_id'],'--output',str(offline),'--python',PYTHON]
            if candidate!='primary':command+=['--candidate',candidate]
            call(command)
            log=save('cpu-offline-'+tag+'.log',offline/'offline.log')
            target=entry if candidate=='primary' else entry['candidates'][0]
            target['offline']={'command':' '.join(command),'construction_sha256':target['construction_sha256'],
                'log':log.name,'log_sha256':sha(log),'exit_code':0}
            compat=SCRATCH/('compat-'+tag)
            ccmd=[PYTHON,str(REPO/'runtime.py'),'compatibility','--manifest',str(MANIFEST),
                  '--case',entry['case_id'],'--output',str(compat),'--library',str(REPO/'runtime/library'),
                  '--validator',str(VALIDATOR)]
            if candidate!='primary':ccmd+=['--candidate',candidate]
            call(ccmd)
            analysis=save('cpu-compat-'+tag+'-analysis.log',compat/'compatibility-analysis.log')
            negative=save('cpu-compat-'+tag+'-negative.log',compat/'negative-analysis.log')
            receipt=HERE/('cpu-compat-'+tag+'-receipt.json')
            shutil.copyfile(compat/'compatibility.json',receipt)
            target['compatibility']={'command':' '.join(ccmd),'log':analysis.name,
                'negative_log':negative.name,'receipt':receipt.name,'sha256':sha(receipt),
                'negative_log_sha256':sha(negative)}
            if candidate=='primary':entry['negative']={'log':negative.name,'log_sha256':sha(negative)}
            print('offline+compat',tag,'passed',flush=True)
    MANIFEST.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    for entry in manifest['cases']:
        slug=entry['case_id'].removeprefix(HERE.name+'__')
        attempt=SCRATCH/('compat-'+slug+'-primary')
        selection=attempt/'candidate-selection.json'
        if selection.exists():selection.unlink()
        output=SCRATCH/('saved-'+slug)
        command=[PYTHON,str(REPO/'runtime.py'),'process-saved','--manifest',str(MANIFEST),
                 '--case',entry['case_id'],'--attempt',str(attempt),'--output',str(output),
                 '--library',str(REPO/'runtime/library'),'--validator',str(VALIDATOR)]
        positive=json.loads(call(command))
        if not positive['passed'] or positive['missing_evidence'] or not positive['originals_preserved'] or not positive['timestamp_joins']['passed']:
            raise ValueError('saved positive incomplete: '+slug)
        log=HERE/('cpu-saved-'+slug+'.log')
        log.write_text(json.dumps(positive,sort_keys=True,indent=2)+'\n')
        missing=SCRATCH/('saved-missing-attempt-'+slug)
        shutil.copytree(attempt,missing)
        (missing/'original-attempt/width_history.json').unlink()
        negative=SCRATCH/('saved-missing-'+slug)
        ncmd=command.copy();ncmd[ncmd.index('--attempt')+1]=str(missing)
        ncmd[ncmd.index('--output')+1]=str(negative)
        failure=json.loads(call(ncmd))
        if not failure['missing_evidence'] or 'width_history.json' not in (negative/'v0001/feedback.json').read_text():
            raise ValueError('missing original width source not classified: '+slug)
        nlog=HERE/('cpu-saved-'+slug+'-missing.log')
        nlog.write_text(json.dumps(failure,sort_keys=True,indent=2)+'\n')
        entry['post_capture']={'command':' '.join(command),'feedback_command':' '.join(ncmd),
            'test_log':log.name,'test_log_sha256':sha(log),'test_exit_code':0,
            'feedback_log':nlog.name,'feedback_log_sha256':sha(nlog),
            'feedback_test_exit_code':0,'recorded_only':True,'diagnostic_fixture':True,
            'physical_acceptance_claimed':False}
        print('saved-only',slug,'passed',flush=True)
    MANIFEST.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':prove()
