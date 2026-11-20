import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path
P=Path('work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver'); B=Path('.runtime-work'); M=json.loads((P/'execution-manifest.json').read_text()); PLAN=json.loads((P/'case-plan.json').read_text()); S=json.loads((P/'final-selected-replay-v2-summary.json').read_text()); E={x['case_id']:x for x in M['cases']}; R={(x['case'],x['candidate']):x for x in S['results']}; assert S['passed_count']==60 and S['manifest_unchanged'] and len(R)==60
assert hashlib.sha256((P/'execution-manifest.json').read_bytes()).hexdigest()==S['manifest_sha256']
for (cid,ident),r in R.items():
 assert cid in E and ident in {'primary','fallback1','fallback2','fallback3'}
 assert all(r[k] for k in ('compat_passed','saved_passed','recorded_only','originals_preserved'))
 for key in ('compat_receipt','saved_receipt'):
  assert hashlib.sha256(Path(r[key]).read_bytes()).hexdigest()==r[key+'_sha256']
for e in E.values():
 recipe=json.loads(Path(e['fixture_recipe']).read_text())
 for item in recipe['sources']:
  assert hashlib.sha256(Path(item['source']).read_bytes()).hexdigest()==item['sha256']
spec=importlib.util.spec_from_file_location('sign',P/'prove_sign_angle_comparison.py'); sign=importlib.util.module_from_spec(spec);spec.loader.exec_module(sign)
entries=sorted([e for e in E.values() if 'sign_angle' in e['case_id']],key=lambda e:sign.LABELS.index(e['case_id'].split('sign_angle_')[-1])); cons=[sign.read(P/e['construction']) for e in entries]; recipes=[sign.read(sign.REPO/e['fixture_recipe']) for e in entries]; source=[{x['path']:x for x in q['sources']} for q in recipes]; roads=[(sign.REPO/x['road.xodr']['source']).read_text() for x in source]; controls=[sign.rows(sign.REPO/x['control_inventory.jsonl']['source']) for x in source];captures=[sign.read(sign.REPO/x['capture/manifest.json']['source']) for x in source]; sign.audit(entries,cons,recipes,roads,controls,captures)
base='.runtime-work/c158190-portable-'; first='.runtime-work/c158190-config15-primary-compat-v1'; pairmap={'approaching_traffic_vs_clear':('through_approaches','clear'),'slowed_vs_no_slow':('through_approaches','no_slow'),'approaching_vs_already_entered':('through_approaches','through_entered'),'same_approaching_traffic_view_speed_2_vs_4':('through_approaches','mid_speed')}
results=[]
for comp in PLAN['comparisons']:
 name=comp['comparison_id']; ids=comp['case_ids']; assert all(x in E for x in ids)
 if name in pairmap:
  a,b=pairmap[name];args=['--left',(first if a=='through_approaches' else base+a+'-primary-compat-v1'),'--right',base+b+'-primary-compat-v1','--comparison',name]; cmd=[sys.executable,str(P/'comparison_audit.py'),*args];p=subprocess.run(cmd,env={'PYTHONPATH':'runtime/scenario_pipeline'},capture_output=True,text=True);assert p.returncode==0,p.stderr; assert json.loads(p.stdout)['software_comparison_passed'];kind='source_and_measurements'
 elif name=='same_approaching_traffic_view_speed_2_4_6':
  cmd=[sys.executable,str(P/'comparison_audit.py'),'--left',first,'--right',base+'mid_speed-primary-compat-v1','--third',base+'speed_6-primary-compat-v1','--comparison',name];p=subprocess.run(cmd,env={'PYTHONPATH':'runtime/scenario_pipeline'},capture_output=True,text=True);assert p.returncode==0,p.stderr;assert json.loads(p.stdout)['closest_view_speeds_mps']==[2,4,6];kind='source_and_measurements'
 elif name=='same_approach_through_speed_3_7_11':
  p=subprocess.run([sys.executable,str(P/'prove_through_speed_comparison.py')],env={'PYTHONPATH':'runtime/scenario_pipeline'},capture_output=True,text=True);assert p.returncode==0,p.stderr;assert json.loads(p.stdout)['software_comparison_passed'];kind='source_and_measurements_historical_receipts_replaced_by_final_replay'
 elif name=='same_approach_sign_face_angle_minus_015_zero_plus_015':
  assert [x.split('sign_angle_')[-1] for x in ids]==list(sign.LABELS);kind='source_geometry_angles_minus_015_zero_plus_015'
 elif name=='same_approach_view_occluder_y12_y15_y18':
  ys=[];rays=[]
  for n in (12,15,18):
   root=Path(base+f'occluder_y{n}-primary-compat-v1'); ctx=json.loads((root/'road_context.json').read_text());ys.append(ctx['view_occluder']['native_location_m'][1]);rays.append(hashlib.sha256((root/'visibility_rays.jsonl').read_bytes()).hexdigest())
  assert ys==[12,15,18];kind='source_geometry_only_visibility_rays_identical' if len(set(rays))==1 else 'source_geometry_and_rays'
 else: raise ValueError(name)
 assert all(R[(x,ident)]['saved_passed'] for x in ids for ident in ('primary','fallback1','fallback2','fallback3'))
 results.append({'comparison_id':name,'cases':len(ids),'kind':kind,'current_manifest_receipts':True})
assert len(results)==8
print(json.dumps({'format':'c158190-current-selected-comparison-audit','manifest_sha256':S['manifest_sha256'],'selected_cases':len(E),'variant_receipts':len(R),'comparisons':results,'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'},indent=2))
