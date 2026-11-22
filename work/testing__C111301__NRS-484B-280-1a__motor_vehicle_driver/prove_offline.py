"""Run pinned exact-case offline checks for the two draft constructions."""
import hashlib
import json
import shutil
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
        output=REPO/'.runtime-work'/f'c111301-offline-{suffix}'
        if output.exists():shutil.rmtree(output)
        args=[str(REPO/'.venv-cpu/bin/python'),'runtime.py','offline',
              '--manifest',str(MANIFEST),'--case',entry['case_id'],
              '--output',str(output),'--python',str(REPO/'.venv-cpu/bin/python')]
        run=subprocess.run(args,cwd=REPO,text=True,stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        log=ROOT/f'proof-{suffix}.log';log.write_text(run.stdout)
        if run.returncode:raise RuntimeError(run.stdout[-1200:])
        entry['offline']={'command':' '.join(args),'exit_code':0,
                          'construction_sha256':entry['construction_sha256'],
                          'log':log.name,'log_sha256':sha(log)}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
