"""900-frame exact-v6 saved-only SOFTWARE diagnostic; never capture or replay.

The compact flat-color diagnostic video is a frame-count/codec stand-in, not
actual camera pixels or evidence of physical visibility/acceptance. All Native-
style records are authored before the source inventory is frozen for processing.
"""
import argparse,copy,hashlib,json,math,pickle,shutil,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
CASE_ID='testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__selected_left_turn'
NATIVE_SHA='f1c4c4d8443a735a4800a7ca4cd7c88db18174ec75768f86ee4551079cfcca9b'
def read(p):return json.loads(Path(p).read_text())
def write(p,v):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lines(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s]
def jsonl(p,rows):Path(p).write_text(''.join(json.dumps(r)+'\n' for r in rows))
def box(x,y):return [[x+dx,y+dy,z] for z in (0.,1.5) for dx,dy in ((-2.,-.8),(-2.,.8),(2.,.8),(2.,-.8))]
def activate():
 sys.path.insert(0,str(ROOT/'work/_shared'));import runtime002
 r=runtime002.prepare_runtime();runtime002.activate_runtime(ROOT,r);return r

def motion_sources(attempt,complete=True):
 geometry={'approach_road_id':1,'connector_road_id':13,'departure_road_id':4,'approach_direction_xy':[1,0],
  'approach_centerline_point_xy':[-7,0],'departure_direction_xy':[0,-1],'departure_centerline_point_xy':[0,-7],
  'intersection_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'two_way':True,
  'source':'Explicitly authored900-frame software diagnostic using original v6 source keys',
  'public_highway_designation':'Authored diagnostic context; no actual legal designation asserted',
  'route_waypoints_native_xy':[[-80,-1.75],[-7,-1.75],[-2,-2],[1.75,-12],[1.75,-80]]}
 body=[];trace=[];mapping=[]
 for i in range(900):
  if not complete:x,y,road,vx,vy,heading=-80.,-1.75,1,0.,0.,0.
  elif i<300:x,y,road,vx,vy,heading=-80+i*.24,-1.75,1,4.8,0.,0.
  elif i<600:
   a=(i-300)/299*math.pi/2;x=-7+8.75*math.sin(a);y=-1.75-5.25*(1-math.cos(a));road=13;vx=4.8*math.cos(a);vy=-4.8*math.sin(a);heading=-math.degrees(a)
  else:x,y,road,vx,vy,heading=1.75,-7-(i-600)*.24,4,0.,-4.8,-90.
  f=21714+i;t=(i+1)/20
  body.append({'frame':f,'time_s':t,'road_id':road,'lane_id':-1,'body_vertices_m':box(x,y),
               'control':{'nearest_route_index':min(i,99),'requested_mps':5.,'control':{'throttle':.25 if complete else 0.,'brake':0. if complete else 1.,'steer':0.}},'camera_originals':{}})
  trace.append({'frame':f,'time_s':t,'position':{'x':x,'y':y,'z':0.},'position_m':[x,y,0.],
                'heading_deg':heading,'speed_mps':math.hypot(vx,vy),'speed_mph':math.hypot(vx,vy)/.44704,'velocity_mps':[vx,vy,0.],
                'control':body[-1]['control']['control'],'wheel_steer_angle_deg':0.,'accel_longitudinal_mps2':0.})
  mapping.append({'video_frame':i,'carla_frame':f,'native_frame':f,'time_s':t})
 write(attempt/'road_geometry.json',geometry);jsonl(attempt/'body_history.jsonl',body);jsonl(attempt/'video_frames.jsonl',mapping);jsonl(attempt/'trace.jsonl',trace)
 return geometry,body,trace,mapping

def stamp(value,frame,time):
 if isinstance(value,dict):
  for k,v in list(value.items()):
   if k in ('frame','original_frame','native_frame','replay_frame') and isinstance(v,int):value[k]=frame
   elif k in ('time_s','recording_time_s') and isinstance(v,(int,float)):value[k]=time
   elif k in ('simulation_time','replay_simulation_time_s') and isinstance(v,(int,float)):value[k]=time+16.273379929363728
   else:stamp(v,frame,time)
 elif isinstance(value,list):
  for v in value:stamp(v,frame,time)

