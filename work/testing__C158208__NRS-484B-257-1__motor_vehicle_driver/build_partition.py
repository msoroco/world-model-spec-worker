"""Reproducible partition-3 package author; writes only partition-owned returns."""
import json, pathlib, hashlib, subprocess, sys, textwrap, math
ROOT=pathlib.Path.cwd()
P=ROOT/'work/testing__C158208__NRS-484B-257-1__motor_vehicle_driver'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n' if not isinstance(obj,str) else obj)
RUNNER=r'''"""Draft physical runner. --check performs no runtime imports or network access."""
import argparse,ast,json,math,pathlib,sys,signal,queue,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent

def load(): return json.loads((ROOT/'config.json').read_text())
def speed(v): return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def wrap(a): return (a+math.pi)%(2*math.pi)-math.pi

def command(position,yaw,velocity,path,index,target,reverse=False):
    """Monotone pure-pursuit route and bounded P speed servo; no teleportation."""
    while index<len(path)-1 and math.hypot(position[0]-path[index][0],position[1]-path[index][1])<3: index+=1
    j=index
    while j<len(path)-1 and math.hypot(position[0]-path[j][0],position[1]-path[j][1])<max(4.,velocity*.7): j+=1
    dx,dy=path[j][0]-position[0],path[j][1]-position[1]
    heading=yaw+(math.pi if reverse else 0)
    alpha=wrap(math.atan2(dy,dx)-heading)
    steering=math.atan2(2*2.8*math.sin(alpha),max(1.,math.hypot(dx,dy)))/.65
    steering=max(-1.,min(1.,steering))*(-1 if reverse else 1)
    error=target-velocity
    return dict(throttle=max(0.,min(.7,.3*error)),brake=max(0.,min(1.,-.5*error)),steer=steering,reverse=reverse),index

def surface_gap(ego,lead):
    """Signed along-heading separation using measured world body corners."""
    t=ego.get_transform(); h=math.radians(t.rotation.yaw); axis=(math.cos(h),math.sin(h))
    def extent(actor):
        return [p.x*axis[0]+p.y*axis[1] for p in actor.bounding_box.get_world_vertices(actor.get_transform())]
    return min(extent(lead))-max(extent(ego))

def static_check():
    c=load();plan=json.loads((ROOT/'case-plan.json').read_text());x=ET.parse(ROOT/'road.xodr').getroot()
    assert x.tag=='OpenDRIVE' and x.findall('road')
    assert c['actor']==plan['actor'] and c['law_id']==plan['law_id']
    assert set(c['supported_case_ids'])=={i['case_id'] for i in plan['cases']}
    assert len(c['cameras'])==4 and c['hz']==20
    assert all(r['length']>=250 for r in c['route_extents'])
    for f in ('runner.py','finalize.py','geometry.py'):ast.parse((ROOT/f).read_text())
    from geometry import validate_map
    validate_map(ROOT/'road.xodr',c['mechanism'])
    construction=json.loads((ROOT/'construction.json').read_text())
    for f in construction['files']:assert (ROOT/f['path']).read_text()==f['content'],f['path']
    assert {o['name'] for o in plan['observations']} <= {i['name'] for i in construction['recording_description']['channels']}
    for proposal in (ROOT/'constructions').glob('*.json'):
        d=json.loads(proposal.read_text()); cfg=next(f for f in d['files'] if f['path']=='config.json')
        assert json.loads(cfg['content'])['selected_case_id']==d['case_id']
        assert next(f for f in d['files'] if f['path']=='runner.py')['content']==(ROOT/'runner.py').read_text()
    print(json.dumps({'offline':True,'case_count':len(plan['cases']),'status':'partial','gaps':c['delivery_gaps']}))

def route(world,c,case):
    m=world.get_map();kind=c['mechanism'];a=case['variable_assignments'];start=a['route_start_s']['value']
    def point(road,s,lane=-1):
        w=m.get_waypoint_xodr(road,lane,s)
        if w is None:raise RuntimeError('Native route missing road/lane/station '+str((road,lane,s)))
        p=w.transform.location; return [p.x,p.y,p.z+.35]
    if kind=='yield': return [point(1,s) for s in range(int(start),490,2)]+[point(11,s) for s in range(0,20,2)]+[point(2,s) for s in range(0,100,2)]
    if kind=='reverse':
        # Fixed straight reverse route crosses native junction connectors when selected.
        return [point(1,s) if s<490 else point(11,s-490) if s<=510 else point(2,s-510) for s in range(int(start),int(start)-60,-2)]
    if kind=='uturn':
        station=a['maneuver_station_m']['value'];p=point(1,station);result=[point(1,s) for s in range(int(start),int(station),2)]
        result += [[p[0]+6*math.sin(t),p[1]-6+6*math.cos(t),p[2]] for t in [i*math.pi/40 for i in range(41)]]
        result += [[p[0]-i,p[1]-12,p[2]] for i in range(2,60,2)];return result
    return [point(1,s) for s in range(int(start),int(start)+200,2)]

def cleanup_resources(capture,streams,sensors,actors,world,old,handlers,result,out,frame_map=None):
    """Attempt every cleanup even if recorder/capture finalization fails."""
    errors=[]
    def attempt(label,action):
        try:action()
        except BaseException as exc:errors.append({'resource':label,'error':type(exc).__name__+': '+str(exc)})
    if capture:attempt('capture',lambda:capture.close(confirmed=bool(result['maneuver_completed'])))
    if frame_map:attempt('frame_map',frame_map.close)
    for name,stream in streams.items():attempt('channel:'+name,stream.close)
    for sensor in sensors:attempt('sensor.stop',sensor.stop)
    for actor in reversed(actors):attempt('actor.destroy',actor.destroy)
    attempt('world.settings',lambda:world.apply_settings(old))
    for sig,handler in handlers.items():attempt('signal.restore',lambda sig=sig,handler=handler:signal.signal(sig,handler))
    result['cleanup_errors']=errors
    if errors:result['physical_failure_flags'].append('cleanup_failure')
    (out/'result.json').write_text(json.dumps(result,indent=2))
    return errors

def execute(args):
    c=load();case=next(i for i in c['cases'] if i['case_id']==(args.case_id or c['selected_case_id']))
    if case['target_type']=='baseline' and not args.include_baselines:raise ValueError('Baseline is not selected by default; explicit --include-baselines required')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    # Exclusive outputs; an existing executor-created directory is supported.
    reservation=(out/'attempt.json').open('x');reservation.write(json.dumps({'case_id':case['case_id']}));reservation.close()
    import carla
    sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))
    from pipeline_capture import PipelineCapture
    client=carla.Client(args.host,args.port);client.set_timeout(30)
    if client.get_client_version()!=client.get_server_version(): raise RuntimeError('CARLA client/server version mismatch')
    world=client.generate_opendrive_world((ROOT/'road.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=1.,max_road_length=50.,wall_height=0.,additional_width=.2,smooth_junctions=True,enable_mesh_visibility=True))
    old=world.get_settings();actors=[];sensors=[];capture=None;streams={};flag={'stop':False};old_handlers={};result=None;frame_map=None;lead_path=None;lead_index=0
    result={'case_id':case['case_id'],'status':'draft','requested_variable_assignments':case['variable_assignments'],'measured_values':{},'target_checks':[],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'initialization','physical_failure_flags':[],'trace_reference':'trace.jsonl','video_references':[],'video_frame_map_reference':'video-frame-map.jsonl','recording_description':case['recording_description'],'recording_evidence':[],'realized_observables':{},'runtime_uncertainties':c['delivery_gaps']}
    def stop(signum,frame):flag['stop']=True
    try:
        for sig in (signal.SIGINT,signal.SIGTERM):old_handlers[sig]=signal.signal(sig,stop)
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/c['hz'];world.apply_settings(settings)
        path=route(world,c,case);a=case['variable_assignments'];reverse=c['mechanism']=='reverse'
        bp=world.get_blueprint_library().find(c['vehicle_blueprint']);bp.set_attribute('role_name','subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(*path[0]),carla.Rotation(yaw=0.)));actors.append(ego)
        lead=None
        if c['mechanism']=='following':
            width=ego.bounding_box.extent.y*2
            if width<2.032:raise RuntimeError('Subject truck width below statutory 80-inch qualifying class')
            gap=a['commanded_surface_gap']['value'];p=path[0]
            lead=world.spawn_actor(bp,carla.Transform(carla.Location(p[0]+gap+ego.bounding_box.extent.x*2,p[1],p[2]),carla.Rotation()));actors.append(lead)
            if lead.bounding_box.extent.y*2<2.032:raise RuntimeError('Lead truck width below statutory qualifying class')
        if c['mechanism']=='yield':
            # Cross participant uses actual native cross-road lane; no officer/signal invented.
            w=world.get_map().get_waypoint_xodr(3,-1,480.)
            if w is None:raise RuntimeError('Cross road unavailable')
            t=w.transform;t.location.z+=.35;lead=world.spawn_actor(world.get_blueprint_library().find('vehicle.lincoln.mkz_2020'),t);actors.append(lead)
            lead_path=[]
            for road,stations in ((3,range(480,490,2)),(21,range(0,20,2)),(4,range(0,200,2))):
                for station in stations:
                    waypoint=world.get_map().get_waypoint_xodr(road,-1,float(station))
                    if waypoint is None:raise RuntimeError('Native cross-participant route missing')
                    location=waypoint.transform.location;lead_path.append([location.x,location.y,location.z+.35])
        # No rendered-sign/crosswalk claim is made from OpenDRIVE metadata alone.
        result['setup_confirmed']=False
        image_queues=[]
        for idx,cam in enumerate(c['cameras']):
            cb=world.get_blueprint_library().find('sensor.camera.rgb');cb.set_attribute('image_size_x',str(cam['width']));cb.set_attribute('image_size_y',str(cam['height']));cb.set_attribute('fov',str(cam['fov']));cb.set_attribute('sensor_tick','0')
            sensor=world.spawn_actor(cb,carla.Transform(carla.Location(*cam['location']),carla.Rotation(pitch=cam['pitch'])),attach_to=ego);actors.append(sensor);sensors.append(sensor);q=queue.Queue();sensor.listen(q.put);image_queues.append(q);(out/('camera-'+str(idx))).mkdir(exist_ok=False)
        put_config=dict(c,selected_case_id=case['case_id']);(out/'config.json').write_text(json.dumps(put_config,indent=2))
        capture=PipelineCapture(client,ego,out,case['case_id'],required_observations=[o['name'] for o in c['observations']])
        for channel in case['recording_description']['channels']:
            name=channel['name'];streams[name]=(out/('channel-'+name.replace('.','_')+'.jsonl')).open('x')
            result['recording_evidence'].append({'name':name,'unit':channel['unit'],'reference':'channel-'+name.replace('.','_')+'.jsonl'})
        frame_map=(out/'video-frame-map.jsonl').open('x');context={'authored_test_context':a,'provenance':'draft authored facts; native physical realization unverified'};(out/'context.json').write_text(json.dumps(context,indent=2))
        i=0;rows=[];gap_values=[];yield_hold_started=None
        for tick in range(int(c['duration_s']*c['hz'])):
            if flag['stop']:result['termination_reason']='signal';break
            t=ego.get_transform();v=speed(ego.get_velocity());target=a['commanded_approach_speed']['value']
            if c['mechanism']=='yield' and t.location.x>475:
                if yield_hold_started is None:yield_hold_started=tick/c['hz']
                if tick/c['hz']-yield_hold_started<a['yield_hold_s']['value']:target=0.
            if c['mechanism']=='following' and lead is not None:
                gap=surface_gap(ego,lead);gap_values.append(gap);target=max(0.,min(12.,target+.15*(gap-a['commanded_surface_gap']['value'])))
                lead.apply_control(carla.VehicleControl(throttle=max(0.,min(.7,.3*(a['commanded_approach_speed']['value']-speed(lead.get_velocity()))))))
            ctl,i=command((t.location.x,t.location.y),math.radians(t.rotation.yaw),v,path,i,target,reverse)
            ego.apply_control(carla.VehicleControl(**ctl));result['behavior_attempted']=True
            if c['mechanism']=='yield' and lead is not None:
                lt=lead.get_transform();lv=speed(lead.get_velocity())
                lead_target=4. if lead_index<len(lead_path)-1 else 0.
                lead_control,lead_index=command((lt.location.x,lt.location.y),math.radians(lt.rotation.yaw),lv,lead_path,lead_index,lead_target)
                lead.apply_control(carla.VehicleControl(**lead_control))
            frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds;row=capture.capture(frame,time_s);rows.append(row)
            frame_map.write(json.dumps({'video_frame':tick,'carla_frame':frame,'time_s':time_s})+'\n')
            for ci,q in enumerate(image_queues):
                image=q.get(timeout=20.)
                while image.frame<frame:image=q.get(timeout=20.)
                if image.frame!=frame:raise RuntimeError('Camera/trace frame mismatch')
                image.save_to_disk(str(out/('camera-'+str(ci))/('%06d.png'%tick)))
            # Directly measured channels only. All unsupported atoms remain null with explicit missing capability.
            measured={'kin.position':row['position'],'kin.heading':row['heading_deg'],'kin.speed':row['speed_mps'],'kin.extent':{'subject_width_m':2*ego.bounding_box.extent.y},'rel.surface_gap':surface_gap(ego,lead) if c['mechanism']=='following' else None,'drv.backing':bool(ego.get_control().reverse and row['speed_mps']>.01)}
            for name,stream in streams.items():stream.write(json.dumps({'time_s':time_s,'value':measured.get(name),'missing_capability':None if name in measured else 'Requires original graph/geometry evidence projection; not substituted from target'})+'\n')
            if i==len(path)-1 and math.hypot(t.location.x-path[-1][0],t.location.y-path[-1][1])<2:result['maneuver_completed']=True;result['termination_reason']='route_complete';break
        else:result['termination_reason']='timeout'
        frame_map.close();result['measured_values']={'last_speed_mps':rows[-1]['speed_mps'] if rows else None,'surface_gap_samples':gap_values,'frames':len(rows)}
        result['physical_failure_flags']=['mandatory_observation_projection_incomplete','native_setup_not_confirmed','review_video_not_encoded']
        for target in ('commanded_approach_speed','commanded_surface_gap','requested_sight_distance'):
            if target not in a:continue
            values=[r['speed_mps'] for r in rows] if target=='commanded_approach_speed' else gap_values if target=='commanded_surface_gap' else []
            result['target_checks'].append({'target':target,'requested':a[target]['value'],'measured':sum(values)/len(values) if values else None,'method':'mean of original samples; full trace retained','tolerance':.22352 if target=='commanded_approach_speed' else 1.,'matched':False,'physical_cause_confirmed':False,'cause_evidence':'capture/evidence.jsonl; requires measured finalization'})
        result['video_references']=[{'path':'camera-'+str(j),'format':'original RGB PNG sequence','encoded_review_video':False} for j in range(4)]
    except BaseException as exc:
        result['termination_reason']='runtime_error:'+str(exc);result['physical_failure_flags'].append(type(exc).__name__)
        raise
    finally:
        cleanup_resources(capture,streams,sensors,actors,world,old,old_handlers,result,out,frame_map)
    return 0 if result['setup_confirmed'] and result['maneuver_completed'] and not result['physical_failure_flags'] else 2

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);p.add_argument('--case-id');p.add_argument('--include-baselines',action='store_true');args=p.parse_args()
    if args.check:static_check();return 0
    if not all((args.output_dir,args.host,args.port)):p.error('--output-dir, --host, --port required')
    return execute(args)
if __name__=='__main__':sys.exit(main())
'''
FINALIZER=r'''"""Recompute recorded streams; never promotes missing observations or legal verdicts."""
import argparse,json,pathlib,math

def summarize(rows,window,statistic):
 values=[r['value'] for r in rows if window[0]<=r['time_s']<=window[1] and isinstance(r['value'],(float,int)) and not isinstance(r['value'],bool)]
 if not values:raise ValueError('No measured scalar samples in frozen window')
 if statistic=='mean':return sum(values)/len(values)
 if statistic=='min':return min(values)
 if statistic=='max':return max(values)
 if statistic=='first':return values[0]
 if statistic=='last':return values[-1]
 raise ValueError('Unsupported statistic')
def main():
 p=argparse.ArgumentParser();p.add_argument('output_dir');p.add_argument('--channel',required=True);p.add_argument('--start',type=float,required=True);p.add_argument('--end',type=float,required=True);p.add_argument('--statistic',choices=['mean','min','max','first','last'],required=True);a=p.parse_args();root=pathlib.Path(a.output_dir)
 rows=[json.loads(s) for s in (root/('channel-'+a.channel.replace('.','_')+'.jsonl')).read_text().splitlines()];value=summarize(rows,[a.start,a.end],a.statistic)
 out={'name':a.channel,'value':value,'sample_window_s':[a.start,a.end],'statistic':a.statistic,'source':'channel-'+a.channel.replace('.','_')+'.jsonl','legal_verdict':None,'status':'diagnostic_pending_full_capture_validation'}
 with (root/('summary-'+a.channel.replace('.','_')+'.json')).open('x') as f:json.dump(out,f,indent=2)
if __name__=='__main__':main()
'''
TESTS=r'''import json,pathlib,unittest,importlib.util,math,xml.etree.ElementTree as ET,tempfile
R=pathlib.Path(__file__).resolve().parents[1]
def module(name):
 s=importlib.util.spec_from_file_location(name,R/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Preparation(unittest.TestCase):
 def test_speed_controller_brakes_overshoot(self):
  m=module('runner');c,i=m.command((0,0),0,12,[[0,0,0],[20,0,0]],0,5);self.assertGreater(c['brake'],0);self.assertEqual(c['throttle'],0)
 def test_reverse_controller(self):
  m=module('runner');c,i=m.command((0,0),0,0,[[0,0,0],[-20,0,0]],0,2,True);self.assertTrue(c['reverse']);self.assertAlmostEqual(c['steer'],0)
 def test_turn_controller_direction(self):
  m=module('runner');c,i=m.command((0,0),0,1,[[0,0,0],[10,10,0]],0,4);self.assertGreater(c['steer'],0)
 def test_summary_uses_saved_window(self):
  m=module('finalize');self.assertEqual(m.summarize([{'time_s':0,'value':100},{'time_s':1,'value':2},{'time_s':2,'value':4}],[1,2],'mean'),3)
 def test_summary_missing_fails(self):
  with self.assertRaises(ValueError):module('finalize').summarize([{'time_s':1,'value':None}],[0,2],'mean')
 def test_preserved_evidence(self):
  c=json.loads((R/'config.json').read_text());p=json.loads((R/'case-plan.json').read_text());self.assertEqual(c['actor'],p['actor']);self.assertTrue(p['sources']);self.assertFalse(c['simulate_baseline_by_default']);self.assertEqual(len(c['cameras']),4)
 def test_map_geometry(self):
  x=ET.parse(R/'road.xodr').getroot();self.assertTrue(x.findall('road'));self.assertTrue(all(float(r.attrib['length'])>0 for r in x.findall('road')))
 def test_contact_geometry_preserved(self):
  m=module('geometry');a=m.rectangle((0,0),0,2,1);b=m.rectangle((4,0),0,2,1);self.assertTrue(m.overlaps(a,b));self.assertFalse(m.overlaps(a,m.rectangle((4.01,0),0,2,1)))
 def test_reverse_footprint_crossing(self):
  m=module('geometry');cross=[[148,-3.5],[152,-3.5],[152,3.5],[148,3.5]];self.assertTrue(m.overlaps(m.rectangle((151,0),0,2,1),cross));self.assertFalse(m.overlaps(m.rectangle((160,0),0,2,1),cross))
 def test_authored_route_geometry(self):
  c=json.loads((R/'config.json').read_text());self.assertTrue(module('geometry').validate_map(R/'road.xodr',c['mechanism'])['authored_geometry_validated'])
 def test_cleanup_survives_capture_error(self):
  m=module('runner');events=[]
  class BadCapture:
   def close(self,confirmed=False):events.append('capture');raise RuntimeError('capture finalization failed')
  class Actor:
   def stop(self):events.append('sensor_stop')
   def destroy(self):events.append('actor_destroy')
  class World:
   def apply_settings(self,value):events.append('settings')
  class Stream:
   def close(self):events.append('stream')
  with tempfile.TemporaryDirectory(dir=R) as tmp:
   out=pathlib.Path(tmp);result={'maneuver_completed':False,'physical_failure_flags':[]};errors=m.cleanup_resources(BadCapture(),{'a':Stream()},[Actor()],[Actor()],World(),object(),{},result,out,Stream());self.assertEqual(len(errors),1);self.assertTrue((out/'result.json').exists());self.assertEqual(events,['capture','stream','stream','sensor_stop','actor_destroy','settings']);self.assertIn('cleanup_failure',result['physical_failure_flags'])
 def test_required_intersection_branch(self):
  c=json.loads((R/'config.json').read_text())
  if c['mechanism']!='reverse':return
  x=ET.parse(R/'road.xodr').getroot();self.assertIsNotNone(x.find('junction'));cases=c['cases'];by={v['case_id'].rsplit('__',1)[1]:v for v in cases};self.assertIn('outside_intersection_reverse',by);self.assertIn('into_intersection_reverse',by);inside=by['into_intersection_reverse']['variable_assignments'];self.assertIsNotNone(inside['intersection_polygon']['value']);self.assertFalse(inside['street_corner_maneuver']['value']);self.assertEqual(inside['route_start_s']['value'],550)
 def test_comparison_implementation_frozen(self):
  original=(R/'runner.py').read_text()
  for f in (R/'constructions').glob('*.json'):
   d=json.loads(f.read_text());self.assertEqual(next(x['content'] for x in d['files'] if x['path']=='runner.py'),original)
'''


