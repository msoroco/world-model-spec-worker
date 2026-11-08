"""Copy eight exact LVMC roundabout requests and CPU checker."""
import hashlib
import json
from pathlib import Path
import shutil

CASE=Path(__file__).resolve().parent
ROOT=CASE.parents[1]
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries=[]
    for witness in ('witness_1','witness_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=NATIVE/'drafts'/witness/candidate
            target=CASE/'offline'/'bundles'/witness/candidate
            target.mkdir(parents=True,exist_ok=True)
            mapping={'config.json':source/'config.json',
                'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                'road.xodr':NATIVE/'road.xodr',
                'island-geometry.json':NATIVE/'island-geometry.json',
                'measurement-contract.json':NATIVE/'measurement-contract.json',
                'runner.py':NATIVE/'runner.py',
                'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                'case-plan.json':CASE/'case-plan.json'}
            for name,path in mapping.items():shutil.copy2(path,target/name)
            entries.append({'case_id':CASE.name+'__'+witness,
                'candidate_id':candidate,'bundle':str(target.relative_to(CASE)),
                'sha256':{name:sha(target/name) for name in mapping},
                'status':'unselected_native_request'})
    result={'format':'c234827-lvmc-exact-offline-v1',
        'assignment_id':CASE.name,
        'construction_manifest_sha256':sha(NATIVE/'drafts'/'manifest.json'),
        'entries':entries,'accepted_originals_replayed':0,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
