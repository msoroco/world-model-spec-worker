"""Stage first exact right-turn reference case without claiming delivery readiness."""
import hashlib,json
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=HERE/'draft-execution-manifest.json';draft=json.loads(source.read_text())
assert len(draft['cases'])==2
reference=deepcopy(next(e for e in draft['cases'] if e['case_id'].endswith('__reference')))
assert reference['kind']=='draft_not_selected' and len(reference['candidates'])==3
reference['kind']='delivery';reference['id']='primary';reference['preparation_status']='selected_reference_probe_cpu_proofs_pending'
probe={'format':'worker-execution-manifest','assignment_id':HERE.name,'runtime_manifest_sha256':draft['runtime_manifest_sha256'],'status':'partial_reference_probe','cases':[reference]}
out=HERE/'update016-selected-reference-probe-manifest.json';out.write_text(json.dumps(probe,indent=2)+'\n')
print(json.dumps({'case':reference['case_id'],'candidates':4,'probe_manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'canonical_selected':False}))
