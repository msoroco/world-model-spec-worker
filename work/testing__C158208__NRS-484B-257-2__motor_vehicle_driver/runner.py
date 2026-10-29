"""Portable exact-case CARLA capture; --check is offline and never imports CARLA."""
import argparse, json, math, queue, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def check():
    cfg=json.loads((ROOT/'config.json').read_text());tree=ET.parse(ROOT/'scene.xodr')
    roads={int(r.attrib['id']):r for r in tree.findall('road')}
    assert roads and all(r.find('planView/geometry') is not None for r in roads.values())
    assert cfg['camera']['width']>=960 and cfg['camera']['height']>=540 and cfg['duration_s']>=20
    assert {'kin.speed','case_observations','scene_geometry'} <= {x['name'] for x in cfg['recording_description']['channels']}
    mode=cfg['mode']
    if mode.startswith('yield'):
        assert {1,2,3,4,11,12}<=set(roads)
        assert any(c.attrib['incomingRoad']=='1' and c.attrib['connectingRoad']=='11' for c in tree.findall('junction/connection'))
        assert any(s.attrib.get('type')=='205' for s in tree.findall('.//signal'))
        assert not any(o.attrib.get('name','').lower().startswith(('stopline','crosswalk')) for o in tree.findall('.//object'))
        assert not any(s.attrib.get('dynamic')=='yes' for s in tree.findall('.//signal'))
        assert cfg['ego_pose'][1]<0 and cfg['other_pose'][0]<0
    elif mode=='curve_407':
        assert any(r.find('planView/geometry/arc') is not None for r in roads.values())
        assert cfg['authored_context']['curve_radius_m']>0
        s=110;radius=cfg['authored_context']['curve_radius_m'];expected=[radius*math.sin(s/radius),radius*(1-math.cos(s/radius))]
        assert math.hypot(cfg['ego_pose'][0]-expected[0],cfg['ego_pose'][1]-expected[1])<2.5
    elif mode=='trucks_127_2':
        assert len(roads)==1 and len(roads[1].findall('lanes/laneSection/right/lane[@type="driving"]'))==1
        assert not roads[1].findall('lanes/laneSection/left/lane[@type="driving"]')
    elif mode=='backing_113_2':
        assert tree.findall('.//object[@name="Crosswalk"]')
    else: raise ValueError('Unsupported exact mode')
    print(json.dumps({'offline_geometry':mode,'roads':sorted(roads),'channels':len(cfg['recording_description']['channels']),'carla_contacted':False}))

