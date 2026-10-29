"""Verify current partition-two exact receipt and source bindings; no Native execution."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];root=ROOT/'work';orig=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids'];bindings=json.loads((root/orig[0]/'additional-bindings.json').read_text());ids=orig+[r['assignment_id'] for r in bindings];sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();laws={};cases=set();comparisons=[];fail=[]
for aid in ids:
 f=root/aid;manifest=json.loads((f/'execution-manifest.json').read_text());ap=ROOT/'inputs'/aid/'assignment.json'
 if not ap.exists():ap=f/'assignment.json'
 a=json.loads(ap.read_text());contrib=json.loads((f/'branch-contribution.json').read_text());laws.setdefault(a['law_id'],{'branches':[]})['branches']+=contrib['branches'];comparisons+=json.loads((f/'case-plan.json').read_text())['comparisons']
 for e in manifest['cases']:
  cid=e['case_id'];cases.add(cid)
  if sha(f/e['construction'])!=e['construction_sha256']:fail.append([cid,'construction'])
  for key in ['offline','post_capture']:
   r=e.get(key,{})
   if not r:fail.append([cid,key]);continue
   log=r.get('log',r.get('test_log'));expected=r.get('log_sha256',r.get('test_log_sha256'))
   if not log or sha(f/log)!=expected:fail.append([cid,key+' log hash'])
  comp=e.get('compatibility',{})
  if not comp:fail.append([cid,'compatibility']);continue
  receipt=json.loads((f/comp['receipt']).read_text())
  if sha(f/comp['receipt'])!=comp['sha256']:fail.append([cid,'receipt hash'])
  if receipt['construction_sha256']!=e['construction_sha256']:fail.append([cid,'receipt construction'])
  if receipt['measurement_contract_sha256']!=sha(f/e['measurement_contract']):fail.append([cid,'contract hash'])
  if receipt['fixture_recipe_sha256']!=sha(ROOT/e['fixture_recipe']):fail.append([cid,'recipe hash'])
  bundle=json.loads((f/e['construction']).read_text());cfg=json.loads(next(x['content'] for x in bundle['files'] if x['path']=='config.json'))
  if cfg['cell_id']!=a['cell_id'] or cfg['law_id']!=a['law_id'] or cfg['actor']!=a['actor']:fail.append([cid,'identity'])
status='cpu_prepared' if not fail else 'proofs_in_progress';v=dict(format='worker-partition-branch-inventory-v1',partition=2,status=status,laws=laws,additional_bindings=bindings,planned_recordings=len(cases),comparisons=len(comparisons),explicit_comparison_reuses=sum(len(c['case_ids']) for c in comparisons)-len(cases),supersedes_initial59_branch_plan=True,authoritative_integrated_coverage='work/_shared/branch-coverage.json',native_executed=0,video_core_accepted=0,native_comparisons_complete=0,tested_capability_blockers=[],proof_failures=fail)
(root/orig[0]/'partition-2-branch-inventory.json').write_text(json.dumps(v,indent=2)+'\n')
(root/orig[0]/'final-receipt-audit.json').write_text(json.dumps(dict(passed=not fail,failures=fail,assignment_count=len(ids),case_count=len(cases),branch_count=sum(len(x['branches']) for x in laws.values()),comparison_count=len(comparisons),reuse_count=v['explicit_comparison_reuses'],measurement_test_log='receipts/partition-measurements.log',measurement_test_log_sha256=sha(root/orig[0]/'receipts/partition-measurements.log')),indent=2)+'\n')
print(json.dumps(dict(assignments=len(ids),cases=len(cases),branches=sum(len(x['branches']) for x in laws.values()),comparisons=len(comparisons),reuses=v['explicit_comparison_reuses'],failures=fail)))
raise SystemExit(bool(fail))
