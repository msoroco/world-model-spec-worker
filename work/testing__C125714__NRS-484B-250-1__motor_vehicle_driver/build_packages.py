"""Partition two exact-case construction; diagnostic fixture evidence is CPU-only."""
import copy,hashlib,importlib.util,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
path=ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py'
s=importlib.util.spec_from_file_location('builder',path);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
IDS=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids']
TOPICS=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws']
TIMES=[.05000000074505806,.10000000149011612,.15000000223517418]
def measurement(key,method,kind='measured'):return dict(output_key=key,method=method,kind=kind,value_type='object',inputs=['case_observation.json'])
def comparison(name,names,axis):return dict(comparison_id=name,cases=names,fixed_conditions=['Same fixed catalog cell, actor classification, route, four-camera profile and full duration','Only declared parameter changes; source factual/legal judgments retained separately'],deliberate_differences=[axis])
def finish(aid,cases,run,analysis,ms,comparisons,branches=None,scene=None):
 a=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text());seed=ROOT/'references/v6-capability'/aid
 analysis=analysis.replace('report={"format":"worker-analysis-report-v1",','report={"case_id":json.loads(required(root,"config.json").read_text())["selected_case_id"],"format":"worker-analysis-report-v1",')
 test='''import unittest,tempfile\nfrom pathlib import Path\nfrom runner import check\nfrom analyze import finalize\nclass T(unittest.TestCase):\n def test_structure(self):self.assertTrue(check()['passed'])\n def test_missing(self):\n  with tempfile.TemporaryDirectory() as t:\n   with self.assertRaisesRegex(ValueError,'Missing required source: case_observation.json'):finalize(Path(t),Path(t)/'analysis-report.json')\n'''
 spec=dict(assignment_id=aid,runner=run,analysis=analysis,test=test,cases=cases,dispositions=[dict(requirement=a['law']['text'] if i==0 else a['witness']['required_context'][min(i-1,len(a['witness']['required_context'])-1)],source=a['law']['source'] if i==0 else 'assignment.witness.required_context',evidence_or_gap='Law-specific original measurements and source-authored context are separated; actual pixels and legal judgments require local review.',measurement=m) for i,m in enumerate(ms)],negative=dict(remove=['case_observation.json'],error_contains='Missing required source: case_observation.json'),measurement_plan='Original-frame law-specific geometry/motion/signal/environment measurements; no invented legal numerical threshold.',static_checks=['Exact connected OpenDRIVE route and participant support','Four synchronized cameras and complete capture duration'],mechanisms=['Configuration-driven physical vehicle controller and original source capture','No scene replay in saved-only finalization'],limitations=['CPU fixtures demonstrate software compatibility only. Native motion, pixels, district/public-authority facts and legal judgments remain unverified.'],observation_mapping={},audits=['Audit every source packet and original frame identity','Review actual four-view subject visibility throughout approach, interaction and clearance','Inspect all stated branch-specific measurements without converting engineering uncertainty into legal standards'],comparisons=comparisons,branches=branches or [dict(name=c['comparison_id'],topic_ids=list(TOPICS[a['law_id']]['topics']),cases=c['cases'],comparison_ids=[c['comparison_id']]) for c in comparisons])
 if scene:spec['scene']=scene
 b.write(ROOT/'work'/aid/'package-spec.json',spec);f=b.build(spec)
 # Exact controlled comparison specs share the lead auditor.
 audit=[]
 for c in comparisons:
  selector=c.get('selector',ms[0]['output_key'])
  audit.append(dict(comparison_id=c['comparison_id'],case_ids=[aid+'__'+n for n in c['cases']],fixed_config_selectors=['duration_s','rate_hz','cameras'],checks=[dict(name='measured_'+c['comparison_id'],case_ids=[aid+'__'+n for n in c['cases']],selector='measurements.'+selector+'.value',operator='distinct')]))
 b.write(f/'comparison-audits.json',audit)
 return f

