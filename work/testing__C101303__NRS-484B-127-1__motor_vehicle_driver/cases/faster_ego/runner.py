"""Single original Native episode on a connected straight roadway."""
import argparse, hashlib, json, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot, restore

ROOT = Path(__file__).resolve().parent

def check():
    cfg = json.loads((ROOT/'config.json').read_text())
    road = ET.parse(ROOT/'scene.xodr').getroot().find("road[@id='1']")
    assert road is not None and float(road.attrib['length']) >= 1500
    assert len(road.findall('.//lane[@type="driving"]')) >= 4
    assert cfg['duration_s'] == 45 and cfg['rate_hz'] == 20
    assert [c['name'] for c in cfg['cameras']] == ['overview','approach','reference_corner','driver_reference']
    assert [(c['width'],c['height']) for c in cfg['cameras']] == [(1920,1080),(1280,720),(1280,720),(1280,720)]
    assert cfg['required_atoms'] == ['kin.speed','kin.velocity','ru.subject','rel.surface_gap','env.wet_road']
    return {'passed': True, 'road_length_m': float(road.attrib['length']), 'cameras': 4, 'carla_contacted': False}

def run(args):
    import carla
    from pipeline_capture import PipelineCapture
    from analyze import finalize
    client = carla.Client(args.host,args.port); client.set_timeout(60)
    saved = snapshot(client); world = None; owned = []; cameras = {}; queues = {}; encoders = {}; streams = {}; capture = None
    out = Path(args.output_dir); cfg = json.loads((ROOT/'config.json').read_text())
    frames = 0; errors = []
    try:
        world = client.generate_opendrive_world((ROOT/'scene.xodr').read_text())
        settings = world.get_settings(); settings.synchronous_mode=True; settings.fixed_delta_seconds=.05
        world.apply_settings(settings); world.set_weather(carla.WeatherParameters(wetness=cfg['wetness'],precipitation=cfg['precipitation'],sun_altitude_angle=70))
        mapping = world.get_map(); wp = mapping.get_waypoint_xodr(1,-1,500)
        if wp is None: raise ValueError('Native lane 1/-1 is missing')
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name','subject_speed_600_1e')
        ego = world.spawn_actor(blueprint, wp.transform); owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        lead_wp=mapping.get_waypoint_xodr(1,-1,500+cfg['requested_gap_m']+4.8)
        if lead_wp is None: raise ValueError('Connected lead lane missing')
        lead_bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        lead_bp.set_attribute('role_name','following_lead')
        leader=world.spawn_actor(lead_bp,lead_wp.transform);owned.append(leader)
        leader.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        queued=None
        if cfg.get('queued_traffic',False):
            qp=mapping.get_waypoint_xodr(1,-1,470)
            queued=world.spawn_actor(lead_bp,qp.transform);owned.append(queued)
            queued.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        surface_authoring={'ice_or_snow':False,'basis':'Explicit generated asphalt construction with no ice/snow layer or added material; absence is authored construction context, not weather inference','scene_sha256':hashlib.sha256((ROOT/'scene.xodr').read_bytes()).hexdigest(),'native_object_names':list(world.get_names_of_all_objects()),'native_actor_inventory':[{'id':a.id,'type':a.type_id} for a in world.get_actors()]}
        for _ in range(20): world.tick()
        for spec in cfg['cameras']:
            name,w,h = spec['name'],spec['width'],spec['height']
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:
                bp.set_attribute(key,str(value))
            if name == 'overview': pose = carla.Transform(carla.Location(x=0,y=0,z=150),carla.Rotation(pitch=-90))
            elif name == 'approach': pose = carla.Transform(carla.Location(x=-12,y=0,z=8),carla.Rotation(pitch=-15))
            elif name == 'reference_corner': pose = carla.Transform(carla.Location(x=750,y=0,z=75),carla.Rotation(pitch=-65))
            else: pose = carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation())
            camera = world.spawn_actor(bp,pose,attach_to=ego if name in ('overview','approach','driver_reference') else None)
            owned.append(camera); cameras[name]=camera; queues[name]=queue.Queue();camera.listen(queues[name].put)
            stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra',
                '-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
        capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
        started=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(out/'video_frames.jsonl') as fmap, (out/'body_history.jsonl').open('x') as body, (out/'following_samples.jsonl').open('x') as following:
            for index in range(cfg['duration_s']*cfg['rate_hz']):
                speed=ego.get_velocity().length(); lead_speed=leader.get_velocity().length()
                ahead=leader.get_transform().location.x-ego.get_transform().location.x
                lead_effort=max(0,min(.5,.25*((cfg['lead_speed_mps'] if index<cfg['lead_brake_tick'] else cfg['braked_speed_mps'])-lead_speed)))
                leader.apply_control(carla.VehicleControl(throttle=lead_effort,brake=max(0,min(.5,.2*(lead_speed-(cfg['lead_speed_mps'] if index<cfg['lead_brake_tick'] else cfg['braked_speed_mps']))))))
                requested=max(0,min(14,lead_speed+cfg['ego_speed_bias_mps']+0.08*(ahead-cfg['requested_gap_m'])))
                effort=max(0,min(.6,.3*(requested-speed)))
                lateral=ego.get_transform().location.y
                target_lateral=5.25 if index>=cfg['lane_change_tick'] else 1.75
                steer=max(-.35,min(.35,.11*(target_lateral-lateral)-.03*ego.get_transform().rotation.yaw))
                ego.apply_control(carla.VehicleControl(throttle=effort,brake=max(0,min(.5,.2*(speed-requested))),steer=steer))
                frame=world.tick(); now=world.get_snapshot().timestamp.elapsed_seconds-started
                native_images={}
                for spec in cfg['cameras']:
                    name=spec['name']; image=queues[name].get(timeout=30)
                    while image.frame<frame: image=queues[name].get(timeout=30)
                    if image.frame!=frame: raise ValueError('Camera original tick mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    native_images[name]={'frame':image.frame,'sha256':hashlib.sha256(image.raw_data).hexdigest()}
                transform=ego.get_transform(); vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(transform)]
                body.write(json.dumps({'frame':frame,'time_s':now,'vertices_m':vertices,'camera_originals':native_images})+'\n')
                lead_t=leader.get_transform();lead_vertices=[[v.x,v.y,v.z] for v in leader.bounding_box.get_world_vertices(lead_t)]
                gap=min(v[0] for v in lead_vertices)-max(v[0] for v in vertices)
                pair={'frame':frame,'time_s':now,'ego_speed_mps':ego.get_velocity().length(),'lead_speed_mps':leader.get_velocity().length(),
                      'ego_body_vertices_m':vertices,'lead_body_vertices_m':lead_vertices,'along_road_body_gap_m':gap,
                      'ego_lane_id':mapping.get_waypoint(transform.location).lane_id,'lead_lane_id':mapping.get_waypoint(lead_t.location).lane_id,
                      'lane_change_requested':index>=cfg['lane_change_tick'],'surrounding_traffic':[{'actor_id':a.id,'type':a.type_id,'speed_mps':a.get_velocity().length(),'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]} for a in world.get_actors().filter('vehicle.*')],'original_weather':{'wetness':world.get_weather().wetness,'precipitation':world.get_weather().precipitation}}
                following.write(json.dumps(pair)+'\n')
                capture.capture(frame,now,extra={'following_case':pair})
                fmap.append(frame,now)
                frames+=1
        if frames!=cfg['duration_s']*cfg['rate_hz']: raise ValueError('Incomplete original duration')
    except BaseException as error:
        errors.append({'message':str(error),'traceback':traceback.format_exc()})
    finally:
        if capture:
            try: capture.close(confirmed=not errors and frames==cfg['duration_s']*cfg['rate_hz'])
            except BaseException as error: errors.append({'capture_close':str(error)})
        for process in encoders.values():
            try:
                process.stdin.close()
                if process.wait(timeout=180): errors.append({'encoder_exit':process.returncode})
            except BaseException as error: errors.append({'encoder':str(error)})
        for stream in streams.values(): stream.close()
        for actor in reversed(owned):
            try: actor.destroy()
            except BaseException as error: errors.append({'destroy':str(error)})
        try: restoration=restore(client,saved)
        except BaseException as error: errors.append({'restore':str(error)}); restoration={'restored':False}
        (out/'native-run-status.json').write_text(json.dumps({'frames':frames,'errors':errors,'restoration':restoration},indent=2)+'\n')
    if errors: raise RuntimeError('Native capture failed: '+str(errors))
    sources={name:out/(name+'.mkv') for name in cameras}
    receipt=compose_four_views(sources,out/'video_frames.jsonl',out/'raw.mkv')
    (out/'four-view-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    context={'highway_source':'synthetic public highway assumption; actual dedication not established',
             'road_geometry_source':'scene.xodr crest and four connected driving lanes; Native readback in road.xodr',
             'surface':cfg['surface_description'],'weather':{'wetness':cfg['wetness'],'precipitation':cfg['precipitation']},
             'traffic_scope':'ego and lead are generated participants; other traffic needs Native inventory'}
    (out/'surface_context.json').write_text(json.dumps(context,indent=2)+'\n')
    context['surface_authoring']=surface_authoring;context['ice_or_snow']=False;context['native_traffic_inventory_source']='trace.jsonl scene_actor_inventory';context['driver_context']='conventional vehicle, controller represents physical-control operation; human identity requires source review'
    (out/'surface_context.json').write_text(json.dumps(context,indent=2)+'\n')
    finalize(out,out/'analysis-report.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir',default='.')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check: print(json.dumps(check()))
    else: run(args)
