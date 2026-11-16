"""Bind the exact pair to a portable assignment-level CPU entrypoint."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
source=json.loads((ROOT/'selected-primary/reference/construction.json').read_text())
config=json.loads(next(f['content'] for f in source['files'] if f['path']=='config.json'))
config['supported_case_ids']=[ROOT.name+'__reference',ROOT.name+'__contrast']
config['dispatch_case_ids']=config['supported_case_ids']
(ROOT/'config.json').write_text(json.dumps(config,indent=2,allow_nan=False)+'\n')
construction={key:source[key] for key in ('case_id','cell_id','law_id','actor','entrypoint',
    'recording_description','measurement_plan','static_checks','termination_rules','mechanisms')}
construction['status']='draft_assignment_dispatch_cpu'
construction['original_native_observed']=False
construction['delivery_ready']=False
construction['mechanisms']['dispatch']='runner.py selects exact manifest case/candidate, materializes fresh bundle, then invokes its Native runner'
construction['files']=[{'path':name,'content':(ROOT/name).read_text()} for name in ('runner.py','config.json')]
(ROOT/'construction.json').write_text(json.dumps(construction,indent=2,allow_nan=False)+'\n')
print(ROOT/'construction.json',len(construction['files']))
