"""Run exact offline and compatibility proofs for the paired visibility fallback."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PYTHON=REPO/'.venv-cpu/bin/python'
MANIFEST=ROOT/'execution-manifest.json'
VALIDATOR=REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command,output):
    if output.exists():shutil.rmtree(output)
    result=subprocess.run(command,cwd=REPO,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(result.stdout[-1800:])


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(ROOT.name+'__')
        candidate=entry['candidates'][0]
        output=REPO/'.runtime-work'/('c10808-fallback-offline-'+suffix)
        command=[str(PYTHON),str(REPO/'runtime.py'),'offline',
                 '--manifest',str(MANIFEST),'--case',entry['case_id'],
                 '--candidate','fallback1','--output',str(output),
                 '--python',str(PYTHON)]
        execute(command,output)
        log=ROOT/('proof-'+suffix+'-fallback1.log')
        shutil.copyfile(output/'offline.log',log)
        candidate['offline']={'command':' '.join(command),'exit_code':0,
            'construction_sha256':candidate['construction_sha256'],
            'log':log.name,'log_sha256':sha(log)}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
        output=REPO/'.runtime-work'/('c10808-fallback-compat-'+suffix)
        command=[str(PYTHON),str(REPO/'runtime.py'),'compatibility',
                 '--manifest',str(MANIFEST),'--case',entry['case_id'],
                 '--candidate','fallback1','--output',str(output),
                 '--library',str(REPO/'runtime/library'),
                 '--validator',str(VALIDATOR)]
        execute(command,output)
        proof=json.loads((output/'compatibility.json').read_text())
        if (proof.get('passed') is not True or proof.get('candidate_id')!='fallback1' or
                proof.get('construction_sha256')!=candidate['construction_sha256']):
            raise ValueError('Fallback compatibility receipt changed')
        files={}
        for key,source,ending in (
                ('receipt','compatibility.json','receipt.json'),
                ('log','compatibility-analysis.log','analysis.log'),
                ('negative_log','negative-analysis.log','negative.log')):
            target=ROOT/('compat-'+suffix+'-fallback1-'+ending)
            shutil.copyfile(output/source,target)
            files[key]=target.name
        files['sha256']=sha(ROOT/files['receipt'])
        files['command']=' '.join(command)
        candidate['compatibility']=files
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Two paired fallback offline and positive/missing-source compatibility proofs passed.')


if __name__=='__main__':main()
