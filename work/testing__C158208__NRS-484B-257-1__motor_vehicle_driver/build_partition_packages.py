"""Partition 3 exact CPU package preparation. Does not import or contact CARLA."""
import copy,hashlib,importlib.util,json,math,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BP=ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py'
sp=importlib.util.spec_from_file_location('builder',BP);B=importlib.util.module_from_spec(sp);sp.loader.exec_module(B)
S=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())
OWNER=Path(__file__).parent
HELPERS={n+'.py':(ROOT/'references'/ (n+'.py')).read_text() for n in ['pipeline_capture','scene_graph_collector','original_observations']}
def lines(v):
 mapping=[json.loads(x) for x in (ROOT/'runtime/main-pipeline-v1/fixtures/retained-speed/video_frames.jsonl').read_text().splitlines()]
 out=[]
 for value in v:
  x=copy.deepcopy(value)
  if x.get('frame') in (1,2,3):m=mapping[x['frame']-1];x['frame']=m['carla_frame'];x['time_s']=m['time_s']
  out.append(x)
 return ''.join(json.dumps(x)+'\n' for x in out)
def body(x,y=0,z=0,half=2,width=.9):return [[x+dx,y+dy,z+dz] for dx in [-half,half] for dy in [-width,width] for dz in [0,1.5]]
def metadata(law,methods,inputs):
 rows=[]
 for i,(tid,t) in enumerate(S['laws'][law]['topics'].items()):
  req=t['text'] if isinstance(t['text'],str) else t['text']['requirement'];lower=req.lower()
  if law.startswith('NRS-484B-257'):
   method='nearest_visible_point' if any(x in lower for x in ['nearest point','view of approaching','sightline']) and not any(x in lower for x in ['stop or yield','shall stop','exclude']) else 'control_and_response_history' if any(x in lower for x in ['police','officer','signal control','controlled by']) else 'governing_control' if any(x in lower for x in ['proper sign','proper yield-sign','proper stop-sign','neither','absence of a clearly marked']) else 'stop_and_yield_history'
  elif law=='NRS-484B-127-2':method='truck_width_and_lanes' if any(x in lower for x in ['80 inches','lane availability','one available','two or more lanes','one available travel lane']) and not any(x in lower for x in ['shall','500 feet','overtaking']) else 'following_space_context'
  elif law=='NRS-484B-407':method='visibility_500ft' if any(x in lower for x in ['raw visibility','raw visibility evidence','both approach directions']) else 'turn_and_visibility'
  else:method='crosswalk_context' if any(x in lower for x in ['classification','driver attribution','residence-district','residence district','highway boundaries']) and not any(x in lower for x in ['motion','footprint','backing']) else 'reverse_crosswalk_overlap'
  if law=='NRS-484B-127-2' and 'momentary closure' in req:req='This shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles; no post-overtake grace duration is supplied by this law.'
  if law=='NRS-484B-113-2' and 'violation is the instant' in req:req='Measure original reversing motion, body-region overlap and path progression around the street corner; preserve statutory contact and boundary judgments without adopting an engineering event as a legal violation.'
  rows.append(dict(requirement=req,source=t['source']+':'+tid,evidence_or_gap='Executed saved '+method+' preserves original source values; statutory judgment and original pixels remain local checks.',measurement=dict(output_key='requirement_'+str(i),method=method,kind='sourced_context' if method in ['governing_control','crosswalk_context','curve_grade_context','truck_width_and_lanes'] else 'measured',value_type='object',inputs=inputs[method])))
 return rows

def alias_analysis(source,ds):
 marker=" output.write_text(json.dumps({'format':'worker-analysis-report-v1'"
 # All seed finalizers create values immediately before output. Add source-bound requirement aliases.
 pos=source.index(marker)
 aliases=''
 for d in ds:
  m=d['measurement'];aliases+=" values["+repr(m['output_key'])+"]={'method':"+repr(m['method'])+",'value':"+m['method']+"(root),'sources':{n:hashlib.sha256(required(root,n).read_bytes()).hexdigest() for n in "+repr(m['inputs'])+"}}\n"
 return source[:pos]+aliases+source[pos:]

def base_spec(aid,ds):
 return dict(assignment_id=aid,dispositions=ds,measurement_plan='Law-specific original full-body motion, geometry, control and source context; exact saved finalizer outputs for every source topic.',static_checks=['connected route geometry','four synchronized camera profile','exact-case diagnostic finalizer outputs','negative missing-law-packet failure'],mechanisms=['prospective physical control only','original synchronized body vertices and Native observations','saved-only finalization and converter pipeline'],limitations=['CPU fixtures establish executable software compatibility only. No Native execution, pixels, Core/video acceptance or legal compliance.','Finite sampled body/ray measurements do not define statutory contact, danger, immediate hazard, cautious proceeding or visibility.'],observation_mapping={},audits=['Review all original source ticks and four views for bodies, governance, markings and occlusion.','Review complete startup, approach, interaction, clearance and final observation.','Compare measured deliberate variable and all fixed conditions; retain uncertainty without legal verdict.'],extra_files=HELPERS.copy(),reference_paths=['references/catalog.json'],cases=[],comparisons=[],branches=[],test='')

def comparison(spec,law,key,names,diff,fixed):
 spec['comparisons'].append(dict(comparison_id=key,cases=names,fixed_conditions=fixed,deliberate_differences=diff))
 spec['branches'].append(dict(name=key,topic_ids=list(S['laws'][law]['topics']),cases=names,comparison_ids=[key]))

