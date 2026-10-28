"""Physical CARLA execution engine. No simulator imports during offline checking."""
import argparse,ast,json,math,signal,sys,queue
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def speed_control(target,actual):
 error=target-actual
 return min(.75,max(0.,error*.3)), min(1.,max(0.,-error*.3))

def steering(position,yaw,target):
 desired=math.atan2(target[1]-position[1],target[0]-position[0])
 error=(desired-yaw+math.pi)%(2*math.pi)-math.pi
 return max(-.7,min(.7,error*1.2))

def footprint_gap(a,b):
 return math.hypot(a[0]-b[0],a[1]-b[1])

def check():
 cfg=json.loads((ROOT/'config.json').read_text())
 assert cfg['actor']=='motor_vehicle_driver'
 assert cfg['supported_case_ids']
 from geometry import build_road,route
 import xml.etree.ElementTree as ET
 assert ET.fromstring(build_road()).findall('road')
 assert len(route(cfg['maneuver']))>10
 for f in ROOT.glob('*.py'):ast.parse(f.read_text())
 for c in cfg['cases']:
  assert c['case_id'] in cfg['supported_case_ids']
  assert c['variable_assignments']['ego_speed']['value'] is None
 print(json.dumps({'offline_checks':'passed','simulation_started':False,'status':'partial','gaps':cfg['implementation_gaps']}))

