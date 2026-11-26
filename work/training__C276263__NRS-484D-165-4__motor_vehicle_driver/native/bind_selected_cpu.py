"""Bind exact offline, public compatibility and saved-only diagnostic receipts."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AID=ROOT.name

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    path=ROOT/'selected-draft-execution-manifest.json'
    manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
        folder=ROOT/'selected-proofs'/suffix
        relative=f'selected-proofs/{suffix}/'
        proof=json.loads((folder/'compatibility.json').read_text())
        if proof['case_id']!=case or proof['construction_sha256']!=entry['construction_sha256']:
            raise ValueError('Stale selected compatibility proof')
        offline=folder/'offline.log';compat=folder/'compatibility.json'
        entry['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/selected-draft-execution-manifest.json --case {case} --output .runtime-work/c276263-selected-offline-{suffix}-v4 --python $PWD/.venv-cpu/bin/python',
                          'exit_code':0,'log':relative+'offline.log','log_sha256':sha(offline),
                          'construction_sha256':entry['construction_sha256']}
        entry['compatibility']={'receipt':relative+'compatibility.json','sha256':sha(compat),
                                'log':relative+'compatibility-analysis.log'}
        entry['negative']={'log':relative+'negative-analysis.log'}
        entry['saved_cpu_diagnostic']={'receipt':relative+'saved-processing.json',
                                       'sha256':sha(folder/'saved-processing.json'),
                                       'scope':'synthetic source-shaped recorded-only processing; no physical or legal acceptance'}
        runner='runner.py'
        entry['acquisition']={
            'kin.position':{'entrypoint':runner,'method':'ego.get_transform after each Native tick','evidence':'native-rows.jsonl original center, footprint and capture/evidence.jsonl'},
            'kin.velocity':{'entrypoint':runner,'method':'ego.get_velocity after each Native tick','evidence':'native-rows.jsonl speed and trace.jsonl velocity'},
            'sig.headlamp':{'entrypoint':runner,'method':'ego.get_light_state after each Native tick','evidence':'native-rows.jsonl original lamp bits plus source-hashed pixel review'},
            'drv.standing_or_parked':{'entrypoint':runner,'method':'handbrake control, original pose and separate activity review','evidence':'native-rows.jsonl and parking-activity-review.json'},
            'rel.occupies':{'entrypoint':runner,'method':'ego.bounding_box.get_world_vertices and parking waypoint','evidence':'native-rows.jsonl original footprint and curb lane'}}
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