def run(args):
    import carla, numpy as np
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import FrameMap
    from pipeline_capture import PipelineCapture
    cfg=json.loads((ROOT/'config.json').read_text());output=Path(args.output_dir).resolve();mode=cfg['mode']
    if not (output/'config.json').is_file():raise ValueError('Materialized exact case required')
    client=carla.Client(args.host,args.port);client.set_timeout(60);saved=snapshot(client)
    owned=[];capture=None;encoder=None
    try:
        world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=30,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon);world.tick();mapping=world.get_map()
        links=[(a.road_id,a.lane_id,b.road_id,b.lane_id) for a,b in mapping.get_topology()]
        if mode.startswith('yield') and not any(a==1 and c==11 for a,_,c,_ in links):raise ValueError('Native signed approach disconnected')
        library=world.get_blueprint_library()
        def actor(name,pose,role):
            bp=library.find(name);bp.set_attribute('role_name',role)
            a=world.spawn_actor(bp,carla.Transform(carla.Location(x=pose[0],y=pose[1],z=pose[2]),carla.Rotation(yaw=pose[3])))
            owned.append(a);return a
        ego=actor(cfg['ego_blueprint'],cfg['ego_pose'],'subject')
        other=None
        if cfg.get('other_blueprint'):other=actor(cfg['other_blueprint'],cfg['other_pose'],'other_vehicle')
        camera_bp=library.find('sensor.camera.rgb')
        for k,v in [('image_size_x',cfg['camera']['width']),('image_size_y',cfg['camera']['height']),('fov',cfg['camera']['fov_deg']),('sensor_tick','0')]:camera_bp.set_attribute(k,str(v))
        camera=world.spawn_actor(camera_bp,carla.Transform(carla.Location(x=0,y=0,z=35),carla.Rotation(pitch=-75)));owned.append(camera)
        images=queue.Queue();camera.listen(images.put)
        encoder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',str(cfg['camera']['width'])+'x'+str(cfg['camera']['height']),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(output/'raw.mkv')],stdin=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],required_observations=cfg['required_atoms'])
        actors=list(world.get_actors());landmarks=[{'id':str(x.id),'type':str(x.type),'road_id':x.road_id,'s':x.s,'valid_lanes':[list(v) for v in x.get_lane_validities()]} for x in mapping.get_all_landmarks()]
        def environment(label):
            return [{'id':x.id,'name':x.name,'position_xy_m':[x.transform.location.x,x.transform.location.y]} for x in world.get_environment_objects(label)]
        environment_lights=environment(carla.CityObjectLabel.TrafficLight)
        environment_signs=environment(carla.CityObjectLabel.TrafficSigns)
        sidewalks=environment(carla.CityObjectLabel.Sidewalks)
        lights=[{'id':a.id,'type_id':a.type_id} for a in actors if a.type_id.startswith('traffic.traffic_light')]+environment_lights
        officers=[{'id':a.id,'type_id':a.type_id} for a in actors if 'police' in a.type_id.lower() or 'officer' in a.attributes.get('role_name','').lower()]
        unclassified=[a.type_id for a in actors if not a.type_id.startswith(('vehicle.','sensor.','traffic.')) and a.type_id!='spectator']
        context=dict(cfg['authored_context']);context['native_inventory']={'officers':officers,'traffic_signals':lights,'survey_scope':'World.get_actors, Map.get_all_landmarks and environment TrafficLight/TrafficSigns/Sidewalks at first original tick','actor_types':[a.type_id for a in actors],'unclassified_actor_types':unclassified,'landmarks':landmarks,'environment_signs':environment_signs,'environment_sidewalks':sidewalks}
        if mode.startswith('yield'):
            governed=[x for x in landmarks if x['type']=='205' and x['road_id']==1]
            if not governed:raise ValueError('Native yield landmark absent from subject approach')
            context['sign']=dict(context['sign'],native_landmarks=governed)
            near_sidewalks=[x for x in sidewalks if abs(x['position_xy_m'][0])<20 and abs(x['position_xy_m'][1])<20]
            context['sidewalk_crosswalk_survey']={'near_sidewalks':len(near_sidewalks),'native_environment_objects':near_sidewalks,'basis':'original native environment-object inventory'}
            if near_sidewalks:raise ValueError('Near-side sidewalk may imply a crosswalk; selected fallback cannot be established')
            if lights or officers or unclassified:raise ValueError('Actual officer/signal control or unclassified actor unresolved')
        if mode=='trucks_127_2' and (2*ego.bounding_box.extent.y<2.032 or other is None or 2*other.bounding_box.extent.y<2.032):
            raise ValueError('Native truck body width below 80 inches')
        if cfg['source_packets']:
            packet={'source':'native OpenDRIVE map topology and authored one-way role','physical_verification':{'native_topology':links,'road_id':1},'directed_roadways':[{'direction_xy':[1,0],'one_way':True,'polygon':[[-60,-3.5],[60,-3.5],[60,0],[-60,0]]}]}
            (output/'scenario_geometry.json').write_text(json.dumps(packet,indent=2)+'\n')
        # The native survey cannot infer legal governance; retain authored sign
        # and route declarations next to the original actor inventory.
        (output/'case_context.json').write_text(json.dumps(context,indent=2)+'\n')
        start=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output/'video_frames.jsonl') as frames,(output/'case_observations.jsonl').open('x') as stream:
            for i in range(int(cfg['duration_s']*20)):
                for vehicle,target in ((ego,cfg['ego_target_xy']),(other,cfg.get('other_target_xy'))):
                    if vehicle is None:continue
                    tr=vehicle.get_transform();v=vehicle.get_velocity();speed=math.hypot(v.x,v.y)
                    if mode=='backing_113_2' and vehicle==ego:
                        vehicle.apply_control(carla.VehicleControl(throttle=.22 if speed<2 else 0,reverse=True,steer=0))
                    else:
                        desired=math.degrees(math.atan2(target[1]-tr.location.y,target[0]-tr.location.x))
                        error=(desired-tr.rotation.yaw+180)%360-180
                        brake=.3 if mode.startswith('yield') and vehicle==ego and -15<tr.location.x<-8 else 0
                        vehicle.apply_control(carla.VehicleControl(throttle=.3 if speed<cfg['target_speed_mps'] else .02,brake=brake,steer=max(-.7,min(.7,error/45))))
                frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                img=images.get(timeout=30)
                while img.frame<frame:img=images.get(timeout=30)
                if img.frame!=frame:raise ValueError('Camera original frame mismatch')
                rgb=np.frombuffer(img.raw_data,dtype=np.uint8).reshape(cfg['camera']['height'],cfg['camera']['width'],4)[:,:,:3][:,:,::-1]
                encoder.stdin.write(rgb.tobytes());frames.append(frame,time_s)
                et=ego.get_transform();ev=ego.get_velocity();ep=et.location;es=math.hypot(ev.x,ev.y)
                row={'frame':frame,'time_s':time_s,'point_xy_m':[ep.x,ep.y],'ego_speed_mps':es,'heading_deg':et.rotation.yaw}
                if other:
                    ot=other.get_transform();op=ot.location;ov=other.get_velocity()
                    row.update(other_inside=abs(op.x)<7 and abs(op.y)<7,other_distance_to_conflict_m=math.hypot(op.x,op.y),other_speed_mps=math.hypot(ov.x,ov.y),other_width_m=2*other.bounding_box.extent.y)
                if mode.startswith('yield'):
                    row.update(distance_to_intersection_m=max(0,-7-ep.x),ego_inside=abs(ep.x)<7 and abs(ep.y)<7,other_obligated=False)
                    if other:
                        eye=carla.Location(x=ep.x,y=ep.y,z=ep.z+1.2);target=carla.Location(x=op.x,y=op.y,z=op.z+1.2)
                        row['clear_ray']=len(world.cast_ray(eye,target))==0
                elif mode=='curve_407':
                    for side in ('forward','reverse'):
                        distance=152.4-(i%3)*20
                        base=mapping.get_waypoint(ep,project_to_road=True)
                        candidates=base.next(distance) if side=='forward' else base.previous(distance)
                        if not candidates:raise ValueError('Native curve lacks 500-foot approach waypoint')
                        location=candidates[0].transform.location
                        ray_start=carla.Location(x=location.x,y=location.y,z=location.z+1.5)
                        ray_target=carla.Location(x=ep.x,y=ep.y,z=ep.z+1.5)
                        sample=dict(row,approach_direction=side,approach_distance_m=distance,clear_ray=len(world.cast_ray(ray_start,ray_target))==0)
                        stream.write(json.dumps(sample)+'\n')
                elif mode=='trucks_127_2' and other:
                    evert=ego.bounding_box.get_world_vertices(et);overt=other.bounding_box.get_world_vertices(ot)
                    row.update(ego_width_m=2*ego.bounding_box.extent.y,body_gap_m=min(x.x for x in overt)-max(x.x for x in evert),same_lane=abs(ep.y-op.y)<1.5,overtaking=False)
                elif mode=='backing_113_2':
                    from shapely.geometry import Polygon
                    body=Polygon([(x.x,x.y) for x in ego.bounding_box.get_world_vertices(et)]).convex_hull
                    cross=Polygon(context['crosswalk_polygon_xy_m'])
                    row.update(backing=ego.get_control().reverse and (ev.x*math.cos(math.radians(et.rotation.yaw))+ev.y*math.sin(math.radians(et.rotation.yaw)))<0,body_crosswalk_overlap_m2=body.intersection(cross).area)
                stream.write(json.dumps(row)+'\n')
                capture.capture(frame,time_s,extra={'case_observation':row})
        capture.close(confirmed=True);capture=None
        encoder.stdin.close()
        if encoder.wait(timeout=120):raise ValueError('Original camera encoder failed')
        encoder=None
        subprocess.run([sys.executable,str(output/'analyze.py'),'--attempt',str(output),'--output',str(output/'analysis-report.json')],check=True)
    finally:
        if capture:capture.close(confirmed=False)
        if encoder:
            encoder.stdin.close();encoder.wait(timeout=120)
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.'):actor.stop()
                actor.destroy()
            except Exception:pass
        (output/'world-restore.json').write_text(json.dumps(restore(client,saved),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);a=p.parse_args()
    if a.check:check()
    else:
        if not all((a.output_dir,a.host,a.port)):p.error('Capture needs output, host and port')
        run(a)