def make_speed():
 aid=IDS[4];seed=ROOT/'references/v6-capability'/aid;run=(seed/'runner.py').read_text();analysis=(seed/'analyze.py').read_text()
 run=run.replace('world.set_weather(carla.WeatherParameters.ClearNoon)','world.set_weather(carla.WeatherParameters(precipitation=cfg.get("precipitation",0),wetness=cfg.get("wetness",0),fog_density=cfg.get("fog_density",2),sun_altitude_angle=45))')
 run=run.replace('get_waypoint_xodr(1,1,1100)','get_waypoint_xodr(1,1,cfg.get("other_station_m",1100))')
 run=run.replace('throttle=.25,brake=0','throttle=cfg.get("other_throttle",.25),brake=0')
 run=run.replace("'roadway_width_m':7,'shoulder_each_m':1.5", "'roadway_width_m':width-3,'shoulder_each_m':1.5")
 run=run.replace("'surface':'authored synthetic asphalt'", "'surface':'authored synthetic asphalt; Native wetness '+str(world.get_weather().wetness)")
 packet=dict(law_id='NRS-484B-600-1a',diagnostic_fixture_only=True,motion_rows=[dict(frame=21714+i,ego_speed_mps=4,other_speed_mps=5,separation_m=100-i) for i in range(3)],highway_width_m=10,roadway_width_m=7,shoulder_each_m=1.5,curvature_per_m=0,surface='dry authored asphalt',surface_provenance='surface_provenance.json',weather_rows=[dict(frame=21714+i,precipitation_native=0,wetness_native=0) for i in range(3)],target_visibility_samples_m=[25,50,100,200,400],sight_ray_samples=[dict(frame=21714+i,clear_distance_m=100-i,ray_tested=True,hit_count=0) for i in range(3)],stopping_event=dict(observed=False,reason='No stop imposed; saved original speed and distance retained'))
 cases=[]
 configs=[('reference',dict(requested_speed_mps=4)),('faster',dict(requested_speed_mps=9)),('rain',dict(requested_speed_mps=4,precipitation=70,wetness=0)),('wet_surface',dict(requested_speed_mps=4,wetness=80)),('fog',dict(requested_speed_mps=4,fog_density=60)),('nearer_traffic',dict(requested_speed_mps=4,other_station_m=250)),('narrower',dict(requested_speed_mps=4))]
 for name,cfg in configs:
  p=copy.deepcopy(packet)
  for r in p['motion_rows']:r['ego_speed_mps']=cfg['requested_speed_mps'];r['separation_m']=20 if name=='nearer_traffic' else r['separation_m']
  for r in p['weather_rows']:r['precipitation_native']=cfg.get('precipitation',0);r['wetness_native']=cfg.get('wetness',0)
  if name=='wet_surface':p['surface']='authored asphalt; Native wetness 80'
  if name=='fog':p['target_visibility_samples_m']=[25,50]
  scene=(seed/'scene.xodr').read_text()
  if name=='narrower':p['highway_width_m']=8;p['roadway_width_m']=5;scene=scene.replace('a="3.5"','a="2.5"')
  cases.append(dict(name=name,rationale='Controlled '+name+' condition; no reasonable/proper speed verdict.',config=cfg,variable_assignments=dict(requested_speed_mps=dict(value=cfg['requested_speed_mps'],kind='controller',unit='m/s')),fixture={'case_observation.json':p},scene=scene))
 ms=[measurement('contemporaneous_speed_and_traffic','traffic_speed'),measurement('width_curvature_and_surface','road_conditions'),measurement('weather_visibility_sight_and_stopping_context','environment_history')]
 cs=[comparison('speed',['reference','faster'],'Requested speed only'),comparison('traffic',['reference','nearer_traffic'],'Other vehicle initial station only'),comparison('surface',['reference','wet_surface'],'Surface wetness only'),comparison('width',['reference','narrower'],'Lane width only; shoulders fixed'),comparison('weather',['reference','rain'],'Precipitation only'),comparison('visibility',['reference','fog'],'Fog density only; calibrate actual rendered target range')]
 for c in cs:c['selector']={'speed':ms[0]['output_key'],'traffic':ms[0]['output_key'],'surface':ms[1]['output_key'],'width':ms[1]['output_key'],'weather':ms[2]['output_key'],'visibility':ms[2]['output_key']}[c['comparison_id']]
 return finish(aid,cases,run,analysis,ms,cs)

def make_direction():
 aid=IDS[3];seed=ROOT/'references/v6-capability'/aid;run=(seed/'runner.py').read_text();analysis=(seed/'analyze.py').read_text()
 run=run.replace('get_waypoint_xodr(1,-1,10)','get_waypoint_xodr(1,-1,100 if cfg.get("reverse_motion") else 10)')
 run=run.replace('throttle=effort,brake=', 'throttle=effort,reverse=cfg.get("reverse_motion",False),brake=')
 geometry=dict(source='synthetic diagnostic one-way roadway',directed_roadways=[dict(polygon=[[0,-8.5],[1800,-8.5],[1800,0],[0,0]],direction_xy=[1,0],one_way=True)],physical_verification=dict(sign_pixels_verified=False))
 cases=[]
 for name,reverse in [('designated',False),('opposed_reverse',True)]:
  p=dict(law_id='NRS-484B-220-1',diagnostic_fixture_only=True,direction_sign=dict(native_id=220001,text='ONE WAY',orientation_deg=0,governs_roadway_indices=[0],original_frames=[21714,21715,21716]),one_way_lanes=[-1,-2],designated_direction_xy=[1,0],velocity_rows=[dict(frame=21714+i,velocity_xy=[-5 if reverse else 5,0]) for i in range(3)])
  rules=''.join(json.dumps(dict(time_s=t,value=dict(devices=[dict(actor_id=220001,native_name='ONE WAY',position_m=[50,-9.5,2],pixel_visibility_verified=False)])))+'\n' for t in TIMES)
  cases.append(dict(name=name,rationale='Actual signed velocity direction with heading and sign fixed.',config=dict(reverse_motion=reverse),fixture={'case_observation.json':p,'scenario_geometry.json':geometry,'scenario_rule_evidence.jsonl':rules}))
 return finish(aid,cases,run,analysis,[measurement('actual_travel_direction','direction_projection'),measurement('governing_direction_sign','sign_scope','sourced_context')],[comparison('actual_direction',['designated','opposed_reverse'],'Physical vehicle reverse flag only; measure actual velocity projection')])

if __name__=='__main__':
 fs=[]
 for name in sys.argv[1:]:fs.append(globals()['make_'+name]())
 print('\n'.join(str(f.relative_to(ROOT)) for f in fs))

