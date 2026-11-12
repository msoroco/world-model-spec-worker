"""Correct unsupported traversal Core atom, retaining native intersection checks."""
import hashlib,json,sys
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'runtime/pipeline'),str(ROOT/'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.preparation import runtime_for
from scenario_pipeline.worker_exchange.atom_preflight import check_required_atoms
runtime=runtime_for(ROOT,json.loads((ROOT/'batch.json').read_text()))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
source=HERE/'execution-manifest.json'; probe=deepcopy(json.loads(source.read_text()))
rows=[]
for entry in probe['cases']:
 suffix=entry['case_id'].rsplit('__',1)[-1]
 if not suffix.startswith('traversal_'): continue
 for candidate in (entry,*entry['candidates']):
  old=json.loads((HERE/candidate['construction']).read_text()); clone=deepcopy(old)
  cfgfile=next(f for f in clone['files'] if f['path']=='config.json'); cfg=json.loads(cfgfile['content'])
  assert cfg['required_atoms'].count('drv.in_intersection')==1
  cfg['required_atoms'].remove('drv.in_intersection')
  assert 'drv.in_intersection' in cfg['mandatory_channels'] and 'st.intersection' in cfg['mandatory_channels']
  check_required_atoms(runtime,cfg['required_atoms'],cfg.get('source_packets',[]),cfg)
  cfgfile['content']=json.dumps(cfg,indent=2)+'\n'
  dest=HERE/'update039-traversal-core-candidates'/suffix/candidate['id']/'construction.json'
  dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(json.dumps(clone,indent=2)+'\n')
  candidate['construction']=str(dest.relative_to(HERE));candidate['construction_sha256']=sha(dest)
  candidate.pop('offline',None);candidate.pop('compatibility',None)
  rows.append({'case_id':entry['case_id'],'candidate_id':candidate['id'],'construction_sha256':candidate['construction_sha256']})
 for name in ('negative','post_capture','physical_preparation','delivery_acceptance'):entry.pop(name,None)
 entry['preparation_status']='traversal_core_bundle_proofs_pending';entry['acquisition']={}
assert len(rows)==8
out=HERE/'update039-traversal-core-probe-manifest.json';out.write_text(json.dumps(probe,indent=2)+'\n')
print(json.dumps({'candidates':8,'manifest_sha256':sha(out),'rows':rows}))
