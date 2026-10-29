"""Single original Native episode on a connected straight roadway."""
import argparse, hashlib, json, math, queue, subprocess, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from worker_exchange.native_output import FrameMap
from worker_exchange.media import compose_four_views
from worker_exchange.world_restore import snapshot, restore

ROOT = Path(__file__).resolve().parent

def check():
    cfg = json.loads((ROOT/'config.json').read_text())
    road = ET.parse(ROOT/'scene.xodr').getroot().find("road[@id='1']")
    assert road is not None and float(road.attrib['length']) >= 393
    assert len(ET.parse(ROOT/'scene.xodr').getroot().findall('.//object[@type="barrier"]')) == 2
    assert len(road.findall('.//lane[@type="driving"]')) >= 2
    assert cfg['duration_s'] == 55 and cfg['rate_hz'] == 20
    assert [c['name'] for c in cfg['cameras']] == ['overview','approach','reference_corner','driver_reference']
    assert [(c['width'],c['height']) for c in cfg['cameras']] == [(1920,1080),(1280,720),(1280,720),(1280,720)]
    assert {'kin.speed','kin.velocity','st.median_or_divider'} <= set(cfg['required_atoms'])
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
        world.apply_settings(settings); world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map(); wp = mapping.get_waypoint_xodr(1,-1,cfg.get("ego_station_m",350))
        if wp is None: raise ValueError('Native lane 1/-1 is missing')
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name','subject_median_crossing_250_2')
        ego = world.spawn_actor(blueprint, wp.transform); owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        other_bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        other_bp.set_attribute('role_name','crossing_other_250_2')
        other_wp=mapping.get_waypoint_xodr(2,1,60) if cfg.get("opposite_other") else mapping.get_waypoint_xodr(3,-1,cfg.get("other_station_m",350))
        if other_wp is None:raise ValueError('Crossing highway lane missing')
        other=world.spawn_actor(other_bp,other_wp.transform);owned.append(other)
        other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        other.set_light_state(carla.VehicleLightState.LeftBlinker if cfg.get("other_intends_left") else carla.VehicleLightState.NONE)
        if cfg.get("governing_control"):
            landmarks=mapping.get_all_landmarks()
            if not any(str(x.id)=="2509001" for x in landmarks):raise ValueError("Authored governing device missing from Native landmark inventory")
            for actor in world.get_actors().filter("traffic.traffic_light*"):
                actor.set_state(carla.TrafficLightState.Off if cfg.get("signal_inoperative") else carla.TrafficLightState.Green);actor.freeze(True)
        for _ in range(20): world.tick()
        for spec in cfg['cameras']:
            name,w,h = spec['name'],spec['width'],spec['height']
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:
                bp.set_attribute(key,str(value))
            if name == 'overview': pose = carla.Transform(carla.Location(x=0,y=0,z=80),carla.Rotation(pitch=-90))
            elif name == 'approach': pose = carla.Transform(carla.Location(x=-12,y=0,z=8),carla.Rotation(pitch=-15))
            elif name == 'reference_corner': pose = carla.Transform(carla.Location(x=-18,y=18,z=28),carla.Rotation(pitch=-55))
            else: pose = carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation())
            camera = world.spawn_actor(bp,pose,attach_to=ego if name in ('overview','approach','driver_reference') else None)
            owned.append(camera); cameras[name]=camera; queues[name]=queue.Queue();camera.listen(queues[name].put)
            stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra',
                '-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
        capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
        started=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(out/'video_frames.jsonl') as fmap, (out/'body_history.jsonl').open('x') as body, (out/'crossing_history.jsonl').open('x') as crossing:
            for index in range(cfg['duration_s']*cfg['rate_hz']):
                speed=ego.get_velocity().length(); effort=max(0,min(.6,.3*(cfg['requested_speed_mps']-speed)))
                ego.apply_control(carla.VehicleControl(throttle=0 if cfg.get("wait_for_other",False) and other.get_transform().location.y<7 else effort,brake=1 if cfg.get("wait_for_other",False) and other.get_transform().location.y<7 else max(0,min(.5,.2*(speed-cfg['requested_speed_mps'])))))
                other_speed=other.get_velocity().length()
                steer=0
                if cfg.get('other_makes_left'):
                    path=[(67,1.75),(30,1.75),(10,1.75),(7,1.75),(3,1),(0,-2),(-1.75,-7),(-1.75,-40),(-1.75,-100)]
                    pose=other.get_transform();x,y=pose.location.x,pose.location.y
                    nearest=min(range(len(path)),key=lambda j:(path[j][0]-x)**2+(path[j][1]-y)**2)
                    look=path[min(nearest+1,len(path)-1)];err=(math.atan2(look[1]-y,look[0]-x)-math.radians(pose.rotation.yaw)+math.pi)%(2*math.pi)-math.pi
                    steer=max(-.7,min(.7,1.4*err))
                other.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.3*(5-other_speed))),brake=max(0,min(.5,.2*(other_speed-5))),steer=steer))
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
                other_vertices=[[v.x,v.y,v.z] for v in other.bounding_box.get_world_vertices(other.get_transform())]
                controls=[{'id':a.id,'type':a.type_id} for a in world.get_actors() if a.type_id.startswith('traffic.')]
                crossing.write(json.dumps({'frame':frame,'time_s':now,'ego_vertices_m':vertices,'other_vertices_m':other_vertices,
                   'ego_speed_mps':ego.get_velocity().length(),'other_speed_mps':other.get_velocity().length(),
                   'official_controls':controls})+'\n')
                capture.capture(frame,now)
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
    history=[json.loads(line) for line in (out/'crossing_history.jsonl').read_text().splitlines() if line]
    def overlaps(vertices):
      xs=[v[0] for v in vertices];ys=[v[1] for v in vertices]
      return min(xs)<7 and max(xs)>-7 and min(ys)<7 and max(ys)>-7
    events={}
    for role in ('ego','other'):
      row=next((r for r in history if overlaps(r[role+'_vertices_m'])),None)
      if row is None:raise ValueError('Missing actual original crossing entry: '+role)
      events[role]={'frame':row['frame'],'time_s':row['time_s']}
    other_clear=next((r['time_s'] for r in history if ((max(v[1] for v in r['other_vertices_m'])<-7 if cfg.get('other_makes_left') else max(v[0] for v in r['other_vertices_m'])<-7) if cfg.get('opposite_other') else min(v[1] for v in r['other_vertices_m'])>7)),None)
    ego_clear=next((r['frame'] for r in history if min(v[0] for v in r['ego_vertices_m'])>7),None)
    if other_clear is None or ego_clear is None:raise ValueError('Incomplete crossing clearance')
    geometry={'source':'authored scene.xodr and Native OpenDRIVE readback','physical_verification':{'road_xodr':'road.xodr',
      'crossing_history':'crossing_history.jsonl','median_barrier_objects_authored':[250101,250102],
      'actual_barrier_pixels_verified':False},
      'prohibited_median_polygons':[[[-400,-.5],[-20,-.5],[-20,.5],[-400,.5]],[[20,-.5],[400,-.5],[400,.5],[20,.5]]],
      'median_opening_polygons':[[[-20,-.5],[20,-.5],[20,.5],[-20,.5]]],
      'intersection_polygon':[[-7,-7],[7,-7],[7,7],[-7,7]]}
    (out/'scenario_geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
    packet={'law_id':cfg['law_id'],'diagnostic_fixture_only':False,'entry_events':events,
      'motion_rows':[{'frame':r['frame'],'ego_speed_mps':r['ego_speed_mps'],'other_speed_mps':r['other_speed_mps']} for r in history],
      'official_control_inventory':[r['official_controls'] for r in history],
      'highway_ids':[1,3],'intersection_polygon':geometry['intersection_polygon'],'separate_crossing_spacing_m':35,
      'other_clearance_time_s':other_clear,'ego_clearance_frame':ego_clear,
      'ego_approach_xy':[1,0],'other_approach_xy':[-1,0] if cfg.get('opposite_other') else [0,1],'crossing_id':'road1-road3-opening',
      'control_context':{'governing_control':cfg.get('governing_control','none'),'signal_inoperative':cfg.get('signal_inoperative',False),'authority':'authored synthetic authority designation; actual jurisdiction must be reviewed'},'opposite_context':{'opposite_approach':cfg.get('opposite_other',False),'controller_intends_left':cfg.get('other_intends_left',False),'controller_makes_left':cfg.get('other_makes_left',False),'driver_intent_is_not_inferred_from_lamp':True},'resolution_s':.05,'other_clearance_frame':next(r['frame'] for r in history if r['time_s']==other_clear)}
    packet['scope_context']={'highway_designation': 'Authored synthetic public highway; independent factual/legal jurisdiction review required', 'vehicle_blueprint': 'vehicle.lincoln.mkz_2020', 'controller_scope': 'Physical throttle/brake/steering commands on conventional vehicle; no automated-driving-system legal inference', 'cell_identity': 'C125763', 'fixed_layout': 'median_opening', 'fixed_maneuver': 'travel', 'fixed_control': 'yield_sign', 'source': 'Exact case config plus authored OpenDRIVE; actual public dedication/driver identity is not established by CPU fixture'}
    (out/'case_observation.json').write_text(json.dumps(packet,indent=2)+'\n')
    finalize(out,out/'analysis-report.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir',default='.')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check: print(json.dumps(check()))
    else: run(args)