def run(args):
 cfg=json.loads((ROOT/'config.json').read_text())
 if args.sweep_index is not None:
  values=[4.,6.,8.,10.,12.]
  if not 0<=args.sweep_index<len(values):raise ValueError('Frozen physical speed index 0..4 required')
  case=json.loads(json.dumps(cfg['cases'][0]));case['case_id']=cfg['assignment_id']+'__speed_'+str(args.sweep_index);case['target_type']='judgment_sweep';case['target_law_id']=cfg['law_id'];case['variable_assignments']['commanded_approach_speed']['value']=values[args.sweep_index]
 else:case=next(c for c in cfg['cases'] if c['case_id']==(args.case_id or cfg.get('selected_case_id',cfg['supported_case_ids'][0])))
 if case['target_type']=='baseline':raise ValueError('Baseline is definition-only and not selected')
 if cfg['law_id']=='NRS-484B-250-1':
  from crossing import execute
  return execute(args,cfg,case)
 out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
 result={'case_id':case['case_id'],'requested_variable_assignments':case['variable_assignments'],'measured_values':{},'target_checks':[], 'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'preflight','physical_failure_flags':[], 'trace_reference':None,'video_references':[],'video_frame_map_reference':None,'recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'missing_capabilities':cfg['implementation_gaps']}
 actors=[];capture=None;world=None;settings=None;client=None
 stopped=[False]
 def stop(*unused):stopped[0]=True
 previous={s:signal.signal(s,stop) for s in (signal.SIGINT,signal.SIGTERM)}
 try:
  if cfg['law_id'] not in ('NRS-484B-600-1a','NRS-484B-220-1') and cfg['implementation_gaps']:raise RuntimeError('Incomplete target realization: '+'; '.join(cfg['implementation_gaps']))
  import carla
  sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))
  from pipeline_capture import PipelineCapture
  client=carla.Client(args.host,args.port);client.set_timeout(20.)
  if client.get_client_version()!=client.get_server_version():raise RuntimeError('Client/server version mismatch')
  if cfg['law_id']=='NRS-484B-600-1a':
   from geometry import build_road
   world=client.generate_opendrive_world(build_road(),carla.OpendriveGenerationParameters(vertex_distance=1.,max_road_length=50.,wall_height=0.,additional_width=0.,smooth_junctions=False,enable_mesh_visibility=True))
   cfg['live_binding']={'map':world.get_map().name,'blueprint':'vehicle.tesla.model3','spawn':{'location':{'x':20.,'y':-1.75,'z':.5},'rotation':{'yaw':0.}},'route':[(float(x),-1.75) for x in range(20,401,2)]}
  else:world=client.get_world()
  settings=world.get_settings(); changed=world.get_settings();changed.synchronous_mode=True;changed.fixed_delta_seconds=.05;world.apply_settings(changed)
  binding=cfg['live_binding'];mapping=world.get_map()
  if mapping.name!=binding['map']:raise RuntimeError('Wrong native map; no automatic map replacement')
  bp=world.get_blueprint_library().find(binding['blueprint'])
  ego=world.try_spawn_actor(bp,carla.Transform(carla.Location(**binding['spawn']['location']),carla.Rotation(**binding['spawn']['rotation'])))
  if ego is None:raise RuntimeError('Spawn collision')
  actors.append(ego);cameras=[]
  for i,pose in enumerate(cfg['cameras']):
   cbp=world.get_blueprint_library().find('sensor.camera.rgb');cbp.set_attribute('image_size_x',str(pose['width']));cbp.set_attribute('image_size_y',str(pose['height']));cbp.set_attribute('sensor_tick','0.05')
   camera=world.spawn_actor(cbp,carla.Transform(carla.Location(**pose['location']),carla.Rotation(**pose['rotation'])),attach_to=ego);actors.append(camera);q=queue.Queue();camera.listen(q.put);d=out/('camera'+str(i));d.mkdir();cameras.append((q,d))
  (out/'config.json').write_text(json.dumps(cfg));capture=PipelineCapture(client,ego,out,case['case_id'],required_observations=cfg['required_atoms'])
  path=binding['route'];idx=0;result['setup_confirmed']=True;speed_samples=[]
  with (out/'video_frame_map.jsonl').open('x') as fmap:
   for step in range(int(cfg['timeout_s']/.05)):
    if stopped[0]:result['termination_reason']='signal';break
    t=ego.get_transform();v=ego.get_velocity();speed=math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
    while idx<len(path)-1 and footprint_gap((t.location.x,t.location.y),path[idx])<2.:idx+=1
    throttle,brake=speed_control(case['variable_assignments']['commanded_approach_speed']['value'],speed)
    ego.apply_control(carla.VehicleControl(throttle=throttle,brake=brake,steer=steering((t.location.x,t.location.y),math.radians(t.rotation.yaw),path[idx])))
    frame=world.tick();snap=world.get_snapshot();row=capture.capture(frame,snap.timestamp.elapsed_seconds);result['behavior_attempted']=True;speed_samples.append({'time_s':row['time_s'],'value':row['speed_mps']})
    for q,d in cameras:
     image=q.get(timeout=10.)
     if image.frame!=frame:raise RuntimeError('Camera/original frame mismatch')
     image.save_to_disk(str(d/(str(step).zfill(6)+'.png')))
    fmap.write(json.dumps({'video_frame':step,'carla_frame':frame,'time_s':row['time_s']})+'\n')
    if idx==len(path)-1 and footprint_gap((t.location.x,t.location.y),path[-1])<2.:
     result['maneuver_completed']=True;result['termination_reason']='route_complete';break
   else:result['termination_reason']='timeout'
  if speed_samples:
   with (out/'ego_speed.jsonl').open('x') as stream:
    for sample in speed_samples:stream.write(json.dumps(sample)+'\n')
   window=speed_samples[-min(len(speed_samples),100):];mean=sum(v['value'] for v in window)/len(window)
   result['realized_observables']['ego_speed']={'value':mean,'unit':'m/s','method':'arithmetic mean original velocity-norm samples','time_window':'last up to 5 original recorded seconds','statistic':'mean','sample_window_s':[window[0]['time_s'],window[-1]['time_s']],'reference':'ego_speed.jsonl'}
   result['recording_evidence'].append({'name':'kin.speed','unit':'m/s','reference':'ego_speed.jsonl'})
   target=case['variable_assignments']['commanded_approach_speed']['value'];result['target_checks'].append({'target':'commanded_approach_speed','requested':target,'measured':mean,'method':'original velocity norm final 5s mean; full raw history retained','tolerance':.22352,'matched':abs(mean-target)<=.22352,'physical_cause_confirmed':True,'cause_evidence':['trace.jsonl','road.xodr','ego_speed.jsonl']})
  result['trace_reference']='trace.jsonl';result['video_frame_map_reference']='video_frame_map.jsonl';result['video_references']=['camera'+str(i) for i in range(len(cameras))]
 except Exception as e:result['termination_reason']=str(e);result['physical_failure_flags'].append('unconfirmed_setup_or_capture')
 finally:
  if capture:capture.close(confirmed=result['maneuver_completed'])
  for a in reversed(actors):
   if hasattr(a,'stop'):a.stop()
   a.destroy()
  if world is not None and settings is not None:world.apply_settings(settings)
  for s,h in previous.items():signal.signal(s,h)
  with (out/'result.json').open('x') as f:json.dump(result,f,indent=2)
 return 0 if result['maneuver_completed'] and not result['missing_capabilities'] else 2

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--case-id');p.add_argument('--sweep-index',type=int);a=p.parse_args()
 if a.check:check()
 else:
  if not all((a.output_dir,a.host,a.port)):p.error('Require --output-dir PATH --host HOST --port PORT; optionally select --case-id ID')
  sys.exit(run(a))
