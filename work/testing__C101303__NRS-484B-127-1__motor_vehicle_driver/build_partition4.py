import json,pathlib,sys,importlib.util,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
BP=ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py'
s=importlib.util.spec_from_file_location('builder',BP);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
IDS=json.loads((ROOT/'partitions/demo-test-04.json').read_text())['assignment_ids']
TOPICS=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws']
def dump(x):return json.dumps(x,indent=2)+'\n'
def lines(x):return ''.join(json.dumps(y)+'\n' for y in x)
def base(aid):
 a=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text());seed=ROOT/'references/v6-capability'/aid
 return dict(assignment_id=aid,runner=(seed/'runner.py').read_text(),analysis=(seed/'analyze.py').read_text(),dispositions=[],cases=[],comparisons=[],branches=[],negative={},measurement_plan='Original synchronized law-specific measurements; diagnostic fixtures establish software compatibility only.',static_checks=['Connected road topology','Case-specific controller inputs','Four cameras at 20Hz','Saved-only original acquisition processing'],mechanisms=['Native physics and original same-tick capture','Source-hashed saved finalization'],limitations=['Native motion, actual pixels and adequate full duration require GPU review.','Statutory reasonableness, authority and physical acceptance remain unconfirmed.'],observation_mapping={},audits=['Review all original four-camera pixels for full approach and clearance','Check measured target contrast with fixed route and context','Separate engineering samples from legal judgment'],test='')
def disposition(spec,req,method,key,inputs):
 spec['dispositions'].append(dict(requirement=req,source=TOPICS[json.loads((ROOT/'inputs'/spec['assignment_id']/'assignment.json').read_text())['law_id']]['law']['source'],evidence_or_gap='Original source measurements; physical/legal outcome retained as separate limitation',measurement=dict(method=method,output_key=key,inputs=inputs,kind='measured',value_type='object')))
def branch(spec,name,names,diffs):
 aid=spec['assignment_id'];law=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())['law_id']
 spec['comparisons'].append(dict(comparison_id=name,cases=names,fixed_conditions=['Original catalog layout, maneuver, control, actor','Camera profile, 45-second duration, route and all other controller inputs'],deliberate_differences=diffs))
 spec['branches'].append(dict(name=name,topic_ids=list(TOPICS[law]['topics']),cases=names,comparison_ids=[name]))
def test_source(method,body):
 return 'import unittest,tempfile,pathlib,json,sys\nsys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))\nimport analyze\nclass TestMeasurement(unittest.TestCase):\n def test_exact_measurement(self):\n'+''.join('  '+line+'\n' for line in body.splitlines())
def speed(aid,posted=False):
 spec=base(aid);seed=ROOT/'references/v6-capability'/aid
 spec['runner']=spec['runner'].replace("    finalize(out,out/'analysis-report.json')", "    (out/'speed_samples.jsonl').write_text((out/'trace.jsonl').read_text())\n    finalize(out,out/'analysis-report.json')")
 spec['analysis']=spec['analysis'].replace("required(root, 'trace.jsonl').read_text().splitlines() if s", "required(root, 'speed_samples.jsonl').read_text().splitlines() if s",1).replace("'sources': {'trace.jsonl': hashlib.sha256(required(root, 'trace.jsonl').read_bytes()).hexdigest()}","'sources': {'speed_samples.jsonl': hashlib.sha256(required(root, 'speed_samples.jsonl').read_bytes()).hexdigest()}")
 key='posted_zone_speed_history' if posted else 'original_speed_history';context='posted_sign_context' if posted else 'highway_context';method='posted_sign_context' if posted else 'highway_context';filename='posted_speed_context.json' if posted else 'alley_context.json'
 disposition(spec,'Retain exact original speeds and strict greater-than rate comparison, without legal tolerance or minimum duration.','speed_history',key,['speed_samples.jsonl'])
 disposition(spec,'Establish qualifying operation and source context for the actual highway portion.',method,context,[filename,'capture/evidence.jsonl'] if posted else [filename])
 limit=30 if posted else 80
 for name,mph in [('below',limit-1),('equal',limit),('above',limit+1)]:
  trace=[dict(frame=21714+i,time_s=.05*(i+1),position_m=[300+i,1.75,0],speed_mps=mph*.44704,velocity_mps=[mph*.44704,0,0]) for i in range(3)]
  ctx=dict(designation_source='Synthetic diagnostic public-way assumption; no actual legal status established',road_geometry_source='scene.xodr and original road.xodr',authority_source='synthetic authority context, requires independent source review',posted_limit_mph=30,sign_station_m=200,native_landmarks=[])
  spec['cases'].append(dict(name=name,rationale=f'Measure {mph} mph relative to {limit} mph with exact strict comparison; no physical result asserted.',config=dict(requested_speed_mps=mph*.44704),variable_assignments=dict(requested_speed_mps=dict(kind='controller',value=mph*.44704,unit='m/s')),fixture={'speed_samples.jsonl':lines(trace),filename:ctx}))
 branch(spec,'strict_rate_boundary',['below','equal','above'],['Requested original measured rate only, below/equal/above statutory rate'])
 spec['negative']=dict(remove=['speed_samples.jsonl'],error_contains='Missing required source: speed_samples.jsonl')
 spec['test']=test_source('speed_history',"with tempfile.TemporaryDirectory() as t:\n p=pathlib.Path(t)\n for mph in (29,30,31):\n  (p/'speed_samples.jsonl').write_text(json.dumps({'frame':1,'time_s':.05,'position_m':[300,0,0],'speed_mps':mph*.44704})+'\\n')\n  v=analyze.speed_history(p)\n  self.assertAlmostEqual(v['max_sampled_mph'],mph)\n (p/'speed_samples.jsonl').unlink()\n with self.assertRaisesRegex(ValueError,'Missing required source: speed_samples.jsonl'):analyze.speed_history(p)")
 return spec
if False: # Historical seed construction; final CLI is below.
 for aid in IDS[1:3]:
  sp=speed(aid,aid==IDS[2]);folder=b.build(sp);(folder/'package-spec.json').write_text(dump(sp));b.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')

