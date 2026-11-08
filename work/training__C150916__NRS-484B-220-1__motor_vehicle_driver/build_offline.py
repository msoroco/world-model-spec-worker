"""Copy exact C150916 request bytes, source and CPU checker into eight bundles."""
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
    for case in ('designated','opposite'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=NATIVE/'drafts'/case/candidate
            target=CASE/'offline'/'bundles'/case/candidate
            target.mkdir(parents=True,exist_ok=True)
            inputs={'config.json':source/'config.json',
                    'requested-tracks.jsonl':source/'requested-tracks.jsonl',
                    'road.xodr':NATIVE/'road.xodr',
                    'measurement-contract.json':NATIVE/'measurement-contract.json',
                    'runner.py':NATIVE/'runner.py',
                    'measure_saved.py':NATIVE/'measure_saved.py',
                    'compare_saved.py':NATIVE/'compare_saved.py',
                    'triggers.py':NATIVE/'triggers.py',
                    'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
                    'case-plan.json':CASE/'case-plan.json'}
            for name,path in inputs.items():shutil.copy2(path,target/name)
            entries.append({'case_id':CASE.name+'__'+case,'candidate_id':candidate,
                            'bundle':str(target.relative_to(CASE)),
                            'sha256':{name:sha(target/name) for name in inputs},
                            'status':'unselected_native_request'})
    manifest={'format':'c150916-exact-offline-bundles-v1',
              'assignment_id':CASE.name,
              'construction_manifest_sha256':sha(NATIVE/'drafts'/'manifest.json'),
              'entries':entries,'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':print(json.dumps({'bundles':len(build()['entries'])}))
