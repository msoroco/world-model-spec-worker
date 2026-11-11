"""Retain current exact synthetic compatibility and saved proofs for intersection pair."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
MANIFEST=HERE/'draft-execution-manifest.json'
LIBRARY=REPO/'runtime/pipeline/library'
VALIDATOR=REPO/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
OUTPUT=REPO/'.runtime-work/c110454-update015-intersection-matrix-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def command(arguments,log):
    result=subprocess.run([sys.executable,str(REPO/'runtime.py'),*arguments],
                          cwd=REPO,capture_output=True,text=True)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Current exact proof failed: '+str(log))
    return json.loads(result.stdout)


def run():
    cases=[]
    for suffix in ('reference','contrast'):
        case_id=HERE.name+'__'+suffix
        candidates=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            folder=HERE/'update015-intersection-proofs'/suffix/candidate
            folder.mkdir(parents=True,exist_ok=True)
            proof_path=folder/'proof.json'
            if proof_path.exists():
                proof=json.loads(proof_path.read_text())
                if proof['manifest_sha256']!=sha(MANIFEST):
                    raise ValueError('Retained construction changed: '+str(proof_path))
                candidates.append(proof)
                print(json.dumps({'case':suffix,'candidate':candidate,'retained':True}),flush=True)
                continue
            attempt=OUTPUT/suffix/candidate/'compatibility'
            saved=OUTPUT/suffix/candidate/'saved'
            common=['--manifest',str(MANIFEST),'--case',case_id,
                    '--library',str(LIBRARY),'--validator',str(VALIDATOR)]
            compatibility=command(['compatibility',*common,'--candidate',candidate,
                                   '--output',str(attempt)],folder/'compatibility.log')
            if (compatibility.get('passed') is not True or
                compatibility.get('case_id')!=case_id or
                compatibility.get('candidate_id')!=candidate or
                compatibility.get('negative_removed')!='native_samples.jsonl'):
                raise ValueError('Current compatibility receipt incomplete')
            processing=command(['process-saved',*common,'--attempt',str(attempt),
                                '--output',str(saved)],folder/'process-saved.log')
            if (processing.get('passed') is not True or
                processing.get('case_id')!=case_id or
                processing.get('candidate_id')!=candidate or
                processing.get('originals_preserved') is not True or
                processing.get('missing_evidence') is not False or
                processing.get('physical_acceptance_claimed') is not False or
                processing.get('legal_acceptance_claimed') is not False):
                raise ValueError('Current saved-processing receipt incomplete')
            write(folder/'compatibility.json',compatibility)
            write(folder/'process-saved.json',processing)
            proof={'case_id':case_id,'candidate_id':candidate,
                   'manifest_sha256':sha(MANIFEST),
                   'recipe_sha256':sha(HERE/f'update015-{suffix}-recipe.json'),
                   'construction_sha256':compatibility['construction_sha256'],
                   'compatibility_sha256':sha(folder/'compatibility.json'),
                   'compatibility_log_sha256':sha(folder/'compatibility.log'),
                   'process_saved_sha256':sha(folder/'process-saved.json'),
                   'process_saved_log_sha256':sha(folder/'process-saved.log'),
                   'selected':False,'synthetic_diagnostic':True}
            write(proof_path,proof)
            candidates.append(proof)
            print(json.dumps({'case':suffix,'candidate':candidate,'passed':True}),flush=True)
        cases.append({'case_id':case_id,'candidates':candidates})
    index={'format':'c110454-update015-intersection-exact-matrix',
           'cases':cases,'compatibility_passed':8,'process_saved_passed':8,
           'selected':False,'physical_acceptance_claimed':False}
    write(HERE/'update015-intersection-proof-index.json',index)
    print(json.dumps({'index_sha256':sha(HERE/'update015-intersection-proof-index.json'),
                      'compatibility_passed':8,'process_saved_passed':8}))


if __name__=='__main__':run()
