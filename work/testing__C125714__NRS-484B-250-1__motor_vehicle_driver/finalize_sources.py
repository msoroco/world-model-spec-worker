"""Join synthetic law packets to original retained fixture frames; fix Native cleanup-source access."""
import copy,importlib.util,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('b',ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids'];ids += [r['assignment_id'] for r in json.loads((ROOT/'work'/ids[0]/'additional-bindings.json').read_text())]
frames=[21714,21715,21716];times=[.05000000074505806,.10000000149011612,.15000000223517418]
for aid in ids:
 folder=ROOT/'work'/aid;spec=json.loads((folder/'package-spec.json').read_text());ap=ROOT/'inputs'/aid/'assignment.json'
 if not ap.exists():ap=folder/'assignment.json'
 a=json.loads(ap.read_text());law=a['law_id'];changed=False
 if law.startswith('NRS-484B-250'):
  for c in spec['cases']:
   p=c['fixture']['case_observation.json'];kind=c['name'];ego=0 if kind=='other_later' else 1 if kind in ['advance'] else 2;other=2 if kind=='other_later' else 0
   p['entry_events']={'ego':{'frame':frames[ego],'time_s':times[ego]},'other':{'frame':frames[other],'time_s':times[other]}}
   p['ego_clearance_frame']=21716;p['other_clearance_frame']=21716 if other==2 else 21715;p['other_clearance_time_s']=times[2] if other==2 else times[1]
  changed=True
 if law=='NRS-484B-413-2':
  for c in spec['cases']:
   p=c['fixture']['case_observation.json'];threshold=p.get('threshold_ft',100)*.3048;short='short' in c['name'];interrupted=c['config'].get('interrupt_signal',False)
   p['path_rows']=[{'x_m':-threshold-10,'y_m':-1.75},{'x_m':-threshold,'y_m':-1.75},{'x_m':0,'y_m':-1.75}];bits=[0,0 if short else 1,0 if interrupted else 1]
   p['indicator_rows']=[dict(frame=frame,lamp_bits=bit,pixel_luminance=80 if bit else 20) for frame,bit in zip(frames,bits)];p['turn_onset_frame']=21716
  spec['analysis']=spec['analysis'].replace("if remaining>=p.get('threshold_ft',100)*.3048:\n            start=min(start+1,len(rows)-1);break", "if remaining>=p.get('threshold_ft',100)*.3048:\n            if remaining>p.get('threshold_ft',100)*.3048:start=min(start+1,len(rows)-1)\n            break")
  changed=True
 if law=='NRS-484B-600-1a':
  run=spec['runner'].replace("'native_map_name':world.get_map().name", "'native_map_name':mapping.name").replace("str(world.get_weather().wetness)", "str(traffic[-1]['weather']['wetness'])")
  run=run.replace('get_waypoint_xodr(1,1,cfg.get("other_station_m",1100))','get_waypoint_xodr(1,1,cfg.get("other_station_m",250))')
  run=run.replace("if name == 'overview': pose = carla.Transform(carla.Location(x=0,y=0,z=80),carla.Rotation(pitch=-90))", "if name == 'overview': pose = carla.Transform(carla.Location(x=150,y=0,z=220),carla.Rotation(pitch=-90))")
  run=run.replace('x=500,y=-15,z=45','x=150,y=-15,z=45').replace("attach_to=ego if name in ('overview','approach','driver_reference') else None", "attach_to=ego if name in ('approach','driver_reference') else None")
  run=run.replace("'weather':fields(world.get_weather())", "'traffic_actor_inventory':[{'id':actor.id,'type_id':actor.type_id,'position_m':[actor.get_location().x,actor.get_location().y,actor.get_location().z]} for actor in world.get_actors() if actor.type_id.startswith(('vehicle.','walker.'))],'weather':fields(world.get_weather())")
  run=run.replace("'surface':'authored synthetic asphalt; Native wetness '", "'traffic_actor_inventory_by_frame':[{'frame':t['frame'],'actors':t['traffic_actor_inventory']} for t in traffic],'surface':'authored synthetic asphalt; Native wetness '")
  spec['analysis']=spec['analysis'].replace("'original_frames':[r['frame'] for r in rows]", "'original_frames':[r['frame'] for r in rows],'traffic_actor_inventory_by_frame':p.get('traffic_actor_inventory_by_frame',[]),'traffic_definition_not_exhausted_by_vehicle_inventory':True")
  for c in spec['cases']:
   if 'other_station_m' in c['config']:c['config']['other_station_m']=180
   cams=copy.deepcopy(json.loads((ROOT/'references/v6-capability'/aid/'config.json').read_text())['cameras']);cams[0]['pose_strategy']='Fixed overhead at Native world(150,0,220), pitch-90; both traffic routes across full45s';cams[2]['pose_strategy']='Fixed roadside at Native world(150,-15,45), pitch-65 toward interaction corridor';c['config']['cameras']=cams
   c['fixture']['case_observation.json']['traffic_actor_inventory_by_frame']=[{'frame':f,'actors':[{'id':1,'type_id':'vehicle.lincoln.mkz_2020'},{'id':2,'type_id':'vehicle.tesla.model3'}]} for f in frames]
  spec['runner']=run;changed=True
 if not changed:continue
 b.write(folder/'package-spec.json',spec);b.build(spec)
 plan=json.loads((folder/'case-plan.json').read_text())
 if not (ROOT/'inputs'/aid/'assignment.json').exists():
  for m in plan['source_observation_mapping'].values():m['source_refs']=[str(ap.relative_to(ROOT))]
 b.write(folder/'case-plan.json',plan);shutil.copyfile(folder/'comparison-audits.json',folder/'comparison-audit-specs.json')
 print('source-joined',aid)
