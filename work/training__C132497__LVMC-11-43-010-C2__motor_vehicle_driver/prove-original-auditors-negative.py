"""Prove production auditors refuse synthetic or reused original sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=REPO/'.runtime-work/c132497-current-all-proof/reference/primary/compatibility'
PYTHON=REPO/'.venv-cpu/bin/python'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reject(name,script,args,needle):
    command=[str(PYTHON),str(ROOT/'native'/script),*map(str,args)]
    result=subprocess.run(command,cwd=REPO,capture_output=True,text=True)
    log=ROOT/('update015-original-auditors-'+name+'.log')
    log.write_text(result.stdout+result.stderr)
    if result.returncode==0 or needle not in log.read_text():
        raise ValueError('Original auditor negative did not reject '+name)
    return {'name':name,'exit_code':result.returncode,'log':log.name,
            'log_sha256':sha(log),'expected_error':needle}


def main():
    if not (BASE/'result.json').is_file():
        raise ValueError('Run prove-current-all.py before original rejection proof')
    case=ROOT.name+'__reference'
    results=[]
    results.append(reject('synthetic-delivery','delivery_audit.py',
        ['--case',case,'--job-id',1,'--attempt-number',1,
         '--recording-id',BASE.parent.name,'--attempt',BASE,
         '--review',BASE/'missing-original-review.json',
         '--primary',BASE/'raw.mkv',
         '--decode-receipt',BASE.parent/'negative-decode.json',
         '--output',BASE/'negative-delivery-audit.json'],
        'Missing delivery source: '+str(BASE/'native-map-readback.json')))
    results.append(reject('reused-pair','audit_original_pair.py',
        ['--reference',BASE,'--contrast',BASE,
         '--reference-receipt',BASE/'missing-reference-audit.json',
         '--contrast-receipt',BASE/'missing-contrast-audit.json',
         '--output',BASE.parent/'negative-pair.json'],
        'Comparison reuses one attempt for both cases'))
    proof={'format':'c132497-original-auditor-negative-proof-v1',
        'source_result_sha256':sha(BASE/'result.json'),'rejections':results,
        'original_native_observed':False,'delivery_ready':False}
    target=ROOT/'update015-original-auditors-negative-proof.json'
    target.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'rejections':len(results),'proof_sha256':sha(target)}))


if __name__=='__main__':main()