def make_crossing():
 folders=[]
 for aid in IDS[:2]:
  seed=ROOT/'references/v6-capability'/aid;run=(seed/'runner.py').read_text();analysis=(seed/'analyze.py').read_text();law=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())['law_id']
  run=run.replace('get_waypoint_xodr(1,-1,340)','get_waypoint_xodr(1,-1,cfg.get("ego_station_m",340))').replace('get_waypoint_xodr(1,-1,350)','get_waypoint_xodr(1,-1,cfg.get("ego_station_m",350))')
  run=run.replace('get_waypoint_xodr(3,-1,350)','get_waypoint_xodr(3,-1,cfg.get("other_station_m",350))')
  run=run.replace('other_clear_before else 0','(other_clear_before or cfg.get("ignore_precedence",False)) else 0').replace('brake=0 if other_clear_before else 1','brake=0 if (other_clear_before or cfg.get("ignore_precedence",False)) else 1')
  if law.endswith('-2'):
   run=run.replace('ego.apply_control(carla.VehicleControl(throttle=effort,brake=max(0,min(.5,.2*(speed-cfg[\'requested_speed_mps\'])))))','ego.apply_control(carla.VehicleControl(throttle=0 if cfg.get("wait_for_other",False) and other.get_transform().location.y<7 else effort,brake=1 if cfg.get("wait_for_other",False) and other.get_transform().location.y<7 else max(0,min(.5,.2*(speed-cfg[\'requested_speed_mps\'])))))')
  analysis=analysis.replace("assert events['other']['time_s'] < events['ego']['time_s']; ","")
  packet=dict(law_id=law,diagnostic_fixture_only=True,highway_ids=[1,3],intersection_polygon=[[-7,-7],[7,-7],[7,7],[-7,7]],separate_crossing_spacing_m=35,entry_events=dict(other=dict(frame=21714,time_s=1),ego=dict(frame=21716,time_s=2)),motion_rows=[dict(frame=21714+i,ego_speed_mps=0 if i<2 else 5,other_speed_mps=5) for i in range(3)],other_clearance_time_s=1.8,ego_clearance_frame=21720,other_clearance_frame=21718,ego_approach_xy=[1,0],other_approach_xy=[0,1],crossing_id='road1-road3-opening',resolution_s=.05,official_control_inventory=[])
  geometry=dict(source='synthetic diagnostic median-opening connected crossing',physical_verification={'diagnostic_fixture_only':True,'native_pixels_verified':False},prohibited_median_polygons=[[[-400,-.5],[-20,-.5],[-20,.5],[-400,.5]],[[20,-.5],[400,-.5],[400,.5],[20,.5]]],median_opening_polygons=[[[-20,-.5],[20,-.5],[20,.5],[-20,.5]]],intersection_polygon=packet['intersection_polygon'])
  names=[('precedence',dict(ignore_precedence=False,wait_for_other=True)),('advance',dict(ignore_precedence=True,wait_for_other=False)),('other_later',dict(ignore_precedence=True,wait_for_other=False,other_station_m=320))]
  cases=[]
  for name,cfg in names:
   p=copy.deepcopy(packet)
   if name=='advance':p['entry_events']['ego']['time_s']=1.1;p['motion_rows'][0]['ego_speed_mps']=5
   if name=='other_later':p['entry_events']['ego']['time_s']=1;p['entry_events']['other']['time_s']=3;p['motion_rows'][0]['ego_speed_mps']=5
   cases.append(dict(name=name,rationale='Original crossing entry/precedence controlled contrast with complete two-vehicle histories.',config=cfg,fixture={'case_observation.json':p,'scenario_geometry.json':geometry}))
  if law.endswith('-1'):ms=[measurement('other_entered_first','earlier_entry'),measurement('same_crossing_geometry','crossing_geometry','sourced_context'),measurement('ego_yield_motion','precedence_history')]
  else:ms=[measurement('two_entry_timing','entry_time_difference'),measurement('left_right_approach_geometry','crossing_side'),measurement('crossing_precedence_motion','precedence_history')]
  cs=[comparison('crossing_precedence',['precedence','advance'],'Subject gives precedence versus advances; both original crossing histories retained'),comparison('crossing_entry_order',['advance','other_later'],'Other initial station only; measure raw entry-time difference without approximately cutoff')]
  cs[0]['selector']='ego_yield_motion' if law.endswith('-1') else 'crossing_precedence_motion';cs[1]['selector']=ms[0]['output_key']
  folders.append(finish(aid,cases,run,analysis,ms,cs))
 return folders

