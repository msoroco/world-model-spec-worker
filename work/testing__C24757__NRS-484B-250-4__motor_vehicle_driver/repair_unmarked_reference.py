"""Correct only the two exact unmarked-crosswalk references and rerun CPU proofs."""
import hashlib,json,os,pathlib,shutil,subprocess,uuid
R=pathlib.Path(__file__).resolve().parents[2];F=pathlib.Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
TEST='''
 def test_reference_matches_actual_sidewalk_band(self):
  import runner,xml.etree.ElementTree as ET
  cfg=json.loads((runner.ROOT/'config.json').read_text())
  tree=ET.fromstring(runner.authored_scene(cfg))
  side=tree.find("road[@id='3']/lanes/laneSection/left")
  roadway_half_width=sum(float(l.find('width').get('a')) for l in side.findall('lane') if l.get('type')=='driving')
  sidewalk_width=float(side.find("lane[@type='sidewalk']/width").get('a'))
  self.assertEqual(cfg['reference_x_m'],-(roadway_half_width+sidewalk_width))
  self.assertEqual(cfg['reference_x_m'],-9)
'''
manifest_path=F/'execution-manifest.json';manifest=read(manifest_path);spec_path=F/'package-spec.json';spec=read(spec_path);changed=[]
for c in spec['cases']:
 if c['name'] not in ('unmarked_crosswalk_stop','unmarked_crosswalk_roll'):continue
 shift=-9-c['config']['reference_x_m']
 c['config']['reference_x_m']=-9;c['fixture']['signal_context.json'].update(reference_line_x_m=-9,crosswalk_band_x_m=[-9,-7])
 history=[json.loads(line) for line in c['fixture']['interaction_history.jsonl'].splitlines() if line]
 for i,row in enumerate(history):
  if i<2:
   for v in row['states']['ego']['body_vertices_m']:v[0]+=shift
  row['sight_ray']['eye_m'][0]+=shift
 c['fixture']['interaction_history.jsonl']=''.join(json.dumps(row)+'\n' for row in history)
 c.setdefault('extra_files',{})['tests/test_case.py']=spec['test']+TEST
 dest=F/'cases'/c['name'];cfg=read(dest/'config.json');cfg['reference_x_m']=-9;write(dest/'config.json',cfg)
 (dest/'tests/test_case.py').write_text(c['extra_files']['tests/test_case.py'])
 for name in ('signal_context.json','interaction_history.jsonl'):
  value=c['fixture'][name];(dest/'fixture-additions'/name).write_text(value if isinstance(value,str) else json.dumps(value,indent=2)+'\n')
 recipe=read(dest/'fixture-recipe.json')
 for addition in recipe['additions']:addition['sha256']=sha(R/addition['source'])
 write(dest/'fixture-recipe.json',recipe)
 construction=read(dest/'construction.json')
 for source in construction['files']:
  if source['path'] in ('config.json','tests/test_case.py'):source['content']=(dest/source['path']).read_text()
 write(dest/'construction.json',construction)
 idx=next(i for i,e in enumerate(manifest['cases']) if e['case_id']==construction['case_id']);manifest['cases'][idx]['construction_sha256']=sha(dest/'construction.json');changed.append(idx)
write(spec_path,spec);write(manifest_path,manifest)
# The final partition generator preserves the same actual sidewalk-band correction.
runroot=R/'.runtime-work'/F.name/('reference-correction-'+uuid.uuid4().hex[:10]);env=dict(os.environ,TMPDIR=str(R/'.runtime-work/tmp'))
def run(args,log):
 with log.open('w') as out:subprocess.run(args,cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT,check=True)
python=str(R/'.venv-cpu/bin/python');library=R/'runtime/main-pipeline-v1/library';validator=R/'.runtime-work/decoder/.lake/build/bin/adapterCheck'
for i in changed:
 entry=manifest['cases'][i];cid=entry['case_id'];out=runroot/('offline-'+str(i));args=[python,str(R/'runtime.py'),'offline','--manifest',str(manifest_path),'--case',cid,'--output',str(out)]
 log=F/'receipts'/('offcheck-'+str(i)+'.log');run(args,log);entry['offline']=dict(command=' '.join(args),exit_code=0,log=str(log.relative_to(F)),log_sha256=sha(log),construction_sha256=entry['construction_sha256']);write(manifest_path,manifest)
 out=runroot/('compatibility-'+str(i));args=[python,str(R/'runtime.py'),'compatibility-recipe','--manifest',str(manifest_path),'--case',cid,'--output',str(out),'--library',str(library),'--validator',str(validator)]
 log=F/'receipts'/('compatcommand-'+str(i)+'.log');run(args,log)
 for source,target in [('compatibility.json','compatcheck-'+str(i)+'.json'),('compatibility-analysis.log','analysis-'+str(i)+'.log'),('negative-analysis.log','negative-'+str(i)+'.log')]:shutil.copyfile(out/source,F/'receipts'/target)
 entry['compatibility']['sha256']=sha(F/entry['compatibility']['receipt']);(out/'result.json').unlink();shutil.rmtree(out/'traffic_spec')
 args=[python,str(R/'runtime.py'),'process-saved','--manifest',str(manifest_path),'--case',cid,'--attempt',str(out),'--output',str(runroot/('saved-'+str(i))),'--library',str(library),'--validator',str(validator)]
 log=F/entry['post_capture']['test_log'];run(args,log);entry['post_capture']['test_log_sha256']=sha(log);write(manifest_path,manifest)
 print(cid,'corrected reference -9, all exact proofs passed',flush=True)
result=read(F/'result.json')
for i in changed:
 e=manifest['cases'][i]
 for t in result['tests']:
  if t['log']==e['offline']['log']:t.update(command=e['offline']['command'],sha256=e['offline']['log_sha256'])
write(F/'result.json',result)
