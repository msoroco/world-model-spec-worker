"""Original Native school-zone U-turn draft; --check is CARLA-free."""
import argparse
import json
from pathlib import Path
import queue
import subprocess

from layout import ZONE,TURN,check as layout_check,open_drive,planned_pose

FRAMES=600
CAMERAS=(('overview',1280,720,-12,-18,25,-65),('zone_entry',1280,720,-25,-12,8,-30),
    ('turn_side',1280,720,-12,12,11,-42),('child_area',1280,720,5,13,12,-45))


def check():
    cfg=json.loads(Path('config.json').read_text())
    if cfg['cell_id']!='C263073' or cfg['law_id']!='NRS-484B-363-3' or cfg['case_suffix'] not in ('controlled_1','controlled_2'):
        raise ValueError('Exact assignment differs')
    if cfg['duration_s']!=30 or cfg['rate_hz']!=20 or len(CAMERAS)!=4:raise ValueError('Capture policy differs')
    return {'passed':True,'geometry':layout_check(),'frame_count':FRAMES,
        'kinematic_path_only':True,'native_imported':False,'physical_acceptance_claimed':False}


def actor_row(actor):
    transform=actor.get_transform()
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,
        'center_xy_m':[transform.location.x,transform.location.y],
        'heading_deg':transform.rotation.yaw,
        'body_xy_m':[[p.x,p.y] for p in actor.bounding_box.get_world_vertices(transform)]}


def execute(output,host,port):
    import carla
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot,restore
    cfg=json.loads(Path('config.json').read_text());check();output=Path(output).resolve()
    if output.exists():raise ValueError('Use fresh original Native output')
    client=carla.Client(host,port);client.set_timeout(180)
    old=client.get_world();saved=snapshot(client)
    if old.get_settings().synchronous_mode or any(a.type_id.startswith(('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    output.mkdir(parents=True);owned=[];encoders={};queues={};changed=False
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True;settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10;world.apply_settings(settings)
        mapping=world.get_map()
        for y,lane in ((-3,-1),(3,1)):
            waypoint=mapping.get_waypoint(carla.Location(x=-12,y=y,z=1),project_to_road=True,lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id!=1 or waypoint.lane_id!=lane:
                raise RuntimeError('Native two-way road readback failed')
        # Diagnostic zone outline does not establish legal designation or sign/beacon activity.
        for x in (-20,20):
            world.debug.draw_line(carla.Location(x=x,y=-8,z=.05),carla.Location(x=x,y=8,z=.05),
                thickness=.08,color=carla.Color(255,255,0),life_time=35,persistent_lines=False)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3')
        ego=world.try_spawn_actor(bp,carla.Transform(carla.Location(x=-25,y=-3,z=1.2),carla.Rotation(yaw=0)))
        if ego is None:raise RuntimeError('Original vehicle spawn failed')
        ego.set_simulate_physics(False);owned.append(ego)
        walker_bp=next((x for x in world.get_blueprint_library().filter('walker.pedestrian.*')),None)
        if walker_bp is None:raise RuntimeError('Original pedestrian blueprint missing')
        walker=world.try_spawn_actor(walker_bp,carla.Transform(carla.Location(x=4,y=7.5,z=1.2)))
        if walker is None:raise RuntimeError('Original pedestrian spawn failed')
        owned.append(walker)
        for name,width,height,x,y,z,pitch in CAMERAS:
            cbp=world.get_blueprint_library().find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',85),('sensor_tick',.05)):
                cbp.set_attribute(key,str(value))
            sensor=world.spawn_actor(cbp,carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch)))
            owned.append(sensor);received=queue.Queue();sensor.listen(received.put);queues[name]=received
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20','-i','-',
                '-frames:v',str(FRAMES),'-c:v','ffv1',str(output/(name+'.mkv'))],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with (output/'native-motion.jsonl').open('x') as motion,FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                x,y,yaw=planned_pose(index,cfg['case_suffix']=='controlled_2')
                ego.set_transform(carla.Transform(carla.Location(x=x,y=y,z=1.2),carla.Rotation(yaw=yaw)))
                native=world.tick()
                motion.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                    'source_kind':'original_native','ego':actor_row(ego),
                    'other_person':actor_row(walker),'kinematic_path_only':True},allow_nan=False)+'\n')
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
        (output/'road.xodr').write_text(open_drive())
        (output/'school-context.json').write_text(json.dumps({'source_kind':'original_native',
            'cell_id':'C263073','zone':ZONE,'turn':TURN,'zone_designation_reviewed':False,
            'school_adjacency_reviewed':False,'highway_status_reviewed':False,
            'child_identity_and_presence_reviewed':False,'session_operation_civil_time_reviewed':False,
            'class_hours_reviewed':False,'beacon_and_sign_state_reviewed':False,
            'all_five_exceptions_reviewed':False,'partial_zone_maneuver_treatment_reviewed':False,
            'path_is_kinematic':True},indent=2)+'\n')
        return {'frames':FRAMES,'camera_names':list(queues),'path_is_kinematic':True,
            'zone_designation_unverified':True,'physical_acceptance_claimed':False}
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
