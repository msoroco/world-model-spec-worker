"""Exact 450-2 near-side crosswalk stop capture; run only against an operator-supplied CARLA endpoint."""
import argparse, json, math, queue, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def check():
    cfg=json.loads((ROOT/'config.json').read_text())
    tree=ET.parse(ROOT/'scene.xodr')
    roads={int(r.attrib['id']):r for r in tree.findall('road')}
    assert {1,2,3,4,11,12}<=set(roads)
    signals=tree.findall('.//signal')
    assert len(signals)==1 and signals[0].attrib['id']=='2001'
    assert not tree.findall('.//object')
    assert cfg['stop_control']['selected_branch']=='near_side_crosswalk'
    assert cfg['duration_s']>=20 and cfg['required_atoms']==['kin.speed']
    print(json.dumps({'offline_geometry':'West governing stop sign; physical near-side crosswalk tiles; no stopline','carla_contacted':False}))

def run(args):
    import carla, numpy as np
    from worker_exchange.world_restore import snapshot,restore
    from worker_exchange.native_output import FrameMap
    from pipeline_capture import PipelineCapture
    from crosswalk_markings import spawn as spawn_crosswalk,observe as observe_crosswalk
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
        if not any(a==1 and c==11 for a,_,c,_ in links): raise ValueError('Native stop approach link absent')
        markers=spawn_crosswalk(carla,world);owned.extend(markers)
        for _ in range(3):world.tick()
        tiles=observe_crosswalk(markers)
        if len(tiles)!=80:raise ValueError('Native near-side crosswalk incomplete')
        signs=[{'id':l.id,'road_id':l.road_id,'s_m':l.s} for l in road.get_all_landmarks()]
        if not any(str(v['id'])=='2001' for v in signs):raise ValueError('Native governing stop sign absent')
        bp=world.get_blueprint_library().find('vehicle.lincoln.mkz_2020');bp.set_attribute('role_name','subject')
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=-38,y=1.75,z=.5),carla.Rotation(yaw=0)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(20):world.tick()
        cam_bp=world.get_blueprint_library().find('sensor.camera.rgb')
        for k,v in [('image_size_x',cfg['camera']['width']),('image_size_y',cfg['camera']['height']),('fov',cfg['camera']['fov_deg']),('sensor_tick','0')]:cam_bp.set_attribute(k,str(v))
        camera=world.spawn_actor(cam_bp,carla.Transform(carla.Location(x=-15,y=0,z=35),carla.Rotation(pitch=-70)))
        owned.append(camera);images=queue.Queue();camera.listen(images.put)
        encoder=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n','-f','rawvideo','-pix_fmt','rgb24','-s',str(cfg['camera']['width'])+'x'+str(cfg['camera']['height']),'-r','20','-i','pipe:0','-an','-c:v','ffv1','-pix_fmt','bgr0',str(output/'raw.mkv')],stdin=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],required_observations=cfg['required_atoms'])
        (output/'stop_control.json').write_text(json.dumps(dict(cfg['stop_control'],native_sign_inventory=signs,native_crosswalk_tile_count=len(tiles)))+'\n')

        start=world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output/'video_frames.jsonl') as fmap,(output/'stop_history.jsonl').open('x') as history:
            hold=0
            for i in range(int(cfg['duration_s']*20)):
                tr=ego.get_transform();pos=tr.location;vel=ego.get_velocity();speed=math.hypot(vel.x,vel.y)
                remaining=-14.5-pos.x
                requested=min(4.0,math.sqrt(3*max(0,remaining)))
                if remaining<.5 and speed<.08:hold+=1
                if hold>=40:requested=4.0
                error=requested-speed
                ego.apply_control(carla.VehicleControl(throttle=max(0,min(.4,error*.3)),brake=max(0,min(1,-error*.5)),steer=0))
                frame=world.tick();now=world.get_snapshot().timestamp.elapsed_seconds-start
                image=images.get(timeout=30)
                while image.frame<frame:image=images.get(timeout=30)
                if image.frame!=frame: raise ValueError('Camera original frame mismatch')
                rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(cfg['camera']['height'],cfg['camera']['width'],4)[:,:,:3][:,:,::-1]
                encoder.stdin.write(rgb.tobytes())
                fmap.append(frame,now)
                vertices=[[v.x,v.y] for v in ego.bounding_box.get_world_vertices(ego.get_transform())]
                history.write(json.dumps({'frame':frame,'time_s':now,'ego_body_xy_m':vertices,'ego_speed_mps':math.hypot(ego.get_velocity().x,ego.get_velocity().y),'applied_brake':ego.get_control().brake,'native_crosswalk_tile_count':len(tiles)})+'\n')
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