GEOMETRY=r'''"""Offline physical geometry checks; CARLA y is opposite authored OpenDRIVE y."""
import math,xml.etree.ElementTree as ET

def elevation(nodes,s):
 selected=[n for n in nodes if float(n.attrib['s'])<=s]
 if not selected:return 0.
 n=selected[-1];d=s-float(n.attrib['s'])
 return sum(float(n.attrib.get(k,0))*d**i for i,k in enumerate('abcd'))

def rectangle(position,yaw,half_length,half_width):
 c,s=math.cos(yaw),math.sin(yaw)
 return [[position[0]+c*x-s*y,position[1]+s*x+c*y] for x,y in [(-half_length,-half_width),(half_length,-half_width),(half_length,half_width),(-half_length,half_width)]]

def overlaps(a,b):
 """Convex SAT with contact retained as contact; downstream chooses legal convention."""
 for poly in (a,b):
  for i,p in enumerate(poly):
   q=poly[(i+1)%len(poly)];axis=(-(q[1]-p[1]),q[0]-p[0])
   aa=[x*axis[0]+y*axis[1] for x,y in a];bb=[x*axis[0]+y*axis[1] for x,y in b]
   if max(aa)<min(bb) or max(bb)<min(aa):return False
 return True

def validate_map(path,mechanism,search_distance=230.):
 root=ET.parse(path).getroot();roads={int(r.attrib['id']):r for r in root.findall('road')}
 assert len(roads)==len(root.findall('road'))
 for r in roads.values():
  geoms=r.findall('./planView/geometry');length=float(r.attrib['length'])
  assert geoms and abs(sum(float(g.attrib['length']) for g in geoms)-length)<1e-6
  assert all(float(l.find('width').attrib['a'])>0 for l in r.findall('./lanes/laneSection/right/lane'))
 if mechanism in ('yield','reverse'):
  # Native topology links: the two crossing movements have actual junction connectors.
  assert roads[11].attrib['junction']=='0' and roads[21].attrib['junction']=='0'
  for cid in (11,21):
   r=roads[cid]
   for tag in ('predecessor','successor'):
    link=r.find('./link/'+tag);assert int(link.attrib['elementId']) in roads
  assert len(root.findall('./junction/connection'))==3
 if mechanism=='uturn':
  # Both incoming directions must extend past the complete planned maneuver envelope.
  start,end=350.,500.
  assert start-search_distance>0 and end+search_distance<float(roads[1].attrib['length'])
  z=roads[1].findall('./elevationProfile/elevation')
  assert elevation(z,500)>elevation(z,300) and elevation(z,500)>elevation(z,700)
 return {'authored_geometry_validated':True,'native_import_and_ray_coverage_confirmed':False}
'''