def following():
 aid=IDS[0];sp=base(aid)
 r=sp['runner'];r=r.replace('mapping.get_waypoint_xodr(1,-1,640)',"mapping.get_waypoint_xodr(1,-1,500+cfg['requested_gap_m']+4.8)")
 r=r.replace('world.set_weather(carla.WeatherParameters.ClearNoon)',"world.set_weather(carla.WeatherParameters(wetness=cfg['wetness'],precipitation=cfg['precipitation'],sun_altitude_angle=70))")
 r=r.replace('.25*(9-lead_speed)',".25*((cfg['lead_speed_mps'] if index<cfg['lead_brake_tick'] else cfg['braked_speed_mps'])-lead_speed)").replace('.2*(lead_speed-9)',".2*(lead_speed-(cfg['lead_speed_mps'] if index<cfg['lead_brake_tick'] else cfg['braked_speed_mps']))")
 r=r.replace('ahead-140',"ahead-cfg['requested_gap_m']").replace('lead_speed+0.08*',"lead_speed+cfg['ego_speed_bias_mps']+0.08*")
 r=r.replace('index>=26*20',"index>=cfg['lane_change_tick']")
 r=r.replace("'surface':'authored dry asphalt; physical material requires Native source review','weather':'Native ClearNoon'", "'surface':cfg['surface_description'],'weather':{'wetness':cfg['wetness'],'precipitation':cfg['precipitation']}")
 # Retain actual frame-level weather and participant inventory through shared capture, rather than infer from labels.
 r=r.replace("    finalize(out,out/'analysis-report.json')", "    context['native_traffic_inventory_source']='trace.jsonl scene_actor_inventory';context['driver_context']='conventional vehicle, controller represents physical-control operation; human identity requires source review'\n    (out/'surface_context.json').write_text(json.dumps(context,indent=2)+'\\n')\n    finalize(out,out/'analysis-report.json')")
 sp['runner']=r
 disposition(sp,'Retain actual following interval, full-body separation, same-lane relation and both original speeds, without legal headway or duration threshold.','following_gap','original_following_geometry',['following_samples.jsonl'])
 disposition(sp,'Retain highway and surface context, actual weather and traffic inventory source while following.','highway_conditions','highway_condition_context',['surface_context.json'])
 variants=[('base',140,9,0,900,9,0,520),('closer',50,9,0,900,9,0,520),('faster_ego',140,9,2,900,9,0,520),('slower_lead',140,6,0,900,6,0,520),('lead_brakes',140,9,0,300,3,0,520),('wet_surface',140,9,0,900,9,80,520),('following_ends',140,9,0,900,9,0,300)]
 for name,gap,lead,bias,bt,brake,wet,change in variants:
  cfg=dict(requested_gap_m=gap,lead_speed_mps=lead,ego_speed_bias_mps=bias,lead_brake_tick=bt,braked_speed_mps=brake,wetness=wet,precipitation=wet/2,lane_change_tick=change,surface_description='authored asphalt; wetness readback '+str(wet)+'; actual material requires original source verification')
  hist=[dict(frame=21714+i,time_s=.05*(i+1),ego_speed_mps=lead+bias,lead_speed_mps=lead,along_road_body_gap_m=gap-i*bias*.05,ego_lane_id=-1 if i<2 else -2,lead_lane_id=-1,lane_change_requested=i==2,ego_body_vertices_m=[[0,0,0],[4,2,1]],lead_body_vertices_m=[[gap+4,0,0],[gap+8,2,1]]) for i in range(3)]
  ctx=dict(highway_source='diagnostic synthetic assumption, no real public status',road_geometry_source='scene.xodr crest/four lanes',surface=cfg['surface_description'],weather=dict(wetness=wet,precipitation=wet/2),native_traffic_inventory_source='trace.jsonl scene_actor_inventory')
  sp['cases'].append(dict(name=name,rationale='Controlled '+name+' following measurement before same lane-change maneuver.',config=cfg,variable_assignments=dict(requested_gap_m=dict(kind='controller',value=gap,unit='m')),fixture={'following_samples.jsonl':lines(hist),'surface_context.json':ctx}))
 for name,other,diff in [('gap','closer','requested body gap only'),('ego_speed','faster_ego','ego speed bias only'),('lead_speed','slower_lead','lead requested speed only'),('lead_braking','lead_brakes','lead deceleration request only'),('wet_surface','wet_surface','weather wetness/precipitation only'),('following_relation','following_ends','lane-change request time and resulting following span only')]:branch(sp,name,['base',other],[diff])
 sp['negative']=dict(remove=['following_samples.jsonl'],error_contains='Missing required source: following_samples.jsonl')
 sp['test']=test_source('following_gap',"with tempfile.TemporaryDirectory() as t:\n p=pathlib.Path(t)\n rows=[{'time_s':i*.05,'ego_speed_mps':10,'lead_speed_mps':9,'along_road_body_gap_m':50-i,'ego_lane_id':-1,'lane_change_requested':False} for i in range(3)]\n (p/'following_samples.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in rows))\n v=analyze.following_gap(p)\n self.assertEqual(v['minimum_body_gap_m'],48)\n self.assertEqual(v['time_gap_s_samples'],[5,4.9,4.8])\n (p/'following_samples.jsonl').unlink()\n with self.assertRaisesRegex(ValueError,'Missing required source'):analyze.following_gap(p)")
 return sp

def box(x,y):return [[x+dx,y+dy,z] for z in (0,1.5) for dx,dy in [(-2,-.8),(-2,.8),(2,.8),(2,-.8)]]
def yellow():
 aid=IDS[3];sp=base(aid);r=sp['runner']
 r=r.replace('carla.TrafficLightState.Green if i<120 or i>=400 else carla.TrafficLightState.Yellow if i<200 else carla.TrafficLightState.Red',"carla.TrafficLightState.Green if i<cfg['yellow_tick'] or i>=cfg['green_return_tick'] else carla.TrafficLightState.Yellow if i<cfg['red_tick'] else carla.TrafficLightState.Red")
 r=r.replace('goal=(-13 if 200<=i<400 else 30)',"goal=(-13 if cfg['obey_red'] and cfg['red_tick']<=i<cfg['green_return_tick'] else cfg['approach_goal_m'])").replace('requested=min(3.5,',"requested=min(cfg['requested_speed_mps'],")
 r=r.replace('map_.get_waypoint_xodr(1,-1,323)',"map_.get_waypoint_xodr(1,-1,cfg['spawn_station_m'])")
 sp['runner']=r
 disposition(sp,'Retain actual governing yellow-alone, related green termination and subsequent red exhibition history.','control_sequence','governing_yellow_red_sequence',['signal_context.json','signal_history.jsonl'])
 disposition(sp,'Compare original full-body intersection entry with red exhibition without adding yellow stop duty or numerical immediacy definition.','entry_order','red_exhibition_vs_body_entry',['signal_history.jsonl'])
 disposition(sp,'Preserve actual one-way to two-way route and statutory intersection boundary context.','roadway_direction','one_way_to_two_way_route',['scenario_geometry.json'])
 geom=dict(source='diagnostic geometry',physical_verification=dict(native_map='road.xodr'),directed_roadways=[dict(polygon=[[-400,-7],[7,-7],[7,0],[-400,0]],direction_xy=[1,0],one_way=True)],intersection_polygon=[[-7,-7],[7,-7],[7,7],[-7,7]])
 for name,obey,station,yt,rt in [('stops_red',True,323,120,200),('enters_red',False,355,120,200),('enters_yellow',False,368,120,200),('inside_on_red',False,380,120,200),('yellow_red',True,323,0,80)]:
  cfg=dict(obey_red=obey,spawn_station_m=station,yellow_tick=yt,red_tick=rt,green_return_tick=400,requested_speed_mps=3.5,approach_goal_m=30)
  if name=='stops_red':xs=[-15,-13,-13]
  elif name=='enters_red':xs=[-15,-13,-5]
  else:xs=[-15,-5,3]
  states=['Green','Yellow','Red'] if name!='yellow_red' else ['Yellow','Yellow','Red']
  hist=[dict(frame=21714+i,time_s=.05*(i+1),signal_actor_id=1,signal_state=states[i],requested_state=states[i],ego=dict(body_vertices_m=box(xs[i],-1.75),speed_mps=3.5),affected_lanes=[[1,0,-1]]) for i in range(3)]
  ctx=dict(west_signal_actor_id=1,affected_lanes=[[1,0,-1]],vehicle_heads=[dict(actor_id=1)],pedestrian_heads=[],route='one-way road1 through connector11 to two-way road2; native proof required')
  sp['cases'].append(dict(name=name,rationale='Controlled '+name+' original signal and body entry history, no legal entry cutoff.',config=cfg,fixture={'signal_context.json':ctx,'signal_history.jsonl':lines(hist),'scenario_geometry.json':geom}))
 for n,cs,d in [('red_entry',['stops_red','enters_red'],'red obedience controller, measured entry relative to red'),('yellow_entry',['enters_yellow','enters_red'],'initial approach station, measured crossing before/after red'),('already_inside',['enters_yellow','inside_on_red'],'initial approach station; preserve already-inside vs new entry history'),('green_termination',['stops_red','yellow_red'],'initial green stage present versus initial yellow; original transition delay retained')]:branch(sp,n,cs,[d])
 sp['negative']=dict(remove=['signal_history.jsonl'],error_contains='Missing required source: signal_history.jsonl')
 sp['test']=test_source('entry_order',"with tempfile.TemporaryDirectory() as t:\n p=pathlib.Path(t)\n rows=[{'frame':i,'time_s':i*.05,'signal_state':state,'ego':{'body_vertices_m':[[x,0,0],[x+1,1,1]]}} for i,(state,x) in enumerate([('Yellow',-20),('Red',-5)])]\n (p/'signal_history.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in rows))\n v=analyze.entry_order(p)\n self.assertEqual(len(v['red_at_entry_events']),1)\n self.assertEqual(v['first_red']['frame'],1)\n (p/'signal_history.jsonl').unlink()\n with self.assertRaisesRegex(ValueError,'Missing required source'):analyze.entry_order(p)")
 return sp

