"""Copy eight exact C132497 CPU request bundles."""
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
    for witness in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=NATIVE/'drafts'/witness/candidate
            target=CASE/'offline'/'bundles'/witness/candidate
            target.mkdir(parents=True,exist_ok=True)
            mapping={'config.json':source/'config.json',
                'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                'controller-intention.json':source/'controller-intention.json',
                'right-exit-road.xodr':NATIVE/'right-exit-road.xodr',
                'measurement-contract.json':NATIVE/'measurement-contract.json',
                'check.py':NATIVE/'check.py',
                'measure_saved.py':NATIVE/'measure_saved.py',
                'prepare_raw.py':NATIVE/'prepare_raw.py',
                'fixture_raw.py':NATIVE/'fixture_raw.py',
                'measure_prepared.py':NATIVE/'measure_prepared.py',
                'triggers.py':NATIVE/'triggers.py',
                'capture.py':NATIVE/'capture.py',
                'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                'case-plan.json':CASE/'case-plan.json'}
            for name in ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json'):
                mapping['saved/'+name]=NATIVE/'saved-fixtures'/witness/candidate/name
            for name,path in mapping.items():
                (target/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,target/name)
            entries.append({'case_id':CASE.name+'__'+witness,
                'candidate_id':candidate,'bundle':str(target.relative_to(CASE)),
                'sha256':{name:sha(target/name) for name in mapping},
                'status':'unselected_native_request'})
    manifest={'format':'c132497-exact-offline-v1','assignment_id':CASE.name,
        'construction_sha256':sha(NATIVE/'manifest.json'),'entries':entries,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