def make_divider():
 aid=IDS[2];seed=ROOT/'references/v6-capability'/aid;run=(seed/'runner.py').read_text();analysis=(seed/'analyze.py').read_text()
 run=run.replace('def route_points(mapping):\n route=[]','def route_points(mapping):\n cfg=json.loads((ROOT/"config.json").read_text());shift=cfg.get("crossing_shift_m",0)\n route=[]')
 run=run.replace('range(350,394,2)','range(300,394+int(shift),2)').replace('range(393,280,-2)','range(393+int(shift),240,-2)')
 # Do not change offline reference-arc assertion; construction geometry check below validates actual parametrized route.
 old='route += [(-7+5.25*math.cos(-math.pi/2+math.pi*i/40),5.25*math.sin(-math.pi/2+math.pi*i/40)) for i in range(41)]'
 run=run.replace(old,'route += [(-7+shift+5.25*math.cos(-math.pi/2+math.pi*i/40),5.25*math.sin(-math.pi/2+math.pi*i/40)) for i in range(41)]')
 run=run.replace('get_waypoint_xodr(1,-2,350)','get_waypoint_xodr(1,2 if cfg.get("wrong_initial_roadway",False) else -2,300)')
 run=run.replace("requested=command(ego,route,cfg['requested_speed_mps']);ego.apply_control(carla.VehicleControl(**requested['control']))", "requested=command(ego,route,cfg['requested_speed_mps'])\n    if cfg.get('pause_midturn',False) and 180<i<220:requested['control'].update(throttle=0,brake=1)\n    ego.apply_control(carla.VehicleControl(**requested['control']))")
 run=run.replace("moving=[r for r in rows if r['speed_mps']>1]", "moving=rows")
 run=run.replace("'opening_width_m':geometry['opening_width_m'],'trajectory':trajectory", "'opening_width_m':geometry['opening_width_m'],'trajectory':trajectory,'authority_context':cfg.get('authority_context',{'designation':'physical opening only','source':'authored test configuration; legal establishment unverified'})")
 start=analysis.index('def turn_trajectory(p):');end=analysis.index('\ndef finalize',start)
 analysis=analysis[:start]+'''def turn_trajectory(p):
    from shapely.geometry import MultiPoint,Polygon
    rows=p['trajectory'];first,last=rows[0],rows[-1]
    blockers=[Polygon(x) for x in p['barrier_polygons']]
    opening=Polygon(p['opening_polygon']);right=Polygon(p['right_roadway_polygon']);opposite=Polygon(p['opposing_roadway_polygon'])
    samples=[]
    for r in rows:
      hull=MultiPoint([v[:2] for v in r['body_vertices_m']]).convex_hull
      samples.append({'frame':r['frame'],'prohibited_divider_overlap':any(hull.intersects(x) for x in blockers),'opening_overlap':hull.intersects(opening),'right_roadway_overlap':hull.intersects(right),'opposing_roadway_overlap':hull.intersects(opposite)})
    return {'frames':len(rows),'initial_velocity_xy':first['velocity_xy'],'final_velocity_xy':last['velocity_xy'],'direction_dot':sum(a*b for a,b in zip(first['velocity_xy'],last['velocity_xy'])),'velocity_history':[r['velocity_xy'] for r in rows],'full_body_occupancy':samples,'median_body_overlap_frames':[r['frame'] for r in samples if r['prohibited_divider_overlap']]}

def authority_context(p):
    return p['authority_context']
''' +analysis[end:]
 analysis=analysis.replace("measurements['complete_uturn_movement']", "measurements['authority_establishment_context']={'method':'authority_context','value':authority_context(p),'sources':{'case_observation.json':h}}\n    measurements['complete_uturn_movement']")
 base=dict(law_id='NRS-484B-227-1',diagnostic_fixture_only=True,right_roadway_polygon=[[-400,-7],[-7,-7],[-7,-.5],[-400,-.5]],opposing_roadway_polygon=[[-400,.5],[-7,.5],[-7,7],[-400,7]],opening_polygon=[[-20,-.5],[20,-.5],[20,.5],[-20,.5]],opening_width_m=40,barrier_polygons=[[[-400,-.5],[-20,-.5],[-20,.5],[-400,.5]],[[20,-.5],[400,-.5],[400,.5],[20,.5]]])
 def box(x,y):return [[x+dx,y+dy,z] for z in [0,1.5] for dx,dy in [(-2,-.8),(-2,.8),(2,.8),(2,-.8)]]
 opts=[('opening',{}),('closed_divider',dict(crossing_shift_m=-40)),('wrong_roadway',dict(wrong_initial_roadway=True)),('paused_uturn',dict(pause_midturn=True)),('authority_crossover',dict(authority_context=dict(designation='crossover',source='authored hypothetical public-authority establishment; actual legal authority unverified'))),('authority_intersection',dict(authority_context=dict(designation='intersection',source='authored hypothetical public-authority establishment; actual legal authority unverified')))]
 cases=[]
 for name,cfg in opts:
  p=copy.deepcopy(base);shift=cfg.get('crossing_shift_m',0);p['authority_context']=cfg.get('authority_context',dict(designation='physical opening only',source='authored configuration; legal establishment unverified'))
  p['trajectory']=[dict(frame=21714+i,velocity_xy=[5,0] if i==0 else [-5,0],body_vertices_m=box(-7+shift,5.25 if i==2 else 0 if i==1 else -5.25),body_overlaps_median=False) for i in range(3)]
  if name=='wrong_roadway':p['trajectory'][0]['body_vertices_m']=box(-60,5.25)
  if name=='paused_uturn':p['trajectory'][1]['velocity_xy']=[0,0]
  cases.append(dict(name=name,rationale='Physical U-turn body geometry and explicit source context; no legal exception verdict.',config=cfg,fixture={'case_observation.json':p,'scenario_geometry.json':dict(source='synthetic diagnostic',physical_verification={'diagnostic_fixture_only':True,'native_pixels_verified':False},prohibited_median_polygons=p['barrier_polygons'],median_opening_polygons=[p['opening_polygon']])}))
 ms=[measurement('complete_uturn_movement','turn_trajectory'),measurement('right_roadway_and_opening','median_geometry','sourced_context'),measurement('authority_establishment_context','authority_context','sourced_context')]
 cs=[comparison('over_across_within_divider',['opening','closed_divider'],'U-turn center shifted longitudinally from opening to closed divider; full body overlap observes over/across/within separately from legal characterization'),comparison('right_hand_roadway',['opening','wrong_roadway'],'Initial roadway only; preserve complete reversal route'),comparison('continuous_multiple_movement',['opening','paused_uturn'],'Brief physical brake hold in original turn'),comparison('established_crossover',['opening','authority_crossover'],'Authored administrative designation/provenance only; no physical authority claim'),comparison('established_intersection',['opening','authority_intersection'],'Authored administrative designation/provenance only; no physical authority claim')]
 for c in cs:c['selector']='authority_establishment_context' if c['comparison_id'].startswith('established') else 'complete_uturn_movement'
 return finish(aid,cases,run,analysis,ms,cs)

