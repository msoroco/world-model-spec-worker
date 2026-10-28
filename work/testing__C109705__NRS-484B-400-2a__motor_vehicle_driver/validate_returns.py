"""Lead-only offline rerun and integrity audit. Never launches CARLA."""
import pathlib,json,subprocess,hashlib,sys,collections,datetime
ROOT=pathlib.Path.cwd();ANCHOR=ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def execute(command,log):
 p=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);log.parent.mkdir(exist_ok=True);log.write_text(p.stdout);return dict(command=' '.join(command),exit_code=p.returncode,log=str(log.relative_to(ROOT)),sha256=sha(log))
def main():
 batch=json.loads((ROOT/'batch.json').read_text());returns={};failures=[]
 for aid in batch['assignments']:
  w=ROOT/'work'/aid;r=json.loads((w/'result.json').read_text());sources={str(p.relative_to(w)):sha(p) for p in w.rglob('*') if p.is_file() and '__pycache__' not in p.parts and (p.suffix in ('.py','.xodr') or str(p.relative_to(w)) in ('config.json','case-plan.json','construction.json','proposals/cases.json'))}
  tests=[]
  for name,cmd in [('lead-check',[sys.executable,str((w/'runner.py').relative_to(ROOT)),'--check']),('lead-tests',[sys.executable,'-m','unittest','discover','-s',str((w/'tests').relative_to(ROOT))])]:
   test=execute(cmd,w/'logs'/(name+'.log'));test['log']=str((ROOT/test['log']).relative_to(w));test['source_sha256']=sources;tests.append(test)
   if test['exit_code']:failures.append(aid+': '+test['command'])
  r['lead_tests']=tests;r['tests']=tests;dump(w/'result.json',r)
  plan=json.loads((w/'case-plan.json').read_text());con=json.loads((w/'construction.json').read_text());config=json.loads((w/'config.json').read_text());proposal=json.loads((w/'proposals/cases.json').read_text());errors=[]
  canonical={'cell_id','actor','case_id','status','files','entrypoint','mechanisms','measurement_plan','recording_description','static_checks','termination_rules'}
  if set(con)!=canonical:errors.append('root noncanonical construction keys '+str(set(con)^canonical))
  for f in con['files']:
   if (w/f['path']).read_text()!=f['content']:errors.append('stale inline '+f['path'])
  orig=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())
  if plan['existing_evidence']!=orig['existing_evidence']:errors.append('existing evidence changed')
  if any(v.get('value') is not None for c in proposal['cases'] for v in c['variable_assignments'].values() if v.get('kind')=='subject_behavior'):errors.append('fabricated subject outcome')
  baseline=[c for c in proposal['cases'] if c['target_type']=='baseline']
  default=config.get('default_case_id',config.get('selected_case_id'))
  if any(c['case_id']==default for c in baseline):errors.append('baseline selected')
  for c in proposal['cases']:
   if c['target_type']=='baseline':continue
   if c['case_id']!=con['case_id'] and not (w/'constructions'/(c['case_id']+'.json')).is_file():errors.append('missing per-case construction '+c['case_id'])
  if errors:failures.extend(aid+': '+s for s in errors)
  returns[aid]=dict(status=r['status'],reason=r.get('reason'),case_count=len(plan['cases']),tests=tests,integrity_errors=errors)
 shared=[]
 for tag,cmd in [('repo-tests',[sys.executable,'-m','unittest','discover','-s','tests'])]+[(name+suffix,cmd) for name in ('intersection','judgment','numeric') for suffix,cmd in [('-check',[sys.executable,'examples/'+name+'/runner.py','--check']),('-tests',[sys.executable,'-m','unittest','discover','-s','examples/'+name+'/tests'])]]+ [('update-status',[sys.executable,'update_status.py']),('complete-contract',[sys.executable,'worker_check.py','--complete'])]:
  t=execute(cmd,ANCHOR/'logs'/('lead-'+tag+'.log'));shared.append(t)
  if t['exit_code']:failures.append(t['command'])
 report=dict(batch_id=batch['batch_id'],applied_update=batch['update_version'],interpreter=sys.version,status_counts=dict(collections.Counter(r['status'] for r in returns.values())),returns=returns,shared_tests=shared,failures=failures,live_execution=False,validation_scope='Offline implementation/contracts only; no physical or legal acceptance')
 dump(ANCHOR/'lead-validation.json',report);print(json.dumps(dict(status_counts=report['status_counts'],failures=failures),indent=2));return bool(failures)
if __name__=='__main__':raise SystemExit(main())
