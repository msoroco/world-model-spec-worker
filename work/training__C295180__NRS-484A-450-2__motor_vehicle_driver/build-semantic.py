"""Build draft canonical stage proposals for the two exact stop-line cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = ROOT / 'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver'
OLD = SEED.name
NEW = HERE.name

def write(name, data):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def adapt(obj):
    value = json.dumps(obj, ensure_ascii=False)
    value = value.replace(OLD + '__line_stop', NEW + '__selected_ef239a06__condition_a')
    value = value.replace(OLD + '__line_pass', NEW + '__selected_ef239a06__condition_b')
    value = value.replace(OLD + '__marked_line_comparison', NEW + '__selected_ef239a06__comparison')
    value = value.replace('C111325', 'C295180')
    return json.loads(value)

refs = {}
for stage in ('relevance_batch','relevance','template','bindings'):
    body = adapt(json.loads((SEED / 'proposals' / (stage + '.json')).read_text()))
    if stage == 'bindings':
        body['established_contexts'] = [{'name':'C295180 signed T-intersection marked-line approach', 'source':'Frozen C295180 catalog cell; original sign and line require Native review'}]
    refs[stage] = write(stage + '.json', body)
refs['judgment_observables'] = []
cases = json.loads((HERE / 'proposals/cases.json').read_text())
baseline = adapt(json.loads((SEED / 'proposals/cases.json').read_text())['cases'][0])
baseline['case_id'] = NEW + '__baseline_reference'
baseline['reuse_case_id'] = NEW + '__selected_ef239a06__condition_b'
baseline['variable_assignments']['near_side_crosswalk_present']['value'] = False
baseline['variable_assignments']['requested_pre_crosswalk_stop']['value'] = None
baseline['variable_assignments']['requested_pre_line_stop']['value'] = False
baseline['recording_description'] = json.loads((HERE / 'selected-condition-b-primary-construction.json').read_text())['recording_description']
cases['cases'].insert(0, baseline)
for case in cases['cases']:
    case['recording_description'] = json.loads((HERE / ('selected-condition-a-primary-construction.json' if case['case_id'].endswith('_a') else 'selected-condition-b-primary-construction.json')).read_text())['recording_description']
refs['cases'] = write('cases.json', cases)
write('semantic-index.json', {'format':'worker-semantic-delivery','assignment_id':NEW,'status':'draft','stages':refs})
print('PASS', NEW, len(cases['cases']))