def author(attempt):
 from traffic_spec_adapter.adapter import load_graph
 base=ROOT/'runtime/main-pipeline-v1/fixtures/retained-speed';shutil.copytree(base,attempt)
 # Keep the genuine frozen config bytes; the old Native constructor is an
 # explicitly different diagnostic object, never a forged historical preimage.
 shutil.copyfile(HERE/'config.json',attempt/'config.json');cfg=read(attempt/'config.json')
 write(attempt/'case.json',cfg['case'])
 native={'case_id':CASE_ID,'cell_id':'C109705','actor':'motor_vehicle_driver','entrypoint':'runner.py',
  'files':[{'path':'analyze.py','content':"raise RuntimeError('STALE ANALYZER MUST NOT RUN')\n"}],
  'diagnostic_original_constructor':True,'expected_real_native_sha256':NATIVE_SHA}
 write(attempt/'construction.json',native);(attempt/'analyze.py').write_text(native['files'][0]['content']);(attempt/'runner.py').write_text("raise RuntimeError('No Native execution is permitted')\n")
 geometry,body,trace,mapping=motion_sources(attempt)
 scene=ROOT/'references/v6-capability/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/scene.xodr'
 shutil.copyfile(scene,attempt/'scene.xodr');shutil.copyfile(scene,attempt/'road.xodr')
 if (attempt/'raw.mkv').exists():(attempt/'raw.mkv').unlink()
 subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=gray:s=640x360:r=20','-frames:v','900','-threads','1','-c:v','ffv1',str(attempt/'raw.mkv')],check=True)
 # Copy the pinned diagnostic source shapes and author all frame identities and
 # subject motion consistently before any saved processing starts.
 template_trace=lines(base/'trace.jsonl')[0];template_evidence=lines(base/'capture/evidence.jsonl')[0]
 template_graph=load_graph(base/'capture/native/graphs/base/00021714.pkl')
 events=[];indices=[];expanded_trace=[]
 surface=read(attempt/'surface_provenance.json');surface['map_sha256']=sha(attempt/'road.xodr');surface['authored_map_sha256']=surface['map_sha256'];write(attempt/'surface_provenance.json',surface)
 relocation=read(attempt/'asset_relocations.json');relocation['surface_provenance_sha256']=sha(attempt/'surface_provenance.json');write(attempt/'asset_relocations.json',relocation)
 for row,b in zip(trace,body):
  f,t=row['frame'],row['time_s'];tr=copy.deepcopy(template_trace);stamp(tr,f,t);tr.update(row)
  def surface_hash(v):
   if isinstance(v,dict):
    if 'surface_sha256' in v:v['surface_sha256']=sha(attempt/'surface_provenance.json')
    for x in v.values():surface_hash(x)
   elif isinstance(v,list):
    for x in v:surface_hash(x)
  surface_hash(tr)
  event=copy.deepcopy(template_evidence);stamp(event,f,t);event.update(original_frame=f,replay_frame=f,recording_time_s=t,replay_simulation_time_s=t+16.273379929363728)
  event['ego'].update(position_m=row['position_m'],heading_deg=row['heading_deg'],speed_mps=row['speed_mps'],body_vertices_m=b['body_vertices_m'])
  observed=event['original_observations'];observed.setdefault('map_context',{})['declared_public_way_road_ids']=cfg['public_way_road_ids']
  event['world']['road_projection'].update(road_id=b['road_id'],lane_id=-1)
  for participant in observed.get('participants',[]):
   if participant['actor_id']==event['actor_id']:participant.update(position_m=row['position_m'],heading_deg=row['heading_deg'],speed_mps=row['speed_mps'],velocity_mps=row['velocity_mps'],body_vertices_m=b['body_vertices_m'])
  graph=copy.deepcopy(template_graph);stamp(graph.graph,f,t);graph.graph['frame']=f;graph.graph['observed_evidence']=copy.deepcopy(observed)
  if 'ego' in graph:
   graph.nodes['ego'].update(vertex=row['position_m'],carla_id=event['actor_id'],entity_id=event['actor_id'],velocity=row['velocity_mps'],speed=row['speed_mps'])
  relative='graphs/base/%08d.pkl'%f;path=attempt/'capture/native'/relative;path.parent.mkdir(parents=True,exist_ok=True)
  with path.open('wb') as stream:pickle.dump(graph,stream)
  indices.append({'frame':f,'simulation_time':t+16.273379929363728,'base':relative,'abstract':'graphs/abstract/00021714.pkl','nodes':len(graph),'edges':graph.number_of_edges(),'diagnostic_fixture':True})
  events.append(event);expanded_trace.append(tr)
 synchronized=[]
 template_sync=lines(base/'synchronized_motion_records.jsonl')[0]
 for row,event in zip(expanded_trace,events):
  record=copy.deepcopy(template_sync);stamp(record,row['frame'],row['time_s'])
  value=record['value']
  for key in list(value):
   if isinstance(value[key],dict) and 'actor_id' in value[key]:del value[key]
  for participant in event['original_observations']['participants']:
   role='ego' if participant['actor_id']==event['actor_id'] else 'other_'+str(participant['actor_id'])
   value[role]=copy.deepcopy(participant)
  # Keep the trace's duplicate Native participant packet coherent with the
  # dedicated synchronized source, before freezing original diagnostics.
  row['speed_comparison_native']=copy.deepcopy(value)
  synchronized.append(record)
 jsonl(attempt/'synchronized_motion_records.jsonl',synchronized)
 jsonl(attempt/'trace.jsonl',expanded_trace);jsonl(attempt/'capture/evidence.jsonl',events);jsonl(attempt/'capture/native/frames.jsonl',indices)
 capture=read(attempt/'capture/manifest.json');capture.update(case_id=CASE_ID,frames=900,source_run='explicit-legacy003-software-diagnostic900',required_observations=cfg['required_atoms'])
 for name in capture['sources']:
  if (attempt/name).is_file():capture['sources'][name]=sha(attempt/name)
 write(attempt/'capture/manifest.json',capture)
 write(attempt/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':True,'acquisition_mode':'explicit_software_authored_legacy_v6_schema','actual_recording_audited':False,'video_scope':'640x360 flat-color900-frame codec stand-in; no actual camera pixels or visibility proof'})
 write(attempt/'native-run-status.json',{'frames':900,'errors':[],'restoration':{'restored':True,'software_fixture_only':True}})
 write(attempt/'result.json',{'case_id':CASE_ID,'maneuver_completed':False,'legacy_original_result_must_be_preserved':True})
 return {'native_construction_sha256':sha(attempt/'construction.json'),'frozen_native_construction_sha256':NATIVE_SHA,'hash_matches':sha(attempt/'construction.json')==NATIVE_SHA,'explicit_diagnostic_exception':True,'frames':900}

def main():
 p=argparse.ArgumentParser();p.add_argument('--unit',action='store_true');a=p.parse_args();runtime=activate();sys.path.insert(0,str(HERE))
 if a.unit:
  import unittest
  result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE/'tests')));raise SystemExit(not result.wasSuccessful())
 from worker_exchange.saved_processing import run,acknowledge_owner_release
 from worker_exchange.common import tree
 from build_package import main as build
 build(sha(runtime/'SOURCE-MANIFEST.json'))
 folder=ROOT/'.runtime-work/legacy003'/uuid.uuid4().hex[:12];folder.mkdir(parents=True);attempt=folder/'attempt';authored=author(attempt)
 owner=folder/'owner-release.json';acknowledge_owner_release(attempt,owner,True)
 before=tree(attempt);output=folder/'processed';library=ROOT/'runtime/main-pipeline-v1/library';validator=ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck'
 command=['.venv-cpu/bin/python','work/_shared/runtime002.py','runtime.py','process-saved','--manifest',str((HERE/'execution-manifest.json').relative_to(ROOT)),'--case',CASE_ID,'--attempt',str(attempt.relative_to(ROOT)),'--output',str(output.relative_to(ROOT)),'--library',str(library.relative_to(ROOT)),'--validator',str(validator.relative_to(ROOT)),'--owner-release-receipt',str(owner.relative_to(ROOT))]
 print('900-frame synthetic saved-only command:', ' '.join(command),flush=True)
 completed=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);print(completed.stdout.replace(str(ROOT),'.'),flush=True);assert completed.returncode==0,completed.stdout
 first=read(output/'v0001/processing.json');result=read(Path(first['result']))
 assert first['case_id']==CASE_ID and first['timestamp_joins']['frames']==900 and first['final_video_checks']['frames']==900
 assert result['physical_checks']['maneuver']['status']=='met' and result['maneuver_completed'] is True
 assert result['provenance_kind']=='native' and result['diagnostic_fixture'] is True and result['realized_observables']
 assert tree(attempt)==before and authored['hash_matches'] is False
 prior=tree(output/'v0001');second=run(HERE/'execution-manifest.json',CASE_ID,attempt,output,library,validator,owner)
 assert Path(second['version']).name=='v0002' and tree(output/'v0001')==prior and tree(attempt)==before
 negatives=[]
 tests=[('renamed_v7_case',CASE_ID.replace('selected_left_turn','near_centerline'),None),('wrong_manifest',CASE_ID,{'kind':'manifest'}),('wrong_embedded_case',CASE_ID,{'kind':'embedded'}),('non_diagnostic_wrong_native_hash',CASE_ID,{'kind':'native_hash'})]
 for name,cid,change in tests:
  target=attempt;manifest=HERE/'execution-manifest.json';owner_path=owner
  if change and change['kind']=='manifest':
   value=read(manifest);value['cases'][0]['case_id']=CASE_ID.replace('selected_left_turn','near_centerline');manifest=folder/'wrong-manifest.json';write(manifest,value)
  elif change:
   target=folder/name;shutil.copytree(attempt,target)
   if change['kind']=='embedded':
    value=read(target/'config.json');value['case']['case_id']=CASE_ID.replace('selected_left_turn','near_centerline');write(target/'config.json',value)
   else:(target/'acquisition-provenance.json').unlink()
   owner_path=folder/(name+'-owner.json');acknowledge_owner_release(target,owner_path,True)
  try:run(manifest,cid,target,folder/(name+'-output'),library,validator,owner_path)
  except Exception as error:negatives.append({'test':name,'rejected':True,'error_type':type(error).__name__,'reason':str(error).replace(str(ROOT),'.') or type(error).__name__});print('EXPECTED REJECTION',name,type(error).__name__,str(error).replace(str(ROOT),'.'),flush=True)
  else:raise AssertionError('Wrong legacy selection accepted: '+name)
 assert tree(attempt)==before
 summary={'format':'worker-legacy-diagnostic-v1','case_id':CASE_ID,'frames':900,'exit_code':0,'software_fixture_only':True,'actual_recording_audited':False,'native_replay_requested':False,'synthetic_native_binding':authored,
  'processing_command':' '.join(command),'first_version':'v0001','second_version':'v0002','originals_preserved':True,'prior_outputs_preserved':True,'selected_analyzer_sha256':sha(HERE/'analyze.py'),'construction_sha256':sha(HERE/'construction.json'),'runtime_manifest_sha256':sha(runtime/'SOURCE-MANIFEST.json'),
  'physical_maneuver_status':result['physical_checks']['maneuver']['status'],'result_sha256':sha(Path(first['result'])),'final_video_frames':first['final_video_checks']['frames'],'negatives':negatives}
 write(HERE/'receipts/diagnostic900.json',summary)
 print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
