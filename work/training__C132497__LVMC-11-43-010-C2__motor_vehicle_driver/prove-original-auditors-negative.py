"""Prove production auditors refuse synthetic or reused original sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=REPO/'.runtime-work/c132497-current-all-proof/reference/primary/compatibility'
MOCK=REPO/'.runtime-work/c132497-original-auditor-negative/mock-recording/attempt-1'
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
    MOCK.mkdir(parents=True,exist_ok=True)
    for name in ('config.json','result.json','controller-intention.json'):
        shutil.copyfile(BASE/name,MOCK/name)
    cfg=json.loads((MOCK/'config.json').read_text())
    (MOCK/'native-map-readback.json').write_text(json.dumps({
        'road_sha256':cfg['road_sha256']}))
    (MOCK/'native-capture-report.json').write_text(json.dumps({
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'observed_frames':240,'error':None}))
    (MOCK/'raw.mkv').write_text('CPU negative marker; not original media')
    (MOCK/'review.json').write_text('{}\n')
    case=ROOT.name+'__reference'
    results=[]
    results.append(reject('synthetic-delivery','delivery_audit.py',
        ['--case',case,'--job-id',1,'--attempt-number',1,
         '--recording-id',MOCK.parent.name,'--attempt',MOCK,
         '--review',MOCK/'review.json',
         '--primary',MOCK/'raw.mkv',
         '--decode-receipt',MOCK.parent/'negative-decode.json',
         '--output',MOCK/'negative-delivery-audit.json'],
        'Synthetic or unreviewed result cannot establish original Native delivery'))
    results.append(reject('reused-pair','audit_original_pair.py',
        ['--reference',MOCK,'--contrast',MOCK,
         '--reference-receipt',MOCK/'missing-reference-audit.json',
         '--contrast-receipt',MOCK/'missing-contrast-audit.json',
         '--output',MOCK.parent/'negative-pair.json'],
        'Comparison reuses one attempt for both cases'))
    proof={'format':'c132497-original-auditor-negative-proof-v1',
        'source_result_sha256':sha(BASE/'result.json'),'rejections':results,
        'original_native_observed':False,'delivery_ready':False}
    target=ROOT/'update015-original-auditors-negative-proof.json'
    target.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'rejections':len(results),'proof_sha256':sha(target)}))


if __name__=='__main__':main()
