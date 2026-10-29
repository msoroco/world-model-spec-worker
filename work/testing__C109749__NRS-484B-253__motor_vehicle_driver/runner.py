"""Exact 253 native left-turn yield capture; run only against an operator-supplied CARLA endpoint."""
import argparse, json, math, queue, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def check():
    cfg=json.loads((ROOT/'config.json').read_text())
    tree=ET.parse(ROOT/'scene.xodr')
    roads={int(r.attrib['id']):r for r in tree.findall('road')}
    assert {1,2,3,4,11,12,13}<=set(roads)
    assert all(len(r.findall('signals/signal'))==0 for r in roads.values())
    assert any(c.attrib['incomingRoad']=='1' and c.attrib['connectingRoad']=='13' for c in tree.findall('junction/connection'))
    assert roads[13].find('planView/geometry/arc') is not None
    assert cfg['duration_s']>=20 and cfg['camera']['width']>=960 and cfg['camera']['height']>=540
    assert cfg['required_atoms']==['kin.speed']
    print(json.dumps({'offline_geometry':'connected curved left turn, undivided opposing roads','signals':0,'capture_channels':len(cfg['recording_description']['channels']),'carla_contacted':False}))

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
        if not any(a==1 and c==13 for a,_,c,_ in links): raise ValueError('Native left-turn road link absent')
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=-38,y=1.75,z=.5),carla.Rotation(yaw=0)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        ego.set_light_state(carla.VehicleLightState.LeftBlinker)
        opposing_bp=world.get_blueprint_library().find('vehicle.tesla.model3');opposing_bp.set_attribute('role_name','opposing_through')
        opposing=world.spawn_actor(opposing_bp,carla.Transform(carla.Location(x=35,y=-1.75,z=.5),carla.Rotation(yaw=180)))
        owned.append(opposing);opposing.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(20):world.tick()
        cam_bp=world.get_blueprint_library().find('sensor.camera.rgb')
        for k,v in [('image_size_x',cfg['camera']['width']),('image_size_y',cfg['camera']['height']),('fov',cfg['camera']['fov_deg']),('sensor_tick','0')]:cam_bp.set_attribute(k,str(v))
        camera=world.spawn_actor(cam_bp,carla.Transform(carla.Location(x=-15,y=0,z=35),carla.Rotation(pitch=-70)))
        owned.append(camera);images=queue.Queue();camera.listen(images.put)
        encoder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',str(cfg['camera']['width'])+'x'+str(cfg['camera']['height']),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(output/'raw.mkv')],stdin=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],required_observations=cfg['required_atoms'])


        start=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'left253_history.jsonl').open('x') as history:
            for i in range(int(cfg['duration_s']*20)):
                tr=ego.get_transform();pos=tr.location;vel=ego.get_velocity();speed=math.hypot(vel.x,vel.y)
                waypoints=[(-12,1.75),(-4,1.5),(2,-2),(1.75,-14),(1.75,-35)]
                target=next((p for p in waypoints if math.hypot(p[0]-pos.x,p[1]-pos.y)>5),waypoints[-1])
                desired=math.degrees(math.atan2(target[1]-pos.y,target[0]-pos.x))
                error=(desired-tr.rotation.yaw+180)%360-180
                steering=max(-.65,min(.65,error/45))
                other_x=opposing.get_transform().location.x
                waiting=pos.x>=-5 and other_x>-10
                ego.apply_control(carla.VehicleControl(throttle=0 if waiting else (.35 if speed<4 else .05),brake=1 if waiting else (.2 if speed>5 else 0),steer=0 if waiting else steering))
                opposing_speed=math.hypot(opposing.get_velocity().x,opposing.get_velocity().y)
                opposing.apply_control(carla.VehicleControl(throttle=.32 if opposing_speed<5 else 0,brake=.15 if opposing_speed>6 else 0))
                frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
                image=images.get(timeout=30)
                while image.frame<frame:image=images.get(timeout=30)
                if image.frame!=frame: raise ValueError('Camera original frame mismatch')
                rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(cfg['camera']['height'],cfg['camera']['width'],4)[:,:,:3][:,:,::-1]
                encoder.stdin.write(rgb.tobytes())
                fmap.append(frame,now)
                vertices=[[v.x,v.y] for v in ego.bounding_box.get_world_vertices(ego.get_transform())]
                opposing_vertices=[[v.x,v.y] for v in opposing.bounding_box.get_world_vertices(opposing.get_transform())]
                other_speed=math.hypot(opposing.get_velocity().x,opposing.get_velocity().y)
                lights=int(ego.get_light_state())
                history.write(json.dumps({'frame':frame,'time_s':now,'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'ego_body_xy_m':vertices,'oncoming_body_xy_m':opposing_vertices,'ego_speed_mps':math.hypot(ego.get_velocity().x,ego.get_velocity().y),'oncoming_speed_mps':other_speed,'ego_turn_intent':'left','ego_turn_progress':pos.x>-3 and pos.y<0,'ego_left_blinker':bool(lights & int(carla.VehicleLightState.LeftBlinker))})+'\n')
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
