"""Execute complete/incomplete/missing Native-style SOFTWARE fixtures through saved processing."""
import argparse,ast,contextlib,copy,pickle,hashlib,importlib.util,json,os,pathlib,shutil,subprocess,sys,uuid
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'work/_shared'))
from update002_tools import read,write,sha

def activate():
 spec=importlib.util.spec_from_file_location('worker_v3_runtime',ROOT/'work/_shared/runtime-v3.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 runtime=module.runtime();sys.path.insert(0,str(runtime/'scenario_pipeline'));sys.path.insert(1,str(runtime/'python'))
 return runtime

def four_sources():
 folder=ROOT/'.runtime-work/update002/four-sources';folder.mkdir(parents=True,exist_ok=True)
 for name,width,height in [('overview',1920,1080),('approach',1280,720),('reference_corner',1280,720),('driver_reference',1280,720)]:
  path=folder/(name+'.mkv')
  if not path.exists():subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-f','lavfi','-i',f'color=c=gray:s={width}x{height}:r=20','-frames:v','3','-threads','1','-c:v','ffv1',str(path)],check=True)
 return folder

def fixture(folder,entry,kind,base,runtime):
 from worker_exchange.fixture_recipe import materialize as recipe
 from worker_exchange.runtime_cli import materialize
 spec=importlib.util.spec_from_file_location('physical_fixtures',ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/physical_assessment002.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 attempt=base/kind;materialize(folder/'execution-manifest.json',entry['case_id'],attempt)
 source=base/(kind+'-fixture');recipe(ROOT,ROOT/entry['fixture_recipe'],source)
 for p in source.iterdir():
  target=attempt/p.name
  if target.exists():raise ValueError('Fixture shadowed current bundle')
  if p.is_dir():shutil.copytree(p,target)
  else:shutil.copyfile(p,target)
 cfg=read(attempt/'config.json')
 # Keep a stale pre-update Native construction/analyzer/result to prove selection of current analysis.
 previous='f52931c56e9b259dc8cc5f5253714f4d4d745986'
 old=json.loads(subprocess.check_output(['git','show',previous+':work/'+folder.name+'/execution-manifest.json'],cwd=ROOT,text=True))
 original_entry=next(c for c in old['cases'] if c['case_id']==entry['case_id'])
 old_construction=json.loads(subprocess.check_output(['git','show',previous+':work/'+folder.name+'/'+original_entry['construction']],cwd=ROOT,text=True))
 construction=read(attempt/'construction.json')
 old_analyzer=next(f['content'] for f in old_construction['files'] if f['path']=='analyze.py')
 next(f for f in construction['files'] if f['path']=='analyze.py')['content']=old_analyzer
 write(attempt/'construction.json',construction)
 (attempt/'analyze.py').write_text(old_analyzer)
 cfg=read(attempt/'config.json')
 generated=m.make_motion_fixture(attempt,cfg,'complete_motion' if kind=='missing_evidence' else kind)
 if cfg['law_id'] in ('NRS-484B-400-2a','NRS-484B-400-2b') and kind!='missing_evidence':
  rows=[json.loads(s) for s in (attempt/'body_history.jsonl').read_text().splitlines() if s]
  for i,row in enumerate(rows):row['road_id']=[1,13,4][i] if kind=='complete_motion' else 1
  (attempt/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 # Exercise capture-only raw sources. The helper removes every derived tail output again.
 fixture_module=importlib.util.spec_from_file_location('native_raw_fixtures',ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/native_fixture_sources002.py');native=importlib.util.module_from_spec(fixture_module);fixture_module.loader.exec_module(native)
 selected=read(folder/entry['construction']);selected_analysis=next(f['content'] for f in selected['files'] if f['path']=='analyze.py')
 preparation=next(n for n in ast.parse(selected_analysis).body if isinstance(n,ast.FunctionDef) and n.name=='prepare_saved')
 native.make_native_sources(attempt,cfg,preparation_source=ast.unparse(preparation),strict=(kind=='complete_motion'))
 # Explicit diagnostic graph authors model actual Native source shapes before sealing.
 authors={}
 for key in ('speed_sign','signal','indicator','visibility'):
  author_path=ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver'/('native_'+key+'_fixture002.py')
  spec=importlib.util.spec_from_file_location('diagnostic_'+key,author_path);author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author);authors[key]=author
 if cfg['law_id']=='NRS-484B-250-4':authors['signal'].diagnostic_enrich2504(attempt,cfg)
 signal_rows=[];signal_context={}
 if cfg['law_id'] in ('NRS-484B-307-6a','NRS-484B-250-4'):
  signal_rows=[json.loads(s) for s in (attempt/('signal_history.jsonl' if cfg['law_id']=='NRS-484B-307-6a' else 'interaction_history.jsonl')).read_text().splitlines() if s]
  signal_context=read(attempt/'signal_context.json')
 indicator_rows=[]
 if cfg['law_id']=='NRS-484B-413-2':indicator_rows=[json.loads(s) for s in (attempt/'signal_history.jsonl').read_text().splitlines() if s]
 (attempt/'road.xodr').write_text((attempt/'scene.xodr').read_text())
 surface=read(attempt/'surface_provenance.json');surface['map_sha256']=sha(attempt/'road.xodr');surface['authored_map_sha256']=surface['map_sha256'];write(attempt/'surface_provenance.json',surface)
 relocations=read(attempt/'asset_relocations.json');relocations['surface_provenance_sha256']=sha(attempt/'surface_provenance.json');write(attempt/'asset_relocations.json',relocations)
 # Join all authored Native-style telemetry before sealing the diagnostic inventory.
 trace=[json.loads(s) for s in (attempt/'trace.jsonl').read_text().splitlines() if s]
 for row in trace:
  row['speed_mph']=row['speed_mps']/.44704
  row['environment_measurements']['surface_sha256']=sha(attempt/'surface_provenance.json')
 (attempt/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in trace))
 evidence=[json.loads(s) for s in (attempt/'capture/evidence.jsonl').read_text().splitlines() if s]
 for evidence_index,(original,row) in enumerate(zip(evidence,trace)):
  original.setdefault('original_observations',{}).setdefault('map_context',{})['declared_public_way_road_ids']=cfg.get('public_way_road_ids',[])
  original['ego'].update(position_m=row['position_m'],heading_deg=row['heading_deg'],speed_mps=row['speed_mps'],body_vertices_m=m._box(row['position_m'][:2]))
  for actor in original.get('original_observations',{}).get('participants',[]):
   if actor['actor_id']==original['actor_id']:actor.update(position_m=row['position_m'],heading_deg=row['heading_deg'],speed_mps=row['speed_mps'],velocity_mps=row['velocity_mps'],body_vertices_m=m._box(row['position_m'][:2]))
  if cfg['law_id']=='NRS-484B-250-4':
   packet=authors['visibility'].author_packet(attempt,cfg,original,signal_rows[evidence_index])
   original['original_observations']['participants']=packet['participants'];original['original_observations']['relations']=packet['relations']
 (attempt/'capture/evidence.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in evidence))
 synchronized=attempt/'synchronized_motion_records.jsonl'
 if synchronized.is_file():
  records=[json.loads(s) for s in synchronized.read_text().splitlines() if s]
  for record,row,event in zip(records,trace,evidence):
   def update_actor(value):
    if isinstance(value,dict):
     if value.get('actor_id')==event['actor_id'] and 'body_vertices_m' in value:
      value.update(position_m=row['position_m'],heading_deg=row['heading_deg'],speed_mps=row['speed_mps'],velocity_mps=row['velocity_mps'],body_vertices_m=m._box(row['position_m'][:2]))
     for v in value.values():update_actor(v)
    elif isinstance(value,list):
     for v in value:update_actor(v)
   update_actor(record)
   if cfg['law_id']=='NRS-484B-250-4':
    value=record['value']
    for name in list(value):
     if isinstance(value[name],dict) and 'actor_id' in value[name]:del value[name]
    for actor in event['original_observations']['participants']:
     value['ego' if actor['actor_id']==event['actor_id'] else 'diagnostic_role_'+str(actor['actor_id'])]=copy.deepcopy(actor)
  synchronized.write_text(''.join(json.dumps(r)+'\n' for r in records))
 from traffic_spec_adapter.adapter import load_graph
 frames=[json.loads(s) for s in (attempt/'capture/native/frames.jsonl').read_text().splitlines() if s]
 for frame_index,(frame,event) in enumerate(zip(frames,evidence)):
  for graph_kind in ('base',):
   graph_path=attempt/'capture/native'/frame[graph_kind];graph=load_graph(graph_path)
   if cfg['law_id']=='NRS-484B-250-4':
    for node,data in list(graph.nodes(data=True)):
     if node!='ego' and data.get('sem_class','').startswith(('vehicle.','walker.')):graph.remove_node(node)
    for actor in event['original_observations']['participants']:
     if actor['actor_id']!=event['actor_id']:
      graph.add_node('diagnostic_role_'+str(actor['actor_id']),sem_class=actor['blueprint'],carla_id=actor['actor_id'],entity_id=actor['actor_id'],vertex=actor['position_m'],diagnostic_fixture=True)
   graph.graph['observed_evidence']=copy.deepcopy(event['original_observations'])
   if cfg['law_id']=='NRS-484B-600-1c':authors['speed_sign'].augment_graph(graph,attempt/'scene.xodr')
   if signal_rows:authors['signal'].augment_graph(graph,signal_rows[frame_index],signal_context)
   if indicator_rows:
    flags=authors['indicator'].indicator_attributes(indicator_rows[frame_index],cfg)
    # Replace retained fixture seed defaults, never real capture. Raw per-frame API bits are authoritative here.
    for node,data in graph.nodes(data=True):
     if node=='ego':data['carla_id']=event['actor_id']
     if data.get('carla_id',data.get('entity_id'))==event['actor_id']:
      data.update(flags);data['vehicle_light_state']=(32 if flags['light_LeftBlinker'] else 0)+(16 if flags['light_RightBlinker'] else 0)
      data['diagnostic_lamp_source']='signal_history.jsonl';data['diagnostic_fixture']=True
    authors['indicator'].augment_graph(graph,indicator_rows[frame_index],cfg,event['actor_id'])
   with graph_path.open('wb') as stream:pickle.dump(graph,stream)
 # Diagnostic converter input is authored before sealing, never repaired after capture.
 manifest=read(attempt/'capture/manifest.json')
 manifest['required_observations']=cfg['required_atoms']
 if cfg['law_id']=='NRS-484B-250-4':manifest['road_user_visibility_observed']=True
 manifest['case_id']=entry['case_id']
 manifest['source_run']='diagnostic-update002-native-style'
 for name in manifest['sources']:
  if (attempt/name).is_file():manifest['sources'][name]=sha(attempt/name)
 write(attempt/'capture/manifest.json',manifest)
 write(attempt/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':True,'acquisition_mode':'software_authored_native_style','fixture_scope':'Not a Native execution or accepted recording'})
 write(attempt/'result.json',{'case_id':entry['case_id'],'maneuver_completed':False,'legacy_result_preserve_exactly':True})
 for p in four_sources().iterdir():shutil.copyfile(p,attempt/p.name)
 if kind=='missing_evidence':
  missing=attempt/m.default_descriptor(cfg)['motion_source']
  if missing.exists():missing.unlink()
 # Complete fixture exercises capture-only four-view composition AFTER owner release.
 if kind=='complete_motion':(attempt/'raw.mkv').unlink()
 return attempt,generated

class FakeServer:
 def __init__(self):self.world={'map':'operator_world','sync':False};self.before=copy.deepcopy(self.world);self.captured=False;self.encoders_open=True
 def capture(self):self.world={'map':'fixture_world','sync':True};self.captured=True
 def close_encoders(self):assert self.captured;self.encoders_open=False
 def restore(self):
  assert not self.encoders_open;self.world=copy.deepcopy(self.before);assert self.world==self.before
  return {'restored':True,'fake_server':True,'readback_verified':self.world==self.before}
class FakeOwner:
 def __init__(self):self.held=True;self.events=[];self.server=FakeServer()
 def capture_finished(self):assert self.held;self.server.capture();self.events.append('capture_finished')
 def close_encoders(self):assert self.held;self.server.close_encoders();self.events.append('encoders_closed');return {n:0 for n in ('overview','approach','reference_corner','driver_reference')}
 def restore(self):assert self.held;value=self.server.restore();self.events.append('restoration_verified');return value
 def native_exit(self):assert self.held and not self.server.encoders_open and self.server.world==self.server.before;self.events.append('native_exit')
 def release(self):assert self.events[-1]=='native_exit';self.held=False;self.events.append('owner_released')
 def processing(self):assert not self.held;self.events.append('saved_processing_started')

def prove_entry(folder,entry,runtime,root_output=None):
 from worker_exchange.native_output import seal_capture
 from worker_exchange.saved_processing import run,record_native_exit,acknowledge_owner_release
 from worker_exchange.common import tree
 spec=importlib.util.spec_from_file_location('capture_boundary',ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/build_migration_sources.py');boundary=importlib.util.module_from_spec(spec);spec.loader.exec_module(boundary)
 boundary_check=boundary.verify_runner(next(f['content'] for f in read(folder/entry['construction'])['files'] if f['path']=='runner.py'))
 base=(root_output or ROOT/'.runtime-work/delivery-v3/physical'/folder.name)/(entry['case_id'].rsplit('__',1)[-1]+'-'+uuid.uuid4().hex[:8]);base.mkdir(parents=True)
 receipts=folder/'receipts';receipts.mkdir(exist_ok=True);key=entry['case_id'].rsplit('__',1)[-1];fixtures=[];life=None
 for kind,status in [('complete_motion','met'),('incomplete_motion','not_met'),('missing_evidence','unverified')]:
  log=receipts/('physical002-'+key+'-'+kind+'.log')
  with log.open('w') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
   attempt,generated=fixture(folder,entry,kind,base,runtime);owner=FakeOwner();owner.capture_finished();codes=owner.close_encoders();restoration=owner.restore()
   context=read(attempt/'acquisition-context.json') if (attempt/'acquisition-context.json').is_file() else {}
   context['software_fixture_only']=True
   if (attempt/'trace.jsonl').is_file():seal_capture(attempt,frames=3,restoration=restoration,errors=[],encoder_exit_codes=codes,context=context)
   else:write(attempt/'native-run-status.json',{'frames':3,'errors':[{'missing_evidence':'trace.jsonl'}],'restoration':restoration})
   record_native_exit(attempt);owner.native_exit();owner.release();owner_path=base/(kind+'-owner.json');acknowledge_owner_release(attempt,owner_path,True)
   before=tree(attempt);owner.processing()
   result=run(folder/'execution-manifest.json',entry['case_id'],attempt,base/(kind+'-processed'),ROOT/'runtime/main-pipeline-v3/library',ROOT/'.runtime-work/decoder-v3/.lake/build/bin/adapterCheck',owner_path)
   value=read(pathlib.Path(result['result']));check=value['physical_checks']['maneuver']
   assert check['status']==status,(entry['case_id'],kind,check)
   assert value['maneuver_completed']==(status=='met')
   assert value['provenance_kind']=='native' and value['diagnostic_fixture'] is True
   assert check['method'] and check['sources'] and all(v.get('status') in ('met','not_met','unverified') and v.get('method') and v.get('sources') for v in value['physical_checks'].values())
   assert tree(attempt)==before,'Original sources changed'
   assert result['native_revision']['construction_sha256']!=result['analysis_revision']['construction_sha256'],'Old Native/new analysis revisions not distinct'
   if kind=='complete_motion':
    assert value['realized_observables'] and result['final_video_checks'] and result['missing_evidence'] is False,'Complete fixture must finish actual selected law analysis and media pipeline'
    previous=tree(pathlib.Path(result['version']))
    # The representative proves stale-result selection and repeat version isolation end to end.
    if 'C109705' in folder.name and '400-2a' in folder.name:
     again=run(folder/'execution-manifest.json',entry['case_id'],attempt,base/(kind+'-processed'),ROOT/'runtime/main-pipeline-v3/library',ROOT/'.runtime-work/decoder-v3/.lake/build/bin/adapterCheck',owner_path)
     assert pathlib.Path(again['version']).name=='v0002' and tree(pathlib.Path(result['version']))==previous
   out=receipts/('physical002-'+key+'-'+kind+'.json');write(out,value)
   print(json.dumps({'fixture_kind':kind,'status':status,'selected_analyzer_sha256':result['analysis_revision']['analyzer_sha256'],'native_revision':result['native_revision'],'source_hashes':check['sources'],'originals_preserved':True,'diagnostic_fixture':True,'final_video_checked':bool(result['final_video_checks'])},indent=2))
   if kind=='complete_motion':life=owner.events
  fixtures.append({'kind':kind,'command':f'python3.11 work/_shared/prove_physical_v3.py --manifest work/{folder.name}/execution-manifest.json --case {entry["case_id"]}', 'exit_code':0,'log':str(log.relative_to(folder)),'log_sha256':sha(log),'result':str(out.relative_to(folder)),'result_sha256':sha(out)})
 lifecycle_log=receipts/('lifecycle002-'+key+'.log');lifecycle_log.write_text(json.dumps({'events':life,'fake_server_and_owner':True,'capture_boundary_ast':boundary_check,'assertions_passed':True,'construction_sha256':entry['construction_sha256'],'no_carla_executed':True},indent=2)+'\n')
 proof={'format':'worker-physical-preparation-v002','construction_sha256':entry['construction_sha256'],'fixtures':fixtures,'lifecycle':{'events':life,'exit_code':0,'log':str(lifecycle_log.relative_to(folder)),'log_sha256':sha(lifecycle_log)},'software_fixture_only':True,'physical_acceptance_claimed':False,'analysis_entrypoint':entry['measurement_procedure']['entrypoint'],'runtime_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),'proof_driver_sha256':sha(pathlib.Path(__file__)),'fixture_author_sha256':sha(ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/physical_assessment002.py'),'native_fixture_author_sha256':sha(ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver/native_fixture_sources002.py'),'diagnostic_graph_authors':{name:sha(ROOT/'work/testing__C125714__NRS-484B-250-1__motor_vehicle_driver'/('native_'+name+'_fixture002.py')) for name in ('speed_sign','signal','indicator','visibility')}}
 out=receipts/('physical002-'+key+'.json');write(out,proof);entry['physical_preparation']={'receipt':str(out.relative_to(folder)),'sha256':sha(out)}
 return entry

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--case');p.add_argument('--kind');a=p.parse_args();runtime=activate();path=pathlib.Path(a.manifest);folder=path.resolve().parent;m=read(path)
 # --kind is a reproducible selection; aggregate proof always covers all required outcomes.
 for i,e in enumerate(m['cases']):
  if a.case and e['case_id']!=a.case:continue
  m['cases'][i]=prove_entry(folder,e,runtime);write(path,m);print(e['case_id'],'physical preparation passed')
if __name__=='__main__':main()