def road_xml(kind):
 def lane(i,width=3.5):return '<lane id="%d" type="driving" level="false"><link/><width sOffset="0" a="%s" b="0" c="0" d="0"/><roadMark sOffset="0" type="solid" color="white" width=".12" laneChange="none"/></lane>'%(i,width)
 def road(rid,x,y,h,length,oneway=False,junc=-1,links='',width=3.5,crest=False):
  elev='<elevation s="0" a="0" b="0" c="0" d="0"/>'
  if crest:elev='<elevation s="0" a="0" b=".04" c="0" d="0"/><elevation s="400" a="16" b=".04" c="-.0002" d="0"/><elevation s="600" a="16" b="-.04" c="0" d="0"/>'
  return '<road name="draft physical road" id="%d" length="%s" junction="%d"><link>%s</link><planView><geometry s="0" x="%s" y="%s" hdg="%s" length="%s"><line/></geometry></planView><elevationProfile>%s</elevationProfile><lateralProfile/><lanes><laneSection s="0">%s<center><lane id="0" type="none" level="false"><roadMark sOffset="0" type="solid" color="yellow" width=".12"/></lane></center><right>%s</right></laneSection></lanes></road>'%(rid,length,junc,links,x,y,h,length,elev,'' if oneway else '<left>'+lane(1,width)+'</left>',lane(-1,width))
 header='<OpenDRIVE><header revMajor="1" revMinor="4" name="partition3 draft" version="1" north="1000" south="-1000" east="2000" west="-1000"><geoReference>+proj=tmerc +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs</geoReference></header>'
 if kind in ('yield','reverse'):
  j='<junction id="0" name="one-way to two-way"><connection id="1" incomingRoad="1" connectingRoad="11" contactPoint="start"><laneLink from="-1" to="-1"/></connection><connection id="2" incomingRoad="3" connectingRoad="21" contactPoint="start"><laneLink from="-1" to="-1"/></connection><connection id="3" incomingRoad="4" connectingRoad="21" contactPoint="end"><laneLink from="1" to="1"/></connection></junction>'
  return header+road(1,0,0,0,490,True,links='<successor elementType="junction" elementId="0"/>')+road(2,510,0,0,490,True,links='<predecessor elementType="junction" elementId="0"/>')+road(3,500,-500,math.pi/2,490,links='<successor elementType="junction" elementId="0"/>')+road(4,500,10,math.pi/2,490,links='<predecessor elementType="junction" elementId="0"/>')+road(11,490,0,0,20,True,0,'<predecessor elementType="road" elementId="1" contactPoint="end"/><successor elementType="road" elementId="2" contactPoint="start"/>')+road(21,500,-10,math.pi/2,20,False,0,'<predecessor elementType="road" elementId="3" contactPoint="end"/><successor elementType="road" elementId="4" contactPoint="start"/>')+j+'</OpenDRIVE>'
 return header+road(1,0,0,0,1800,oneway=kind=='following',width=12 if kind=='uturn' else 3.5,crest=kind=='uturn')+'</OpenDRIVE>'