def make_signal():
 aid=IDS[5];seed=ROOT/'references/v6-capability'/aid;run=(seed/'runner.py').read_text();analysis=(seed/'analyze.py').read_text()
 run=run.replace('world.set_weather(carla.WeatherParameters.ClearNoon)','world.set_weather(carla.WeatherParameters(precipitation=cfg.get("precipitation",0),sun_altitude_angle=45))')
 run=run.replace('ego.set_light_state(carla.VehicleLightState.RightBlinker)','ego.set_light_state(carla.VehicleLightState.NONE)')
 run=run.replace("requested=command(ego,route,cfg['requested_speed_mps']);ego.apply_control(carla.VehicleControl(**requested['control']))", "remaining_approach=max(0,-7-ego.get_transform().location.x)\n    display=remaining_approach<=cfg.get('signal_on_distance_ft',100)*.3048\n    if cfg.get('interrupt_signal',False) and 10<remaining_approach<15:display=False\n    ego.set_light_state(carla.VehicleLightState.RightBlinker if display else carla.VehicleLightState.NONE)\n    requested=command(ego,route,cfg['requested_speed_mps']);ego.apply_control(carla.VehicleControl(**requested['control']))")
 run=run.replace("'zone_designation_source':geometry['loading_zone_designation_source']", "'zone_designation_source':geometry['loading_zone_designation_source'],'threshold_ft':cfg.get('signal_reference_ft',100),'district_class':cfg.get('district_class','business'),'weather_context':{'precipitation':cfg.get('precipitation',0)}")
 analysis=analysis.replace('if remaining>=30.48:break',"if remaining>=p.get('threshold_ft',100)*.3048:break").replace("'threshold_ft':100,'threshold_m':30.48", "'threshold_ft':p.get('threshold_ft',100),'threshold_m':p.get('threshold_ft',100)*.3048")
 analysis=analysis.replace("'source':p['district_source']", "'source':p['district_source'],'district_class':p.get('district_class','business'),'weather_context':p.get('weather_context',{})")
 cases=[]
 for name,cfg in [('continuous100',dict(signal_on_distance_ft=100)),('short80',dict(signal_on_distance_ft=80)),('interrupted',dict(signal_on_distance_ft=100,interrupt_signal=True)),('rain',dict(signal_on_distance_ft=100,precipitation=70))]:
  rows=[dict(x_m=-50+i*10,y_m=-1.75) for i in range(6)];onset=[int(50-i*10<=cfg['signal_on_distance_ft']*.3048) for i in range(6)]
  if cfg.get('interrupt_signal'):onset[-2]=0
  p=dict(law_id='NRS-484B-413-2',diagnostic_fixture_only=True,road_id=1,frontage_m=120,business_use_frontage_m=90,district_source='authored diagnostic frontage; statutory status externally reviewed',turn_onset_frame=21719,path_rows=rows,indicator_rows=[dict(frame=21714+i,lamp_bits=v,pixel_luminance=80 if v else 20) for i,v in enumerate(onset)],zone_polygon=[[-50,-10],[-25,-10],[-25,-7],[-50,-7]],zone_route_distance_m=6,zone_designation_source='authored loading-zone object',district_class='business',weather_context=dict(precipitation=cfg.get('precipitation',0)),threshold_ft=100)
  cases.append(dict(name=name,rationale='Last 100-foot traveled-path intention signal contrast with weather retained.',config=cfg,fixture={'case_observation.json':p}))
 ms=[measurement('last_100ft_traveled_path','approach_path'),measurement('original_lamp_display_history','indicator_continuity'),measurement('business_district_context','district_frontage','sourced_context'),measurement('designated_zone_location','loading_zone','sourced_context')]
 cs=[comparison('business_right_distance',['continuous100','short80'],'Signal onset distance only; original body and API/pixel display evidence retained'),comparison('signal_continuity',['continuous100','interrupted'],'One signal interruption interval only'),comparison('regardless_weather',['continuous100','rain'],'Precipitation only; law threshold unchanged')]
 for c in cs:c['selector']='business_district_context' if c['comparison_id']=='regardless_weather' else 'original_lamp_display_history'
 return finish(aid,cases,run,analysis,ms,cs)

