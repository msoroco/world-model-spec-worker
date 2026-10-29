"""One original signaled lane-change episode on a two-lane one-way road."""
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
    assert {lane.get('id') for lane in road.findall('.//lane[@type="driving"]')} == {'-1','-2'}
    assert cfg['duration_s'] == 45 and cfg['rate_hz'] == 20
    assert [c['name'] for c in cfg['cameras']] == ['overview','approach','reference_corner','driver_reference']
    assert [(c['width'],c['height']) for c in cfg['cameras']] == [(1920,1080),(1280,720),(1280,720),(1280,720)]
    assert cfg['required_atoms'] == ['kin.speed','kin.velocity','st.one_way_roadway'] and cfg['source_packets'] == ['scenario_geometry']
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
        mapping = world.get_map(); wp = mapping.get_waypoint_xodr(1,-2,100)
        if wp is None: raise ValueError('Native lane 1/-1 is missing')
        blueprint = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name','subject_lane_change_223')
        ego = world.spawn_actor(blueprint, wp.transform); owned.append(ego)
        other_bp=world.get_blueprint_library().find('vehicle.tesla.model3');other_bp.set_attribute('role_name','target_lane_vehicle')
        other_wp=mapping.get_waypoint_xodr(1,-1,cfg.get("target_station_m",220));other=world.spawn_actor(other_bp,other_wp.transform);owned.append(other)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True));other.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(20): world.tick()
        for spec in cfg['cameras']:
            name,w,h = spec['name'],spec['width'],spec['height']
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in [('image_size_x',w),('image_size_y',h),('fov',spec['fov_deg']),('sensor_tick',0)]:
                bp.set_attribute(key,str(value))
            if name == 'overview': pose = carla.Transform(carla.Location(x=0,y=0,z=65),carla.Rotation(pitch=-90))
            elif name == 'approach': pose = carla.Transform(carla.Location(x=-12,y=0,z=8),carla.Rotation(pitch=-15))
            elif name == 'reference_corner': pose = carla.Transform(carla.Location(x=180,y=14,z=30),carla.Rotation(pitch=-65))
            else: pose = carla.Transform(carla.Location(x=0,y=0,z=1.5),carla.Rotation())
            camera = world.spawn_actor(bp,pose,attach_to=ego if name in ('overview','approach','driver_reference') else None)
            owned.append(camera); cameras[name]=camera; queues[name]=queue.Queue();camera.listen(queues[name].put)
            stream=(out/(name+'.encoder.log')).open('x');streams[name]=stream
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','bgra',
                '-s',f'{w}x{h}','-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(out/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=stream)
        geometry={'source':'Native generated OpenDRIVE road and original lane readback','physical_verification':{'native_map':'road.xodr','lane_readback':'lane_history.jsonl'},
          'directed_roadways':[{'polygon':[[0,-7],[1500,-7],[1500,7],[0,7]],'direction_xy':[1,0],'one_way':True}],
          'lane_centers_native_y_m':{'-2':mapping.get_waypoint_xodr(1,-2,100).transform.location.y,'-1':mapping.get_waypoint_xodr(1,-1,100).transform.location.y},
          'marking':'OpenDRIVE broken white lane divider; Native pixels unverified'}
        (out/'scenario_geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
        capture=PipelineCapture(client,ego,out,cfg['selected_case_id'],required_observations=cfg['required_atoms'])
        started=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(out/'video_frames.jsonl') as fmap, (out/'lane_history.jsonl').open('x') as lane:
            for index in range(cfg['duration_s']*cfg['rate_hz']):
                speed=ego.get_velocity().length();effort=max(0,min(.55,.3*(cfg['requested_speed_mps']-speed)))
                other_speed=other.get_velocity().length();other.apply_control(carla.VehicleControl(throttle=max(0,min(.5,.25*(5-other_speed)))))
                if index>=cfg.get("signal_tick",80):ego.set_light_state(carla.VehicleLightState.LeftBlinker)
                target_y=geometry['lane_centers_native_y_m']['-2'] if index<160 else geometry['lane_centers_native_y_m']['-1']
                lateral=ego.get_transform().location.y-target_y;steer=max(-.35,min(.35,-.16*lateral))
                ego.apply_control(carla.VehicleControl(throttle=effort,brake=max(0,min(.5,.2*(speed-cfg['requested_speed_mps']))),steer=steer))
                frame=world.tick(); now=world.get_snapshot().timestamp.elapsed_seconds-started
                native_images={}
                for spec in cfg['cameras']:
                    name=spec['name']; image=queues[name].get(timeout=30)
                    while image.frame<frame: image=queues[name].get(timeout=30)
                    if image.frame!=frame: raise ValueError('Camera original tick mismatch: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    native_images[name]={'frame':image.frame,'sha256':hashlib.sha256(image.raw_data).hexdigest()}
                transform=ego.get_transform(); vertices=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(transform)]
                other_t=other.get_transform();other_vertices=[[v.x,v.y,v.z] for v in other.bounding_box.get_world_vertices(other_t)]
                lane.write(json.dumps({'frame':frame,'time_s':now,'subject_vertices_m':vertices,'target_vehicle_vertices_m':other_vertices,
                  'subject_lane_id':mapping.get_waypoint(transform.location).lane_id,'target_lane_id':mapping.get_waypoint(other_t.location).lane_id,
                  'subject_speed_mps':ego.get_velocity().length(),'target_speed_mps':other.get_velocity().length(),
                  'left_indicator_bit':bool(ego.get_light_state() & carla.VehicleLightState.LeftBlinker),'camera_originals':native_images})+'\n')
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
    finalize(out,out/'analysis-report.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--output-dir',default='.')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check: print(json.dumps(check()))
    else: run(args)
