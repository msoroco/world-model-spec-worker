"""Independently bind eight source-shaped right-turn candidate CPU receipts."""
import copy,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MANIFEST=HERE/'update017-selected-pair-probe-manifest.json';INDEX=HERE/'update017-selected-pair-probe-index.json'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(c,m):
 if not c:raise ValueError(m)
def audit(index):
 m=read(MANIFEST);require(index['manifest_sha256']==sha(MANIFEST) and index['candidates']==len(index['results'])==8,'Probe matrix incomplete')
 rows={(r['case_id'],r['candidate_id']):r for r in index['results']};require(len(rows)==8,'Duplicate candidate')
 outcomes={}
 for e in m['cases']:
  suffix=e['case_id'].rsplit('__',1)[-1];require(suffix in ('reference','contrast'),'Unexpected case')
  for c in (e,*e['candidates']):
   ident=c['id'];r=rows[(e['case_id'],ident)];proof_path=HERE/r['proof'];proof=read(proof_path)
   require(sha(proof_path)==r['sha256'] and proof['manifest_sha256']==sha(MANIFEST) and proof['construction_sha256']==c['construction_sha256']==sha(HERE/c['construction']),'Exact proof binding changed')
   source=ROOT/'.runtime-work/c110919-update017-selected-pair-probe'/suffix/ident/'compatibility';saved=ROOT/'.runtime-work/c110919-update017-selected-pair-probe'/suffix/ident/'saved/v0001/processing.json';compat=read(source/'compatibility.json');processing=read(saved)
   require(sha(source/'compatibility.json')==proof['compatibility_receipt_sha256'] and sha(saved)==proof['saved_receipt_sha256'] and compat['negative_log_sha256']==sha(source/'negative-analysis.log') and compat['negative_removed']=='road_geometry.json' and compat['passed'] is True,'Positive or negative compatibility changed')
   require(processing['passed'] is True and processing['originals_preserved'] is True and processing['original_source_hashes']['native_samples.jsonl']==sha(source/'native_samples.jsonl') and processing['original_source_hashes']['road_geometry.json']==sha(source/'road_geometry.json'),'Saved original source binding changed')
   measurement=compat['measurement_examples']['right_turn_stop']['value'];require(measurement['stationary_pre_crossing_frames']==(30 if suffix=='reference' else 0) and measurement['halt_before_nearest_boundary'] is (suffix=='reference'),'Stopped-before-boundary contrast changed')
   require(processing['physical_acceptance_claimed'] is False and processing['legal_acceptance_claimed'] is False,'Synthetic receipt promoted')
   outcomes[(suffix,ident)]=measurement
 require(len(outcomes)==8,'Missing outcome')
 return {'format':'c110919-selected-pair-independent-cpu-audit-v1','manifest_sha256':sha(MANIFEST),'candidates_checked':8,'reference_stopped_frames':30,'contrast_stopped_frames':0,'original_native_accepted':False}
index=read(INDEX);result=audit(index)
for damage in ('missing','wrong_sha'):
 changed=copy.deepcopy(index)
 if damage=='missing':changed['results'].pop()
 else:changed['results'][0]['sha256']='0'*64
 try:audit(changed)
 except ValueError:pass
 else:raise AssertionError('Damaged probe accepted: '+damage)
result['damaged_receipts_rejected']=2
out=HERE/'update017-selected-pair-probe-audit.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'candidates_checked':8,'damaged_receipts_rejected':2,'audit_sha256':sha(out)}))