def inoperative():
 aid=IDS[4];sp=base(aid);r=sp['runner'];a=sp['analysis']
 marking=(ROOT/'references/accepted-sources/C111325/stop257_markings_v2.py').read_text()
 marking=marking.replace("def spawn(carla,world):", "def spawn(carla,world):\n import json\n from pathlib import Path\n cfg=json.loads(Path(__file__).with_name('config.json').read_text())\n if cfg['reference_kind']=='sight':return []")
 # Render line or actual marked crossing with mesh tiles. Four approaches retain corresponding stop references.
 marking=marking.replace("for side,x,sign in [('west',-11,1),('east',11,-1)]:", "for side,x,sign in [('west',cfg['reference_x_m'],1),('east',-cfg['reference_x_m'],-1)]:")
 marking=marking.replace("for i in range(20):", "for i in range(40 if cfg['reference_kind']=='marked_crosswalk' else 20):")
 marking=marking.replace("y=sign*(.175+.35*i)","y=sign*(.175+.35*(i%20));x=x+(1.2*(i//20) if cfg['reference_kind']=='marked_crosswalk' else 0)")
 marking=marking.replace("if cfg['reference_kind']=='sight':return []", "if cfg['reference_kind'] in ('sight','unmarked_crosswalk'):return []")
 sp['extra_files']={'physical_stopline.py':marking};sp['reference_paths']=['references/accepted-sources/C111325/stop257_markings_v2.py']
 # Author reference geometry consistently with selected case and retain full Native readback.
 r=r.replace("assert len(root.findall('.//object[@name=\"StopLine\"]'))==4", "assert cfg['reference_kind'] in ('line','marked_crosswalk','unmarked_crosswalk','sight')")
 r=r.replace("world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text())", "source_tree=ET.fromstring((ROOT/'scene.xodr').read_text())\n  if cfg['reference_kind']!='line':\n   for road in source_tree.findall('road'):\n    for objects in road.findall('objects'):\n     for obj in list(objects):\n      if obj.get('name')=='StopLine':objects.remove(obj)\n  world=client.generate_opendrive_world(ET.tostring(source_tree,encoding='unicode'))")
 r=r.replace("'reference_line_x_m':-11,'crosswalk_present':False", "'reference_line_x_m':cfg['reference_x_m'],'reference_kind':cfg['reference_kind'],'crosswalk_present':cfg['reference_kind'] in ('marked_crosswalk','unmarked_crosswalk'),'crosswalk_definition':cfg['crosswalk_definition']")
 r=r.replace("13 if i<160 else -30", "13 if i<cfg['earlier_release_tick'] else -30").replace("13 if i<340 else -30", "13 if i<cfg['occupant_release_tick'] else -30")
 r=r.replace("-13 if i<600 else 30", "cfg['reference_x_m']-2.5 if i<cfg['ego_release_tick'] else 30")
 r=r.replace("requests['ego']=approach_control(actors['ego'],cfg['reference_x_m']-2.5 if i<cfg['ego_release_tick'] else 30,0,1)", "requests['ego']=approach_control(actors['ego'],cfg['reference_x_m']-2.5 if i<cfg['ego_release_tick'] and cfg['request_stop'] else 30,0,1)")
 sp['runner']=r
 a=a.replace("if not context.get('physical_stopline_tiles'):raise ValueError('Physical stop line inventory absent')", "if context.get('reference_kind','line')=='line' and not context.get('physical_stopline_tiles'):raise ValueError('Physical stop line inventory absent')")
 a=a.replace("'uncovered_pixel_verified':False,", "'uncovered_pixel_verified':False,'reference_kind':context.get('reference_kind','line'),")
 a=a.replace("if not entries or not halts:raise ValueError('Missing stop or entry observation')", "if not entries:raise ValueError('Missing entry observation')")
 a=a.replace("'sampled_halt_precedes_entry':halts[0]['frame']<entries[0]['frame']", "'sampled_halt_precedes_entry':bool(halts) and halts[0]['frame']<entries[0]['frame'],'reference_kind':context.get('reference_kind','line'),'exact_zero_speed_before_reference_frames':[r['frame'] for r in samples if r['states']['ego']['speed_mps']==0 and max(v[0] for v in r['states']['ego']['body_vertices_m'])<stopline]")
 a=a.replace("'sampled_halt_precedes_entry'],\n   'physical_cause_confirmed'", "'sampled_halt_precedes_entry']==cfg['request_stop'],\n   'physical_cause_confirmed'")
 sp['analysis']=a
 for req,method,key,inputs in [
 ('Installed uncovered vehicular signals wholly inoperative at entry, with actual governance and original head histories.','inoperative_heads','installed_dark_signal_heads',['signal_context.json','interaction_history.jsonl']),
 ('Stop at marked line; absent line before near-side marked or sidewalk-connection crosswalk; absent both nearest point with view.','stop_before_entry','marked_line_stop_before_entry',['signal_context.json','interaction_history.jsonl']),
 ('After stopping proceed cautiously, yielding to previously stopped vehicles and vehicles within intersection, keeping complete original histories.','priority_sequence','earlier_stop_and_intersection_occupancy',['signal_context.json','interaction_history.jsonl']),
 ('Retain original driver viewpoint, real occluder rays and sight history without declaring continuous nearest point or legal visibility.','sight_obstruction','sampled_sight_obstruction',['interaction_history.jsonl'])]:disposition(sp,req,method,key,inputs)
 variants=[]
 for kind in ['line','marked_crosswalk','unmarked_crosswalk','sight']:
  for stop in [True,False]:variants.append((kind+('_stop' if stop else '_roll'),kind,stop,600,160,340))
 variants += [('earlier_stop_ego_first','line',True,200,400,340),('occupied_ego_first','line',True,280,160,600),('fast_departure','line',True,450,160,340)]
 for name,kind,stop,release,er,oc in variants:
  ref=-11 if kind=='line' else -10 if 'crosswalk' in kind else -8
  cfg=dict(reference_kind=kind,reference_x_m=ref,request_stop=stop,ego_release_tick=release,earlier_release_tick=er,occupant_release_tick=oc,crosswalk_definition='sidewalk lateral lines connected at curbs' if kind=='unmarked_crosswalk' else 'distinct pedestrian crossing surface markings' if kind=='marked_crosswalk' else 'none')
  ctx=dict(head_count=4,installed_heads=[dict(actor_id=i) for i in range(1,5)],physical_stopline_tiles=[dict(actor_id=10)] if kind=='line' else [],reference_line_x_m=ref,reference_kind=kind,crosswalk_present='crosswalk' in kind,crosswalk_definition=cfg['crosswalk_definition'],intersection_polygon_xy_m=[[-7,-7],[7,-7],[7,7],[-7,7]])
  hist=[]
  for i in range(3):
   states=dict(ego=dict(body_vertices_m=box(ref-3 if i<2 else -4,-1.75),speed_mps=0 if stop and i<2 else 4),earlier_stopped=dict(body_vertices_m=box(0,15 if i==0 else 2),speed_mps=0 if i==0 else 4),inside_vehicle=dict(body_vertices_m=box(3 if i<2 else -20,1.75),speed_mps=4))
   hist.append(dict(frame=21714+i,time_s=.05*(i+1),states=states,head_states=[dict(actor_id=j,state='Off') for j in range(1,5)],sight_ray=dict(eye_m=[ref-3,-1.75,1.5],hits=[dict(label='building')],target_m=[0,15,0])))
  sp['cases'].append(dict(name=name,rationale='Controlled '+name+' under four installed inoperative uncovered head candidates; physical qualification remains original pixel audit.',config=cfg,fixture={'signal_context.json':ctx,'interaction_history.jsonl':lines(hist)}))
 for kind in ['line','marked_crosswalk','unmarked_crosswalk','sight']:branch(sp,kind+'_reference',[kind+'_stop',kind+'_roll'],['Requested complete stop versus rolling at same '+kind+' reference; legal cessation is exact, sampled epsilon descriptive only'])
 for n,other,diff in [('earlier_stop','earlier_stop_ego_first','ego and other release ordering'),('occupied','occupied_ego_first','occupant and ego release ordering'),('cautious','fast_departure','ego post-stop release time; measured history, no numeric cautiousness verdict')]:branch(sp,n,['line_stop',other],[diff])
 sp['negative']=dict(remove=['interaction_history.jsonl'],error_contains='Missing required source: interaction_history.jsonl')
 sp['test']=test_source('stop_before_entry',"with tempfile.TemporaryDirectory() as t:\n p=pathlib.Path(t)\n (p/'signal_context.json').write_text(json.dumps({'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'reference_line_x_m':-11}))\n rows=[{'frame':i,'time_s':i*.05,'states':{'ego':{'body_vertices_m':[[x,0,0],[x+1,1,1]],'speed_mps':0 if i==0 else 4}}} for i,x in enumerate([-15,-5])]\n (p/'interaction_history.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in rows))\n self.assertTrue(analyze.stop_before_entry(p)['sampled_halt_precedes_entry'])\n rows[0]['states']['ego']['speed_mps']=4\n (p/'interaction_history.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in rows))\n self.assertFalse(analyze.stop_before_entry(p)['sampled_halt_precedes_entry'])")
 return sp

