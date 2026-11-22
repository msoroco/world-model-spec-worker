"""Rerun exact CPU offline and compatibility proofs for both head slots."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PYTHON=str(REPO/'.venv-cpu/bin/python')
MANIFEST=ROOT/'execution-manifest.json'
VALIDATOR=REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args,log):
    result=subprocess.run(args,cwd=REPO,text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    log.write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f'{log}: exit {result.returncode}: {result.stdout[-1200:]}')


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        for selected in [entry,*entry['candidates']]:
            candidate=selected.get('id','primary')
            name=f'{suffix}-{candidate}'
            offline_dir=REPO/'.runtime-work'/f'c111125-offline-{name}'
            compat_dir=REPO/'.runtime-work'/f'c111125-compat-{name}'
            for generated in (offline_dir,compat_dir):
                if generated.exists():shutil.rmtree(generated)
            offline=[PYTHON,'runtime.py','offline','--manifest',str(MANIFEST),
                     '--case',entry['case_id'],'--output',str(offline_dir),
                     '--python',PYTHON,'--candidate',candidate]
            offline_log=ROOT/f'proof-{name}.log'
            run(offline,offline_log)
            selected['offline']={'command':' '.join(offline),'exit_code':0,
                                 'construction_sha256':selected['construction_sha256'],
                                 'log':offline_log.name,'log_sha256':sha(offline_log)}
            compat=[PYTHON,'runtime.py','compatibility','--manifest',str(MANIFEST),
                    '--case',entry['case_id'],'--output',str(compat_dir),
                    '--library',str(REPO/'runtime/library'),'--validator',str(VALIDATOR),
                    '--candidate',candidate]
            attempt_log=ROOT/f'compat-{name}-attempt.log'
            run(compat,attempt_log)
            receipt_src=compat_dir/'compatibility.json'
            receipt=ROOT/f'compat-{name}-receipt.json'
            analysis=ROOT/f'compat-{name}-analysis.log'
            negative=ROOT/f'compat-{name}-negative.log'
            shutil.copyfile(receipt_src,receipt)
            shutil.copyfile(compat_dir/'compatibility-analysis.log',analysis)
            shutil.copyfile(compat_dir/'negative-analysis.log',negative)
            selected['compatibility']={'receipt':receipt.name,'sha256':sha(receipt),
                                       'log':analysis.name,'negative_log':negative.name,
                                       'command':' '.join(compat)}
            if candidate=='primary':selected['negative']={'log':negative.name}
            MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
