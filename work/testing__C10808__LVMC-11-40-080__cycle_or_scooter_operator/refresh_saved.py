"""Exercise the pinned saved-only path on both exact diagnostic source bundles."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'
PYTHON=REPO/'.venv-cpu/bin/python'
VALIDATOR=REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command):
    result=subprocess.run(command,cwd=REPO,text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    return result.returncode,result.stdout


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(ROOT.name+'__')
        alias='dismount' if suffix=='dismount_before_uturn' else 'mounted'
        source=REPO/'.runtime-work'/('c10808-compat-'+alias)
        attempt=REPO/'.runtime-work'/('c10808-saved-'+alias+'-attempt')
        if attempt.exists():shutil.rmtree(attempt)
        code,log=run([str(PYTHON),str(REPO/'runtime.py'),'materialize',
                      '--manifest',str(MANIFEST),'--case',entry['case_id'],
                      '--output',str(attempt)])
        if code:raise RuntimeError(log[-1400:])
        receipt=json.loads((ROOT/entry['compatibility']['receipt']).read_text())
        for name in receipt['fixture_manifest']:
            original=source/name
            if not original.is_file():raise ValueError('Diagnostic source missing: '+name)
            target=attempt/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(original,target)
        output=REPO/'.runtime-work'/('c10808-saved-'+alias)
        if output.exists():shutil.rmtree(output)
        command=[str(PYTHON),str(REPO/'runtime.py'),'process-saved',
                 '--manifest',str(MANIFEST),'--case',entry['case_id'],
                 '--attempt',str(attempt),'--output',str(output),
                 '--library',str(REPO/'runtime/library'),'--validator',str(VALIDATOR)]
        code,log=run(command)
        saved_log=ROOT/('saved-'+suffix+'.log');saved_log.write_text(log)
        if code:raise RuntimeError(suffix+': '+log[-1600:])
        entry['post_capture']={'recorded_only':True,'command':' '.join(command),
            'feedback_command':' '.join(command),'test_log':saved_log.name,
            'test_log_sha256':sha(saved_log),'test_exit_code':0}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Two exact saved-only CPU proofs passed.')


if __name__=='__main__':main()
