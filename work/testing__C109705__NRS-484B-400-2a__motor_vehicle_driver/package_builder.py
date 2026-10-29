"""Build exact textual packages from law-specific implementation and fixture specs.
No Native execution; proof execution is explicit and CPU only.
"""
import json,hashlib,pathlib,subprocess,sys,shutil,os,uuid
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def build(spec):
 aid=spec['assignment_id'];folder=ROOT/'work'/aid;folder.mkdir(parents=True,exist_ok=True)
 ap=ROOT/'inputs'/aid/'assignment.json'
 if not ap.exists():ap=folder/'assignment.json'
 a=json.loads(ap.read_text());seed=ROOT/'references/v6-capability'/spec.get('seed_assignment_id',aid)
 sources=[ap,ROOT/'inputs/definitions.jsonl',ROOT/'references/v6-capability/index.json',seed/'runner.py',seed/'analyze.py',seed/'scene.xodr',ROOT/'examples/measurement/README.md']
 sources += [ROOT/p for p in spec.get('reference_paths',[])]
 cfg0=json.loads((seed/'config.json').read_text());cases=[];entries=[]
 ids=[aid+'__'+s['name'] for s in spec['cases']]
 ds=[dict(requirement=d['requirement'],source=d['source'],status='selected_required',evidence_or_gap=d['evidence_or_gap'],case_ids=[aid+'__'+n for n in d.get('cases',[s['name'] for s in spec['cases']])]) for d in spec['dispositions']]
 for i,s in enumerate(spec['cases']):
  cid=ids[i];case=json.loads(json.dumps(cfg0['case']));case.update(case_id=cid,rationale=s['rationale']);case['variable_assignments'].update(s.get('variable_assignments',{}));cases.append(case)
  cfg=json.loads(json.dumps(cfg0));cfg.update(s.get('config',{}));cfg.update(case=case,selected_case_id=cid,supported_case_ids=ids,cell_id=a['cell_id'],actor=a['actor'],law_id=a['law_id'])
  dest=folder if i==0 else folder/'cases'/s['name'];dest.mkdir(parents=True,exist_ok=True)
  runner=spec.get('runner',(seed/'runner.py').read_text());analysis=spec.get('analysis',(seed/'analyze.py').read_text())
  test=spec['test']
  texts={'runner.py':runner,'analyze.py':analysis,'config.json':json.dumps(cfg,indent=2)+'\n','scene.xodr':s.get('scene',spec.get('scene',(seed/'scene.xodr').read_text())),'tests/test_case.py':test}
  texts.update(spec.get('extra_files',{}));texts.update(s.get('extra_files',{}))
  for path,text in texts.items():p=dest/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
  bundle=dict(case_id=cid,cell_id=a['cell_id'],actor=a['actor'],entrypoint='runner.py',files=[dict(path=k,content=v,source=str((dest/k).relative_to(ROOT))) for k,v in texts.items()],recording_description=case['recording_description'],measurement_plan=spec['measurement_plan'],static_checks=spec['static_checks'],termination_rules=['Complete exact duration or fail; preserve startup through clearance'],mechanisms=spec['mechanisms'])
  write(dest/'construction.json',bundle)
  contract=dict(format='worker-measurement-contract-v1',requirements=[dict(disposition_index=j,requirement=d['requirement'],source=d['source'],**spec['dispositions'][j]['measurement']) for j,d in enumerate(ds) if cid in d['case_ids']],negative=spec['negative'])
  write(dest/'measurement-contract.json',contract)
  additions=[]
  for name,data in s['fixture'].items():
   p=dest/'fixture-additions'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data if isinstance(data,str) else json.dumps(data,indent=2)+'\n');additions.append(dict(path=name,source=str(p.relative_to(ROOT)),sha256=sha(p)))
  write(dest/'fixture-recipe.json',dict(format='worker-fixture-recipe-v1',base='runtime/main-pipeline-v1/fixtures/retained-speed',remove=['case.json','config.json','result.json'],additions=additions))
  rel=lambda p:str(p.relative_to(folder))
  entries.append(dict(case_id=cid,kind='capability',construction=rel(dest/'construction.json'),construction_sha256=sha(dest/'construction.json'),measurement_procedure=dict(entrypoint='analyze.py',output_schema='worker-analysis-report-v1'),measurement_contract=rel(dest/'measurement-contract.json'),fixture_recipe=str((dest/'fixture-recipe.json').relative_to(ROOT)),native_handoff=dict(python_env_var='CARLA_PYTHON',host_env_var='CARLA_HOST',port_env_var='CARLA_PORT'),acquisition={c['name']:dict(entrypoint='runner.py',method=c['method'],evidence='Original Native acquisition and source finalizer') for c in case['recording_description']['channels']}))
  for atom in cfg.get('required_atoms',[]):
   entries[-1]['acquisition'].setdefault(atom,dict(entrypoint='runner.py',method='PipelineCapture.capture and original source packets',evidence='Original subject/actor/road/control/weather observations in capture/evidence.jsonl; declared geometry/rule/environment packets: '+','.join(cfg.get('source_packets',[]))))
 write(folder/'proposals/cases.json',dict(cell_id=a['cell_id'],actor=a['actor'],status='draft',sweep_specs=[],cases=cases))
 comparisons=[dict(comparison_id=x['comparison_id'],case_ids=[aid+'__'+n for n in x['cases']],fixed_conditions=x['fixed_conditions'],deliberate_differences=x['deliberate_differences']) for x in spec['comparisons']]
 plan=dict(assignment_id=aid,actor=a['actor'],cell_id=a['cell_id'],law_id=a['law_id'],selected_branch=a['branch'],cases=cases,comparisons=comparisons,observations=[dict(name=c['name'],mandatory=True) for c in cases[0]['recording_description']['channels']],sources=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in sources],existing_evidence=a['existing_evidence'],runtime_uncertainties=spec['limitations'],requirement_dispositions=ds,source_observation_mapping={t['term']:dict(evidence=spec['observation_mapping'].get(t['term'],spec['measurement_plan']),channels=[c['name'] for c in cases[0]['recording_description']['channels']],source_refs=[str((ROOT/'inputs'/aid/'assignment.json').relative_to(ROOT))]) for t in a['source_observation_terms']},camera_plan=dict(profile='overview1080-capability-v1',duration_s=cfg0['duration_s'],composition='synchronized_four_view_primary',coverage=[dict(subject='All participant bodies and route context',interval=[0,cfg0['duration_s']],view='overview'),dict(subject='Approach and lane body position',interval=[0,cfg0['duration_s']],view='approach'),dict(subject='Junction boundaries and priority interaction',interval=[0,cfg0['duration_s']],view='reference_corner'),dict(subject='Driver perspective and controls',interval=[0,cfg0['duration_s']],view='driver_reference')]),physical_pixel_audits=spec['audits'])
 write(folder/'case-plan.json',plan)
 manifest=dict(format='worker-execution-manifest-v1',assignment_id=aid,runtime_manifest_sha256=sha(ROOT/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),cases=entries);write(folder/'execution-manifest.json',manifest)
 branches=[dict(branch_id=a['law_id']+'-'+b['name'],topic_ids=b['topic_ids'],status='runnable',assignment_id=aid,case_ids=[aid+'__'+n for n in b['cases']],comparison_ids=b['comparison_ids']) for b in spec['branches']];write(folder/'branch-contribution.json',dict(law_id=a['law_id'],branches=branches))
 return folder

