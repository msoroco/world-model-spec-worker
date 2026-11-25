"""Original Native slow-traffic extreme-right draft; no legal duty conclusion."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

FRAMES=600
RATE=20
CAMERAS=(
    ('overview',1280,720,0,-22,18,-40),
    ('approach',1280,720,0,-13,8,-20),
    ('reference_corner',1280,720,-30,-10,9,-22),
    ('driver_reference',1280,720,25,-14,10,-30),
)


def check():
    geometry=geometry_check()
    if FRAMES/RATE!=30 or len(CAMERAS)!=4 or len({x[0] for x in CAMERAS})!=4:
        raise ValueError('four cameras and 30-second capture required')
    return {'passed':True,'geometry':geometry,'frames':FRAMES,'rate_hz':RATE,
            'camera_names':[x[0] for x in CAMERAS],
            'physical_acceptance_claimed':False}


def survey(world,carla):
    mapping=world.get_map()
    lanes=[]
    for name,y,lane_id,lane_type in (
            ('forward',-1.75,-1,carla.LaneType.Driving),
            ('opposing',1.75,1,carla.LaneType.Driving),
            ('right_paved_margin',-5.0,-2,carla.LaneType.Shoulder)):
        wp=mapping.get_waypoint(carla.Location(x=0,y=y,z=1),
                                project_to_road=True,lane_type=lane_type)
        if wp is None or wp.road_id!=1 or wp.lane_id!=lane_id:
            raise RuntimeError('Native one-lane-each-way paved width readback failed: '+name)
        lanes.append({'name':name,'road_id':wp.road_id,'lane_id':wp.lane_id,
                      'native_xy_m':[wp.transform.location.x,wp.transform.location.y]})
    return {'lanes':lanes,'right_paved_edge_y_m':-6.5,
            'public_highway_verified':False,'physical_edge_verified':False}


def corners(actor):
    transform=actor.get_transform()
    extent=actor.bounding_box.extent
    x,y=transform.location.x,transform.location.y
    yaw=math.radians(transform.rotation.yaw)
    co,si=math.cos(yaw),math.sin(yaw)
    return [[x+dx*co-dy*si,y+dx*si+dy*co]
            for dx,dy in ((-extent.x,-extent.y),(extent.x,-extent.y),
                          (extent.x,extent.y),(-extent.x,extent.y))]


def execute(output_dir,extreme_right,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot,restore
    check()
    output=Path(output_dir).resolve()
    if (output/'road.xodr').exists() or (output/'slow-traffic-trace.jsonl').exists():
        raise ValueError('choose a fresh original Native attempt directory')
    client=carla.Client(host,port)
    client.set_timeout(180)
    saved=snapshot(client)
    old=client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('requires an exclusive idle asynchronous Native world')
    owned,encoders,queues=[],{},{}
    encoder_exit_codes={}
    capture=None
    changed=False
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=25,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings()
        settings.synchronous_mode=True
        settings.fixed_delta_seconds=1/RATE
        settings.substepping=True
        settings.max_substep_delta_time=.01
        settings.max_substeps=10
        world.apply_settings(settings)
        readback=survey(world,carla)
        output.mkdir(parents=True,exist_ok=True)
        source_map=world.get_map().to_opendrive().encode()
        (output/'slow-traffic-context.json').write_text(json.dumps({
            'assignment_id':'training__C230259__NRS-484B-627-1a__motor_vehicle_driver',
            'source_kind':'native_saved_sample','road_id':'1',
            'map_source_sha256':hashlib.sha256(source_map).hexdigest(),
            'highway_public_status_source_sha256':None,
            'state':'Nevada','public_highway':None,'native_survey':readback,
            'forward_lane_id':-1,'opposing_lane_id':1,'right_shoulder_lane_id':-2,
            'right_paved_edge_y_m':-6.5,'paved_width_m':10.0,
            'nrs_484b_630_applicability':None,
            'source_review_required':True},indent=2)+'\n')
        blueprints=world.get_blueprint_library()
        ego_bp=blueprints.find('vehicle.tesla.model3')
        ego_bp.set_attribute('role_name','c230259_slow_subject')
        traffic_bp=blueprints.find('vehicle.audi.tt')
        traffic_bp.set_attribute('role_name','c230259_immediate_follower')
        ego=world.spawn_actor(ego_bp,carla.Transform(
            carla.Location(x=-30,y=-1.75,z=1),carla.Rotation(yaw=0)))
        owned.append(ego)
        other=world.spawn_actor(traffic_bp,carla.Transform(
            carla.Location(x=-48,y=-1.75,z=1),carla.Rotation(yaw=0)))
        owned.append(other)
        for name,width,height,x,y,z,pitch in CAMERAS:
            bp=blueprints.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x',str(width))
            bp.set_attribute('image_size_y',str(height))
            bp.set_attribute('fov','85')
            bp.set_attribute('sensor_tick',str(1/RATE))
            camera=world.spawn_actor(bp,carla.Transform(
                carla.Location(x=x,y=y,z=z),carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q=queue.Queue()
            camera.listen(q.put)
            queues[name]=q
            encoders[name]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}',
                '-r',str(RATE),'-i','-','-frames:v',str(FRAMES),
                '-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,
            'training__C230259__NRS-484B-627-1a__motor_vehicle_driver__'+
            ('controlled_1' if extreme_right else 'controlled_2'),
            required_observations=[])
        with FrameMap(output/'video_frames.jsonl') as frame_map, (output/'slow-traffic-trace.jsonl').open('x') as trace:
            first_elapsed=None
            for index in range(FRAMES):
                # Longitudinal speed, follower policy and capture are fixed across the pair.
                # Only requested subject lateral placement changes.
                lateral = -.65 if extreme_right and 150 <= index < 240 else 0.0
                ego.set_target_velocity(carla.Vector3D(x=1.5,y=lateral,z=0))
                ego_xy=ego.get_transform().location
                follower_xy=other.get_transform().location
                gap=ego_xy.x-follower_xy.x
                clear_lateral=abs(ego_xy.y-follower_xy.y)>2.5
                follower_command=5.0 if (gap>8 or clear_lateral) and follower_xy.x<65 else 1.5
                other.set_target_velocity(carla.Vector3D(x=follower_command,y=0,z=0))
                native_frame=world.tick()
                snap=world.get_snapshot()
                if snap.frame!=native_frame:
                    raise RuntimeError('Native frame/snapshot identity differs')
                absolute=snap.timestamp.elapsed_seconds
                if first_elapsed is None:
                    first_elapsed=absolute
                relative=absolute-first_elapsed
                mapped={}
                for name in queues:
                    image=queues[name].get(timeout=30)
                    while image.frame<native_frame:
                        image=queues[name].get(timeout=30)
                    if image.frame!=native_frame:
                        raise RuntimeError('Original camera frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data)
                    mapped[name]=image.frame
                frame_map.append(native_frame,relative,camera_native_frames=mapped)
                ego_wp=world.get_map().get_waypoint(ego.get_transform().location,
                    project_to_road=True,lane_type=carla.LaneType.Any)
                follower_wp=world.get_map().get_waypoint(other.get_transform().location,
                    project_to_road=True,lane_type=carla.LaneType.Any)
                sample={'video_frame':index,'native_frame':native_frame,
                    'time_s':relative,'native_elapsed_seconds':absolute,
                    'camera_native_frames':mapped,
                    'ego_id':str(ego.id),'traffic_id':str(other.id),
                    'ego_road_id':str(ego_wp.road_id) if ego_wp else None,
                    'traffic_road_id':str(follower_wp.road_id) if follower_wp else None,
                    'ego_lane_id':ego_wp.lane_id if ego_wp else None,
                    'traffic_lane_id':follower_wp.lane_id if follower_wp else None,
                    'ego_xy_m':[ego.get_transform().location.x,ego.get_transform().location.y],
                    'traffic_xy_m':[other.get_transform().location.x,other.get_transform().location.y],
                    'ego_footprint_xy_m':corners(ego),'traffic_footprint_xy_m':corners(other),
                    'ego_speed_mps':ego.get_velocity().length(),
                    'ego_forward_velocity_mps':ego.get_velocity().x,
                    'traffic_speed_mps':other.get_velocity().length(),
                    'ego_requested_speed_mps':1.5,'follower_free_flow_request_mps':5.0,
                    'follower_command_mps':follower_command,'pre_tick_gap_m':gap,
                    'lateral_clearance_rule_active':clear_lateral}
                capture.capture(native_frame,relative,extra={'c230259_slow_traffic':sample})
                trace.write(json.dumps(sample,allow_nan=False)+'\n')
        for name,process in encoders.items():
            process.stdin.close()
            stderr=process.stderr.read()
            encoder_exit_codes[name]=process.wait(timeout=180)
            if encoder_exit_codes[name] or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: '+name+': '+stderr.decode()[-400:])
        capture.close(confirmed=True)
        capture=None
        return {'frames':FRAMES,'extreme_right_requested':extreme_right,
                'native_survey':readback,'source_review_required':True,
                'physical_acceptance_claimed':False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restored=restore(client,saved)
            if capture is None and len(encoder_exit_codes)==4:
                seal_capture(output,frames=FRAMES,restoration=restored,errors=[],
                    encoder_exit_codes=encoder_exit_codes,
                    context={'case_id':'training__C230259__NRS-484B-627-1a__motor_vehicle_driver__'+
                             ('controlled_1' if extreme_right else 'controlled_2')})
                record_native_exit(output)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--check',action='store_true')
    p.add_argument('--output-dir')
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,default=2000)
    a=p.parse_args()
    if a.check:
        if a.output_dir:
            raise SystemExit('--check cannot create a Native attempt')
        print(json.dumps(check()))
    else:
        if not a.output_dir:
            raise SystemExit('--output-dir required for Native execution')
        extreme_right=json.loads((Path(__file__).parent/'config.json').read_text())['extreme_right_requested']
        print(json.dumps(execute(a.output_dir,extreme_right,a.host,a.port)))
