"""Stage both exact right-turn cases as a noncanonical selected CPU probe."""
import hashlib,json
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent;draft=json.loads((HERE/'draft-execution-manifest.json').read_text())
assert len(draft['cases'])==2
probe=deepcopy(draft);probe['status']='partial_selected_pair_probe'
for entry in probe['cases']:
 assert entry['kind']=='draft_not_selected' and len(entry['candidates'])==3
 entry['kind']='delivery';entry['id']='primary';entry['preparation_status']='selected_pair_cpu_proofs_pending'
out=HERE/'update017-selected-pair-probe-manifest.json';out.write_text(json.dumps(probe,indent=2)+'\n')
print(json.dumps({'cases':2,'candidates':8,'manifest_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'canonical_selected':False}))
