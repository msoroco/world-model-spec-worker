"""Retain independent exact-case audit positive/rejected software proofs."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'
PYTHON=REPO/'.venv-cpu/bin/python'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    environment=dict(os.environ,
        SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO/'.runtime-work/c10808-audit'))
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(ROOT.name+'__')
        results={}
        for mode in ('positive','negative'):
            output=REPO/'.runtime-work'/('c10808-audit-'+suffix+'-'+mode)
            if output.exists():shutil.rmtree(output)
            command=[str(PYTHON),str(ROOT/'audit_probe.py'),
                     '--case',entry['case_id'],'--mode',mode,
                     '--output',str(output)]
            run=subprocess.run(command,cwd=REPO,env=environment,text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            log=ROOT/('audit-'+suffix+'-'+mode+'.log')
            log.write_text(run.stdout)
            if mode=='positive' and run.returncode!=0:
                raise RuntimeError(suffix+' positive: '+run.stdout[-1200:])
            if mode=='negative' and (run.returncode==0 or
                    'sealed original missing or changed' not in run.stdout):
                raise RuntimeError(suffix+' negative did not reject changed source')
            results[mode]=(command,run.returncode,log)
        pos=results['positive'];neg=results['negative']
        entry['delivery_acceptance']={
            'case_id':entry['case_id'],'sets':['full-test'],
            'checks':['native_source','all_participants','time_join',
                      'full_video_decode','actual_pixels','physical_completion'],
            'script':'delivery_audit.py','script_sha256':sha(ROOT/'delivery_audit.py'),
            'command':' '.join(pos[0]),'test_exit_code':0,
            'test_log':pos[2].name,'test_log_sha256':sha(pos[2]),
            'negative_command':' '.join(neg[0]),
            'negative_exit_code':neg[1],
            'negative_expected_error':'sealed original missing or changed',
            'negative_log':neg[2].name,'negative_log_sha256':sha(neg[2]),
            'proof_scope':'Synthetic Native-shaped audit fixture only; actual source decoding and pixels require local review'}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Two exact independent audit positive/rejected CPU probes passed.')


if __name__=='__main__':main()
