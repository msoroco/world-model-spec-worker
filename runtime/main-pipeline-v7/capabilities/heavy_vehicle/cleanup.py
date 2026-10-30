"""Owned-scene teardown barriers and fresh-client baseline restoration, CARLA0.9.15."""
import hashlib,json,time

def restore(carla,client,world,owned,previous,weather,prior_path,prior_xml,host,port,directory):
 def event(stage,**values):
  with (directory/'cleanup-progress-v3.jsonl').open('a') as f:f.write(json.dumps(dict(at=time.time(),stage=stage,**values),allow_nan=False)+'\n')
 ids={a.id for a in owned};event('stop_all_owned_sensor_callbacks',owned_actor_ids=sorted(ids))
 for a in owned:
  if a.type_id.startswith('sensor.') and a.is_listening:a.stop()
 event('batch_destroy_owned_actors')
 order=sorted(owned,key=lambda a:not a.type_id.startswith('sensor.'))
 fresh_destroy=carla.Client(host,port,2);fresh_destroy.set_timeout(30)
 responses=fresh_destroy.apply_batch_sync([carla.command.DestroyActor(a.id) for a in order],False)
 if any(r.has_error() for r in responses):raise RuntimeError('Owned actor batch destruction failed: '+str([r.error for r in responses if r.has_error()]))
 for _ in range(2):world.tick()
 remaining=[{'id':a.id,'type':a.type_id} for a in world.get_actors() if a.id in ids or a.type_id.startswith(('vehicle.','walker.','sensor.'))]
 if remaining:raise RuntimeError('Native dynamic actors remain after teardown barrier: '+str(remaining))
 event('native_actor_absence_confirmed',remaining=remaining)
 world.apply_settings(previous)
 first=world.wait_for_tick(30);second=world.wait_for_tick(30)
 if not second.frame>first.frame:raise RuntimeError('No native asynchronous frame advance before map restoration')
 event('native_async_frames_confirmed',frames=[first.frame,second.frame])
 fresh=carla.Client(host,port,2);fresh.set_timeout(180)
 event('load_prior_native_map_with_settings_preserved',native_map_path=prior_path)
 restored=fresh.load_world(prior_path,False)
 restored.set_weather(weather);restored.apply_settings(previous)
 actual=hashlib.sha256(restored.get_map().to_opendrive().encode()).hexdigest();expected=hashlib.sha256(prior_xml.encode()).hexdigest()
 if actual!=expected:raise RuntimeError('Prior native map hash mismatch')
 for observed,target in [(restored.get_settings(),previous),(restored.get_weather(),weather)]:
  for k in dir(target):
   if k.startswith('_'):continue
   v=getattr(target,k)
   if not isinstance(v,(bool,int,float,type(None))):continue
   got=getattr(observed,k)
   if isinstance(v,(int,float)) and not isinstance(v,bool):
    if abs(got-v)>1e-5:raise RuntimeError('Prior native settings/weather mismatch: '+k)
   elif got!=v:raise RuntimeError('Prior native settings/weather mismatch: '+k)
 event('prior_native_baseline_verified',map_sha256=actual)
 return {'restored':True,'previous_map_name':restored.get_map().name,'previous_map_sha256':actual,'settings_and_weather_verified':True,'restoration_method':'sensor stop, ordered batch destruction, native absence and asynchronous-frame barriers; fresh bounded client native-map reload preserving settings','cleanup_implementation':'cleanup_v3.py'}
