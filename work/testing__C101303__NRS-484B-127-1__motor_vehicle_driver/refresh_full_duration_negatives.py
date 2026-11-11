"""Recheck rejected audit branches against retained full-duration diagnostic sources."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
manifest_path=folder/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def reject(case,source,root,mode,log,expected):
    command=[str(repo/'.venv-cpu/bin/python'),str(folder/'delivery_fixture_proof.py'),
             '--case',case,'--output-root',str(root.relative_to(repo)),
             mode,'--negative-source-root',str(source.relative_to(repo))]
    with log.open('w') as out:
        result=subprocess.run(command,cwd=repo,stdout=out,stderr=subprocess.STDOUT)
    if result.returncode==0 or expected not in log.read_text():
        raise ValueError('Negative audit proof failed: '+str(log))
    return command,result.returncode


for entry in manifest['cases']:
    case=entry['case_id'];label=case.rsplit('source_verified_',1)[1]
    source=repo/'.runtime-work/c101303-full-duration'/(label+'-positive-v1')
    root=repo/'.runtime-work/c101303-full-duration'/(label+'-negative-v2')
    proof=entry['delivery_acceptance'];log=folder/proof['negative_log']
    command,code=reject(case,source,root,'--negative-missing-source',log,
                        proof['negative_expected_error'])
    proof['negative_command']=shlex.join(command)
    proof['negative_exit_code']=code
    proof['negative_log_sha256']=sha(log)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('full-duration missing-source rejection',label,flush=True)

base=manifest['cases'][0]['case_id']
source=repo/'.runtime-work/c101303-full-duration/base-positive-v1'
for label,mode,expected in [
    ('identity','--negative-review-identity','Pixel review actor identity differs from original source'),
    ('unsealed','--negative-unsealed-source','Capture seal omits required original source')]:
    root=repo/'.runtime-work/c101303-full-duration'/('base-negative-'+label+'-v2')
    log=folder/'delivery-proofs/base'/('negative-'+label+'.log')
    reject(base,source,root,mode,log,expected)
    print('full-duration '+label+' rejection',flush=True)
