"""Exact 223-1b marked-lane capture; run only against an operator-supplied CARLA endpoint."""
import argparse, json, math, queue, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def check():
    cfg=json.loads((ROOT/'config.json').read_text())
    tree=ET.parse(ROOT/'scene.xodr')
    roads=tree.findall('road')
    assert len(roads)==1 and roads[0].attrib['id']=='1'
    for lane in ('-1','-2'):
        assert roads[0].find("lanes/laneSection/right/lane[@id='"+lane+"']") is not None
    mark=roads[0].find("lanes/laneSection/right/lane[@id='-1']/roadMark")
    assert mark is not None and mark.attrib['type']=='broken'
    assert cfg['duration_s']>=20 and cfg['camera']['width']>=960
    assert cfg['required_atoms']==['kin.speed']
    print(json.dumps({'offline_geometry':'two same-direction marked lanes on connected straight road','carla_contacted':False}))

def run(args):
    import carla, numpy as np
    from worker_exchange.world_restore import snapshot,restore
    from worker_exchange.native_output import FrameMap
    from pipeline_capture import PipelineCapture
    cfg=json.loads((ROOT/'config.json').read_text())
    output=Path(args.output_dir).resolve()
    if output!=ROOT.resolve() and not (output/'config.json').is_file(): raise ValueError('Materialized exact case required')
    client=carla.Client(args.host,args.port);client.set_timeout(60)
    saved=snapshot(client);owned=[];capture=None;encoder=None;camera=None;frames=0
    try:
        world=client.generate_opendrive_world((ROOT/'scene.xodr').read_text(),carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=30,wall_height=0,additional_width=0,smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        setting=world.get_settings();setting.synchronous_mode=True;setting.fixed_delta_seconds=.05;world.apply_settings(setting)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        world.tick()
        road=world.get_map()
        links=[(a.road_id,a.lane_id,b.road_id,b.lane_id) for a,b in road.get_topology()]
        if road.get_waypoint_xodr(1,-1,250) is None or road.get_waypoint_xodr(1,-2,250) is None: raise ValueError('Two Native marked lanes absent')
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=-130,y=5.25,z=.5),carla.Rotation(yaw=0)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        target_bp=world.get_blueprint_library().find('vehicle.tesla.model3');target_bp.set_attribute('role_name','target_lane_vehicle')
        target=world.spawn_actor(target_bp,carla.Transform(carla.Location(x=-150,y=1.75,z=.5),carla.Rotation(yaw=0)))
        owned.append(target);target.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(20):world.tick()
        cam_bp=world.get_blueprint_library().find('sensor.camera.rgb')
        for k,v in [('image_size_x',cfg['camera']['width']),('image_size_y',cfg['camera']['height']),('fov',cfg['camera']['fov_deg']),('sensor_tick','0')]:cam_bp.set_attribute(k,str(v))
        camera=world.spawn_actor(cam_bp,carla.Transform(carla.Location(x=-15,y=0,z=35),carla.Rotation(pitch=-70)))
        owned.append(camera);images=queue.Queue();camera.listen(images.put)
        encoder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',str(cfg['camera']['width'])+'x'+str(cfg['camera']['height']),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(output/'raw.mkv')],stdin=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],required_observations=cfg['required_atoms'])

        (output/'lane_geometry.json').write_text(json.dumps({'road_id':1,'same_direction_lane_ids':[-1,-2],'lane_boundary_marking':'broken white','lane_boundary_y_m':3.5,'native_topology':links})+'\n')
        start=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'lane_change_history.jsonl').open('x') as history:
            for i in range(int(cfg['duration_s']*20)):
                tr=ego.get_transform();pos=tr.location;vel=ego.get_velocity();speed=math.hypot(vel.x,vel.y)
                if pos.x>-100:ego.set_light_state(carla.VehicleLightState.LeftBlinker)
                target_y=1.75 if pos.x>-80 else 5.25
                desired=math.degrees(math.atan2(target_y-pos.y,12))
                error=(desired-tr.rotation.yaw+180)%360-180
                steering=max(-.5,min(.5,error/35))
                ego.apply_control(carla.VehicleControl(throttle=.35 if speed<5 else 0,brake=.1 if speed>6 else 0,steer=steering))
                target_speed=math.hypot(target.get_velocity().x,target.get_velocity().y)
                target.apply_control(carla.VehicleControl(throttle=.32 if target_speed<5 else 0,brake=.1 if target_speed>6 else 0))
                frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
                image=images.get(timeout=30)
                while image.frame<frame:image=images.get(timeout=30)
                if image.frame!=frame: raise ValueError('Camera original frame mismatch')
                rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(cfg['camera']['height'],cfg['camera']['width'],4)[:,:,:3][:,:,::-1]
                encoder.stdin.write(rgb.tobytes())
                fmap.append(frame,now)
                vertices=[[v.x,v.y] for v in ego.bounding_box.get_world_vertices(ego.get_transform())]
                target_vertices=[[v.x,v.y] for v in target.bounding_box.get_world_vertices(target.get_transform())]
                history.write(json.dumps({'frame':frame,'time_s':now,'ego_body_xy_m':vertices,'target_body_xy_m':target_vertices,'ego_speed_mps':math.hypot(ego.get_velocity().x,ego.get_velocity().y),'target_speed_mps':math.hypot(target.get_velocity().x,target.get_velocity().y),'left_blinker':bool(int(ego.get_light_state()) & int(carla.VehicleLightState.LeftBlinker)),'driver_check_recorded':False})+'\n')
                capture.capture(frame,now,extra={'left_turn_approach':{'body_vertices_xy_m':vertices,'control':{'throttle':ego.get_control().throttle,'steer':ego.get_control().steer,'brake':ego.get_control().brake}}})
                frames+=1

        capture.close(confirmed=True);capture=None
        encoder.stdin.close()
        if encoder.wait(timeout=120): raise ValueError('Original camera encoder failed')
        encoder=None
        subprocess.run([sys.executable,str(output/'analyze.py'),'--attempt',str(output),'--output',str(output/'analysis-report.json')],check=True)
    finally:
        if capture:capture.close(confirmed=False)
        if encoder:
            encoder.stdin.close();encoder.wait(timeout=120)
        for actor in reversed(owned):
            try:actor.stop() if actor.type_id.startswith('sensor.') else None;actor.destroy()
            except Exception:pass
        receipt=restore(client,saved)
        (output/'world-restore.json').write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--output-dir');p.add_argument('--host');p.add_argument('--port',type=int);a=p.parse_args()
    if a.check:check()
    else:
        if not all([a.output_dir,a.host,a.port]):p.error('Capture requires output, host and port')
        run(a)