def expand_crossings():
 import xml.etree.ElementTree as ET
 for aid in IDS[:2]:
  spec=json.loads((ROOT/'work'/aid/'package-spec.json').read_text());run=spec['runner'];analysis=spec['analysis'];law=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())['law_id'];seed=ROOT/'references/v6-capability'/aid
  run=run.replace('import argparse, hashlib, json, queue,','import argparse, hashlib, json, math, queue,')
  run=run.replace('other_wp=mapping.get_waypoint_xodr(3,-1,cfg.get("other_station_m",350))','other_wp=mapping.get_waypoint_xodr(2,1,60) if cfg.get("opposite_other") else mapping.get_waypoint_xodr(3,-1,cfg.get("other_station_m",350))')
  run=run.replace('other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))','other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))\n        other.set_light_state(carla.VehicleLightState.LeftBlinker if cfg.get("other_intends_left") else carla.VehicleLightState.NONE)\n        if cfg.get("governing_control"):\n            landmarks=mapping.get_all_landmarks()\n            if not any(str(x.id)=="2509001" for x in landmarks):raise ValueError("Authored governing device missing from Native landmark inventory")\n            for actor in world.get_actors().filter("traffic.traffic_light*"):\n                actor.set_state(carla.TrafficLightState.Off if cfg.get("signal_inoperative") else carla.TrafficLightState.Green);actor.freeze(True)')
  run=run.replace('other_clear_before=min(v[1] for v in ov_before)>7','other_clear_before=(max(v[1] for v in ov_before)<-7 if cfg.get("other_makes_left") else max(v[0] for v in ov_before)<-7) if cfg.get("opposite_other") else min(v[1] for v in ov_before)>7')
  target='other_speed=other.get_velocity().length();other.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.3*(5-other_speed))),brake=max(0,min(.5,.2*(other_speed-5)))))'
  repl='''other_speed=other.get_velocity().length()
                steer=0
                if cfg.get('other_makes_left'):
                    path=[(67,1.75),(30,1.75),(10,1.75),(7,1.75),(3,1),(0,-2),(-1.75,-7),(-1.75,-40),(-1.75,-100)]
                    pose=other.get_transform();x,y=pose.location.x,pose.location.y
                    nearest=min(range(len(path)),key=lambda j:(path[j][0]-x)**2+(path[j][1]-y)**2)
                    look=path[min(nearest+1,len(path)-1)];err=(math.atan2(look[1]-y,look[0]-x)-math.radians(pose.rotation.yaw)+math.pi)%(2*math.pi)-math.pi
                    steer=max(-.7,min(.7,1.4*err))
                other.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.3*(5-other_speed))),brake=max(0,min(.5,.2*(other_speed-5))),steer=steer))'''
  assert target in run;run=run.replace(target,repl)
  run=run.replace("other_clear=next((r['time_s'] for r in history if min(v[1] for v in r['other_vertices_m'])>7),None)","other_clear=next((r['time_s'] for r in history if ((max(v[1] for v in r['other_vertices_m'])<-7 if cfg.get('other_makes_left') else max(v[0] for v in r['other_vertices_m'])<-7) if cfg.get('opposite_other') else min(v[1] for v in r['other_vertices_m'])>7)),None)")
  run=run.replace("'ego_approach_xy':[-1,0],'other_approach_xy':[0,-1]", "'ego_approach_xy':[1,0],'other_approach_xy':[-1,0] if cfg.get('opposite_other') else [0,1]")
  run=run.replace("'resolution_s':.05,", "'control_context':{'governing_control':cfg.get('governing_control','none'),'signal_inoperative':cfg.get('signal_inoperative',False),'authority':'authored synthetic authority designation; actual jurisdiction must be reviewed'},'opposite_context':{'opposite_approach':cfg.get('opposite_other',False),'controller_intends_left':cfg.get('other_intends_left',False),'controller_makes_left':cfg.get('other_makes_left',False),'driver_intent_is_not_inferred_from_lamp':True},'resolution_s':.05,")
  analysis=analysis.replace('def finalize(root,output):',"def governing_control(p):\n    return {'native_inventory':p.get('official_control_inventory',[]),'context':p.get('control_context',{'governing_control':'none'}),'opposite_context':p.get('opposite_context',{'opposite_approach':False})}\n\ndef finalize(root,output):")
  analysis=analysis.replace('measurements={}',"measurements={'governing_control_and_opposite_context':{'method':'governing_control','value':governing_control(p),'sources':{'case_observation.json':h}}}")
  packet=copy.deepcopy(spec['cases'][0]['fixture']['case_observation.json']);geometry=spec['cases'][0]['fixture']['scenario_geometry.json'];new=[]
  for name,code,off in [('official_signal','1000001',False),('official_stop','206',False),('official_yield','205',False),('inoperative_signal','1000001',True)]:
   root=ET.fromstring((seed/'scene.xodr').read_text());road=root.find("road[@id='1']");sig=ET.SubElement(road,'signals');ET.SubElement(sig,'signal',dict(id='2509001',s='375',t='-8',zOffset='2',dynamic='yes' if code=='1000001' else 'no',orientation='+',country='DEU',type=code,subtype='-1',value='0',name=name,hOffset='0',pitch='0',roll='0',height='2',width='1'))
   cfg=dict(governing_control=name,signal_inoperative=off,wait_for_other=True,ignore_precedence=False);p=copy.deepcopy(packet);p['official_control_inventory']=[dict(id=2509001,type=name)];p['control_context']=dict(governing_control=name,signal_inoperative=off,authority='authored hypothetical designation; legal jurisdiction unverified')
   new.append(dict(name=name,rationale='Official-control qualification with full original device inventory and explicit authority limitation.',config=cfg,scene=ET.tostring(root,encoding='unicode'),fixture={'case_observation.json':p,'scenario_geometry.json':geometry}))
  for name,intends,makes in [('opposite_straight',False,False),('opposite_intends_left',True,False),('opposite_makes_left',True,True)]:
   cfg=dict(opposite_other=True,other_intends_left=intends,other_makes_left=makes,wait_for_other=True,ignore_precedence=False);p=copy.deepcopy(packet);p['other_approach_xy']=[-1,0];p['opposite_context']=dict(opposite_approach=True,controller_intends_left=intends,controller_makes_left=makes,driver_intent_is_not_inferred_from_lamp=True)
   new.append(dict(name=name,rationale='Other opposite driver fixed approach with distinct intention/controller action; actual driver intention requires independent evidence.',config=cfg,fixture={'case_observation.json':p,'scenario_geometry.json':geometry}))
  spec['cases']+=new;spec['runner']=run;spec['analysis']=analysis
  spec['dispositions'].append(dict(requirement='Official-device exclusion, subsection-4 qualification, and opposite-direction intended or actual left-turn exclusions.',source='NRS 484B.250(1)/(2); with 484B.250(5)',evidence_or_gap='Original device inventory plus explicit control/authority and opposite-controller intent contexts; no legal exception automatically concluded.',measurement=measurement('governing_control_and_opposite_context','governing_control','sourced_context')))
  for name in ['official_signal','official_stop','official_yield','inoperative_signal']:
   spec['comparisons'].append(comparison(name+'_qualification',['precedence',name],'Official governing control type/state only; geometry and physical precedence controller held fixed'))
  spec['comparisons'] += [comparison('opposite_intention',['opposite_straight','opposite_intends_left'],'Other controller left-turn intention and emitted intention signal only'),comparison('opposite_actual_left',['opposite_intends_left','opposite_makes_left'],'Other physical steering route only, intention held fixed')]
  spec['branches']=[dict(name=c['comparison_id'],topic_ids=list(TOPICS[law]['topics']),cases=c['cases'],comparison_ids=[c['comparison_id']]) for c in spec['comparisons']]
  b.write(ROOT/'work'/aid/'package-spec.json',spec);f=b.build(spec)
  audits=[]
  for c in spec['comparisons']:
   key='governing_control_and_opposite_context' if c['comparison_id'] not in ['crossing_precedence','crossing_entry_order'] else ('ego_yield_motion' if law.endswith('-1') else 'crossing_precedence_motion') if c['comparison_id']=='crossing_precedence' else ('other_entered_first' if law.endswith('-1') else 'two_entry_timing')
   audits.append(dict(comparison_id=c['comparison_id'],case_ids=[aid+'__'+n for n in c['cases']],fixed_config_selectors=['duration_s','rate_hz','cameras'],checks=[dict(name=c['comparison_id'],case_ids=[aid+'__'+n for n in c['cases']],selector='measurements.'+key+'.value',operator='distinct')]))
  b.write(f/'comparison-audits.json',audits)

