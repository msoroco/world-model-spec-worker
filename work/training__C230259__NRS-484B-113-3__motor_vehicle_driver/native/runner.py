"""Original Native backing/other-moving-vehicle draft; --check is CARLA-free."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from layout import CONFLICT,check as layout_check,open_drive

FRAMES=600
CAMERAS=(('overview',1920,1080,10,-14,18,-65),('approach',1280,720,22,-11,6,-25),
         ('reference_corner',1280,720,-10,-10,7,-30),('driver_reference',1280,720,12,9,9,-35))


def check():
    cfg=json.loads(Path('config.json').read_text())
    if cfg['cell_id']!='C230259' or cfg['law_id']!='NRS-484B-113-3' or cfg['case_suffix'] not in ('controlled_1','controlled_2','pedestrian_1','pedestrian_2'):
        raise ValueError('Exact assignment differs')
    if cfg['rate_hz']!=20 or cfg['duration_s']!=30 or len(CAMERAS)!=4:raise ValueError('Capture policy differs')
    if cfg.get('other_start_x_m',-35) not in (-35,-45) or cfg.get('ego_start_x_m',23) not in (23,27):
        raise ValueError('Unreviewed engineering start position')
    return {'passed':True,'geometry':layout_check(),'frame_count':FRAMES,
            'section_stem_recovered':True,'native_imported':False,'physical_acceptance_claimed':False}


def actor_row(actor):
    transform=actor.get_transform();velocity=actor.get_velocity()
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,
        'center_xy_m':[transform.location.x,transform.location.y],
        'body_xy_m':[[p.x,p.y] for p in actor.bounding_box.get_world_vertices(transform)],
        'velocity_xy_mps':[velocity.x,velocity.y],
        'speed_mps':math.hypot(velocity.x,velocity.y)}


def execute(output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    cfg=json.loads(Path('config.json').read_text());check();output=Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use fresh materialized exact-case output')
    client=carla.Client(host,port);client.set_timeout(180)
    old=client.get_world();saved=snapshot(client)
    if old.get_settings().synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned=[];encoders={};queues={};changed=False;capture=None
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True;settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings)
        waypoint=world.get_map().get_waypoint(carla.Location(x=12,y=-3,z=1),project_to_road=True,lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=-1:
            raise RuntimeError('Native highway lane readback failed')
        other_waypoint=world.get_map().get_waypoint(carla.Location(x=cfg.get('other_start_x_m',-35),y=-3,z=1),project_to_road=True,lane_type=carla.LaneType.Driving)
        if other_waypoint is None or other_waypoint.road_id!=1 or other_waypoint.lane_id!=-1:
            raise RuntimeError('Moving-traffic highway route readback failed')
        bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        ego=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=cfg.get('ego_start_x_m',23),y=-7,z=1.2),carla.Rotation(yaw=0)))
        other=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=cfg.get('other_start_x_m',-35),y=-3,z=1.2),carla.Rotation(yaw=0)))
        if ego is None or other is None:raise RuntimeError('Original vehicle spawn failed')
        if ego.id==other.id or not ego.type_id.startswith('vehicle.') or not other.type_id.startswith('vehicle.'):
            raise RuntimeError('Distinct original vehicle classification failed')
        owned.extend((ego,other))
        pedestrian=None
        if cfg['case_suffix'].startswith('pedestrian_'):
            walker_bp=next((item for item in world.get_blueprint_library().filter('walker.pedestrian.*') if item.id),None)
            if walker_bp is None:raise RuntimeError('Pedestrian blueprint unavailable')
            pedestrian=world.try_spawn_actor(walker_bp,carla.Transform(carla.Location(x=12,y=4,z=1.2),carla.Rotation(yaw=-90)))
            if pedestrian is None or not pedestrian.type_id.startswith('walker.pedestrian.'):
                raise RuntimeError('Original pedestrian spawn failed')
            owned.append(pedestrian)
        for name,width,height,x,y,z,pitch in CAMERAS:
            cbp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',85),('sensor_tick',.05)):
                cbp.set_attribute(key,str(value))
            sensor=world.spawn_actor(cbp,carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch)))
            owned.append(sensor);received=queue.Queue();sensor.listen(received.put);queues[name]=received
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20','-i','-',
                '-frames:v',str(FRAMES),'-c:v','ffv1',str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,cfg['case_id'],visibility=False,
            required_observations=cfg.get('required_atoms',[]))
        with (output/'native-motion.jsonl').open('x') as motion,FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                # Timing is the only selected comparison variable; both cases use the same backing command.
                backing=(245<=index<335) if cfg['case_suffix'] in ('controlled_1','pedestrian_1') else (55<=index<145)
                ego.set_target_velocity(carla.Vector3D(x=-2.5 if backing else 0,y=.8 if backing else 0,z=0))
                other.set_target_velocity(carla.Vector3D(x=6 if index<300 else 0,y=0,z=0))
                if pedestrian is not None:
                    pedestrian.apply_control(carla.WalkerControl(direction=carla.Vector3D(x=0,y=-1,z=0),
                        speed=.8 if 50<=index<300 else 0))
                native=world.tick()
                original_row={'native_frame':native,'frame':native,'video_frame':index,'time_s':index/20,
                    'source_kind':'original_native','ego':actor_row(ego),'other':actor_row(other),
                    'pedestrian':actor_row(pedestrian) if pedestrian is not None else None,
                    'backing_commanded':backing}
                capture.capture(native,index/20,extra={'c230259_native':original_row})
                motion.write(json.dumps(original_row,allow_nan=False)+'\n')
                camera_frames={}
                for name,*_ in CAMERAS:
                    image=queues[name].get(timeout=30)
                    while image.frame<native:image=queues[name].get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original four-camera join differs')
                    encoders[name].stdin.write(image.raw_data);camera_frames[name]=image.frame
                frame_map.append(native,index/20,camera_native_frames=camera_frames)
        for name,process in encoders.items():
            process.stdin.close();error=process.stderr.read()
            if process.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original FFV1 encoding failed: '+name+error.decode()[-400:])
        capture.close(confirmed=True);capture=None
        (output/'road.xodr').write_text(open_drive())
        (output/'traffic-context.json').write_text(json.dumps({'source_kind':'original_native',
            'cell_id':'C230259','conflict_region':CONFLICT,'section_stem_recovered':True,
            'section_source':'https://www.leg.state.nv.us/NRS/NRS-484B.html',
            'other_highway_use_reviewed':True,'other_road_id':other_waypoint.road_id,
            'other_lane_id':other_waypoint.lane_id,'other_route_direction':'increasing road s',
            'other_commanded_speed_mps':6,
            'driver_control_reviewed':True,'ego_actor_id':ego.id,'other_actor_id':other.id,
            'driver_control_source':'runner.py script controls ego target velocity per original Native frame',
            'pedestrian_presence_reviewed':True,'pedestrian_actor_count_at_start':int(pedestrian is not None),
            'pedestrian_actor_id':pedestrian.id if pedestrian is not None else None,
            'precedence_reviewed':False,'right_of_way_legal_verdict':None},indent=2)+'\n')
        return {'frames':FRAMES,'camera_names':list(queues),
            'section_stem_recovered':True,'physical_acceptance_claimed':False}
    finally:
        if capture is not None:
            try:capture.close(confirmed=False)
            except Exception:pass
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        if changed:restore(client,saved)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:print(json.dumps(check()))
    else:
        if args.output_dir is None:parser.error('Original Native output directory required')
        print(json.dumps(execute(args.output_dir,args.host,args.port)))
