"""Bind two independently drafted intersection cases into a nine-case CPU probe."""
import hashlib,json,runpy
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=read(HERE/'execution-manifest.json'); draft=read(HERE/'draft-execution-manifest.json')
retained=read(HERE/'update040-intersection-draft-retained-index.json')
assert len(base['cases'])==7 and len(draft['cases'])==2 and retained['candidate_count']==8
assert retained['manifest_sha256']==sha(HERE/'draft-execution-manifest.json')
rows={(r['case_id'],r['candidate_id']):r for r in retained['candidates']}
acquisition=runpy.run_path(str(HERE/'bind-selected-package-receipts.py'))['acquisition']
template=next(e for e in base['cases'] if e['case_id'].endswith('__traversal_reference'))
for prior in draft['cases']:
 e=deepcopy(prior);suffix=e['case_id'].rsplit('__',1)[-1];e['kind']='delivery'
 for c in (e,*e['candidates']):
  ident=c['id'];r=rows[(e['case_id'],ident)];assert r['construction_sha256']==c['construction_sha256']
  proof=HERE/'update040-intersection-draft-proofs'/suffix/ident
  c['offline']={'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {e["case_id"]} --candidate {ident} --output ${{OFFLINE_DIR}} --python .venv-cpu/bin/python','exit_code':0,'construction_sha256':c['construction_sha256'],'log':str((proof/'offline.log').relative_to(HERE)),'log_sha256':sha(proof/'offline.log')}
  files=r['files'];c['compatibility']={'receipt':files['compatibility.json']['path'],'sha256':files['compatibility.json']['sha256'],'log':files['compatibility-analysis.log']['path'],'negative_log':files['negative-analysis.log']['path']}
 neg=rows[(e['case_id'],'primary')]['files']['negative-analysis.log'];e['negative']={'log':neg['path'],'log_sha256':neg['sha256']}
 saved=HERE/'update040-intersection-draft-proofs'/suffix/'primary/process-saved.log'
 e['post_capture']=deepcopy(template['post_capture']);e['post_capture']['command']=e['post_capture']['command'].replace(template['case_id'],e['case_id']);e['post_capture']['test_log']=str(saved.relative_to(HERE));e['post_capture']['test_log_sha256']=sha(saved)
 e['native_handoff']=deepcopy(template['native_handoff']);e['acquisition']=acquisition(read(HERE/e['construction']))
 physical=HERE/'update040-intersection-physical-preparation'/suffix/'proof.json';e['physical_preparation']={'receipt':str(physical.relative_to(HERE)),'sha256':sha(physical)}
 e['preparation_status']='nine_case_probe_final_hash_proofs_pending'
 base['cases'].append(e)
assert len(base['cases'])==9
base['status']='partial_nine_case_probe'
out=HERE/'update040-nine-case-bound-probe-manifest.json';out.write_text(json.dumps(base,indent=2)+'\n')
print(json.dumps({'cases':9,'candidates':36,'manifest_sha256':sha(out),'delivery_audit_binding_pending':True}))