def bind_controls():
 bindings=[]
 catalog=json.loads((ROOT/'inputs/coverage/candidate-cells.json').read_text())['cells']
 for aid in IDS[:2]:
  spec=json.loads((ROOT/'work'/aid/'package-spec.json').read_text());original=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text())
  for name,ctl in [('official_signal','traffic_light'),('official_stop','stop_sign'),('official_yield','yield_sign'),('inoperative_signal','inoperative_signal')]:
   cell=next(c for c in catalog if (c['layout'],c['maneuver'],c['control'])==('median_opening','travel',ctl) and 'motor_vehicle_driver' in c['candidate_ego_parties'] and not any('train' in x or 'held' in x for x in c['allocated_sets']))
   newaid=f"testing__{cell['cell_id']}__{original['law_id']}__motor_vehicle_driver";folder=ROOT/'work'/newaid;folder.mkdir(exist_ok=True)
   a=copy.deepcopy(original);a.update(assignment_id=newaid,cell_id=cell['cell_id'],cell=cell,role='testing');b.write(folder/'assignment.json',a)
   source=next(c for c in spec['cases'] if c['name']==name);new=copy.deepcopy(spec);new.update(assignment_id=newaid,seed_assignment_id=aid)
   first=copy.deepcopy(source);first['name']='precedence';second=copy.deepcopy(source);second['name']='advance';second['config'].update(ignore_precedence=True,wait_for_other=False);second['fixture']['case_observation.json']['motion_rows'][0]['ego_speed_mps']=5;second['fixture']['case_observation.json']['entry_events']['ego']['time_s']=1.1
   new['cases']=[first,second];new['comparisons']=[comparison(name+'_precedence',['precedence','advance'],'Subject precedence controller only; exact '+ctl+' governance fixed')];new['branches']=[dict(name=name+'_qualification',topic_ids=list(TOPICS[a['law_id']]['topics']),cases=['precedence','advance'],comparison_ids=[name+'_precedence'])]
   b.write(folder/'package-spec.json',new);b.build(new)
   key='ego_yield_motion' if a['law_id'].endswith('-1') else 'crossing_precedence_motion'
   b.write(folder/'comparison-audits.json',[dict(comparison_id=name+'_precedence',case_ids=[newaid+'__precedence',newaid+'__advance'],fixed_config_selectors=['duration_s','rate_hz','cameras','governing_control','signal_inoperative'],checks=[dict(name='precedence_motion',case_ids=[newaid+'__precedence',newaid+'__advance'],selector='measurements.'+key+'.value',operator='distinct')])])
   bindings.append(dict(assignment_id=newaid,original_assignment_id=aid,original_cell_incompatibility='Original fixed control other_vehicle cannot supply governing '+ctl+' branch.',binding_reason='Official-device exclusion/subsection-4 qualification in compatible same-layout travel cell.'))
  spec['cases']=[c for c in spec['cases'] if c['name'] not in ['official_signal','official_stop','official_yield','inoperative_signal']]
  spec['comparisons']=[c for c in spec['comparisons'] if not c['comparison_id'].endswith('_qualification')]
  spec['branches']=[dict(name=c['comparison_id'],topic_ids=list(TOPICS[original['law_id']]['topics']),cases=c['cases'],comparison_ids=[c['comparison_id']]) for c in spec['comparisons']]
  b.write(ROOT/'work'/aid/'package-spec.json',spec);b.build(spec)
  audit=json.loads((ROOT/'work'/aid/'comparison-audits.json').read_text());b.write(ROOT/'work'/aid/'comparison-audits.json',[x for x in audit if not x['comparison_id'].endswith('_qualification')])
 b.write(ROOT/'work'/IDS[0]/'additional-bindings.json',bindings)
 return bindings

