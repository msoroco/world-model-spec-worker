import json,hashlib
from pathlib import Path
p=Path('work/heldout__C382420__LVMC-11-20-070__motor_vehicle_driver');s=Path('.runtime-work/c382420-stage');specs=[json.loads((p/('diagnostic-'+arm+'_downstream.json')).read_text()) for arm in ('intersection_clear','intersection_blocked')]
scene=[json.loads(x['files']['space_scene.json']) for x in specs];rows=[[json.loads(line) for line in x['files']['space_frames.jsonl'].splitlines()] for x in specs]
assert scene[0]=={**scene[1],'case_id':scene[0]['case_id']}
assert len(rows[0])==len(rows[1])==9
for clear,blocked in zip(*rows):
 assert clear['downstream_occupants']==[] and len(blocked['downstream_occupants'])==1
 assert {k:v for k,v in clear.items() if k!='downstream_occupants'}=={k:v for k,v in blocked.items() if k!='downstream_occupants'}
 assert blocked['downstream_occupants'][0]['speed_mps']==0
receipts=[json.loads((s/name/'compatibility.json').read_text()) for name in ('intersection_clear_downstream-compat-v1','intersection_blocked_downstream-compat-v1')]
assert all(x['passed'] and 'negative_case_source' in x['checks'] for x in receipts)
measurement=[x['measurement_examples']['space_at_entry']['value']['entry'] for x in receipts]
assert [x['downstream_available_length_m'] for x in measurement]==[14.0,3.0]
assert [x['first_downstream_occupant'] for x in measurement]==[None,'intersection-blocker-1']
assert all(x['frame']==2 and x['signal_state']=='proceed' and x['region_kind']=='intersection' for x in measurement)
result={'kind':'source-bound-intersection-comparison','passed':True,'fixed':['ego original footprints and time','entry region and receiving geometry','participant passage and signal readback','four original cameras'],'changed':['standing downstream occupant footprint'],'source_spec_sha256':[hashlib.sha256((p/('diagnostic-'+arm+'_downstream.json')).read_bytes()).hexdigest() for arm in ('intersection_clear','intersection_blocked')],'measured_available_length_m':[14.0,3.0],'legal_acceptance_claimed':False,'physical_acceptance_claimed':False};(s/'intersection-pair-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
