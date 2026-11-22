"""Prove saved-only processing on the current exact primary diagnostic bundles."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'
VALIDATOR=REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix='clear' if entry['case_id'].endswith('clear_path') else 'crossing'
        source=REPO/'.runtime-work'/f'c111301-compat-{suffix}'
        attempt=REPO/'.runtime-work'/f'c111301-saved-{suffix}-attempt-refresh'
        if attempt.exists():shutil.rmtree(attempt)
        materialize=[str(REPO/'.venv-cpu/bin/python'),'runtime.py','materialize',
                     '--manifest',str(MANIFEST),'--case',entry['case_id'],
                     '--output',str(attempt)]
        created=subprocess.run(materialize,cwd=REPO,text=True,stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
        if created.returncode:raise RuntimeError(created.stdout[-1000:])
        receipt=json.loads((ROOT/f'compat-{suffix}-receipt.json').read_text())
        for name in receipt['fixture_manifest']:
            original=source/name
            if not original.is_file():raise RuntimeError('diagnostic source missing: '+name)
            target=attempt/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(original,target)
        output=REPO/'.runtime-work'/f'c111301-saved-{suffix}-refresh'
        if output.exists():shutil.rmtree(output)
        args=[str(REPO/'.venv-cpu/bin/python'),'runtime.py','process-saved',
              '--manifest',str(MANIFEST),'--case',entry['case_id'],
              '--attempt',str(attempt),'--output',str(output),
              '--library',str(REPO/'runtime/library'),'--validator',str(VALIDATOR)]
        result=subprocess.run(args,cwd=REPO,text=True,stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        log=ROOT/f'saved-{suffix}-refresh.log';log.write_text(result.stdout)
        if result.returncode:raise RuntimeError(f'{suffix}: {result.stdout[-1200:]}')
        entry['post_capture']={'recorded_only':True,'command':' '.join(args),
                               'feedback_command':' '.join(args),
                               'test_log':log.name,'test_log_sha256':sha(log),
                               'test_exit_code':0}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
