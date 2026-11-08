"""Copy paragraph (a) signal-pair candidate requests and executable preflight."""
import hashlib
import json
from pathlib import Path
import shutil

BRANCH=Path(__file__).resolve().parent
NATIVE=BRANCH.parent
CASE=NATIVE.parent
ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
    entries=[]
    for witness in ('exception_1_1','exception_1_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=BRANCH/'drafts'/witness/candidate
            bundle=BRANCH/'offline/bundles'/witness/candidate
            files={'config.json':source/'config.json',
                'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                'case-plan.json':CASE/'case-plan.json',
                'one-way-pass.xodr':NATIVE/'one-way-pass.xodr',
                'measurement-contract.json':BRANCH/'measurement-contract.json',
                'check.py':BRANCH/'check.py',
                'capture.py':NATIVE/'capture.py'}
            for name,path in files.items():
                (bundle/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,bundle/name)
            entries.append({'case_id':CASE.name+'__'+witness,
                'candidate_id':candidate,
                'bundle':str(bundle.relative_to(BRANCH)),
                'sha256':{name:sha(bundle/name) for name in files},
                'status':'unselected_native_request'})
    receipt={'format':'c146314-paragraph-a-exact-offline-v1',
        'assignment_id':CASE.name,
        'construction_sha256':sha(BRANCH/'manifest.json'),
        'measurement_contract_sha256':sha(BRANCH/'measurement-contract.json'),
        'entries':entries,'original_native_observed':False,
        'delivery_ready':False}
    target=BRANCH/'offline/manifest.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
