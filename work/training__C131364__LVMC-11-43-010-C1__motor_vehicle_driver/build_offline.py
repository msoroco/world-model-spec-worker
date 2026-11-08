"""Copy all exact C131364 source-bound CPU request bundles."""
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
                     'connected-config.json':NATIVE/'exit-network-drafts'/witness/candidate/'config.json',
                     'connected-requested-tracks.jsonl':NATIVE/'exit-network-drafts'/witness/candidate/'requested-tracks.jsonl',
                     'connected-road.xodr':NATIVE/'left-exit-road.xodr',
                     'measurement-contract.json':NATIVE/'measurement-contract.json',
                     'runner.py':NATIVE/'runner.py',
                     'measure_saved.py':NATIVE/'measure_saved.py',
                     'measure_exit_saved.py':NATIVE/'measure_exit_saved.py',
                     'prepare_connected_raw.py':NATIVE/'prepare_connected_raw.py',
                     'fixture_connected_raw.py':NATIVE/'fixture_connected_raw.py',
                     'triggers.py':NATIVE/'triggers.py',
                     'compare_saved.py':NATIVE/'compare_saved.py',
                     'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                     'case-plan.json':CASE/'case-plan.json'}
            for name in ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json'):
                mapping[f'connected-saved/{name}']=NATIVE/'exit-saved-fixtures'/witness/candidate/name
            for saved_witness in ('witness_1','witness_2'):
                for name in ('native-observed.jsonl','lane-readback.json','camera-frames.jsonl'):
                    relative=f'saved-fixtures/{saved_witness}/{name}'
                    mapping[relative]=NATIVE/relative
            for name,path in mapping.items():
                (target/name).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,target/name)
            entries.append({'case_id':CASE.name+'__'+witness,'candidate_id':candidate,
                            'bundle':str(target.relative_to(CASE)),
                            'sha256':{name:sha(target/name) for name in mapping},
                            'status':'unselected_native_request'})
    result={'format':'c131364-exact-offline-v1','assignment_id':CASE.name,
            'construction_manifest_sha256':sha(NATIVE/'drafts'/'manifest.json'),
            'connected_manifest_sha256':sha(NATIVE/'exit-network-drafts'/'manifest.json'),
            'entries':entries,'original_native_observed':False,
            'actual_left_exit_observed':False,'delivery_ready':False}
    (CASE/'offline'/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
