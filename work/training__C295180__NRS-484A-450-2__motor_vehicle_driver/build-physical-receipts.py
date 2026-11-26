"""Bind exact synthetic motion and Native closure proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for condition in ('a', 'b'):
    folder = HERE / 'physical-preparation' / condition
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = folder / f'{kind}-result.json'
        log = HERE / f'physical-{condition}-{kind}.log'
        fixtures.append({'kind':kind,'command':f'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c295180-physical-output PYTHONPATH=$PWD/runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/prove-selected-physical.py --condition {condition} --kind {kind}', 'exit_code':0,'log':log.relative_to(HERE).as_posix(),'log_sha256':sha(log),'result':result.relative_to(HERE).as_posix(),'result_sha256':sha(result)})
    life=HERE/f'physical-{condition}-lifecycle.log'
    receipt={'format':'c295180-physical-preparation-v1','case_id':HERE.name+f'__selected_ef239a06__condition_{condition}','construction_sha256':sha(HERE/f'selected-condition-{condition}-primary-construction.json'),'fixtures':fixtures,'lifecycle':{'events':['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started'],'exit_code':0,'command':f'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c295180-physical-output PYTHONPATH=$PWD/runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{HERE.name}/prove-selected-physical.py --condition {condition} --kind lifecycle','log':life.relative_to(HERE).as_posix(),'log_sha256':sha(life)},'physical_acceptance_claimed':False}
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(condition,sha(folder/'receipt.json'))