_original_speed=speed
def speed(aid,posted=False):
 sp=_original_speed(aid,posted)
 if not posted:
  sp['test']=sp['test'].replace('(29,30,31)','(79,80,81)').replace("self.assertAlmostEqual(v['max_sampled_mph'],mph)","self.assertAlmostEqual(v['max_sampled_mph'],mph)\n    self.assertEqual(bool(v['above_80_mph_original_frames']),mph>80)")
 sp['audits']=[dict(subject='Absolute speed or actual posted-portion speed',case_ids=[aid+'__'+c['name'] for c in sp['cases']],sources=['speed_samples.jsonl','trace.jsonl','body_history.jsonl','raw.mkv'],checks=['Original frame/timestamp identity and velocity provenance','Route clearance and uninterrupted actual movement over full episode','For posted law, visible authority sign, direction and governed portion; for absolute law strict greater than 80 mph without duration or measurement-tolerance rule'],acceptance='independent Native source/pixel review; diagnostic pass is software only')]
 return sp
_original_inoperative=inoperative
def inoperative():
 sp=_original_inoperative();sp['analysis']=sp['analysis'].replace("'target':'sampled_stop_before_entry','requested':True", "'target':'sampled_stop_before_entry','requested':cfg['request_stop']")
 r=sp['runner'];r=r.replace("head_rows=[{'actor_id':head.id", "sight_candidates=[]\n    for sx in range(-20,-6):\n     viewpoint=carla.Location(x=sx,y=eye.y,z=eye.z)\n     candidate_hits=world.cast_ray(viewpoint,target)\n     obstruction=[h for h in candidate_hits if not actors['earlier_stopped'].bounding_box.contains(h.location,actors['earlier_stopped'].get_transform()) and not actors['ego'].bounding_box.contains(h.location,actors['ego'].get_transform())]\n     sight_candidates.append({'eye_m':[sx,eye.y,eye.z],'hit_count':len(obstruction),'clear':not obstruction,'distance_to_intersection_m':max(0,-7-sx)})\n    head_rows=[{'actor_id':head.id")
 r=r.replace("'physical_stopline_tiles':len(line_inventory),'sight_ray'", "'sight_candidates':sight_candidates,'physical_stopline_tiles':len(line_inventory),'sight_ray'")
 sp['runner']=r
 a=sp['analysis'];a=a.replace("return {'sample_count':len(rays),'blocked_samples':blocked,'observer_points_m':[r['eye_m'] for r in rays],", "candidates=[dict(frame=r['frame'],time_s=r['time_s'],**c) for r in samples for c in r.get('sight_candidates',[])]\n if not candidates:raise ValueError('Missing original sampled viewpoint candidates')\n clear=[c for c in candidates if c['clear']]\n nearest=min(clear,key=lambda c:c['distance_to_intersection_m']) if clear else None\n return {'sample_count':len(rays),'blocked_samples':blocked,'observer_points_m':[r['eye_m'] for r in rays],'sampled_viewpoint_candidates':candidates,'nearest_sampled_clear_point':nearest,'clear_candidate_count':len(clear),'sampling_spacing_m':1,")
 sp['analysis']=a
 for c in sp['cases']:
  rows=[json.loads(x) for x in c['fixture']['interaction_history.jsonl'].splitlines()]
  for row in rows:row['sight_candidates']=[dict(eye_m=[x,-1.75,1.5],hit_count=1 if x<-9 else 0,clear=x>=-9,distance_to_intersection_m=-7-x) for x in range(-20,-6)]
  c['fixture']['interaction_history.jsonl']=lines(rows)
 sp['test'] += "\n def test_nearest_clear(self):\n  with tempfile.TemporaryDirectory() as t:\n   p=pathlib.Path(t)\n   r={'frame':1,'time_s':.05,'sight_ray':{'hits':[{}],'eye_m':[-12,0,1.5]},'sight_candidates':[{'eye_m':[-12,0,1.5],'hit_count':1,'clear':False,'distance_to_intersection_m':5},{'eye_m':[-9,0,1.5],'hit_count':0,'clear':True,'distance_to_intersection_m':2},{'eye_m':[-8,0,1.5],'hit_count':0,'clear':True,'distance_to_intersection_m':1}]}\n   (p/'interaction_history.jsonl').write_text(json.dumps(r)+'\\n')\n   self.assertEqual(analyze.sight_obstruction(p)['nearest_sampled_clear_point']['eye_m'][0],-8)\n"
 aid=sp['assignment_id'];sp['audits']=[dict(subject='Inoperative control and exact '+c['name']+' stopping reference',case_ids=[aid+'__'+c['name']],sources=['interaction_history.jsonl','signal_context.json','road.xodr','four-view-receipt.json'],checks=['Every installed vehicular head uncovered and actually dark at subject body entry, governs correct lane','Full all-entrance approach, complete-cessation, occupancy and clearance histories','Marked line/crosswalk pixels or sidewalk-connection geometry, with absence of higher priority reference','Native viewpoint scan nearest sampled clear point and 1m resolution; continuous nearest point remains independent review','Cautiousness and yielding require independent legal/physical assessment'],acceptance='pending independent original Native pixel/physical review') for c in sp['cases']]
 return sp