def prove(folder,library,validator):
 (ROOT/'.runtime-work/tmp').mkdir(parents=True,exist_ok=True)
 manifest=folder/'execution-manifest.json';m=json.loads(manifest.read_text());aid=folder.name;runroot=ROOT/'.runtime-work'/aid/('proof-'+os.environ.get('PROOF_RUN',uuid.uuid4().hex[:10]));receipts=folder/'receipts';receipts.mkdir(exist_ok=True)
 def run(command,log):
  with log.open('w') as out:r=subprocess.run(command,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,env=dict(os.environ,TMPDIR=str(ROOT/'.runtime-work/tmp')))
  if r.returncode:raise RuntimeError(str(log)+' failed '+str(r.returncode))
 for i,e in enumerate(m['cases']):
  cid=e['case_id'];attempt=runroot/('offline-'+str(i));cmd=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'offline','--manifest',str(manifest),'--case',cid,'--output',str(attempt)]
  log=receipts/('offcheck-'+str(i)+'.log');run(cmd,log);e['offline']=dict(command=' '.join(cmd),exit_code=0,log=str(log.relative_to(folder)),log_sha256=sha(log),construction_sha256=e['construction_sha256']);write(manifest,m)
  out=runroot/('compatibility-'+str(i));cmd=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'compatibility-recipe','--manifest',str(manifest),'--case',cid,'--output',str(out),'--library',str(library),'--validator',str(validator)]
  log=receipts/('compatcommand-'+str(i)+'.log');run(cmd,log)
  for src,name in [('compatibility.json','compatcheck-'+str(i)+'.json'),('compatibility-analysis.log','analysis-'+str(i)+'.log'),('negative-analysis.log','negative-'+str(i)+'.log')]:shutil.copyfile(out/src,receipts/name)
  e['compatibility']=dict(receipt='receipts/compatcheck-'+str(i)+'.json',sha256=sha(receipts/('compatcheck-'+str(i)+'.json')),log='receipts/analysis-'+str(i)+'.log');e['negative']=dict(log='receipts/negative-'+str(i)+'.log')
  gpu=f'python3.11 runtime.py capture --manifest work/{aid}/execution-manifest.json --case {cid} --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --output .runtime-work/{aid}/native-{i}'
  process=f'python3.11 runtime.py process-saved --manifest work/{aid}/execution-manifest.json --case {cid} --attempt .runtime-work/{aid}/native-{i} --output .runtime-work/{aid}/processed-{i} --library "$TRAFFIC_SPEC_LIBRARY" --validator "$TRAFFIC_SPEC_VALIDATOR"'
  e['gpu_command']=gpu
  # Exercise finalizer and full saved-only path against the retained diagnostic attempt.
  (out/'result.json').unlink();shutil.rmtree(out/'traffic_spec')
  cmd=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'process-saved','--manifest',str(manifest),'--case',cid,'--attempt',str(out),'--output',str(runroot/('saved-'+str(i))),'--library',str(library),'--validator',str(validator)]
  log=receipts/('saved-'+str(i)+'.log');run(cmd,log)
  e['post_capture']=dict(recorded_only=True,command=process,feedback_command='cat .runtime-work/'+aid+'/processed-'+str(i)+'/feedback.json',test_log=str(log.relative_to(folder)),test_log_sha256=sha(log),test_exit_code=0);write(manifest,m)
 ap=ROOT/'inputs'/aid/'assignment.json'
 if not ap.exists():ap=folder/'assignment.json'
 a=json.loads(ap.read_text());batch=json.loads((ROOT/'batch.json').read_text())
 write(folder/'result.json',dict(assignment_id=aid,input_sha256=sha(ap),status='ready',applied_update=batch['update_version'],readiness_kind='capability',first_gpu_capability_command=m['cases'][0]['gpu_command'],tests=[dict(command=e['offline']['command'],exit_code=0,log=e['offline']['log'],sha256=e['offline']['log_sha256']) for e in m['cases']],acceptance_claimed=False))
 (folder/'HANDOFF.md').write_text('CPU software compatibility only. Native motion, original pixels, legal status and legal judgments remain unverified. No CARLA executed.\n\n'+ '\n\n'.join(e['gpu_command']+'\n\n'+e['post_capture']['command'] for e in m['cases']))
if __name__=='__main__':
 p=pathlib.Path(sys.argv[1]);s=json.loads(p.read_text());f=build(s)
 if len(sys.argv)>3:prove(f,pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