def prepare_113():
 law='NRS-484B-113-2';aid=S['laws'][law]['original_assignment_id'];seed=ROOT/'references/v6-capability'/aid
 ds=metadata(law,['reverse_crosswalk_overlap','crosswalk_context'],{'reverse_crosswalk_overlap':['reverse_history.jsonl','crosswalk_context.json'],'crosswalk_context':['crosswalk_context.json']})
 analysis=(seed/'analyze.py').read_text()
 analysis=analysis.replace("stripe=box(west,south,east,north);samples=[]","stripe=box(west,south,east,north);samples=[]\n region=box(*context.get('intersection_xy_m',[-7,-7,7,7]))\n corner=context.get('corner_xy_m',[0,0])")
 analysis=analysis.replace("'reverse_control':bool(row['reverse_control'])}","'reverse_control':bool(row['reverse_control']),'intersection_overlap_m2':body.intersection(region).area,'heading_deg':row['heading_deg'],'centroid_xy_m':[body.centroid.x,body.centroid.y],'corner_bearing_deg':math.degrees(math.atan2(body.centroid.y-corner[1],body.centroid.x-corner[0])),'corner_distance_m':body.centroid.distance(__import__('shapely.geometry',fromlist=['Point']).Point(*corner)),'corner_approach_gate_overlap':body.intersects(box(*context.get('corner_approach_gate_xy_m',[-8,-3,-7,3]))),'corner_departure_gate_overlap':body.intersects(box(*context.get('corner_departure_gate_xy_m',[-3,7,3,8])))}")
 analysis=analysis.replace("'maximum_body_overlap_area_m2':max", "'intersection_backing_frames':[r['frame'] for r in samples if r['reverse_control'] and r['signed_forward_velocity_mps']<0 and r['intersection_overlap_m2']>0],\n  'intersection_entry_transitions':[{'before_frame':a['frame'],'entry_frame':b['frame']} for a,b in zip(samples,samples[1:]) if a['intersection_overlap_m2']==0 and b['intersection_overlap_m2']>0 and b['reverse_control'] and b['signed_forward_velocity_mps']<0],\n  'street_corner_progression':{'corner_xy_m':corner,'approach_gate':context.get('corner_approach_gate_xy_m',[-7,-3,-6,3]),'departure_gate':context.get('corner_departure_gate_xy_m',[-3,7,3,8]),'approach_gate_frames':[r['frame'] for r in samples if r['corner_approach_gate_overlap']],'departure_gate_frames':[r['frame'] for r in samples if r['corner_departure_gate_overlap']],'body_centroid_bearings_deg':[r['corner_bearing_deg'] for r in samples],'body_centroid_xy_m':[r['centroid_xy_m'] for r in samples],'nearest_corner_distance_m':min(r['corner_distance_m'] for r in samples),'bearing_change_deg':sum((b['corner_bearing_deg']-a['corner_bearing_deg']+180)%360-180 for a,b in zip(samples,samples[1:]))},'backing_heading_range_deg':max(r['heading_deg'] for r in samples)-min(r['heading_deg'] for r in samples),'crosswalk_definition':context.get('crosswalk_definition','marked'),'retained_region_context':context,'maximum_body_overlap_area_m2':max")
 analysis=alias_analysis(analysis,ds)
 runner=(seed/'runner.py').read_text().replace('argparse,hashlib','argparse,math,hashlib')
 runner=runner.replace("  from crosswalk_markings import spawn,observe\n",'')
 runner=runner.replace(" from crosswalk_markings import spawn,observe\n",'')
 runner=runner.replace("  markings=spawn(carla,world,False);owned.extend(markings)","  from physical_regions import spawn,observe\n  markings=spawn(carla,world,cfg['crosswalk_definition']);owned.extend(markings)")
 runner=runner.replace("  if len(inventory)!=80:raise ValueError('Incomplete physical crosswalk stripe inventory')","  if cfg['crosswalk_definition']=='marked' and not inventory:raise ValueError('Incomplete physical crosswalk stripe inventory')")
 runner=runner.replace("'band_xy_m':[-8.45,-7.05,-7,7],","'band_xy_m':[-8.45,-7.05,-7,7],'intersection_xy_m':[-7,-7,7,7],'corner_xy_m':[-7,7],'street_boundary_segments_xy_m':[[[-400,7],[-7,7]],[[-7,7],[-7,400]]],'crosswalk_definition':cfg['crosswalk_definition'],'sidewalk_lateral_connections_m':cfg.get('sidewalk_lateral_connections_m',[]),")
 runner=runner.replace("  for spec in cfg['cameras']:","  context=json.loads((out/'crosswalk_context.json').read_text());context.update(subject={'actor_id':ego.id,'blueprint':ego.type_id,'classification_context':'conventional motor vehicle; statutory qualification remains source review'},driver_attribution={'role':'authored conventional driver','physical_control_source':'reverse_history.jsonl original applied controls; legal attribution not established'},highway_context={'district':'authored residence district','boundary_source':'scene.xodr roadway edge geometry','public_dedication':'authored context, not independently verified'});(out/'crosswalk_context.json').write_text(json.dumps(context))\n  for spec in cfg['cameras']:",1)
 runner=runner.replace("  start=world.get_snapshot().timestamp.elapsed_seconds","  start=world.get_snapshot().timestamp.elapsed_seconds;route_index=0")
 start=runner.index("    before=ego.get_transform();speed=");end=runner.index("    frame=world.tick();",start)
 runner=runner[:start]+'''    before=ego.get_transform();speed=ego.get_velocity().length();route=cfg['motion_route_xy_m']
    target=route[min(route_index,len(route)-1)];distance=math.hypot(target[0]-before.location.x,target[1]-before.location.y)
    if distance<1 and route_index<len(route)-1:route_index+=1;target=route[route_index];distance=math.hypot(target[0]-before.location.x,target[1]-before.location.y)
    reverse=not (cfg.get('forward_after_reverse') and i>=cfg['forward_switch_tick'])
    desired_heading=math.degrees(math.atan2(target[1]-before.location.y,target[0]-before.location.x))+(180 if reverse else 0)
    error=(desired_heading-before.rotation.yaw+180)%360-180
    steer=max(-.7,min(.7,error/50))*(-1 if reverse else 1)
    desired=min(2.0,distance*.6) if route_index<len(route)-1 or distance>1 else 0;effort=desired-speed
    ego.apply_control(carla.VehicleControl(reverse=reverse,steer=steer,throttle=max(0,min(.4,.4*effort)),brake=max(0,min(.8,-.5*effort)),hand_brake=desired==0 and speed<.05))
''' +runner[end:]
 spec=base_spec(aid,ds);spec.update(runner=runner,analysis=analysis,negative={'remove':['reverse_history.jsonl'],'error_contains':'Missing required source: reverse_history.jsonl'})
 marking=(ROOT/'references/accepted-sources/C111325/stop257_markings_v2.py').read_text();marking=marking[:marking.index('def spawn(')]+'''def spawn(carla,world,definition):
 actors=[];bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
 # Marked crossing uses actual mesh stripes; sidewalk-derived crossing uses raised walkway edges.
 for i in range(80):
  if definition=='marked':x=-8.25+(i%4)*.35;y=-6.8+(i//4)*.7;z=.002
  else:x=-8.25+(i%4)*.35;y=(-9.8+(i//4)*.3 if i<40 else 7.1+((i-40)//4)*.3);z=.15
  actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0],y=y,z=z)));actor.set_simulate_physics(False);actor.set_collisions(False);actors.append(actor)
 return actors

def observe(actors):
 return [{'actor_id':a.id,'asset':a.attributes.get('mesh_path'),'position_m':[a.get_location().x,a.get_location().y,a.get_location().z],'body_vertices_m':[[p.x,p.y,p.z] for p in a.bounding_box.get_world_vertices(a.get_transform())]} for a in actors]
'''
 spec['extra_files']['physical_regions.py']=marking
 definitions=[('marked_crosswalk',True,'marked',[[-4,1.75]],False),('clear_marked',False,'marked',[[-15,1.75]],False),('intersection',True,'marked',[[4,1.75]],False),('clear_intersection',False,'marked',[[-11,1.75]],False),('sidewalk_crosswalk',True,'sidewalk_derived',[[-4,1.75]],False),('clear_sidewalk',False,'sidewalk_derived',[[-15,1.75]],False),('street_corner',True,'marked',[[-4,1.75],[0,4],[0,18]],False),('clear_corner',False,'marked',[[-4,1.75]],False),('forward_overlap',False,'marked',[[-14,1.75],[4,1.75]],True)]
 for name,hit,definition,route,forward in definitions:
  xy=[-7 if hit else -15,-3 if name=='street_corner' else 1.75];verts=body(*xy)
  fixture={'crosswalk_context.json':{'band_xy_m':[-8.45,-7.05,-7,7],'intersection_xy_m':[-7,-7,7,7],'corner_xy_m':[-7,7],'street_boundary_segments_xy_m':[[[-400,7],[-7,7]],[[-7,7],[-7,400]]],'crosswalk_definition':definition,'physical_marking_source':'DIAGNOSTIC authored region, never physical evidence','band_source':'fixture','non_alley_intersection':True,'subject':{'actor_id':100,'blueprint':'vehicle.lincoln.mkz_2020','classification_context':'DIAGNOSTIC conventional motor vehicle'},'driver_attribution':{'role':'DIAGNOSTIC authored conventional driver','legal_attribution_established':False},'highway_context':{'district':'DIAGNOSTIC authored residence district','public_dedication':'authored source context, not independently verified'}},'reverse_history.jsonl':lines([{'frame':i,'time_s':i*.05,'body_vertices_m':body(*(([-12,1.75],[-4,1.75],[0,12])[i-1] if name=='street_corner' else ([-12,1.75],[-4,1.75],[-4,1.75])[i-1] if name=='clear_corner' else ([[-14,1.75],[-7,1.75],[4,1.75]][i-1] if name=='intersection' else [-20+3*i,1.75] if not hit else [-16+4*i,1.75]))),'heading_deg':180 if name!='street_corner' else 180+(i-1)*35,'velocity_mps':([-math.cos(math.radians(180+(i-1)*35)),-math.sin(math.radians(180+(i-1)*35)),0] if name=='street_corner' else [1 if not forward else -1,0,0]),'reverse_control':not forward} for i in [1,2,3]])}
  spec['cases'].append(dict(name=name,rationale='Measure '+name+' with synchronized signed motion, body region overlap and heading; no statutory verdict.',config={'crosswalk_definition':definition,'motion_route_xy_m':route,'forward_after_reverse':forward,'forward_switch_tick':160,'sidewalk_lateral_connections_m':[[-8.45,-7],[-7.05,7]] if definition=='sidewalk_derived' else []},fixture=fixture))
 for key,names in [('marked_crosswalk',['marked_crosswalk','clear_marked']),('intersection',['intersection','clear_intersection']),('sidewalk_derived_crosswalk',['sidewalk_crosswalk','clear_sidewalk']),('street_corner',['street_corner','clear_corner']),('simultaneous_backing_overlap',['marked_crosswalk','forward_overlap'])]:comparison(spec,law,key,names,['reverse destination or signed movement at crossing'],['same fixed residence district, reverse task, marked control and ordinary vehicle','same 35s four-view capture and region geometry'])
 for d in spec['dispositions']:
  if 'marked pedestrian crossing' in d['requirement'].lower():d['cases']=[c['name'] for c in spec['cases'] if c['config']['crosswalk_definition']=='marked']
 spec['test']="""import json,tempfile,unittest
from pathlib import Path
import analyze
class MeasurementTests(unittest.TestCase):
 def test_saved_entry_corner_and_simultaneity(self):
  def body(x,y):return [[x+a,y+b,z] for a in [-2,2] for b in [-1,1] for z in [0,2]]
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'crosswalk_context.json').write_text(json.dumps({'band_xy_m':[-8.45,-7.05,-7,7],'intersection_xy_m':[-7,-7,7,7],'corner_xy_m':[-7,7]}))
   rows=[{'frame':i,'time_s':i*.05,'body_vertices_m':body(x,y),'heading_deg':180,'velocity_mps':[1,0,0],'reverse_control':True} for i,x,y in [(1,-12,1.75),(2,-7,1.75),(3,0,10)]]
   (p/'reverse_history.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in rows))
   value=analyze.reverse_crosswalk_overlap(p)
   self.assertEqual(value['intersection_entry_transitions'][0]['entry_frame'],2)
   self.assertGreater(abs(value['street_corner_progression']['bearing_change_deg']),1)
   self.assertEqual(value['backing_overlap_original_frames'],[2])
   for r in rows:r['reverse_control']=False
   (p/'reverse_history.jsonl').write_text(''.join(json.dumps(r)+'\\n' for r in rows))
   self.assertEqual(analyze.reverse_crosswalk_overlap(p)['backing_overlap_original_frames'],[])
   (p/'reverse_history.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source: reverse_history.jsonl'):analyze.reverse_crosswalk_overlap(p)
"""
 return spec