def rebuild_prove(sp):
 import shutil
 aid=sp['assignment_id'];tmp=ROOT/'.runtime-work'/aid
 if tmp.exists():shutil.rmtree(tmp)
 f=b.build(sp);(f/'package-spec.json').write_text(dump(sp));b.prove(f,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')

_original_following=following
def following():
 sp=_original_following();aid=sp['assignment_id'];r=sp['runner']
 r=r.replace("        for _ in range(20): world.tick()", "        queued=None\n        if cfg.get('queued_traffic',False):\n            qp=mapping.get_waypoint_xodr(1,-1,470)\n            queued=world.spawn_actor(lead_bp,qp.transform);owned.append(queued)\n            queued.apply_control(carla.VehicleControl(brake=1,hand_brake=True))\n        surface_authoring={'ice_or_snow':False,'basis':'Explicit generated asphalt construction with no ice/snow layer or added material; absence is authored construction context, not weather inference','scene_sha256':hashlib.sha256((ROOT/'scene.xodr').read_bytes()).hexdigest(),'native_object_names':list(world.get_names_of_all_objects()),'native_actor_inventory':[{'id':a.id,'type':a.type_id} for a in world.get_actors()]}\n        for _ in range(20): world.tick()")
 r=r.replace("'lane_change_requested':index>=cfg['lane_change_tick']}", "'lane_change_requested':index>=cfg['lane_change_tick'],'surrounding_traffic':[{'actor_id':a.id,'type':a.type_id,'speed_mps':a.get_velocity().length(),'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]} for a in world.get_actors().filter('vehicle.*')],'original_weather':{'wetness':world.get_weather().wetness,'precipitation':world.get_weather().precipitation}}")
 r=r.replace("context['native_traffic_inventory_source']=", "context['surface_authoring']=surface_authoring;context['ice_or_snow']=False;context['native_traffic_inventory_source']=")
 sp['runner']=r
 a=sp['analysis'];a=a.replace('def finalize(root, output):',"def traffic_conditions(root):\n rows=[json.loads(s) for s in required(root,'following_samples.jsonl').read_text().splitlines() if s]\n return {'original_frames':[r['frame'] for r in rows],'participant_counts':[len(r['surrounding_traffic']) for r in rows],'surrounding_traffic':[r['surrounding_traffic'] for r in rows],'original_weather':[r['original_weather'] for r in rows],'scope':'Original full participant body/velocity inventory and weather readback, no reasonable/prudent cutoff'}\n\ndef finalize(root, output):")
 a=a.replace("'measurements':{'original_following_geometry'", "'measurements':{'traffic_condition_history':{'method':'traffic_conditions','value':traffic_conditions(root),'sources':{'following_samples.jsonl':hashlib.sha256(required(root,'following_samples.jsonl').read_bytes()).hexdigest()}},'original_following_geometry'")
 sp['analysis']=a
 queued=json.loads(json.dumps(sp['cases'][0]));queued.update(name='queued_traffic',rationale='Actual third conventional vehicle queued behind while following and before lane change; traffic inventory retained.');queued['config']['queued_traffic']=True;sp['cases'].append(queued)
 for c in sp['cases']:
  rows=[json.loads(s) for s in c['fixture']['following_samples.jsonl'].splitlines()]
  for row in rows:
   row['surrounding_traffic']=[dict(actor_id=i,type='vehicle.lincoln.mkz_2020',speed_mps=0 if i==3 else row['ego_speed_mps'],body_vertices_m=box(30*i,1.75)) for i in range(1,4 if c['name']=='queued_traffic' else 3)]
   row['original_weather']=dict(wetness=c['config']['wetness'],precipitation=c['config']['precipitation'])
  c['fixture']['following_samples.jsonl']=lines(rows)
  c['fixture']['surface_context.json'].update(ice_or_snow=False,surface_authoring=dict(ice_or_snow=False,basis='Diagnostic generated asphalt without ice/snow source layers; not weather inference',native_object_names=['generated_road']))
 disposition(sp,'Retain synchronized surrounding traffic bodies/speeds and actual weather throughout following.','traffic_conditions','traffic_condition_history',['following_samples.jsonl'])
 branch(sp,'traffic',['base','queued_traffic'],['Presence of third actual queued qualifying vehicle only; preserve original inventory'])
 mappings={
 'drv.following':'following_samples.jsonl ego_lane_id, lead_lane_id, ego_speed_mps and along_road_body_gap_m before lane_change_requested; following_gap()',
 'drv.time_gap':'following_samples.jsonl original full-body gap divided by ego_speed_mps only when moving; following_gap(); no legal gap cutoff',
 'rel.surface_gap':'following_samples.jsonl along_road_body_gap_m from every original ego front/lead rear body vertex projection',
 'rel.ahead_behind_in_lane':'following_samples.jsonl ego_lane_id and lead_lane_id plus signed full-body longitudinal projection',
 'kin.speed':'following_samples.jsonl ego_speed_mps and lead_speed_mps from Native original get_velocity; trace.jsonl velocity supports ego',
 'env.wet_road':'following_samples.jsonl original_weather wetness/precipitation captured each original tick; traffic_conditions()',
 'env.ice_or_snow':'surface_context.json surface_authoring explicit absence of authored ice/snow source layers with scene hash/native object inventory; highway_conditions(); not inferred from weather',
 'drv.queue_behind':'following_samples.jsonl surrounding_traffic all vehicle IDs, full bodies and speeds; queued_traffic variation; traffic_conditions()',
 'drv.hard_deceleration':'following_samples.jsonl lead_speed_mps original time-series and control request; lead_brakes comparison, preserve derivative without a legal deceleration standard'}
 sp['observation_mapping']=mappings
 sp['audits']=[dict(subject='Original following bodies, traffic and surface for '+c['name'],case_ids=[aid+'__'+c['name']],sources=['following_samples.jsonl','surface_context.json','raw.mkv','four-view-receipt.json'],checks=['Ego and lead qualifying bodies visible for full actual following before completed lane change','Original same-lane/behind relation and 3D velocities join same ticks','All surrounding participants including queued vehicle appear in inventory and pixels','Dry/wet actual native weather readback and authored no-ice source inventory; no weather inference for ice','Lead braking original derivative and gap retained without reasonable/prudent numerical verdict'],acceptance='independent original Native pixels and motion verification pending') for c in sp['cases']]
 return sp

def posted():
 sp=speed(IDS[2],True);a=sp['analysis'];start=a.index('def speed_history(root):');end=a.index('\ndef posted_sign_context',start)
 fn='''def speed_history(root):
    rows=[json.loads(s) for s in required(root,'speed_samples.jsonl').read_text().splitlines() if s]
    context=json.loads(required(root,'posted_speed_context.json').read_text())
    if not rows:raise ValueError('Empty original speed samples')
    limit=float(context['posted_rate']);limit_mps=limit*.44704 if context['posted_unit']=='mph' else limit/3.6
    direction=context['governed_direction_xy'];lo,hi=context['governed_station_interval_m']
    zone=[r for r in rows if lo<=r['position_m'][0]<=hi and sum(x*y for x,y in zip(r['velocity_mps'][:2],direction))>=0 and context['authority_asserted']]
    return {'sample_count':len(rows),'zone_sample_count':len(zone),'max_sampled_mps':max(r['speed_mps'] for r in rows),'max_sampled_mph':max(r['speed_mps'] for r in rows)/.44704,'in_zone_max_sampled_mps':max([r['speed_mps'] for r in zone],default=0),'above_posted_30_mph_original_frames':[r['frame'] for r in zone if r['speed_mps']>limit_mps],'evaluated_original_frames':[r['frame'] for r in zone],'posted_limit_mps':limit_mps,'governed_interval_m':[lo,hi],'governed_direction_xy':direction,'authority_asserted':context['authority_asserted'],'scope':'Authored governance and original speeds; public authority factual status and rendered sign remain independently reviewed, no tolerance/duration rule'}
'''
 a=a[:start]+fn+a[end:];a=a.replace("'sources': {'speed_samples.jsonl': hashlib.sha256(required(root, 'speed_samples.jsonl').read_bytes()).hexdigest()}","'sources': {n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in ['speed_samples.jsonl','posted_speed_context.json']}")
 sp['analysis']=a;sp['dispositions'][0]['measurement']['inputs']=['speed_samples.jsonl','posted_speed_context.json']
 r=sp['runner'];r=r.replace('world = client.generate_opendrive_world((ROOT/\'scene.xodr\').read_text())',"tree=ET.fromstring((ROOT/'scene.xodr').read_text())\n        for sign in tree.findall('.//signal[@type=\"274\"]'):\n            sign.set('value',str(cfg['posted_rate']));sign.set('unit',cfg['posted_unit']);sign.set('s',str(cfg['sign_station_m']))\n        world = client.generate_opendrive_world(ET.tostring(tree,encoding='unicode'))")
 r=r.replace("'road_id':1,'sign_station_m':200,'posted_limit_mph':30,", "'road_id':1,'sign_station_m':cfg['sign_station_m'],'posted_limit_mph':cfg['posted_rate'] if cfg['posted_unit']=='mph' else cfg['posted_rate']/1.609344,'posted_rate':cfg['posted_rate'],'posted_unit':cfg['posted_unit'],'governed_station_interval_m':cfg['governed_station_interval_m'],'governed_direction_xy':cfg['governed_direction_xy'],'authority_asserted':cfg['authority_asserted'],'authority_source':cfg['authority_source'],")
 r=r.replace("mapping.get_waypoint_xodr(1,-1,100)","mapping.get_waypoint_xodr(1,-1,cfg['spawn_station_m'])")
 sp['runner']=r
 common=dict(posted_rate=30,posted_unit='mph',governed_station_interval_m=[200,1800],governed_direction_xy=[1,0],authority_asserted=True,authority_source='authored synthetic public-authority candidate; actual jurisdiction requires independent source review',sign_station_m=200,spawn_station_m=100)
 for c in sp['cases']:c['config'].update(common);c['fixture']['posted_speed_context.json'].update(common)
 for name,opts in [('outside_zone',dict(governed_station_interval_m=[900,1800])),('opposite_direction',dict(governed_direction_xy=[-1,0])),('non_authority_sign',dict(authority_asserted=False,authority_source='authored private non-authority sign candidate')),('metric_equivalent',dict(posted_rate=48.28032,posted_unit='km/h')),('sign_not_in_view',dict(sign_station_m=1,spawn_station_m=300))]:
  c=json.loads(json.dumps(sp['cases'][2]));c.update(name=name,rationale='Controlled '+name+' source governance qualification on same narrow-road travel cell.');c['config'].update(opts);c['fixture']['posted_speed_context.json'].update(opts);sp['cases'].append(c)
 for name,other,diff in [('governed_portion','outside_zone','governed portion boundaries, with identical speed and samples'),('governed_direction','opposite_direction','source sign governing direction, identical subject route and speed'),('authority','non_authority_sign','independently sourced authority qualification context only'),('units','metric_equivalent','equivalent posted unit representation only'),('source_visibility','sign_not_in_view','sign station before camera recorded route, retain governing-limit reading assumption')]:branch(sp,name,['above',other],[diff])
 sp['test']=test_source('speed_history',"with tempfile.TemporaryDirectory() as t:\n p=pathlib.Path(t)\n ctx={'posted_rate':30,'posted_unit':'mph','governed_direction_xy':[1,0],'governed_station_interval_m':[200,1800],'authority_asserted':True}\n (p/'posted_speed_context.json').write_text(json.dumps(ctx))\n for mph in (29,30,31):\n  (p/'speed_samples.jsonl').write_text(json.dumps({'frame':1,'time_s':.05,'position_m':[300,0,0],'velocity_mps':[mph*.44704,0,0],'speed_mps':mph*.44704})+'\\n')\n  v=analyze.speed_history(p)\n  self.assertEqual(bool(v['above_posted_30_mph_original_frames']),mph>30)\n ctx['governed_direction_xy']=[-1,0];(p/'posted_speed_context.json').write_text(json.dumps(ctx))\n self.assertEqual(analyze.speed_history(p)['zone_sample_count'],0)")
 return sp

_original_yellow=yellow
def yellow():
 sp=_original_yellow();aid=sp['assignment_id'];r=sp['runner']
 r=r.replace("world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text())", "source_tree=ET.fromstring((ROOT/'scene.xodr').read_text())\n  if cfg.get('companion_aspect',False) or cfg.get('other_route_signal',False):\n   road=source_tree.find(\"road[@id='3']\") if cfg.get('other_route_signal',False) else source_tree.find(\"road[@id='1']\")\n   signals=road.find('signals')\n   if signals is None:signals=ET.SubElement(road,'signals')\n   template=source_tree.find(\"road[@id='1']/signals/signal\")\n   secondary=ET.fromstring(ET.tostring(template,encoding='unicode'));secondary.set('id','3077');secondary.set('name','yellow_companion_or_other_route');secondary.set('s','380');signals.append(secondary)\n  world=client.generate_opendrive_world(ET.tostring(source_tree,encoding='unicode'))")
 r=r.replace("()=='3076'", "()==('3077' if cfg.get('other_route_signal',False) else '3076')")
 r=r.replace("if not any(v[0]==1 and v[2] in (-1,-2) for v in affected):", "if not cfg.get('other_route_signal',False) and not any(v[0]==1 and v[2] in (-1,-2) for v in affected):")
 r=r.replace("signal=west_heads[0];signal.freeze(True)", "signal=west_heads[0];signal.freeze(True)\n  for h in heads:\n   if h.id!=signal.id:h.freeze(True);h.set_state(carla.TrafficLightState.Red)")
 r=r.replace("'requested_state':str(desired).split('.')[-1]", "'requested_state':str(desired).split('.')[-1],'facing_subject':not cfg.get('other_route_signal',False),'companion_aspects':[str(h.get_state()).split('.')[-1] for h in heads if h.id!=signal.id and cfg.get('companion_aspect',False)]")
 sp['runner']=r
 a=sp['analysis'];a=a.replace("'readback_matches_requests':all", "'yellow_alone_frames':[r['frame'] for r in samples if r['signal_state']=='Yellow' and not r.get('companion_aspects',[])],'facing_subject_history':[r.get('facing_subject',True) for r in samples],'companion_aspect_history':[r.get('companion_aspects',[]) for r in samples],\n  'readback_matches_requests':all")
 sp['analysis']=a
 for c in sp['cases']:
  c['config'].update(companion_aspect=False,other_route_signal=False)
  hist=[json.loads(l) for l in c['fixture']['signal_history.jsonl'].splitlines()]
  for row in hist:row.update(facing_subject=True,companion_aspects=[])
  if c['name']=='inside_on_red':
   for row,x in zip(hist,[-5,0,10]):row['ego']['body_vertices_m']=box(x,-1.75)
  c['fixture']['signal_history.jsonl']=lines(hist)
 for name,comp,other in [('yellow_non_alone',True,False),('red_other_route',False,True)]:
  c=json.loads(json.dumps(sp['cases'][1 if other else 0]));c.update(name=name,rationale='Controlled qualification '+name+' original indications and actual governed lane identity retained.');c['config'].update(companion_aspect=comp,other_route_signal=other)
  hist=[json.loads(l) for l in c['fixture']['signal_history.jsonl'].splitlines()]
  for row in hist:row.update(facing_subject=not other,companion_aspects=['Red'] if comp else [])
  c['fixture']['signal_history.jsonl']=lines(hist)
  if other:c['fixture']['signal_context.json']['affected_lanes']=[[3,0,-1]]
  sp['cases'].append(c)
 branch(sp,'steady_yellow_alone',['stops_red','yellow_non_alone'],['Companion original head Red aspect on same approach, measuring yellow-alone qualification only'])
 branch(sp,'facing_governance',['enters_red','red_other_route'],['Selected controlled signal actual road/lane governance belongs to subject versus cross route'])
 sp['audits']=[dict(subject='Facing signal indications and body entry for '+c['name'],case_ids=[aid+'__'+c['name']],sources=['signal_history.jsonl','signal_context.json','raw.mkv','scenario_geometry.json'],checks=['Original actual illuminated vehicle aspects alone or concurrent companion, head identity, facing direction and governed Native lanes','Related green termination and exact yellow/red same-tick history','Full original body entry boundary, including already-inside clearance history','Pedestrian heads treated separately from vehicular indications','No yellow stop obligation, legal entry point or immediate-after numerical threshold invented'],acceptance='independent original Native signal pixels and motion review pending') for c in sp['cases']]
 return sp

_original_inoperative2=inoperative
def inoperative():
 sp=_original_inoperative2();aid=sp['assignment_id'];r=sp['runner'];a=sp['analysis']
 r=r.replace("if cfg['reference_kind']!='line':", "if cfg.get('installed_heads',True) is False:\n   for road in source_tree.findall('road'):\n    for signals in road.findall('signals'):\n     for obj in list(signals):signals.remove(obj)\n  if cfg['reference_kind']!='line':")
 r=r.replace("if len(selected)!=4:", "if len(selected)!=(4 if cfg.get('installed_heads',True) else 0):")
 r=r.replace("for head in selected:head.freeze(True);head.set_state(carla.TrafficLightState.Off)", "for head in selected:head.freeze(True);head.set_state(carla.TrafficLightState.Green if cfg.get('operative_at_entry',False) else carla.TrafficLightState.Off)\n  covers=[]\n  if cfg.get('cover_heads',False):\n   from physical_stopline import ASSET\n   cb=world.get_blueprint_library().find('static.prop.mesh');cb.set_attribute('mesh_path',ASSET);cb.set_attribute('scale','20');cb.set_attribute('mass','0')\n   for head in selected:\n    tr=head.get_transform();tr.location.z+=2.5;tr.rotation.pitch=90\n    cover=world.spawn_actor(cb,tr);cover.set_simulate_physics(False);cover.set_collisions(False);covers.append(cover);owned.append(cover)")
 r=r.replace("'head_count':len(selected),'uncovered_source'", "'head_count':len(selected),'covered_requested':cfg.get('cover_heads',False),'native_covers':[{'actor_id':x.id,'position_m':[x.get_location().x,x.get_location().y,x.get_location().z]} for x in covers],'uncovered_source'")
 sp['runner']=r
 a=a.replace("if context.get('head_count')!=4 or len(context.get('installed_heads',[]))!=4:", "if context.get('head_count')!=len(context.get('installed_heads',[])):")
 a=a.replace("'installed_head_count':4,", "'installed_head_count':context['head_count'],'covered_requested':context.get('covered_requested',False),'native_covers':context.get('native_covers',[]),")
 a=a.replace("all(s=='Off' for s in at_entry.values())", "bool(at_entry) and all(s=='Off' for s in at_entry.values())")
 sp['analysis']=a
 for c in sp['cases']:c['config'].update(installed_heads=True,cover_heads=False,operative_at_entry=False)
 c=json.loads(json.dumps(sp['cases'][0]));c.update(name='covered_heads',rationale='Installed inoperative head candidates physically covered by retained Native mesh actors; source pixels must verify uncovered predicate absence.');c['config']['cover_heads']=True;c['fixture']['signal_context.json'].update(covered_requested=True,native_covers=[dict(actor_id=99,position_m=[-10,-3,4])]);sp['cases'].append(c)
 branch(sp,'uncovered',['line_stop','covered_heads'],['Cover mesh actors only, preserving installed head controls and subject motion'])
 return sp

def supplemental250():
 import copy
 original=IDS[4];original_assignment=json.loads((ROOT/'inputs'/original/'assignment.json').read_text());catalog={c['cell_id']:c for c in json.loads((ROOT/'inputs/coverage/candidate-cells.json').read_text())['cells']}
 outputs=[];bindings=[]
 for cell,kind in [('C24811','inoperative_entry'),('C376646','installed')]:
  aid='testing__'+cell+'__NRS-484B-250-4__motor_vehicle_driver';folder=ROOT/'work'/aid;folder.mkdir(exist_ok=True)
  ass=copy.deepcopy(original_assignment);ass.update(assignment_id=aid,cell_id=cell,cell=catalog[cell],role='testing');(folder/'assignment.json').write_text(dump(ass))
  sp=inoperative();sp.update(assignment_id=aid,seed_assignment_id=original);sp['cases']=[copy.deepcopy(sp['cases'][0]),copy.deepcopy(sp['cases'][0])];sp['comparisons']=[];sp['branches']=[]
  if kind=='inoperative_entry':names=['dark_heads','operative_heads'];options=[{},dict(operative_at_entry=True)]
  else:names=['no_installed_signal_stop','no_installed_signal_roll'];options=[dict(installed_heads=False),dict(installed_heads=False,request_stop=False)]
  for c,n,opt in zip(sp['cases'],names,options):
   c.update(name=n,rationale='Controlled '+n+' qualification source context in compatible '+cell+' fixed control cell.');c['config'].update(opt,cell_id=cell)
   rows=[json.loads(l) for l in c['fixture']['interaction_history.jsonl'].splitlines()];ctx=c['fixture']['signal_context.json']
   if kind=='installed':
    ctx.update(head_count=0,installed_heads=[])
    for row in rows:row['head_states']=[];row['states']['ego']['speed_mps']=0 if c['config']['request_stop'] and row['frame']<21716 else 4
   elif opt.get('operative_at_entry'):
    for row in rows:
     for head in row['head_states']:head['state']='Green'
   c['fixture']['interaction_history.jsonl']=lines(rows)
  # build's branch helper resolves original source using inputs, so supplemental rows are declared explicitly.
  topics=list(TOPICS['NRS-484B-250-4']['topics']);sp['comparisons']=[dict(comparison_id=kind,cases=names,fixed_conditions=['Same supplemental catalog layout, maneuver, actor and control','Same reference line, motion except stop/roll no-signal context pair, cameras and duration'],deliberate_differences=['Actual original head operation at entry' if kind=='inoperative_entry' else 'Requested stop versus roll with no installed signal; qualification absence fixed'])];sp['branches']=[dict(name=kind,topic_ids=topics,cases=names,comparison_ids=[kind])]
  bindings.append(dict(assignment_id=aid,original_assignment_id=original,original_cell_incompatibility='Fixed original control inoperative_signal cannot represent '+('operative signal' if kind=='inoperative_entry' else 'no installed signal'),binding_reason='Unused compatible testing candidate '+cell+' retains blind_intersection/travel/actor and supports '+kind+' qualification context'))
  outputs.append(sp)
 p=ROOT/'work'/original/'additional-bindings.json';p.write_text(dump(bindings));return outputs

_previous_following=following
def following():
 sp=_previous_following()
 for c in sp['cases']:
  hist=[json.loads(s) for s in c['fixture']['following_samples.jsonl'].splitlines()]
  if c['name']=='lead_brakes':
   for row,speed in zip(hist,[9,6,3]):row['lead_speed_mps']=speed
  if c['name']=='following_ends':
   hist[1]['lane_change_requested']=True;hist[1]['ego_lane_id']=-2
  c['fixture']['following_samples.jsonl']=lines(hist)
 return sp
_previous_inoperative=inoperative
def inoperative():
 sp=_previous_inoperative()
 for c in sp['cases']:
  hist=[json.loads(s) for s in c['fixture']['interaction_history.jsonl'].splitlines()]
  if c['name']=='earlier_stop_ego_first':
   for i,row in enumerate(hist):row['states']['earlier_stopped'].update(body_vertices_m=box(0,15),speed_mps=0 if i==2 else 4)
  if c['name']=='occupied_ego_first':
   for i,row in enumerate(hist):row['states']['inside_vehicle']['body_vertices_m']=box(3 if i==2 else 20,1.75)
  if c['name']=='fast_departure':hist[1]['states']['ego'].update(body_vertices_m=box(-4,-1.75),speed_mps=4)
  c['fixture']['interaction_history.jsonl']=lines(hist)
 return sp

_previous_inoperative3=inoperative
def inoperative():
 sp=_previous_inoperative3()
 helper=sp['extra_files']['physical_stopline.py'];helper=helper.replace("  for i in range(40 if", "  base_x=x\n  for i in range(40 if").replace(";x=x+(1.2*(i//20)",";x=base_x+(1.2*(i//20)")
 sp['extra_files']['physical_stopline.py']=helper
 sp['runner']=sp['runner'].replace("source_tree=ET.fromstring((ROOT/'scene.xodr').read_text())", "source_tree=ET.fromstring((ROOT/'scene.xodr').read_text())\n  if cfg['reference_kind']=='unmarked_crosswalk':\n   for road in source_tree.findall('road'):\n    if road.get('junction')=='-1':\n     for section in road.findall('./lanes/laneSection'):\n      for side_name,lane_id in [('left','3'),('right','-3')]:\n       side=section.find(side_name)\n       if side is not None:\n        lane=ET.SubElement(side,'lane',{'id':lane_id,'type':'sidewalk','level':'true'})\n        ET.SubElement(lane,'link');ET.SubElement(lane,'width',{'sOffset':'0','a':'2','b':'0','c':'0','d':'0'});ET.SubElement(lane,'height',{'sOffset':'0','inner':'.15','outer':'.15'})")
 return sp

_previous_inoperative4=inoperative
def inoperative():
 sp=_previous_inoperative4();r=sp['runner'];start=r.index("  source_tree=ET.fromstring");end=r.index("  world=client.generate_opendrive_world",start)
 body=r[start:end];function='def authored_scene(cfg):\n'+''.join(' '+line[2:]+'\n' for line in body.splitlines())+" return ET.tostring(source_tree,encoding='unicode')\n\n"
 r=r[:start]+"  world=client.generate_opendrive_world(authored_scene(cfg))\n"+r[r.index('\n',end)+1:];r=r.replace('def state(actor):',function+'def state(actor):')
 r=r.replace("return {'passed':True,'authored_signal_heads':4", "generated=ET.fromstring(authored_scene(cfg))\n if cfg['reference_kind']=='unmarked_crosswalk':assert len(generated.findall('.//lane[@type=\"sidewalk\"]'))>=8\n if cfg.get('installed_heads',True) is False:assert not generated.findall('.//signal')\n return {'passed':True,'authored_signal_heads':4")
 sp['runner']=r
 sp['test'] += "\n def test_actual_authored_reference_geometry(self):\n  import runner,xml.etree.ElementTree as ET\n  cfg=json.loads(pathlib.Path(runner.ROOT/'config.json').read_text());cfg['reference_kind']='unmarked_crosswalk'\n  tree=ET.fromstring(runner.authored_scene(cfg))\n  self.assertGreaterEqual(len(tree.findall('.//lane[@type=\"sidewalk\"]')),8)\n  self.assertFalse(tree.findall('.//object[@name=\"StopLine\"]'))\n  cfg['installed_heads']=False\n  self.assertFalse(ET.fromstring(runner.authored_scene(cfg)).findall('.//signal'))\n"
 return sp

_previous_inoperative5=inoperative
def inoperative():
 sp=_previous_inoperative5();sp['runner']=sp['runner'].replace("'authored_signal_heads':4,'stop_line_objects':4", "'authored_signal_heads':len(generated.findall('.//signal')),'stop_line_objects':len(generated.findall('.//object[@name=\"StopLine\"]'))")
 return sp

_previous_speed2=speed
def speed(aid,posted=False):
 sp=_previous_speed2(aid,posted)
 if posted:return sp
 import xml.etree.ElementTree as ET
 tree=ET.fromstring((ROOT/'references/v6-capability'/aid/'scene.xodr').read_text());tree.find('header').set('name','C10301 long synthetic alley with adjacent marked access aisle')
 tree.find('road').set('name','C10301 alley travel route')
 aisle=ET.SubElement(tree,'road',{'name':'C10301 adjacent marked access aisle pavement','length':'20','id':'2','junction':'-1'});ET.SubElement(aisle,'link');pv=ET.SubElement(aisle,'planView');ET.SubElement(ET.SubElement(pv,'geometry',{'s':'0','x':'400','y':'5','hdg':'0','length':'20'}),'line');lanes=ET.SubElement(aisle,'lanes');sec=ET.SubElement(lanes,'laneSection',{'s':'0'});center=ET.SubElement(sec,'center');ET.SubElement(center,'lane',{'id':'0','type':'none','level':'false'});right=ET.SubElement(sec,'right');ln=ET.SubElement(right,'lane',{'id':'-1','type':'driving','level':'false'});ET.SubElement(ln,'link');ET.SubElement(ln,'width',{'sOffset':'0','a':'2.5','b':'0','c':'0','d':'0'})
 sp['scene']=ET.tostring(tree,encoding='unicode')
 helper='''"""Physical accepted road-line mesh adaptation for the adjacent access aisle."""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])
def positions():
 points=[]
 for i in range(58):
  x=400+.35*i
  points += [(x,5.175),(x,7.325)]
 for i in range(8):points += [(400,5+.35*i),(420,5+.35*i)]
 for stripe in range(8):
  for i in range(6):points.append((400+stripe*2.5+i*.35,5.2+i*.35))
 return points
def spawn(carla,world):
 bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0');actors=[]
 for i,(x,y) in enumerate(positions()):
  bp.set_attribute('role_name','access_aisle_mark_%03d'%i);a=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0]*SCALE,y=y,z=.002-EXTENT[2]*SCALE)));a.set_simulate_physics(False);a.set_collisions(False);actors.append(a)
 return actors
'''
 sp['extra_files']={'access_aisle.py':helper};sp['reference_paths']=['references/accepted-sources/C111325/stop257_markings_v2.py']
 r=sp['runner'];r=r.replace('        mapping = world.get_map();',"        from access_aisle import spawn as spawn_aisle\n        aisle_marks=spawn_aisle(carla,world);owned.extend(aisle_marks)\n        aisle_inventory=[{'actor_id':a.id,'type':a.type_id,'position_m':[a.get_location().x,a.get_location().y,a.get_location().z],'mesh_path':a.attributes.get('mesh_path')} for a in aisle_marks]\n        mapping = world.get_map();")
 r=r.replace("'road_id':1,'native_map_name'", "'road_id':1,'marked_access_aisle_polygon_xy':[[400,5],[420,5],[420,7.5],[400,7.5]],'native_aisle_markings':aisle_inventory,'aisle_relative_to_ego_route':'adjacent to right pavement boundary at x400..420, y5..7.5; ego lane center y1.75','native_map_name'")
 sp['runner']=r
 for c in sp['cases']:c['fixture']['alley_context.json'].update(marked_access_aisle_polygon_xy=[[400,5],[420,5],[420,7.5],[400,7.5]],native_aisle_markings=[dict(actor_id=200,position_m=[400,5.2,0])],aisle_relative_to_ego_route='adjacent right of actual travel route')
 sp['test'] += "\n def test_access_aisle_geometry(self):\n  import access_aisle,runner,xml.etree.ElementTree as ET\n  tree=ET.parse(runner.ROOT/'scene.xodr')\n  self.assertEqual(tree.find(\"road[@id='2']\").get('length'),'20')\n  self.assertGreater(len(access_aisle.positions()),150)\n  self.assertTrue(all(399<=x<=421 and 5<=y<=7.5 for x,y in access_aisle.positions()))\n"
 return sp

_previous_speed3=speed
def speed(aid,posted=False):
 sp=_previous_speed3(aid,posted)
 if not posted:sp['runner']=sp['runner'].replace('mapping = world.get_map(); wp =','mapping = world.get_map(); native_map_name=mapping.name; wp =').replace("'native_map_name':world.get_map().name", "'native_map_name':native_map_name")
 return sp
_previous_supplement=supplemental250
def supplemental250():
 specs=_previous_supplement()
 for sp in specs:
  sp['audits']=[dict(subject='Signal installation/operation qualification '+c['name'],case_ids=[sp['assignment_id']+'__'+c['name']],sources=['signal_context.json','interaction_history.jsonl','raw.mkv','road.xodr'],checks=['Actual selected compatible cell identity and no hidden signal in no-installed context','Every original signal head state, pixel covering and governed lane at body entry','Complete approach/stop/entry/clearance and other-vehicle histories','Qualification absence does not create a legal compliance verdict'],acceptance='independent original Native pixels and physical verification pending') for c in sp['cases']]
 return specs

_previous_posted=posted
def posted():
 sp=_previous_posted();sp['analysis']=sp['analysis'].replace("limit=float(context['posted_rate']);limit_mps=limit*.44704 if context['posted_unit']=='mph' else limit/3.6", "from decimal import Decimal\n    limit=Decimal(str(context['posted_rate']));limit_mps=float(limit*Decimal('.44704') if context['posted_unit']=='mph' else limit/Decimal('3.6'))")
 sp['test'] += "\n def test_exact_unit_conversion(self):\n  from decimal import Decimal\n  self.assertEqual(Decimal('30')*Decimal('.44704'),Decimal('48.28032')/Decimal('3.6'))\n"
 return sp

_previous_speed4=speed
def speed(aid,posted=False):
 sp=_previous_speed4(aid,posted)
 if posted:return sp
 import xml.etree.ElementTree as ET,copy
 tree=ET.fromstring(sp['scene']);tree.remove(tree.find("road[@id='2']"));lanes=tree.find("road[@id='1']/lanes");original=lanes.find('laneSection')
 for station,width in [(400,4),(420,1.5)]:
  section=copy.deepcopy(original);section.set('s',str(station))
  for lane in section.findall('right/lane'):
   if lane.get('id')=='-2':lane.find('width').set('a',str(width))
  lanes.append(section)
 for section in lanes.findall('laneSection'):
  for lane in section.findall('.//lane'):
   if lane.get('id')!='0':
    link=lane.find('link')
    if link is None:link=ET.SubElement(lane,'link')
    ET.SubElement(link,'predecessor',{'id':lane.get('id')});ET.SubElement(link,'successor',{'id':lane.get('id')})
 sp['scene']=ET.tostring(tree,encoding='unicode');sp['test']=sp['test'].replace("self.assertEqual(tree.find(\"road[@id='2']\").get('length'),'20')", "self.assertEqual(tree.find(\"road[@id='1']/lanes/laneSection[@s='400']/right/lane[@id='-2']/width\").get('a'),'4')")
 return sp

_previous_posted2=posted
def posted():
 sp=_previous_posted2();r=sp['runner']
 r=r.replace("sign.set('s',str(cfg['sign_station_m']))", "sign.set('s',str(cfg['sign_station_m']));sign.set('orientation','+' if cfg['governed_direction_xy'][0]>0 else '-')")
 r=r.replace("'road_id':x.road_id,'s':x.s}", "'road_id':x.road_id,'s':x.s,'orientation':str(x.orientation)}")
 start=r.index('        tree=ET.fromstring');end=r.index('        world = client.generate_opendrive_world',start);body=r[start:end]
 fn='def authored_scene(cfg):\n'+''.join(' '+line[8:]+'\n' for line in body.splitlines())+" return ET.tostring(tree,encoding='unicode')\n\n"
 r=r[:start]+"        world = client.generate_opendrive_world(authored_scene(cfg))\n"+r[r.index('\n',end)+1:];r=r.replace('def check():',fn+'def check():');sp['runner']=r
 sp['test'] += "\n def test_sign_orientation_and_units(self):\n  import runner,xml.etree.ElementTree as ET\n  cfg=json.loads((runner.ROOT/'config.json').read_text());cfg.update(governed_direction_xy=[-1,0],posted_rate=48.28032,posted_unit='km/h')\n  sign=ET.fromstring(runner.authored_scene(cfg)).find('.//signal[@type=\"274\"]')\n  self.assertEqual(sign.get('orientation'),'-');self.assertEqual(sign.get('value'),'48.28032');self.assertEqual(sign.get('unit'),'km/h')\n"
 return sp


_previous_unmarked_reference=inoperative
def inoperative():
 sp=_previous_unmarked_reference()
 for c in sp['cases']:
  if c['name'] in ('unmarked_crosswalk_stop','unmarked_crosswalk_roll'):
   c['config']['reference_x_m']=-9;c['fixture']['signal_context.json'].update(reference_line_x_m=-9,crosswalk_band_x_m=[-9,-7])
   rows=[json.loads(line) for line in c['fixture']['interaction_history.jsonl'].splitlines() if line]
   for i,row in enumerate(rows):
    if i<2:
     for v in row['states']['ego']['body_vertices_m']:v[0]+=1
    row['sight_ray']['eye_m'][0]+=1
   c['fixture']['interaction_history.jsonl']=lines(rows)
   c.setdefault('extra_files',{})['tests/test_case.py']=sp['test']+'\n def test_reference_matches_actual_sidewalk_band(self):\n  import runner,xml.etree.ElementTree as ET\n  cfg=json.loads((runner.ROOT/\'config.json\').read_text())\n  tree=ET.fromstring(runner.authored_scene(cfg))\n  side=tree.find("road[@id=\'3\']/lanes/laneSection/left")\n  roadway_half_width=sum(float(l.find(\'width\').get(\'a\')) for l in side.findall(\'lane\') if l.get(\'type\')==\'driving\')\n  sidewalk_width=float(side.find("lane[@type=\'sidewalk\']/width").get(\'a\'))\n  self.assertEqual(cfg[\'reference_x_m\'],-(roadway_half_width+sidewalk_width))\n  self.assertEqual(cfg[\'reference_x_m\'],-9)\n'
 return sp

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description='Rebuild and rerun partition four exact CPU proofs; never runs CARLA')
 parser.add_argument('--only',choices=['following','absolute','posted','yellow','inoperative','supplemental','all'],default='all')
 args=parser.parse_args();specs=[]
 if args.only in ('all','following'):specs.append(following())
 if args.only in ('all','absolute'):specs.append(speed(IDS[1]))
 if args.only in ('all','posted'):specs.append(posted())
 if args.only in ('all','yellow'):specs.append(yellow())
 if args.only in ('all','inoperative'):specs.append(inoperative())
 if args.only in ('all','supplemental'):specs.extend(supplemental250())
 for spec in specs:rebuild_prove(spec)
