"""Original Native public-premises parking attempt; --check is CARLA-free."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from layout import AISLE, BAY, check as layout_check, open_drive

FRAMES=600
CAMERAS=(('overview',1920,1080,3,-17,20,-65),
         ('approach',1280,720,-16,-13,6,-20),
         ('reference_corner',1280,720,3,-13,6,-30),
         ('driver_reference',1280,720,3,7,10,-45))


def check():
    geometry=layout_check()
    cfg=json.loads(Path('config.json').read_text())
    if cfg['cell_id']!='C200542' or cfg['law_id']!='LVMC-11-52-136' or cfg['case_suffix'] not in ('controlled_1','controlled_2'):
        raise ValueError('Frozen assignment or exact case differs')
    if cfg['duration_s']!=30 or cfg['rate_hz']!=20 or len(CAMERAS)!=4:
        raise ValueError('Original duration/camera contract differs')
    return {'passed':True,'case_id':cfg['case_id'],'geometry':geometry,
            'frames':FRAMES,'native_imported':False,'physical_acceptance_claimed':False}


def actor_row(actor):
    transform=actor.get_transform();velocity=actor.get_velocity()
    body=actor.bounding_box.get_world_vertices(transform)
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,
            'center_xy_m':[transform.location.x,transform.location.y],
            'body_xy_m':[[p.x,p.y] for p in body],
            'speed_mps':math.hypot(velocity.x,velocity.y)}


def execute(output,host,port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    cfg=json.loads(Path('config.json').read_text());check()
    output=Path(output).resolve()
    if output.exists():raise ValueError('Use a fresh original Native attempt directory')
    client=carla.Client(host,port);client.set_timeout(180)
    old=client.get_world();saved=snapshot(client)
    if old.get_settings().synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    output.mkdir(parents=True)
    owned=[];encoders={};queues={};changed=False
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        mapping=world.get_map()
        waypoint=mapping.get_waypoint(carla.Location(x=3.5,y=-6,z=1),project_to_road=True,
                                     lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=-1:
            raise RuntimeError('Native public-premises drivable surface readback failed')
        # Diagnostic hatching is rendered into all original camera views. Its official status remains unreviewed.
        for x in (0,1,2,3,4,5,6,7):
            world.debug.draw_line(carla.Location(x=x,y=-8,z=.05),
                carla.Location(x=min(x+2,7),y=-4,z=.05),thickness=.08,
                color=carla.Color(255,255,0),life_time=35,persistent_lines=False)
        for y in (-8,-4):
            world.debug.draw_line(carla.Location(x=0,y=y,z=.05),
                carla.Location(x=7,y=y,z=.05),thickness=.12,
                color=carla.Color(255,255,0),life_time=35,persistent_lines=False)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        target_y=-2.0 if cfg['case_suffix']=='controlled_1' else -6.0
        vehicle=world.try_spawn_actor(bp,carla.Transform(
            carla.Location(x=-20,y=target_y,z=1.3),carla.Rotation(yaw=0)))
        if vehicle is None:raise RuntimeError('Original parked vehicle spawn failed')
        owned.append(vehicle)
        for name,width,height,x,y,z,pitch in CAMERAS:
            camera_bp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',85),('sensor_tick',.05)):
                camera_bp.set_attribute(key,str(value))
            sensor=world.spawn_actor(camera_bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                carla.Rotation(pitch=pitch)))
            owned.append(sensor);received=queue.Queue();sensor.listen(received.put);queues[name]=received
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20','-i','-',
                '-frames:v',str(FRAMES),'-c:v','ffv1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with (output/'native-vehicle.jsonl').open('x') as motion,FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                vehicle.set_target_velocity(carla.Vector3D(x=4 if index<118 else 0,y=0,z=0))
                native_frame=world.tick();row=actor_row(vehicle)
                motion.write(json.dumps({'native_frame':native_frame,'video_frame':index,
                    'time_s':index/20,'source_kind':'original_native',**row},allow_nan=False)+'\n')
                camera_frames={}
                for name,*_ in CAMERAS:
                    image=queues[name].get(timeout=30)
                    while image.frame<native_frame:image=queues[name].get(timeout=30)
                    if image.frame!=native_frame:raise RuntimeError('Original four-camera join differs')
                    encoders[name].stdin.write(image.raw_data);camera_frames[name]=image.frame
                frame_map.append(native_frame,index/20,camera_native_frames=camera_frames)
        for name,process in encoders.items():
            process.stdin.close();error=process.stderr.read()
            if process.wait(timeout=180) or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original FFV1 encoding failed: '+name+error.decode()[-400:])
        (output/'road.xodr').write_text(open_drive())
        (output/'aisle-context.json').write_text(json.dumps({'source_kind':'original_native',
            'cell_id':'C200542','access_aisle':AISLE,'adjacent_accessible_bay':BAY,
            'premises_public_access_reviewed':False,'access_aisle_designation_reviewed':False,
            'marking_source':'Native diagnostic hatch only; official designation unconfirmed',
            'parked_classification_reviewed':False},indent=2)+'\n')
        return {'frames':FRAMES,'camera_names':list(queues),
                'official_access_aisle_unverified':True,'physical_acceptance_claimed':False}
    finally:
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