if __name__=='__main__' and '--407' not in sys.argv and '--127' not in sys.argv and '--257' not in sys.argv:
 spec=prepare_113();B.write(OWNER/'spec-113.json',spec);folder=B.build(spec)
 if '--prove' in sys.argv:B.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')
 print(folder)

def prepare_407():
 law='NRS-484B-407';aid=S['laws'][law]['original_assignment_id'];seed=ROOT/'references/v6-capability'/aid
 ds=metadata(law,['curve_grade_context','visibility_500ft','turn_motion','turn_and_visibility'],{'curve_grade_context':['curve_context.json'],'visibility_500ft':['visibility_samples.jsonl'],'turn_motion':['turn_history.jsonl'],'turn_and_visibility':['curve_context.json','visibility_samples.jsonl','turn_history.jsonl']})
 spec=base_spec(aid,ds);runner=(seed/'runner.py').read_text();analysis=alias_analysis((seed/'analyze.py').read_text().replace("'speed_mps':r['speed_mps']}","'speed_mps':r['speed_mps'],'reverse_control':r.get('reverse_control',False)}").replace('def finalize(root,output):',"def turn_and_visibility(root):\n return {'location':curve_grade_context(root),'bidirectional_visibility':visibility_500ft(root),'opposite_direction_motion':turn_motion(root)}\n\ndef finalize(root,output):"),ds)
 runner=runner.replace("for role,lane,station in [('ego',-1,650),('ahead_opposing',1,760),('behind_same_direction',-1,530)]:","for role,lane,station in [('ego',-1,cfg['turn_station_m']-35),('ahead_opposing',1,cfg['turn_station_m']+110),('behind_same_direction',-1,cfg['turn_station_m']-120)]:")
 runner=runner.replace("  for _ in range(20):world.tick()","  from native_occluder import spawn\n  occluders=spawn(carla,world,map_,cfg);owned.extend(occluders)\n  for _ in range(20):world.tick()")
 runner=runner.replace("'native_road_id':1,","'native_road_id':1,'subject_actor_id':actors['ego'].id,'subject_blueprint':actors['ego'].type_id,'driver_attribution_context':'Authored ordinary conventional driver; original applied controls and legal attribution require review','turn_station_m':cfg['turn_station_m'],'location_kind':cfg['location_kind'],'occluder_inventory':[{'actor_id':a.id,'type_id':a.type_id,'position_m':[a.get_location().x,a.get_location().y,a.get_location().z],'extent_m':[a.bounding_box.extent.x,a.bounding_box.extent.y,a.bounding_box.extent.z]} for a in occluders],")
 runner=runner.replace("hits=world.cast_ray(eye,target)","targets=list(ego.bounding_box.get_world_vertices(t));body_rays=[]\n     for point in targets:\n      original_hits=world.cast_ray(eye,point);blocked=[h for h in original_hits if not other.bounding_box.contains(h.location,ot) and not ego.bounding_box.contains(h.location,t)]\n      body_rays.append({'target_body_vertex_m':[point.x,point.y,point.z],'raw_hit_locations_m':[[h.location.x,h.location.y,h.location.z] for h in original_hits],'blocker_count':len(blocked),'clear':not bool(blocked)})\n     hits=[h for ray in body_rays for h in ray['raw_hit_locations_m']]")
 runner=runner.replace("'clear_ray':not bool(hits),'ray_hit_count':len(hits),", "'clear_ray':any(ray['clear'] for ray in body_rays),'body_vertex_rays':body_rays,'ray_hit_count':len(hits),")
 runner=runner.replace("'turn_started':turn_started,","'reverse_control':ego.get_control().reverse,'turn_started':turn_started,")
 runner=runner.replace("wp.s>=685","wp.s>=cfg['turn_station_m']")
 runner=runner.replace("if turn_started and abs(turn_degrees)<175:control=carla.VehicleControl(throttle=.23,steer=.7,brake=0)","if turn_started and abs(turn_degrees)<175:\n     reverse=cfg.get('discontinuous') and 85<abs(turn_degrees)<160\n     control=carla.VehicleControl(throttle=.23,steer=-.7 if reverse else .7,brake=0,reverse=bool(reverse))")
 spec.update(runner=runner,analysis=analysis,negative={'remove':['visibility_samples.jsonl'],'error_contains':'Missing required source: visibility_samples.jsonl'})
 spec['extra_files']['native_occluder.py']='''def spawn(carla,world,map_,cfg):
 actors=[]
 for direction in cfg['occluded_directions']:
  station=cfg['turn_station_m']+(55 if direction=='ahead_opposing' else -55)
  wp=map_.get_waypoint_xodr(1,-1,station)
  options=list(world.get_blueprint_library().filter('static.prop.*container*'))
  if not options:raise ValueError('Native occluder blueprint unavailable: static.prop.*container*')
  bp=options[0];pose=wp.transform;pose.location.z+=2
  actor=world.spawn_actor(bp,pose);actor.set_simulate_physics(False);actors.append(actor)
 return actors
'''
 for location,station in [('curve',615),('approach_to_crest',710),('near_crest',748)]:
  for variant,occluded in [('clear',[]),('ahead_blocked',['ahead_opposing']),('behind_blocked',['behind_same_direction'])]:
   name=location+'_'+variant
   fixture={'curve_context.json':{'native_road_id':1,'curvature_per_m':.004,'turn_station_m':station,'location_kind':location,'source':'DIAGNOSTIC geometry, not physical evidence','driver_eye_height_m':1.5,'visibility_reference_ft':500},'visibility_samples.jsonl':lines([{'frame':i,'time_s':i*.05,'approach':direction,'route_distance_m':dist,'clear_ray':direction not in occluded,'observer_eye_m':[station+dist,0,1.5],'subject_target_m':[station,0,1.5]} for i,dist in [(1,150),(2,100),(3,50)] for direction in ['ahead_opposing','behind_same_direction']]),'turn_history.jsonl':lines([{'frame':i,'time_s':i*.05,'road_station_m':station,'heading_deg':heading,'cumulative_heading_change_deg':heading,'speed_mps':2,'body_vertices_m':body(station),'turn_started':True} for i,heading in [(1,0),(2,90),(3,180)]])}
   spec['cases'].append(dict(name=name,rationale='Compare original sight samples for '+location+' and '+variant+' across statutory 500-foot range in both approach directions.',config={'location_kind':location,'turn_station_m':station,'occluded_directions':occluded,'discontinuous':False},fixture=fixture))
  for direction,variant in [('ahead_opposing','ahead_blocked'),('behind_same_direction','behind_blocked')]:comparison(spec,law,location+'_'+direction,[location+'_clear',location+'_'+variant],['one direction physical occluder inventory'],['same reversal, location station, eye geometry and other-direction ray acquisition','same four-view 45s capture','500ft statutory distance retained exactly; no visibility pixel rule invented'])
 extra=copy.deepcopy(spec['cases'][1]);extra['name']='curve_multipoint';extra['config']['discontinuous']=True;extra['fixture']['turn_history.jsonl']=lines([dict(r,reverse_control=r['frame'] in (2,21715)) for r in map(json.loads,extra['fixture']['turn_history.jsonl'].splitlines())]);extra['rationale']='Opposite-direction turn accomplished by multiple movements; acquire heading, reverse control and visibility.';spec['cases'].append(extra)
 comparison(spec,law,'discontinuous_reversal',['curve_ahead_blocked','curve_multipoint'],['continuous versus multiple opposite-direction turning movements'],['same curve station and occluder','same other actors, visibility ranges and cameras'])
 spec['test']='''import tempfile,unittest,json
from pathlib import Path
import analyze
class VisibilityTests(unittest.TestCase):
 def test_two_directions_and_500ft_range(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);rows=[{'frame':1,'route_distance_m':152.4,'approach':a,'clear_ray':False} for a in ['ahead_opposing','behind_same_direction']]
   (p/'visibility_samples.jsonl').write_text(''.join(json.dumps(x)+'\\n' for x in rows))
   v=analyze.visibility_500ft(p);self.assertEqual(len(v['within_500ft_samples']),2);self.assertEqual(v['500ft_m'],152.4)
   (p/'visibility_samples.jsonl').unlink()
   with self.assertRaisesRegex(ValueError,'Missing required source: visibility_samples.jsonl'):analyze.visibility_500ft(p)
'''
 return spec

