"""Copy eight exact C146314 construction and synthetic saved CPU bundles."""
import hashlib
import json
from pathlib import Path
import shutil

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
NATIVE=CASE/'native'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    entries=[]
    for witness in ('witness_1','witness_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=NATIVE/'drafts'/witness/candidate
            saved=NATIVE/'saved-fixtures'/witness/candidate
            target=CASE/'offline'/'bundles'/witness/candidate
            target.mkdir(parents=True,exist_ok=True)
            files={'config.json':source/'config.json',
                'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                'one-way-pass.xodr':NATIVE/'one-way-pass.xodr',
                'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                'case-plan.json':CASE/'case-plan.json',
                'measurement-contract.json':NATIVE/'measurement-contract.json',
                'check.py':NATIVE/'check.py',
                'measure_saved.py':NATIVE/'measure_saved.py',
                'route_fallbacks.py':NATIVE/'route_fallbacks.py'}
            for name in ('native-observed.jsonl','camera-frames.jsonl','readback.json'):
                files['saved/'+name]=saved/name
            for name,path in files.items():
                (target/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,target/name)
            entries.append({'case_id':CASE.name+'__'+witness,
                'candidate_id':candidate,
                'bundle':str(target.relative_to(CASE)),
                'sha256':{name:sha(target/name) for name in files},
                'status':'unselected_native_request'})
    manifest={'format':'c146314-exact-offline-diagnostic-v1',
        'assignment_id':CASE.name,
        'construction_sha256':sha(NATIVE/'manifest.json'),
        'measurement_contract_sha256':sha(NATIVE/'measurement-contract.json'),
        'entries':entries,'original_native_observed':False,
        'delivery_ready':False}
    target=CASE/'offline'/'manifest.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
