"""Materialize a canonical root example from the selected full-stop construction."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SEED=ROOT/'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver/selected-line_stop-primary-construction.json'
selected=json.loads((HERE/'selected-condition-a-primary-construction.json').read_text())
seed=json.loads(SEED.read_text())
for key in ('law_id','measurement_plan','static_checks','termination_rules','mechanisms'):
    if key=='law_id':
        selected[key]='NRS-484A-450-2'
    else:
        value=json.dumps(seed[key]).replace('C111325','C295180').replace('training__C111325__NRS-484A-450-2__motor_vehicle_driver__line_stop',HERE.name+'__selected_ef239a06__condition_a')
        selected[key]=json.loads(value)
(HERE/'construction.json').write_text(json.dumps(selected,indent=2,ensure_ascii=False)+'\n')
for file in selected['files']:
    path=HERE/file['path']
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(file['content'])
print('PASS',len(selected['files']))