if __name__=='__main__' and '--407' in sys.argv:
 spec=prepare_407();B.write(OWNER/'spec-407.json',spec);folder=B.build(spec)
 if '--prove' in sys.argv:B.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')
 print(folder)

def supplemental(original,cell_id):
 a=json.loads((ROOT/'inputs'/original/'assignment.json').read_text());c=next(c for c in json.loads((ROOT/'inputs/coverage/candidate-cells.json').read_text())['cells'] if c['cell_id']==cell_id)
 assert a['actor'] in c['candidate_ego_parties'] and not {'full-train','held-out','full-heldout'}&set(c['allocated_sets']);aid=original.replace('__'+a['cell_id']+'__','__'+cell_id+'__');a['assignment_id']=aid;a['cell_id']=cell_id;a['cell']=c;a['role']='testing';B.write(ROOT/'work'/aid/'assignment.json',a);return aid

def prepare_127(overtake=False):
 law='NRS-484B-127-2';original=S['laws'][law]['original_assignment_id'];aid=supplemental(original,'C149752') if overtake else original;seed=ROOT/'references/v6-capability'/original
 methods=['body_gap','truck_width_and_lanes','entry_space_history','following_space_context'];inputs={'body_gap':['truck_history.jsonl'],'truck_width_and_lanes':['truck_context.json'],'entry_space_history':['truck_history.jsonl','truck_context.json'],'following_space_context':['truck_history.jsonl','truck_context.json']};ds=metadata(law,methods,inputs)
 # Preserve source checklist but explicitly reject unsupported summary grace duration.
 for d in ds:
  if d['source'].endswith('timing_requirements-1'):
   d['source']=S['laws'][law]['law']['source']+'; original-law correction to unsupported summary post-overtake duration'
  if 'momentary closure' in d['requirement']:d['evidence_or_gap']='Summary adds a post-overtake duration absent from the statutory text. No legal grace duration adopted; saved actual following/overtaking history and gap are retained for review.'
 analysis=(seed/'analyze.py').read_text();analysis=analysis.replace("    output.write_text", "    values=measurements\n    output.write_text");analysis=analysis.replace("len(ego)!=8 or len(lead)!=8","len(ego)%8 or len(lead)%8 or not ego or not lead")
 extra='''def entry_space_history(root):
    rows=[json.loads(s) for s in required(root,'truck_history.jsonl').read_text().splitlines() if s]
    context=json.loads(required(root,'truck_context.json').read_text())
    samples=[]
    for r in rows:
        ego=r['ego_vertices_m'];lead=r['lead_vertices_m'];entrant=r.get('entrant_vertices_m',[])
        rear=max(v[0] for v in ego);front=min(v[0] for v in lead)
        samples.append({'frame':r['frame'],'time_s':r['time_s'],'body_gap_m':front-rear,'entrant_body_vertices_m':entrant,'entrant_within_longitudinal_space':bool(entrant) and min(v[0] for v in entrant)>=rear and max(v[0] for v in entrant)<=front,'entrant_lateral_span_m':[min((v[1] for v in entrant),default=0),max((v[1] for v in entrant),default=0)],'ego_lateral_span_m':[min(v[1] for v in ego),max(v[1] for v in ego)],'lead_lateral_span_m':[min(v[1] for v in lead),max(v[1] for v in lead)],'overtaking_front_of_lead':min(v[0] for v in ego)>max(v[0] for v in lead),'requested_phase':r.get('requested_phase','following')})
    return {'samples':samples,'conditions_context':context.get('conditions_context',{}),'same_direction_lane_count':context['same_direction_lane_count'],'overtaking_front_frames':[r['frame'] for r in samples if r['overtaking_front_of_lead']],'entrant_space_frames':[r['frame'] for r in samples if r['entrant_within_longitudinal_space']],'judgment_limit':'Measured geometry only; conditions permit and without danger are not classified.'}

'''
 extra+='def following_space_context(root):\n    return {\'all_unit_gap\':body_gap(root),\'width_and_lanes\':truck_width_and_lanes(root),\'entry_and_activity\':entry_space_history(root)}\n\n'
 analysis=analysis.replace('def finalize(root,output):',extra+'def finalize(root,output):')
 # Seed indentation is four spaces, normalize only output marker for helper.
 analysis=analysis.replace("    output.write_text(json.dumps({'format':'worker-analysis-report-v1'", " output.write_text(json.dumps({'format':'worker-analysis-report-v1'")
 analysis=alias_analysis(analysis,ds);analysis=analysis.replace("\n values['requirement_", "\n    values['requirement_");analysis=analysis.replace("\n output.write_text", "\n    output.write_text")
 runner=(seed/'runner.py').read_text().replace("assert cfg['required_atoms']==['kin.speed']","assert cfg['required_atoms']==['kin.speed','st.one_way_roadway']").replace(" assert len(road.findall('.//lane[@type=\"driving\"]'))==2", " assert len(road.findall('.//lane[@type=\"driving\"]'))==cfg['same_direction_lane_count']")
 runner=runner.replace("bp=world.get_blueprint_library().find(cfg['truck_blueprint'])","bp=world.get_blueprint_library().find(cfg['ego_blueprint'])")
 runner=runner.replace("bp2=world.get_blueprint_library().find(cfg['truck_blueprint'])","bp2=world.get_blueprint_library().find(cfg['lead_blueprint'])")
 runner=runner.replace("wp2=world.get_map().get_waypoint_xodr(1,-1,460)","wp2=world.get_map().get_waypoint_xodr(1,-1,300+cfg['requested_body_gap_m']+12)")
 runner=runner.replace("  for truck in (ego,lead):", "  from truck_extensions import spawn_extras,apply_hitches,extend_state\n  trailers,entrant=spawn_extras(carla,world,cfg,ego,lead,owned)\n  for truck in (ego,lead):")
 runner=runner.replace("  if not all(t['physical_width_at_least_80in'] for t in contexts):raise ValueError('Truck blueprint physical width <80 inches')", "  for row in contexts:row['class']=cfg['ego_class'] if row['role']=='ego' else cfg['lead_class'];row['drawn_vehicle_actor_id']=trailers[row['role']].id if row['role'] in trailers else None")
 runner=runner.replace("'trucks':contexts,'same_direction_lane_count':1,", "'trucks':contexts,'same_direction_lane_count':cfg['same_direction_lane_count'],'conditions_context':cfg['conditions_context'],")
 runner=runner.replace("  for spec in cfg['cameras']:", "  (out/'scenario_geometry.json').write_text(json.dumps({'source':'Authored scene.xodr with original Native map inventory','physical_verification':'Native lane and pixels unverified; authored declaration only','directed_roadways':[{'polygon':[[0,-14],[1500,-14],[1500,0],[0,0]],'direction_xy':[1,0],'one_way':True}]}))\n  for spec in cfg['cameras']:",1)
 runner=runner.replace("    before_ego,before_lead=state(ego),state(lead);now_before=i*.05", "    apply_hitches(carla,ego,lead,trailers)\n    before_ego,before_lead=extend_state(state(ego),trailers.get('ego')),extend_state(state(lead),trailers.get('lead'));now_before=i*.05")
 runner=runner.replace("    ego.apply_control(carla.VehicleControl(throttle=command['throttle'],brake=command['brake'],hand_brake=command['hand_brake']))", "    if cfg['overtake'] and 100<i<650:\n     lateral_target=-6 if i<400 else -1.75;error=lateral_target-ego.get_location().y\n     command['throttle']=.55;command['brake']=0;command['hand_brake']=False;steer=max(-.4,min(.4,error*.12))\n    else:steer=0\n    ego.apply_control(carla.VehicleControl(throttle=command['throttle'],brake=command['brake'],steer=steer,hand_brake=command['hand_brake']))\n    entrant_speed=entrant.get_velocity().length();target_y=-1.75 if i>cfg['entrant_start_tick'] else -8\n    entrant.apply_control(carla.VehicleControl(throttle=max(0,min(.5,.3*(9-entrant_speed))),steer=max(-.35,min(.35,.1*(target_y-entrant.get_location().y)))))")
 runner=runner.replace("current_ego,current_lead=state(ego),state(lead)","current_ego,current_lead=extend_state(state(ego),trailers.get('ego')),extend_state(state(lead),trailers.get('lead'))")
 runner=runner.replace("'requested_controls':command,", "'entrant_vertices_m':[[p.x,p.y,p.z] for p in entrant.bounding_box.get_world_vertices(entrant.get_transform())],'requested_phase':'overtaking' if cfg['overtake'] and 100<i<650 else 'following','requested_controls':command,")
 # Exact same-direction lane OpenDRIVE inventory, preserving existing crest profile.
 import xml.etree.ElementTree as ET
 road=ET.fromstring((seed/'scene.xodr').read_text());ls=road.find('.//laneSection');left=ls.find('left');ls.remove(left)
 controller=(ROOT/'runtime/main-pipeline-v1/capabilities/heavy_vehicle/following_controller.py').read_text().replace('if len(vertices) != 8','if not vertices or len(vertices) % 8')
 extensions='''def spawn_extras(carla,world,cfg,ego,lead,owned):
 trailers={}
 for role,tractor in [('ego',ego),('lead',lead)]:
  if cfg[role+'_class']=='combination':
   pose=tractor.get_transform();pose.location=pose.transform(carla.Location(x=-8))
   tr=world.spawn_actor(world.get_blueprint_library().find('vehicle.carlamotors.carlacola'),pose);owned.append(tr);trailers[role]=tr;tr.apply_control(carla.VehicleControl(throttle=0,brake=0,hand_brake=False))
 wp=world.get_map().get_waypoint_xodr(1,-1,390);pose=wp.transform;pose.location.y=-8
 entrant=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),pose);owned.append(entrant)
 return trailers,entrant

def apply_hitches(carla,ego,lead,trailers):
 for role,trailer in trailers.items():
  tractor=ego if role=='ego' else lead;hitch=tractor.get_transform().transform(carla.Location(x=-3.5));coupler=trailer.get_transform().transform(carla.Location(x=3.5));tv=tractor.get_velocity();rv=trailer.get_velocity()
  force=carla.Vector3D(x=1800*(hitch.x-coupler.x)+650*(tv.x-rv.x),y=1800*(hitch.y-coupler.y)+650*(tv.y-rv.y),z=0)
  trailer.add_force(force,coupler);tractor.add_force(carla.Vector3D(x=-force.x,y=-force.y,z=0),hitch)

def extend_state(value,trailer):
 if trailer:
  t=trailer.get_transform();value['drawn_body_vertices_m']=[[p.x,p.y,p.z] for p in trailer.bounding_box.get_world_vertices(t)];value['body_vertices_m']+=value['drawn_body_vertices_m']
 return value
'''
 # Retain a physically authored condition obstruction, all-unit widths, and an ordinary wide single lane.
 for lane in road.findall('.//lane[@type="driving"]/width'):lane.set('a','12.0')
 runner=runner.replace("lateral_target=-6 if i<400 else -1.75", "lateral_target=-2 if i<400 else -6")
 runner=runner.replace("target_y=-1.75 if i>cfg['entrant_start_tick'] else -8", "target_y=-6 if i>cfg['entrant_start_tick'] else -11")
 runner=runner.replace("  contexts=[]", "  condition_actors=[]\n  if cfg['conditions_context']['authored_condition']!='available':\n   options=list(world.get_blueprint_library().filter('static.prop.*container*'))\n   if not options:raise ValueError('Native condition obstruction asset unavailable')\n   pose=world.get_map().get_waypoint_xodr(1,-1,390).transform;ob=world.spawn_actor(options[0],pose);ob.set_simulate_physics(False);owned.append(ob);condition_actors.append(ob)\n  cfg['conditions_context']['native_obstruction_bodies']=[{'actor_id':ob.id,'body_vertices_m':[[p.x,p.y,p.z] for p in ob.bounding_box.get_world_vertices(ob.get_transform())]} for ob in condition_actors]\n  contexts=[]")
 runner=runner.replace("width=2*truck.bounding_box.extent.y;contexts.append", "vertices=extend_state(state(truck),trailers.get(role))['body_vertices_m'];width=max(v[1] for v in vertices)-min(v[1] for v in vertices);contexts.append")
 spec=base_spec(aid,ds);spec.update(seed_assignment_id=original,analysis=analysis,runner=runner,scene=ET.tostring(road,encoding='unicode'),negative={'remove':['truck_history.jsonl'],'error_contains':'Missing required source: truck_history.jsonl'})
 spec['extra_files'].update({'following_controller.py':controller,'truck_extensions.py':extensions});spec['reference_paths'].append('runtime/main-pipeline-v1/capabilities/heavy_vehicle/following_controller.py')
 variants=[]
 if overtake:variants=[('follow_reference','truck','truck',160,1,False,'available',300,False),('overtake_probe','truck','truck',160,1,True,'available',300,False)]
 else:
  for ec,lc in [('truck','truck'),('truck','combination'),('combination','truck'),('combination','combination')]:
   for gap in [160,140]:variants.append((ec+'_'+lc+'_'+str(gap),ec,lc,gap,1,False,'available',300,False))
  variants += [('subject_width_probe','truck','truck',160,1,False,'available',300,'ego'),('lead_width_probe','truck','truck',160,1,False,'available',300,'lead'),('constrained_conditions','truck','truck',160,1,False,'documented obstruction',300,False),('entrant_late','truck','truck',160,1,False,'available',500,False),('two_available_lanes','truck','truck',160,2,False,'available',300,False)]
 for name,ec,lc,gap,lanes,ov,conditions,entry,narrow in variants:
  widths={'ego':2.4,'lead':2.4};
  if narrow:widths[narrow]=2.0
  context={'trucks':[{'role':'ego','class':ec,'measured_bbox_width_m':widths['ego'],'physical_width_at_least_80in':widths['ego']>=2.032},{'role':'lead','class':lc,'measured_bbox_width_m':widths['lead'],'physical_width_at_least_80in':widths['lead']>=2.032}],'same_direction_lane_count':lanes,'source':'DIAGNOSTIC synthetic truck context; not Native evidence','conditions_context':{'authored_condition':conditions,'legal_conditions_permit': 'unresolved','native_obstruction_bodies':[{'actor_id':500,'body_vertices_m':body(390,y=-6)}] if conditions!='available' else []}}
  rows=[]
  for i in [1,2,3]:
   ev=body(300+i,half=5,width=widths['ego']/2);lv=body(310+gap+i,half=5,width=widths['lead']/2)
   if ec=='combination':ev+=body(288+i,half=5)
   if lc=='combination':lv+=body(298+gap+i,half=5)
   if ov and i==3:ev=body(330+gap+i,half=5)
   rows.append({'frame':i,'time_s':i*.05,'ego_vertices_m':ev,'lead_vertices_m':lv,'entrant_vertices_m':body(350+i,y=-1.75 if entry==300 else -8),'requested_phase':'overtaking' if ov else 'following'})
  fixture={'truck_context.json':context,'truck_history.jsonl':lines(rows),'scenario_geometry.json':{'source':'DIAGNOSTIC authored one-way road','physical_verification':'Diagnostic fixture only, no physical claim','directed_roadways':[{'polygon':[[0,-14],[1500,-14],[1500,0],[0,0]],'direction_xy':[1,0],'one_way':True}]}}
  cfg=dict(cell_id=aid.split('__')[1],ego_class=ec,lead_class=lc,ego_blueprint='vehicle.tesla.cybertruck' if narrow=='ego' else 'vehicle.carlamotors.carlacola',lead_blueprint='vehicle.tesla.cybertruck' if narrow=='lead' else 'vehicle.carlamotors.carlacola',requested_body_gap_m=gap,same_direction_lane_count=lanes,overtake=ov,conditions_context=context['conditions_context'],entrant_start_tick=entry,required_atoms=['kin.speed','st.one_way_roadway'],source_packets=['scenario_geometry'])
  case=dict(name=name,rationale='Measure full combination widths, actual all-unit gap, entrant occupancy, lane availability and prospective activity for '+name,config=cfg,variable_assignments={'requested_body_gap_m':{'kind':'world_setup','value':gap}},fixture=fixture)
  if lanes==2:
   two=copy.deepcopy(road);right=two.find('.//laneSection/right');l2=copy.deepcopy(right.find('lane'));l2.set('id','-2');right.append(l2);case['extra_files']={'scene.xodr':ET.tostring(two,encoding='unicode')}
  spec['cases'].append(case)
 if overtake:comparison(spec,law,'overtaking_passing',['follow_reference','overtake_probe'],['actual following versus overtaking and passing controller and history'],['same truck widths, requested initial gap, lane count and source duration'])
 else:
  for ec,lc in [('truck','truck'),('truck','combination'),('combination','truck'),('combination','combination')]:comparison(spec,law,ec+'_'+lc+'_500ft_space',[ec+'_'+lc+'_160',ec+'_'+lc+'_140'],['requested body space 160m versus 140m'],['same classes widths lanes speed entrant timing and road geometry','statutory 500ft=152.4m; no conditions/danger verdict'])
  for key,probe in [('subject_width','subject_width_probe'),('lead_width','lead_width_probe'),('conditions_permit','constrained_conditions'),('enter_and_occupy','entrant_late'),('two_available_lanes','two_available_lanes')]:comparison(spec,law,key,['truck_truck_160',probe],['only '+key+' intervention; actual measured width is audited rather than assumed from blueprint'],['same remaining classes, controller, 160m requested gap and capture contract'])
 spec['test']='''import tempfile,json,unittest
from pathlib import Path
import analyze
class TruckTests(unittest.TestCase):
 def test_all_unit_extrema(self):
  from following_controller import along_route_body_gap
  a=[[300+dx,dy,dz] for dx in [-5,5] for dy in [-1,1] for dz in [0,2]];b=[[470+dx,dy,dz] for dx in [-5,5] for dy in [-1,1] for dz in [0,2]]
  self.assertGreater(along_route_body_gap(a,b),152.4)
  self.assertLess(along_route_body_gap(a,b+a),0)
 def test_missing_history(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: truck_history.jsonl'):analyze.body_gap(Path(d))
'''
 return spec