def var(kind,value):return {'kind':kind,'value':value}
def unit(name):
 return 'm/s' if name=='kin.speed' else 'm' if name in ('kin.position','kin.extent','rel.surface_gap','st.sight_distance') else 'deg' if name=='kin.heading' else 'raw_structured_evidence'
PART=json.load(open('partitions/demo-test-03.json'));batch=json.load(open('batch.json'))
for aid in PART['assignment_ids']:
 d=json.load(open('inputs/'+aid+'/assignment.json'));folder=ROOT/'work'/aid;folder.mkdir(parents=True,exist_ok=True)
 law=d['law_id'];kind='yield' if '257' in law else 'following' if '127' in law else 'uturn' if '407' in law else 'reverse'
 observations=[{'name':o['atom'],'mandatory':True,'note':o['note']} for o in d['summary']['required_observations']]
 for name in ('kin.position','kin.speed','kin.heading'):
  if name not in [o['name'] for o in observations]:observations.append({'name':name,'mandatory':True,'note':'original kinematic trace'})
 gaps=['No CARLA execution: spawn inventory, road import, collision/departure, controller tracking and camera visibility unverified.','Mandatory raw atom streams are implemented only for direct telemetry; remaining atom projections require completion against retained original-frame PipelineCapture evidence.','Primary encoded review videos are not implemented; runner saves four synchronized original RGB PNG sequences and exact frame map.']
 if kind=='yield':gaps+=['Native properly erected yield sign and governed-lane verification not implemented; OpenDRIVE-only topology cannot establish a rendered device.','Nearest-view fallback and absence of sidewalk-derived crosswalk need physical inventory; authored topology alone is insufficient.','Cross participant and yield timing are requests; immediate hazard/cautiousness have no adopted threshold.']
 if kind=='following':gaps+=['Truck blueprint dimensions and goods-transport classification require queried inventory; width-gating code refuses sub-80-inch actors.','80-inch width boundary probes cannot yet select physically matched blueprints without altering other dimensions.','Conditions permit and entering without danger remain unresolved; no timing bound for overtaking is inferred from summary.']
 if kind=='uturn':gaps+=['The crest exists in authored elevation profile but paired sight targets need a calibrated inverse station-to-nine-point-horizon mapping before first-run readiness.','U-turn footprint containment and incoming native route search coverage for every frame need stronger static certification; route endpoints alone do not prove sight coverage.']
 if kind=='reverse':gaps+=['Distinctly marked rendered crosswalk, residence-district setting and statutory region extents are authored draft context; native/rendered crosswalk realization is not implemented.','Crosswalk footprint intersection projection and native highway boundary checks require completion; backing telemetry alone does not establish overlap.']
 recording={'channels':[{'name':o['name'],'unit':unit(o['name']),'sampling_rate_hz':20,'method':'direct actor telemetry where supported; otherwise retained original PipelineCapture evidence pending explicit projection','time_window':'entire original execution','reference_frame':'CARLA world coordinates, metres; yaw degrees','uncertainty':'native geometry and sampling uncertainty unverified; unavailable projections are null'} for o in observations],'context_inputs':[{'name':'authored_test_context','unit':'structured','method':'config snapshot with draft provenance'}],'limitations':gaps}
 base={'commanded_approach_speed':var('controller',4. if kind!='following' else 8.),'commanded_turn_path':var('controller',d['cell']['maneuver']),'route_start_s':var('world_setup',350 if kind=='uturn' else 450 if kind=='yield' else 200 if kind=='reverse' else 400),'ego_speed':var('subject_behavior',None),'ego_trajectory':var('subject_behavior',None)}
 if kind=='yield':base.update(yield_hold_s=var('controller',4.),proper_yield_sign=var('world_setup',True),officer_control=var('world_setup',False),signal_control=var('world_setup',False),stop_line=var('world_setup',False),crosswalk=var('world_setup',False),through_highway=var('world_setup',law.endswith('-1')),other_vehicle_within_intersection=var('world_setup',True),approaching_hazard_exercised=var('world_setup',False))
 if kind=='following':base.update(commanded_surface_gap=var('controller',152.4),subject_truck_width=var('subject_behavior',None),lead_truck_width=var('subject_behavior',None),available_same_direction_lanes=var('world_setup',1),goods_transport_class=var('world_setup',True),public_highway=var('world_setup',True),overtaking=var('world_setup',False),conditions_permit=var('world_setup','explicit synthetic assumption; not measured'),without_danger=var('world_setup','unresolved, not certified'))
 if kind=='uturn':base.update(maneuver_station_m=var('controller',430.),requested_sight_distance=var('controller',152.4),sight_distance=var('subject_behavior',None),crest_elevation_profile=var('world_setup','road.xodr: crest at station 500m, radius from vertical polynomial'),curve_at_turn=var('world_setup',False))
 if kind=='reverse':base.update(crosswalk_polygon=var('world_setup',[[148,-3.5],[152,-3.5],[152,3.5],[148,3.5]]),residence_district=var('world_setup','synthetic authored district; native appearance unconfirmed'),street_corner_maneuver=var('world_setup',False),intersection_polygon=var('world_setup',[[490,-10],[510,-10],[510,10],[490,10]]))
 cases=[]
 def case(suffix,typ,rationale,overrides={},probe=None):
  a=json.loads(json.dumps(base));a.update({k:var(v[0],v[1]) for k,v in overrides.items()});c={'case_id':aid+'__'+suffix,'target_law_id':None if typ=='baseline' else law,'target_type':typ,'rationale':rationale,'variable_assignments':a,'unresolved_judgment_calls':[],'recording_description':recording}
  if typ!='baseline':c.update(paired_probe_id=aid+'__comparison',deliberate_differences=list(overrides) or ['yield_hold_s'],probe=probe or {'primary_variable':next(iter(overrides),'yield_hold_s'),'comparison_or_standard':'exact plain branch; no judgment standard','target_value_or_branch':suffix})
  cases.append(c);return c
 case('baseline','baseline','Neutral definition retained and not selected by default.')
 judgments=[]
 if kind=='yield':
  judgments=[{'phrase':'immediate hazard','note':"'immediate hazard' is a judgement element"}]
  if law.endswith('-2'):judgments.insert(0,{'phrase':'proceed cautiously','note':"'proceed cautiously' and 'immediate hazard' are judgement elements"})
  for suffix,hold,typ in [('occupied_yield_attempt',8.,'compliant_attempt'),('occupied_no_yield_attempt',0.,'violating_attempt')]:
   c=case(suffix,typ,'Other vehicle is within the intersection, independent of approaching-hazard interpretation. Yield outcome remains measured, not assumed.',{'yield_hold_s':('controller',hold)})
   c['deterministic_branch']={'source_clause':'shall yield the right-of-way to other vehicles which have entered the intersection' if law.endswith('-1') else 'yielding to vehicles not so obligated to stop or yield and which are within the intersection','judgment_context':[{'phrase':j['phrase'],'note':j['note'],'status':'not_exercised' if j['phrase']=='immediate hazard' else 'fixed_assumption','reason':'Occupied-intersection branch; no approaching-hazard cutoff. Cautiousness is fixed synthetic context, not measured.' ,'world_setup_refs':[] if j['phrase']=='immediate hazard' else ['other_vehicle_within_intersection']} for j in judgments]}
 elif kind=='following':
  judgments=[{'phrase':'whenever conditions permit','note':"'whenever conditions permit' is a judgement element"},{'phrase':'without danger','note':'exact text qualifier: so that an overtaking vehicle may enter and occupy such space without danger'}]
  for suffix,value in [('below',147.4),('at',152.4),('above',157.4)]:case('gap_'+suffix,'boundary_probe','500-foot statutory gap probe. All physical setup is fixed; servo requests measured footprint gap.',{'commanded_surface_gap':('controller',value)}, {'primary_variable':'commanded_surface_gap','comparison_or_standard':'statutory minimum 500 feet','target_value_or_branch':value,'threshold_ref':law+'.space_500_feet','operator':'>=','unit':'m','test_value':value,'epsilon_used':5.})
 elif kind=='uturn':
  judgments=d['templates'][0]['structure']['judgment_calls_needed']
  for suffix,value,station in [('below',147.4,425.),('at',152.4,430.),('above',157.4,435.)]:case('sight_'+suffix,'boundary_probe','500-foot two-approach visibility probe; desired horizon must be measured. Station-to-horizon calibration is outstanding, never infer achieved distance.',{'requested_sight_distance':('controller',value),'maneuver_station_m':('controller',station)}, {'primary_variable':'maneuver_station_m','comparison_or_standard':'500-foot statutory sight distance','target_value_or_branch':value,'threshold_ref':law+'.visibility_500_feet','operator':'>=','unit':'m','test_value':value,'epsilon_used':5.})
 elif kind=='reverse':
  case('outside_crosswalk_reverse','compliant_attempt','Backing remains entirely upstream of marked crossing; no street-corner maneuver.',{'route_start_s':('world_setup',230)})
  case('over_crosswalk_reverse','violating_attempt','Same reverse controller requests crossing footprint overlap; no street-corner maneuver.',{'route_start_s':('world_setup',190)})
  case('outside_intersection_reverse','compliant_attempt','Straight backing stays downstream of the authored native junction; no street-corner maneuver and no crosswalk overlap.',{'route_start_s':('world_setup',600)})
  case('into_intersection_reverse','violating_attempt','Identical straight reverse controller crosses road 2 into native junction connector 11, with observed footprint against authored intersection bounds; no street-corner maneuver.',{'route_start_s':('world_setup',550)})
  for c in cases[1:]:c['paired_probe_id']=aid+('__intersection_pair' if 'intersection' in c['case_id'] else '__crosswalk_pair')
 for c in cases:c['unresolved_judgment_calls']=judgments
 sweeps=[{'sweep_id':aid+'__judgment_'+str(i),'target_law_id':law,'judgment_refs':[j],'status':'incomplete','mode':'one_dimensional','axes':[],'landmarks':[],'rationale':'Keep exact judgment open; cannot freeze physically feasible range until native setup and required raw observation projection are implemented. No labels or invented cutoffs.','missing_inputs':gaps,'variable_assignments':base,'recording_description':recording} for i,j in enumerate(judgments)]
 # Preserve statutory class probes explicitly as incomplete definitions, rather than invent truck blueprints.
 if kind=='following':sweeps.append({'sweep_id':aid+'__width_class_boundary','target_law_id':law,'status':'incomplete','mode':'one_dimensional','axes':[],'landmarks':[{'name':'80-inch qualifying width','value':2.032,'unit':'m','source':d['law']['source'],'verification_evidence':d['law']['text'],'purpose':'coverage_landmark'}],'judgment_refs':[],'missing_inputs':['Physically matched sub/at/above-80-inch subject and lead inventory; no scale manipulation or fabricated dimensions.'],'rationale':'Statutory width below/at/above remains pending inventory, independent of gap triple.','variable_assignments':base,'recording_description':recording})
 comparisons=[]
 if len(cases)>2:
  for pair in sorted({c['paired_probe_id'] for c in cases[1:]}):
   members=[c for c in cases[1:] if c['paired_probe_id']==pair]
   comparisons.append({'case_ids':[c['case_id'] for c in members],'deliberate_differences':sorted({k for c in members for k in c['deliberate_differences']}),'fixed_conditions':'identical runner.py, road.xodr, cameras, participant blueprints, controller gains, weather defaults and observation methods; only listed scalar configuration differences change'})
 sources=[]
 for path in ['inputs/'+aid+'/assignment.json','runtime/stage-contracts.json','runtime/target-environment.json','runtime/python/pipeline_capture.py','runtime/python/traffic_spec_adapter/geometry.py','examples/intersection/original-construction.json','examples/numeric/native/scene.xodr','updates/002.json']:
  sources.append({'path':path,'sha256':sha(ROOT/path)})
 plan={'assignment_id':aid,'actor':d['actor'],'cell_id':d['cell_id'],'law_id':law,'cases':cases,'comparisons':comparisons,'observations':observations,'sources':sources,'existing_evidence':d['existing_evidence'],'runtime_uncertainties':gaps,'baseline_selected':False,'summary_text_conflicts':(['Summary adds an overtaking-duration bound not present numerically in exact text; no numeric bound invented.'] if kind=='following' else [])}
 put(folder/'case-plan.json',plan);put(folder/'runner.py',RUNNER);put(folder/'finalize.py',FINALIZER);put(folder/'geometry.py',GEOMETRY);put(folder/'road.xodr',road_xml(kind));put(folder/'tests/test_preparation.py',TESTS)
 cameras=[{'name':'overview','width':1920,'height':1080,'location':[-12,0,12],'pitch':-35,'fov':90}]+[{'name':n,'width':1280,'height':720,'location':p,'pitch':pitch,'fov':80} for n,p,pitch in [('chase',[-7,0,3],-12),('driver',[0,0,1.6],0),('oblique',[-4,5,5],-25)]]
 cfg={'law_id':law,'actor':d['actor'],'cell_id':d['cell_id'],'supported_case_ids':[c['case_id'] for c in cases],'selected_case_id':cases[1]['case_id'],'simulate_baseline_by_default':False,'cases':cases,'mechanism':kind,'vehicle_blueprint':'vehicle.carlamotors.carlacola' if kind=='following' else 'vehicle.lincoln.mkz_2020','hz':20,'duration_s':45,'cameras':cameras,'observations':observations,'route_extents':[{'road_id':1,'length':490 if kind in ('yield','reverse') else 1800,'search_distance_m':230}],'delivery_gaps':gaps,'authored_test_context':{'core_assumptions':['public highway is synthetic authored fact; not jurisdictional evidence'],'proper_sign_and_rendering_confirmed':False}}
 put(folder/'config.json',cfg)
 proposal={'cell_id':d['cell_id'],'actor':d['actor'],'status':'draft','case_defaults':{'variable_assignments':base,'recording_description':recording},'cases':cases,'sweep_specs':sweeps};put(folder/'proposals/cases.json',proposal)
 quote=d['law']['text'];tid=law+'@'+d['actor'];numeric=[]
 if kind in ('following','uturn'):numeric=[{'variable':'surface_gap' if kind=='following' else 'sight_distance.minimum_from_either_approach','operator':'>=' if kind=='following' else '<','value':500,'unit':'feet'}]
 template={'template_id':tid,'law_id':law,'actor':d['actor'],'quote':quote,'structure':{'law_id':law,'activation':{'condition':'; '.join(d['summary']['activation_conditions']),'numeric_conditions':[]},'obligation':{'description':quote,'type':'must_not' if kind in ('reverse','uturn') else 'must','numeric_conditions':numeric},'exceptions':[{'trigger':s,'effect':'exception or qualification as exact source states','replacement_obligation':None,'source_clause':s if s in quote else quote} for s in d['summary']['exceptions']],'timing':{'description':'; '.join(i['requirement'] for i in d['summary']['timing_requirements']),'numeric_conditions':[]},'judgment_calls_needed':judgments},'parameter_refs':[{'name':k,'kind':v['kind'],'range_or_domain':'draft frozen case values; no inferred legal cutoff'} for k,v in base.items()]}
 put(folder/'proposals/template.json',template)
 put(folder/'proposals/relevance.json',{'cell_id':d['cell_id'],'actor':d['actor'],'status':'draft','relevant_laws':[{'law_id':law,'quote':quote,'applies_to':[d['actor']],'relevance_type':d['witness']['relevance_type'],'confidence':d['witness']['confidence'],'notes':d['witness']['reason']+' Conditions remain explicit: '+'; '.join(d['witness']['required_context'])}],'borderline_excluded':[]})
 put(folder/'proposals/bindings.json',{'cell_id':d['cell_id'],'actor':d['actor'],'status':'draft','established_contexts':['synthetic authored contexts in case variable assignments; physical realization unconfirmed'],'law_refs':[{'template_id':tid,'binding_kind':'requires_context'}],'context_refs':[],'fixed_parameters':[{'name':k,'value':d['cell'][k],'rationale':'supplied exact cell'} for k in ('layout','maneuver','control')],'variable_parameters':[{'name':k,'kind':v['kind'],'range_or_domain':'frozen explicit assignments','used_by_laws':[law]} for k,v in base.items()]})
 put(folder/'proposals/judgment-observables.json',[{'template_id':tid,**j,'status':'draft','observable_requirements':{'observables':[{'name':o['name'],'unit':unit(o['name']),'description':o['note']} for o in observations],'context_inputs':[],'sweep_dimensions':[],'landmarks':[],'recording_needs':[{'name':o['name'],'unit':unit(o['name']),'description':'original-frame evidence without legal interpretation'} for o in observations],'limitations':['No numerical legal standard selected; mental state not directly observable.']}} for j in judgments])
 def construction(case,conf):
  return {'cell_id':d['cell_id'],'actor':d['actor'],'case_id':case['case_id'],'status':'draft','files':[{'path':n,'content':json.dumps(conf,indent=2)+'\n' if n=='config.json' else (folder/n).read_text()} for n in ('runner.py','finalize.py','geometry.py','road.xodr','config.json')],'entrypoint':'runner.py','mechanisms':{'builder':'authored OpenDRIVE '+kind,'controller':'monotone pure pursuit and bounded speed servo; gap feedback for trucks; reverse gear controller for backing','cameras':cameras,'unconfirmed':gaps},'measurement_plan':{'source':'original-frame PipelineCapture + actor telemetry; never requested targets as observation','finalization':'finalize.py recomputes explicit frozen time-window/statistic from saved channel streams. Before acceptance implement all mandatory atom projections, verify native setup/cause, encode full-trace videos, compare targets and frame mapping; physical sweeps remain incomplete until feasible range frozen.','statutory_thresholds':numeric},'recording_description':recording,'static_checks':['--check validates source syntax, map XML, inline materialization, coverage and camera settings','unittest validates controller sign/overshoot, windowed raw recomputation, map shape and implementation reuse'],'termination_rules':{'signals':['SIGINT','SIGTERM'],'time_limit_s':45,'completion':'native route final point reached within 2m engineering tolerance','cleanup':'stop/destroy owned sensors and actors; close recorder/capture; restore saved world settings; never stop simulator server','failures':'nonzero code 2 for any unresolved setup, target, physical, capture or video requirement'}}
 put(folder/'construction.json',construction(cases[1],cfg))
 for c in cases:
  cc=dict(cfg,selected_case_id=c['case_id']);put(folder/('constructions/'+c['case_id']+'.json'),construction(c,cc))
 put(folder/'update-acknowledgements.json',{'assignment_id':aid,'applied_update':2,'notices':[{'version':2,'action':'continue','path':'updates/002.json','sha256':sha(ROOT/'updates/002.json'),'effect':'fresh full implementation; partial gaps explicitly retained'}],'paused':False})
 handoff='# '+aid+'\n\nStatus: **partial**. All six preparation responsibilities have authored artifacts and executable CPU-checked components; this is not first-run readiness.\n\nExact law, cell, actor, witness, summary and existing evidence are preserved in the hashed input and case plan. Relevance, law template, bindings, value-free judgment requirements, canonical cases and constructions are under proposals/ and constructions/. No historical observation is claimed as current evidence.\n\nCases and comparisons: '+ '; '.join(c['case_id']+': '+c['rationale'] for c in cases)+'\n\nThe root construction is the first non-baseline case anchor. Additional canonical case proposals (each contains its own config.json and identical implementation/map/camera files):\n\n'+''.join('- constructions/'+c['case_id']+'.json\n' for c in cases)+'\nRunner: `/usr/bin/python3.11 '+str(folder.relative_to(ROOT))+'/runner.py --check`. Later native Python 3.8+ launch accepts `--output-dir PATH --host HOST --port PORT --case-id ID`; its runtime imports remain lazy. It owns the generated world settings and spawned actors, never the simulator server. Baselines require explicit --include-baselines. The already-created executor output directory is allowed; attempt/capture files are exclusive.\n\nOriginal capture uses runtime/python/PipelineCapture immediately after each tick, with camera queues joined by exact CARLA frame. Saves native graph/evidence, recorder additional data, road, full trace, four RGB sequences and frame map. Missing mandatory projections emit null and a missing-capability reason, never targets as observations. The runner deliberately returns failure until all required setup/capture/video checks are implemented and measured.\n\nMeasured finalization: retain failed attempt and hashes; implement missing atom/cause projections, then execute each frozen setting once. Recompute summaries with `finalize.py OUTPUT --channel NAME --start T0 --end T1 --statistic mean` using actual saved sample times; match the frozen method/window/statistic, keep raw streams, validate both approach horizons/footprints and all original frames, encode and inspect full-trace camera review videos with frame map, and compare requested versus measured quantities. A diagnostic summary does not authorize endpoint changes, extra sweep points, legal thresholds, or acceptance. Repair the implementation at the same setting under a new retained attempt if realization fails. Physics-dependent ranges remain explicitly incomplete and need feasibility evidence before freezing.\n\nRuntime/implementation uncertainties and remaining work:\n\n'+''.join('- '+s+'\n' for s in gaps)+'\nSummary/text conflict: '+('The supplied following summary mentions a bound on overtaking duration not numerically specified in the exact law; no numeric bound is invented.' if kind=='following' else 'No direct textual contradiction detected; witness/summary facts remain proposals, not observations.')+'\n\nNo CARLA run, statutory judgment, physical acceptance or human-review blocker is claimed. Update 002 applied; continue does not release any future pause.\n'
 put(folder/'HANDOFF.md',handoff)
 tests=[]
 for label,cmd in [('check',['/usr/bin/python3.11',str(folder.relative_to(ROOT)/'runner.py'),'--check']),('unittest',['/usr/bin/python3.11','-m','unittest','discover','-s',str(folder.relative_to(ROOT)/'tests')])]:
  process=subprocess.run(cmd,capture_output=True,text=True);log=folder/('logs/'+label+'.log');put(log,'$ '+' '.join(cmd)+'\n'+process.stdout+process.stderr+'\nexit_code='+str(process.returncode)+'\n');tests.append({'command':' '.join(cmd),'exit_code':process.returncode,'log':str(log.relative_to(folder)),'sha256':sha(log),'source_sha256':{str(f.relative_to(folder)):sha(f) for f in [folder/'runner.py',folder/'geometry.py',folder/'finalize.py',folder/'tests/test_preparation.py',folder/'config.json',folder/'road.xodr']}})
 put(folder/'result.json',{'assignment_id':aid,'input_sha256':batch['assignments'][aid]['input_sha256'],'applied_update':2,'status':'partial','reason':'; '.join(gaps),'tests':tests,'runtime_execution':'not performed: CARLA unavailable','six_steps':{'read_exact_evidence':True,'explain_cases_comparisons':True,'implement_builders_controllers_cameras':True,'implement_geometry_capture_results':'partial mandatory projections/native mechanisms unfinished','offline_tests':all(t['exit_code']==0 for t in tests),'deliver_executable_package':True}})
 print(aid,[(t['command'],t['exit_code']) for t in tests])
