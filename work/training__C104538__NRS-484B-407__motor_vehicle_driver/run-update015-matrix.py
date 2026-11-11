"""Run and retain current exact unselected CPU proofs for all C104538 candidates."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
RUNTIME=REPO/'runtime.py'
LIBRARY=REPO/'runtime/pipeline/library'
VALIDATOR=REPO/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'
OUTPUT=REPO/'.runtime-work/c104538-update015-matrix-v2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run_command(args,log):
    process=subprocess.run([sys.executable,str(RUNTIME),*args],
                           text=True,capture_output=True,cwd=REPO)
    log.write_text(process.stdout+process.stderr)
    if process.returncode:
        raise ValueError(f'CPU proof failed: {log} (exit {process.returncode})')
    return json.loads(process.stdout)


def run():
    cases=[]
    for suffix in ('below_500_ft','at_500_ft','above_500_ft'):
        case_id=HERE.name+'__'+suffix
        candidates=[]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            manifest=HERE/f'update015-manifest-{candidate}.json'
            recipe=HERE/f'update015-{suffix}-{candidate}-recipe.json'
            folder=HERE/'update015-proofs-v2'/suffix/candidate
            folder.mkdir(parents=True,exist_ok=True)
            proof_path=folder/'proof.json'
            if proof_path.exists():
                proof=json.loads(proof_path.read_text())
                if proof['manifest_sha256']!=sha(manifest) or proof['recipe_sha256']!=sha(recipe):
                    raise ValueError('Retained proof source changed: '+str(proof_path))
                candidates.append(proof)
                print(json.dumps({'case':suffix,'candidate':candidate,'retained':True}),flush=True)
                continue
            attempt=OUTPUT/suffix/candidate/'compatibility'
            saved=OUTPUT/suffix/candidate/'saved'
            common=['--manifest',str(manifest),'--case',case_id,
                    '--library',str(LIBRARY),'--validator',str(VALIDATOR)]
            compatibility=run_command(['compatibility',*common,'--candidate',candidate,
                                       '--output',str(attempt)],folder/'compatibility.log')
            if (compatibility.get('passed') is not True or
                compatibility.get('case_id')!=case_id or
                compatibility.get('candidate_id')!=candidate or
                compatibility.get('negative_removed')!='native_body_history.jsonl' or
                'four_camera_sources' not in compatibility.get('checks',[])):
                raise ValueError('Incomplete current compatibility proof')
            processing=run_command(['process-saved',*common,'--attempt',str(attempt),
                                    '--output',str(saved)],folder/'process-saved.log')
            if (processing.get('passed') is not True or
                processing.get('case_id')!=case_id or
                processing.get('candidate_id')!=candidate or
                processing.get('originals_preserved') is not True or
                processing.get('missing_evidence') is not False or
                processing.get('physical_acceptance_claimed') is not False or
                processing.get('legal_acceptance_claimed') is not False):
                raise ValueError('Incomplete current saved-processing proof')
            write(folder/'compatibility.json',compatibility)
            write(folder/'process-saved.json',processing)
            proof={'case_id':case_id,'candidate_id':candidate,
                   'manifest_sha256':sha(manifest),'recipe_sha256':sha(recipe),
                   'construction_sha256':compatibility['construction_sha256'],
                   'compatibility_sha256':sha(folder/'compatibility.json'),
                   'compatibility_log_sha256':sha(folder/'compatibility.log'),
                   'process_saved_sha256':sha(folder/'process-saved.json'),
                   'process_saved_log_sha256':sha(folder/'process-saved.log'),
                   'synthetic_diagnostic':True,'selected':False,'accepted':False}
            write(proof_path,proof)
            candidates.append(proof)
            print(json.dumps({'case':suffix,'candidate':candidate,'passed':True}),flush=True)
        cases.append({'case_id':case_id,'candidates':candidates})
    summary={'format':'c104538-update015-exact-unselected-matrix',
             'cases':cases,'compatibility_passed':12,'process_saved_passed':12,
             'selected':False,'physical_acceptance_claimed':False}
    write(HERE/'update015-proof-index-v2.json',summary)
    print(json.dumps({'proof_index_sha256':sha(HERE/'update015-proof-index-v2.json'),
                      'compatibility_passed':12,'process_saved_passed':12}))


if __name__=='__main__':
    run()