if __name__=='__main__' and '--127' in sys.argv:
 for overtake in [False,True]:
  spec=prepare_127(overtake);B.write(OWNER/('spec-127-overtake.json' if overtake else 'spec-127.json'),spec);folder=B.build(spec)
  if '--prove' in sys.argv:B.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')
  print(folder)

def prepare_257(law,control):
 original=S['laws'][law]['original_assignment_id'];aid=original if control=='yield' else supplemental(original,{'stop':'C158190','officer':'C157964','signal':'C158196'}[control]);seed=ROOT/'references/v6-capability'/original
 methods=['governing_control','interaction_timing','nearest_visible_point','control_and_response_history','stop_and_yield_history'];inp={'governing_control':['control_context.json'],'interaction_timing':['interaction_history.jsonl'],'nearest_visible_point':['view_samples.jsonl','control_context.json'],'control_and_response_history':['interaction_history.jsonl','control_context.json'],'stop_and_yield_history':['interaction_history.jsonl','control_context.json','view_samples.jsonl']};ds=metadata(law,methods,inp)
 analysis=(seed/'analyze.py').read_text().replace("'frame':winner['frame'],'clear_sample_count'","'source_frames':[r['frame'] for r in rows],'sample_spacing_m':[abs(b['distance_to_intersection_m']-a['distance_to_intersection_m']) for a,b in zip(rows,rows[1:])],'frame':winner['frame'],'clear_sample_count'")
 analysis=analysis.replace("'ego_min_x_m':min", "'ego_center_xy_m':[sum(v[0] for v in e['body_vertices_m'])/len(e['body_vertices_m']),sum(v[1] for v in e['body_vertices_m'])/len(e['body_vertices_m'])],'ego_min_x_m':min")
 analysis=analysis.replace("'engineering_stop_samples_upstream':[", "'exact_zero_speed_original_frames':[v['frame'] for v in samples if v['ego_speed_mps']==0],\n  'engineering_stop_samples_upstream':[")
 extra='''def control_and_response_history(root):
 context=json.loads(required(root,'control_context.json').read_text())
 rows=[json.loads(s) for s in required(root,'interaction_history.jsonl').read_text().splitlines() if s]
 samples=[]
 for row in rows:
  e=row['ego'];other=row['through'];front=max(v[0] for v in e['body_vertices_m']);reference=context['stopping_reference_x_m']
  samples.append({'frame':row['frame'],'time_s':row['time_s'],'ego_speed_mps':e['speed_mps'],'body_front_x_m':front,'reference_x_m':reference,'body_front_minus_reference_m':front-reference,'governing_control_observation':row.get('governing_control_observation',{}),'ego_applied_control':row['ego_applied_control'],'other_speed_mps':other['speed_mps'],'other_obligation':context['other_entrance_obligation'],'ego_body_vertices_m':e['body_vertices_m'],'other_body_vertices_m':other['body_vertices_m']})
 return {'reference_kind':context['reference_kind'],'governing_control_sample_count':sum(bool(s['governing_control_observation'].get('controls_subject')) for s in samples),'maximum_original_ego_speed_mps':max(s['ego_speed_mps'] for s in samples),'samples':samples,'governing_observation_samples':[s['governing_control_observation'] for s in samples],'exact_zero_speed_original_frames':[s['frame'] for s in samples if s['ego_speed_mps']==0],'minimum_reference_offset_m':min(s['body_front_minus_reference_m'] for s in samples),'maximum_reference_offset_m':max(s['body_front_minus_reference_m'] for s in samples),'other_entrance_obligation':context['other_entrance_obligation'],'non_through_highway':context['non_through_highway'],'measurement_limit':'Raw stopping, motion, geometry and actual control readback; no legal hazard, yield, visibility or caution verdict.'}

'''
 extra+="def stop_and_yield_history(root):\n return {'reference_and_control':control_and_response_history(root),'interaction':interaction_timing(root),'sampled_sight':nearest_visible_point(root)}\n\n"
 analysis=analysis.replace('def finalize(root,output):',extra+'def finalize(root,output):');analysis=alias_analysis(analysis,ds)
 analysis=analysis.replace("['view_samples.jsonl']))","['view_samples.jsonl','control_context.json']))")
 analysis=analysis.replace("return {'point_xy_m':winner","context=json.loads(required(root,'control_context.json').read_text())\n return {'reference_context':context,'point_xy_m':winner")
 runner=(seed/'runner.py').read_text()
 start=runner.index(" signals=west.findall");end=runner.index(" assert cfg['duration_s']",start)
 runner=runner[:start]+" signals=west.findall('./signals/signal');assert signals\n assert any(s.get('type') in ('205','206','1000001') for s in signals)\n"+runner[end:]
 runner=runner.replace("cfg['required_atoms']==['kin.speed']","cfg['required_atoms']==['kin.speed','st.one_way_roadway']")
 start=runner.index("  if cfg['mode']=='stop_within':");end=runner.index("  map_=world.get_map();",start)
 runner=runner[:start]+"  from entrance_controls import spawn_markings,setup_governance,observe_governance\n  markings=spawn_markings(carla,world,cfg);owned.extend(markings)\n  marking_inventory=[{'actor_id':a.id,'type_id':a.type_id,'position_m':[a.get_location().x,a.get_location().y,a.get_location().z]} for a in markings]\n"+runner[end:]
 runner=runner.replace("  for vehicle in (ego,through):", "  governance=setup_governance(carla,world,map_,cfg,owned)\n  for vehicle in (ego,through):")
 runner=runner.replace("'actual_officer_signal_control':'No officer or signal actor spawned; full world inventory required',", "'actual_officer_signal_control':{'requested':cfg['governing_active'],'kind':cfg['control_kind'],'readback_source':'interaction_history.jsonl governing_control_observation'},'reference_kind':cfg['reference_kind'],'stopping_reference_x_m':cfg['stopping_reference_x_m'],'other_entrance_obligation':cfg['other_entrance_obligation'],'non_through_highway':cfg['non_through_highway'],'physical_region_definition':cfg['reference_kind'],'driver_context':{'ordinary_vehicle':'vehicle.lincoln.mkz_2020','actual_physical_control':'Authored conventional driver control; original actuation retained'},")
 runner=runner.replace("'stopline_present':cfg['mode']=='stop_within','crosswalk_present':False,", "'stopline_present':cfg['reference_kind']=='marked_stop_line','crosswalk_present':'crosswalk' in cfg['reference_kind'],")
 runner=runner.replace("  for spec in cfg['cameras']:", "  (out/'scenario_geometry.json').write_text(json.dumps({'source':'authored one-way west and two-way crossroad with Native map readback','physical_verification':{'map':'road.xodr','governance':'control_context.json'},'directed_roadways':[{'polygon':[[-400,-7],[7,-7],[7,0],[-400,0]],'direction_xy':[1,0],'one_way':True}],'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]]}))\n  for spec in cfg['cameras']:",1)
 start=runner.index("    target_x=30 if through_clear");end=runner.index("    e_speed=e_before",start)
 runner=runner[:start]+'''    observation=observe_governance(carla,world,governance,cfg,i)
    active=observation.get('controls_subject',False)
    may_depart=(through_clear or cfg['ignore_other_priority']) and i>=cfg['minimum_release_tick']
    if active:may_depart=observation.get('direction')=='proceed' or observation.get('signal_state')=='Green'
    target_x=30 if may_depart else cfg['stopping_reference_x_m']-2.5
    desired=min(cfg['departure_speed_mps'],max(0,(target_x-e_before['position_m'][0])*.6))
    if cfg['initial_response']=='none' and not active:desired=cfg['departure_speed_mps']
    if cfg['initial_response']=='stopped' and not may_depart and e_before['position_m'][0]>cfg['stopping_reference_x_m']-3:desired=0
''' +runner[end:]
 runner=runner.replace("    through_desired=7 if i<600 else 0", "    through_desired=7 if cfg['through_start_tick']<=i<cfg['through_start_tick']+600 else 0")
 runner=runner.replace("'through_clear':through_clear,", "'governing_control_observation':observation,'through_clear':through_clear,")
 runner=runner.replace("if cfg['mode']=='yield_nearest' and e['position_m'][0]<-7:","if e['position_m'][0]<-7:")
 runner=runner.replace("hits=world.cast_ray(eye,target)","hits=world.cast_ray(eye,target);blockers=[h for h in hits if not ego.bounding_box.contains(h.location,ego.get_transform()) and not through.bounding_box.contains(h.location,through.get_transform())]")
 runner=runner.replace("'clear_ray':not bool(hits),'ray_hit_count':len(hits),","'clear_ray':not bool(blockers),'ray_hit_count':len(hits),'blocker_count':len(blockers),'original_ray_hits_m':[[h.location.x,h.location.y,h.location.z] for h in hits],")
 # Keep exact connected one-way layout from source-hashed signal capability seed.
 import xml.etree.ElementTree as ET
 scene=ET.parse(ROOT/'references/v6-capability/testing__C158196__NRS-484B-307-6a__motor_vehicle_driver/scene.xodr').getroot()
 for rd in scene.findall('road'):
  sigs=rd.find('signals')
  if sigs is not None:rd.remove(sigs)
 west=scene.find("road[@id='1']");signals=ET.SubElement(west,'signals');ET.SubElement(signals,'signal',{'id':'257west','s':'385','t':'-5','dynamic':'no','orientation':'+','zOffset':'0','country':'DEU','type':'206' if control=='stop' else '205','subtype':'-1','value':'-1','name':'authorized testing '+control})
 if control=='signal':
  # Governing/passive cases freeze a Native head on west/north respectively.
  target=west;ss=signals;ET.SubElement(ss,'signal',{'id':'257light','s':'385','t':'-5','dynamic':'yes','orientation':'+','zOffset':'5','country':'OpenDRIVE','type':'1000001','subtype':'-1','value':'-1','name':'governing west vehicular signal'})
 spec=base_spec(aid,ds);spec.update(seed_assignment_id=original,analysis=analysis,runner=runner,scene=ET.tostring(scene,encoding='unicode'),negative={'remove':['interaction_history.jsonl'],'error_contains':'Missing required source: interaction_history.jsonl'})
 markings=(ROOT/'references/accepted-sources/C111325/stop257_markings_v2.py').read_text();markings=markings[:markings.index('def spawn(')]
 ext=markings+'''def spawn_markings(carla,world,cfg):
 actors=[];kind=cfg['reference_kind']
 if kind=='nearest_view':return actors
 bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
 for i in range(80 if 'crosswalk' in kind else 20):
  if kind=='marked_stop_line':x=-11;y=-.175-.35*i;z=.002
  elif kind=='near_side_marked_crosswalk':x=-8.25+(i%4)*.35;y=-6.8+(i//4)*.7;z=.002
  else:x=-8.25+(i%4)*.35;y=(-9.8+(i//4)*.3 if i<40 else 7.1+((i-40)//4)*.3);z=.15
  a=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0],y=y,z=z)));a.set_simulate_physics(False);a.set_collisions(False);actors.append(a)
 return actors

def setup_governance(carla,world,map_,cfg,owned):
 result={}
 if cfg['control_kind']=='officer':
  bp=world.get_blueprint_library().find('walker.pedestrian.0001');officer=world.spawn_actor(bp,carla.Transform(carla.Location(x=-10,y=-9,z=.3),carla.Rotation(yaw=90)));owned.append(officer);result['officer']=officer
 elif cfg['control_kind']=='signal':
  heads=[a for a in world.get_actors() if a.type_id.startswith('traffic.traffic_light') and getattr(a,'get_opendrive_id',lambda:'' )()=='257light']
  if len(heads)!=1:raise ValueError('Exactly one installed Native governance signal required')
  signal=heads[0];signal.freeze(True);result['signal']=signal
 return result

def observe_governance(carla,world,g,cfg,tick):
 inventory=[{'actor_id':a.id,'type_id':a.type_id} for a in world.get_actors() if a.type_id.startswith(('walker.','traffic.traffic_light'))]
 result={'world_control_actor_inventory':inventory,'controls_subject':False}
 if 'officer' in g:
  officer=g['officer'];direction='stop' if tick<200 else 'proceed';active=cfg['governing_active']
  bones=officer.get_bones();names=[b.name for b in bones.bone_transforms if 'arm' in b.name.lower()]
  if active:
   if not names:raise ValueError('Native officer skeleton has no arm bones for direction')
   officer.set_bones(carla.WalkerBoneControlIn([(names[0],carla.Transform(rotation=carla.Rotation(roll=-85 if direction=='stop' else -20)))]));officer.blend_pose(1.0)
  observed=officer.get_bones();roll=next((b.relative.rotation.roll for b in observed.bone_transforms if names and b.name==names[0]),None)
  observed_direction='stop' if roll is not None and abs(roll+85)<5 else 'proceed' if roll is not None and abs(roll+20)<5 else 'unrecognized'
  result.update(officer_actor_id=officer.id,direction=observed_direction if active else 'no direction',controls_subject=active and observed_direction!='unrecognized',bone_readback=[{'name':b.name,'relative':str(b.relative),'relative_roll_deg':b.relative.rotation.roll} for b in observed.bone_transforms],officer_authority_context='Authored sworn traffic officer; credential/legal authority requires source review')
 if 'signal' in g:
  signal=g['signal'];signal.set_state(carla.TrafficLightState.Red if tick<200 else carla.TrafficLightState.Green)
  affected=[[w.road_id,w.section_id,w.lane_id] for w in signal.get_affected_lane_waypoints()]
  controls=any(r==1 and lane in (-1,-2) for r,sec,lane in affected)
  result.update(signal_actor_id=signal.id,signal_state=str(signal.get_state()).split('.')[-1],affected_lanes=affected,controls_subject=controls)
 return result
'''
 spec['extra_files']['entrance_controls.py']=ext
 refs=[('nearest_view',-7.5),('marked_stop_line',-11),('near_side_marked_crosswalk',-8.45),('near_side_sidewalk_derived_crosswalk',-8.45)]
 variants=[]
 if control in ['officer','signal']:
  variants=[('active_control','nearest_view',-7.5,'slowed',False,0,True,6,False),('passive_control','nearest_view',-7.5,'slowed',False,0,False,6,False)]
 else:
  for ref,x in refs:
   variants.append((ref+'_response',ref,x,'stopped' if control=='stop' else 'slowed',False,0,False,6,False));variants.append((ref+'_uninterrupted',ref,x,'none',False,0,False,6,False))
  variants += [('occupied_priority_probe','nearest_view',-7.5,'stopped' if control=='stop' else 'slowed',True,0,False,6,False),('approaching_phase_probe','nearest_view',-7.5,'stopped' if control=='stop' else 'slowed',False,120,False,6,False),('later_history_probe','nearest_view',-7.5,'stopped' if control=='stop' else 'slowed',False,250,False,6,False)]
  if control=='yield':variants += [('nearest_view_stopped','nearest_view',-7.5,'stopped',False,0,False,6,False)]
  if law.endswith('-2'):variants += [('cautious_profile_probe','nearest_view',-7.5,'stopped' if control=='stop' else 'slowed',False,0,False,3,False),('other_obligated_probe','nearest_view',-7.5,'stopped' if control=='stop' else 'slowed',False,0,False,6,True)]
 for name,ref,x,response,ignore,phase,active,speed,otherob in variants:
  mode='stop_within' if control=='stop' else 'yield_nearest';cfg=dict(cell_id=aid.split('__')[1],mode=mode,control_kind=control,reference_kind=ref,stopping_reference_x_m=x,initial_response=response,ignore_other_priority=ignore,through_start_tick=phase,minimum_release_tick=120 if response=='stopped' else 0,governing_active=active,departure_speed_mps=speed,other_entrance_obligation='yield' if otherob else 'none',non_through_highway=law.endswith('-2'),required_atoms=['kin.speed','st.one_way_roadway'],source_packets=['scenario_geometry'])
  context=dict(mode=mode,map_landmarks=[{'id':'257west','road_id':1,'type':'206' if control=='stop' else '205'}],physical_stopline_tiles=[{'actor_id':20}] if ref=='marked_stop_line' else [],actual_officer_signal_control={'kind':control,'active':active},stopline_present=ref=='marked_stop_line',crosswalk_present='crosswalk' in ref,sign_authorization='DIAGNOSTIC authored proper-sign provenance; not physical evidence',reference_kind=ref,stopping_reference_x_m=x,other_entrance_obligation='yield' if otherob else 'none',non_through_highway=law.endswith('-2'))
  history=[]
  for i in [1,2,3]:
   ex=-16+6*i if response=='none' or ignore else -16+2*i;tx=1.75;ty=8-4*i+phase*.05
   history.append(dict(frame=i,time_s=i*.05,ego={'body_vertices_m':body(ex,y=-1.75),'speed_mps':0 if response=='stopped' and i==2 else speed if response=='none' or i==3 else 1},through={'body_vertices_m':body(tx,y=ty),'speed_mps':7},ego_applied_control={'throttle':.2,'brake':.8 if response=='stopped' and i==2 else 0},governing_control_observation={'controls_subject':active,'direction':'stop' if control=='officer' and active else 'no direction','signal_state':'Red' if control=='signal' else 'absent','affected_lanes':[[1,0,-1]] if control=='signal' and active else [[4,0,1]],'bone_readback':[{'name':'upperarm','relative_roll_deg':-85 if active else 0}] if control=='officer' else []}))
  fixture={'control_context.json':context,'interaction_history.jsonl':lines(history),'view_samples.jsonl':lines([dict(frame=i,time_s=i*.05,point_xy_m=[-16+2*i,-1.75],distance_to_intersection_m=9-2*i,clear_ray=True,ray_hit_count=0) for i in [1,2,3]]),'scenario_geometry.json':{'source':'DIAGNOSTIC authored one-way west entrance','physical_verification':'Fixture only; Native pixels unverified','directed_roadways':[{'polygon':[[-400,-7],[7,-7],[7,0],[-400,0]],'direction_xy':[1,0],'one_way':True}]}}
  case=dict(name=name,rationale='Measure '+control+' '+ref+' '+name+' through startup, initial response and all across-or-within interaction history.',config=cfg,fixture=fixture)
  if name=='cautious_profile_probe':case['extra_files']={'runner.py':runner.replace("desired=min(cfg['departure_speed_mps'],max(0,","desired=min(cfg['departure_speed_mps'] if may_depart else 6,max(0,")}
  if control=='signal' and not active:
   sc=copy.deepcopy(scene);ss=sc.find("road[@id='1']/signals");head=next(q for q in ss if q.get('id')=='257light');ss.remove(head);north=sc.find("road[@id='4']");ns=north.find('signals')
   if ns is None:ns=ET.SubElement(north,'signals')
   head.set('s','15');head.set('orientation','-');ns.append(head);case['extra_files']={'scene.xodr':ET.tostring(sc,encoding='unicode')}
  if otherob:
   sc=copy.deepcopy(scene);north=sc.find("road[@id='4']");ns=ET.SubElement(north,'signals');ET.SubElement(ns,'signal',{'id':'other_yield','s':'15','t':'5','dynamic':'no','orientation':'-','zOffset':'0','country':'DEU','type':'205','subtype':'-1','value':'-1','name':'other entrance yield'});case['extra_files']={'scene.xodr':ET.tostring(sc,encoding='unicode')}
  spec['cases'].append(case)
 if control in ['officer','signal']:comparison(spec,law,control+'_governing_exception',['active_control','passive_control'],['actual officer gesture direction applied to controller' if control=='officer' else 'Native affected approach lanes'],['same officer identity and approach, or same official signal states','same subject motion capability','same 45s cameras and source readback'])
 else:
  for ref,x in refs:comparison(spec,law,control+'_'+ref,[ref+'_response',ref+'_uninterrupted'],['initial stop/yield response versus uninterrupted approach'],['same sign control provenance','same reference geometry and traffic trajectories','same four-view duration'])
  for key,name in [('occupied_traffic','occupied_priority_probe'),('approaching_traffic','approaching_phase_probe'),('across_or_within_history','later_history_probe')]:comparison(spec,law,control+'_'+key,['nearest_view_response',name],['subject release priority' if 'occupied' in key else 'other approach phase'],['same reference, sign and participant routes','same raw across-or-within history acquisition','no numeric immediate hazard cutoff'])
  if control=='yield':comparison(spec,law,'yield_slowed_or_stopped',['nearest_view_response','nearest_view_stopped'],['yield approach slowing versus complete-cessation request'],['same yield sign reference and other traffic','same departure policy'])
  if law.endswith('-2'):
   comparison(spec,law,control+'_proceed_cautiously',['nearest_view_response','cautious_profile_probe'],['departure speed profile'],['same initial action geometry traffic obligations','no legal caution speed cutoff'])
   comparison(spec,law,control+'_not_so_obligated',['nearest_view_response','other_obligated_probe'],['other entrance actual yield sign obligation'],['same subject signed entrance','same non-through highway status, other route and motion','full all-entrance sign inventory'])
 if control=='stop':
  for d in spec['dispositions']:
   if 'proper yield-sign' in d['requirement'].lower():d['requirement']=d['requirement'].replace('proper yield-sign','proper stop-sign');d['source']=S['laws'][law]['law']['source']+'; alternative proper stop-sign branch'
 # Exceptions are represented by actual governance in their own binding and by measured absence elsewhere.
 for d in spec['dispositions']:
  low=d['requirement'].lower()
  if d['source'].startswith('assignment.summary:exceptions-'):
   kind='officer' if 'officer' in low else 'signal'
   if control==kind:d['cases']=['active_control']
   else:d['requirement']='Establish absence of actual '+kind+' traffic control for this sign-governed comparison; the statutory exception remains explicit.';d['source']=S['laws'][law]['law']['source']+'; governing-control exception absence'
 if control in ['officer','signal']:
  for d in spec['dispositions']:
   low=d['requirement'].lower()
   if any(x in low for x in ['exclude actual','traffic is not controlled','traffic is not being controlled']):d['cases']=['passive_control']
 # Each original selected witness absence statement applies only to nearest-view cases.
 for d in spec['dispositions']:
  if any(w in d['requirement'].lower() for w in ['absence of a clearly marked','neither a clearly marked','neither stop line']):d['cases']=[c['name'] for c in spec['cases'] if c['config']['reference_kind']=='nearest_view']
 spec['test']='''import json,tempfile,unittest
from pathlib import Path
import analyze
class EntranceMeasurements(unittest.TestCase):
 def test_nearest_is_sampled_not_continuous(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'control_context.json').write_text(json.dumps({'reference_kind':'nearest_view','source':'diagnostic actual-context join'}));(p/'view_samples.jsonl').write_text(json.dumps({'frame':1,'point_xy_m':[-10,0],'distance_to_intersection_m':3,'clear_ray':True})+'\\n'+json.dumps({'frame':2,'point_xy_m':[-8,0],'distance_to_intersection_m':1,'clear_ray':True})+'\\n')
   self.assertEqual(analyze.nearest_visible_point(p)['frame'],2)
 def test_missing_original_history(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Missing required source: interaction_history.jsonl'):analyze.interaction_timing(Path(d))
'''
 return spec

if __name__=='__main__' and '--257' in sys.argv:
 for law in ['NRS-484B-257-1','NRS-484B-257-2']:
  if '--law1' in sys.argv and law.endswith('-2'):continue
  if '--law2' in sys.argv and law.endswith('-1'):continue
  for control in ['yield','stop','officer','signal']:
   spec=prepare_257(law,control);B.write(OWNER/('spec-'+law+'-'+control+'.json'),spec);folder=B.build(spec)
   if '--prove' in sys.argv:B.prove(folder,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck')
   print(folder,flush=True)