def expand_signal():
 import xml.etree.ElementTree as ET
 aid=IDS[5];base=json.loads((ROOT/'work'/aid/'package-spec.json').read_text());original=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text());catalog=json.loads((ROOT/'inputs/coverage/candidate-cells.json').read_text())['cells'];bindings=json.loads((ROOT/'work'/IDS[0]/'additional-bindings.json').read_text())
 for maneuver in ['right_turn','left_turn','change_lane']:
  ctl='freight_loading_zone' if maneuver=='right_turn' else 'other_vehicle'
  cell=next(c for c in catalog if (c['layout'],c['maneuver'],c['control'])==('paved_road',maneuver,ctl) and 'motor_vehicle_driver' in c['candidate_ego_parties'] and not any('train' in x or 'held' in x for x in c['allocated_sets']))
  newaid=f"testing__{cell['cell_id']}__{original['law_id']}__motor_vehicle_driver";folder=ROOT/'work'/newaid;folder.mkdir(exist_ok=True);a=copy.deepcopy(original);a.update(assignment_id=newaid,cell_id=cell['cell_id'],cell=cell,role='testing');b.write(folder/'assignment.json',a)
  spec=copy.deepcopy(base);spec.update(assignment_id=newaid,seed_assignment_id=aid);run=spec['runner'];analysis=spec['analysis'];scene=(ROOT/'references/v6-capability'/aid/'scene.xodr').read_text()
  if maneuver=='left_turn':
   left=ET.parse(ROOT/'references/v6-capability'/IDS[0].replace('C125714__NRS-484B-250-1','C109705__NRS-484B-400-2a')/'scene.xodr').getroot()
   old=ET.fromstring(scene);objects=old.find("road[@id='1']/objects")
   if objects is not None:left.find("road[@id='1']").append(copy.deepcopy(objects))
   scene=ET.tostring(left,encoding='unicode')
   start=run.index('def check():');end=run.index('\ndef route_points',start)
   run=run[:start]+'''def check():
 cfg=json.loads((ROOT/'config.json').read_text());root=ET.parse(ROOT/'scene.xodr').getroot();roads={r.get('id'):r for r in root.findall('road')}
 assert {'1','2','3','4','13'}<=set(roads)
 assert roads['13'].find('link/predecessor').get('elementId')=='1' and roads['13'].find('link/successor').get('elementId')=='4'
 assert cfg['duration_s']==50 and len(cfg['cameras'])==4
 return {'passed':True,'left_turn_connected':True,'physical_motion_verified':False}
''' +run[end:]
   run=run.replace("[(1,range(280,393,2),-1),(14,[i*10.995574287564276/20 for i in range(21)],-1),(3,range(393,339,-2),1)]","[(1,range(280,393,2),-1),(13,[i*10.995574287564276/20 for i in range(21)],-1),(4,range(2,102,2),-1)]")
   run=run.replace('carla.VehicleLightState.RightBlinker','carla.VehicleLightState.LeftBlinker').replace("r['road_id']==14","r['road_id']==13")
  elif maneuver=='change_lane':
   start=run.index('def route_points(mapping):');end=run.index('\ndef command',start)
   run=run[:start]+'''def route_points(mapping):
 route=[]
 for station in range(280,393):
  a=mapping.get_waypoint_xodr(1,-1,float(station));b=mapping.get_waypoint_xodr(1,-2,float(station))
  if a is None or b is None:raise ValueError('Native lane-change route missing')
  fraction=max(0,min(1,(station-370)/20));route.append((a.transform.location.x,a.transform.location.y*(1-fraction)+b.transform.location.y*fraction))
 for road,stations in [(11,range(0,14)),(2,range(0,100))]:
  for station in stations:
   a=mapping.get_waypoint_xodr(road,-2,float(station))
   if a is None:raise ValueError('Native lane-change departure missing')
   route.append((a.transform.location.x,a.transform.location.y))
 return route
''' +run[end:]
   run=run.replace("'road_id':None if wp is None else wp.road_id,'position_m'", "'road_id':None if wp is None else wp.road_id,'lane_id':None if wp is None else wp.lane_id,'position_m'")
   run=run.replace("r['road_id']==14","r.get('lane_id')==-2")
   run=run.replace('remaining_approach=max(0,-7-ego.get_transform().location.x)','remaining_approach=max(0,-30-ego.get_transform().location.x)')
  # Fixed other_vehicle requires an actual separately acquired actor; its stationary body remains out of the ego route.
  if ctl=='other_vehicle':
   run=run.replace('ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))',"ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))\n  other=world.spawn_actor(world.get_blueprint_library().find('vehicle.tesla.model3'),mapping.get_waypoint_xodr(2,-2,20).transform);owned.append(other);other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))")
   run=run.replace("'control':requested,'camera_originals':originals", "'other_body_vertices_m':[[v.x,v.y,v.z] for v in other.bounding_box.get_world_vertices(other.get_transform())],'control':requested,'camera_originals':originals")
  run=run.replace("'district_source':geometry['district_source']", "'district_source':cfg.get('district_source',geometry['district_source'])")
  cases=[];comparisons=[]
  districts=['residence','other_area'] if maneuver=='right_turn' else ['business','residence','other_area']
  for district in districts:
   threshold=300 if district=='other_area' else 100
   for short in [False,True]:
    name=district+('_short' if short else '_continuous');cfg=dict(signal_on_distance_ft=threshold-20 if short else threshold,signal_reference_ft=threshold,district_class=district,district_source='Authored synthetic '+district+' highway frontage/use context; actual statutory district classification requires source review',course=maneuver)
    p=copy.deepcopy(base['cases'][0]['fixture']['case_observation.json']);p.update(district_class=district,district_source=cfg['district_source'],threshold_ft=threshold,frontage_m=120,business_use_frontage_m=90 if district=='business' else 0)
    rows=[dict(x_m=-110+i*10,y_m=-1.75) for i in range(12)];p['path_rows']=rows;p['indicator_rows']=[dict(frame=21714+i,lamp_bits=int(110-i*10<=cfg['signal_on_distance_ft']*.3048),pixel_luminance=80) for i in range(12)];p['turn_onset_frame']=21725
    cases.append(dict(name=name,rationale=district+' '+maneuver+' statutory signal-distance contrast; original signal display and complete path retained.',config=cfg,fixture={'case_observation.json':p},scene=scene))
   comparisons.append(comparison(district+'_'+maneuver+'_distance',[district+'_continuous',district+'_short'],'Signal onset distance only; exact '+str(threshold)+'ft statutory reference, district and course fixed'))
  spec.update(cases=cases,runner=run,analysis=analysis,comparisons=comparisons,branches=[dict(name=c['comparison_id'],topic_ids=list(TOPICS[a['law_id']]['topics']),cases=c['cases'],comparison_ids=[c['comparison_id']]) for c in comparisons])
  # Exact law text applies to each case; inherited right-turn/business witness rows do not.
  spec['dispositions']=[dict(requirement=original['law']['text'],source=original['law']['source'],evidence_or_gap='Saved traveled path and signal continuity at the selected course-change engineering reference; actual legal onset/district judgments remain separate.',measurement=measurement('last_100ft_traveled_path','approach_path')),dict(requirement='Intention signal continuity before course change, including original display evidence.',source=original['law']['source'],evidence_or_gap='Original API lamp bits and unclassified body photometry are retained; emitted lamp pixels require independent audit.',measurement=measurement('original_lamp_display_history','indicator_continuity')),dict(requirement='District class, highway and frontage/building-use source facts; statutory threshold is 100 feet in business or residence and 300 elsewhere.',source=original['law']['source'],evidence_or_gap='Authored district context and threshold source retained without legal district acceptance.',measurement=measurement('business_district_context','district_frontage','sourced_context'))]
  b.write(folder/'package-spec.json',spec);b.build(spec)
  b.write(folder/'comparison-audits.json',[dict(comparison_id=c['comparison_id'],case_ids=[newaid+'__'+n for n in c['cases']],fixed_config_selectors=['duration_s','rate_hz','cameras','district_class','signal_reference_ft','course'],checks=[dict(name='original_signal_continuity',case_ids=[newaid+'__'+n for n in c['cases']],selector='measurements.original_lamp_display_history.value',operator='distinct')]) for c in comparisons])
  bindings.append(dict(assignment_id=newaid,original_assignment_id=aid,original_cell_incompatibility='Original fixed business_district/right_turn cannot support '+','.join(districts)+'/'+maneuver+' alternatives.',binding_reason='Paved road does not fix district; exact compatible maneuver and control retained. District uses/frontage are case-specific sourced context.'))
 b.write(ROOT/'work'/IDS[0]/'additional-bindings.json',bindings)
 return bindings
