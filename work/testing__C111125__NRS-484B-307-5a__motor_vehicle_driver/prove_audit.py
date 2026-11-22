"""Bind positive and negative synthetic delivery-audit tests to exact cases."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        specs=[]
        for negative in (False,True):
            output=REPO/'.runtime-work'/f'c111125-audit-{suffix}'/('negative' if negative else 'positive')
            args=[str(REPO/'.venv-cpu/bin/python'),str(ROOT/'audit_probe.py'),
                  '--case',entry['case_id'],'--output',str(output)]
            if negative:args.append('--negative')
            run=subprocess.run(args,cwd=REPO,text=True,stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
            log=ROOT/f'audit-{suffix}-{"negative" if negative else "positive"}.log'
            log.write_text(run.stdout)
            if (negative and (run.returncode==0 or 'sealed original missing or changed' not in run.stdout)) or (not negative and run.returncode):
                raise RuntimeError(f'{suffix} audit probe failed: {run.stdout[-1000:]}')
            specs.append((' '.join(args),run.returncode,log.name,sha(log)))
        positive,negative=specs
        entry['delivery_acceptance']={'case_id':entry['case_id'],'sets':['full-test'],
             'checks':['native_source','all_participants','time_join','full_video_decode',
                       'actual_pixels','physical_completion'],
             'script':'delivery_audit.py','script_sha256':sha(ROOT/'delivery_audit.py'),
             'command':positive[0],'test_exit_code':positive[1],
             'test_log':positive[2],'test_log_sha256':positive[3],
             'negative_command':negative[0],'negative_exit_code':negative[1],
             'negative_expected_error':'sealed original missing or changed',
             'negative_log':negative[2],'negative_log_sha256':negative[3]}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
