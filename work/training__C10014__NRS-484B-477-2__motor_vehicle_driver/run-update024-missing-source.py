"""Reproduce selected missing-Native-samples saved diagnostics, never originals."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PYTHON=REPO/'.venv-cpu/bin/python'
VALIDATOR=REPO/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def main():
    if not VALIDATOR.is_file():raise FileNotFoundError(VALIDATOR)
    manifest=HERE/'execution-manifest-staged-update021.json'
    entries={c['case_id'].rsplit('__',1)[-1]:c for c in json.loads(manifest.read_text())['cases']}
    for suffix in ('reference','contrast'):
        source=REPO/f'.runtime-work/c10014-update021-{suffix}-primary-compat'
        attempt=REPO/f'.runtime-work/c10014-update024-{suffix}-primary-missing-samples'
        saved=REPO/f'.runtime-work/c10014-update024-{suffix}-primary-missing-saved'
        if attempt.exists() or saved.exists():raise FileExistsError('Retain prior diagnostic: '+str(attempt))
        shutil.copytree(source,attempt)
        (attempt/'native_samples.jsonl').unlink()
        command=[str(PYTHON),str(REPO/'runtime.py'),'process-saved',
                 '--manifest',str(manifest),'--case',entries[suffix]['case_id'],
                 '--attempt',str(attempt),'--output',str(saved),
                 '--library',str(REPO/'runtime/pipeline/library'),
                 '--validator',str(VALIDATOR)]
        run=subprocess.run(command,cwd=REPO,capture_output=True,text=True,timeout=300)
        log=HERE/f'update024-{suffix}-primary-missing-source.log'
        log.write_text(run.stdout+run.stderr)
        if run.returncode:raise RuntimeError(f'{suffix} saved diagnostic exit {run.returncode}: {log}')
        receipt=json.loads((saved/'v0001/processing.json').read_text())
        if receipt.get('missing_evidence') is not True or receipt.get('recorded_only') is not True:
            raise ValueError('Missing Native samples did not cause missing-evidence saved path')
        print(json.dumps({'case':suffix,'missing_evidence':True,'saved':str(saved/'v0001')}),flush=True)


if __name__=='__main__':main()
