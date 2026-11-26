"""Original Native parking capture; --check validates a materialized CPU bundle."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from parking_scene import check as scene_check

FRAMES = 600
CAMERAS = (('overview',1920,1080,0,-17,22,-55),
           ('approach',1280,720,-22,-5,7,-17),
           ('reference_corner',1280,720,0,5,7,-25),
           ('driver_reference',1280,720,5,-11,3,-12))


def check():
    root = Path.cwd()
    config = json.loads((root/'config.json').read_text())
    request = json.loads((root/'request.json').read_text())
    scene_check(request)
    if config['case_id'] != config['selected_case_id'] or config['case_id'].rsplit('__',1)[-1] != request['case']:
        raise ValueError('Exact case identity mismatch')
    if config['frames'] != FRAMES or config['rate_hz'] != 20 or config['duration_s'] != 30:
        raise ValueError('Capture timing mismatch')
    if hashlib.sha256((root/'request.json').read_bytes()).hexdigest() != config['request_sha256']:
        raise ValueError('Construction request hash mismatch')
    if (root/'road.xodr').read_text() != request['source_map']:
        raise ValueError('Road differs from request')
    return {'passed':True,'case_id':config['case_id'],'frames':FRAMES,
            'original_native_observed':False,'authority_verified':False}


def actor_row(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    wheels = actor.get_physics_control().wheels
    raw_wheels = []
    for wheel in wheels:
        location = getattr(wheel,'position',None)
        if location is None:
            raise RuntimeError('Native wheel-position API unavailable; original wheel source missing')
        raw_wheels.append({'position_raw_xyz':[location.x,location.y,location.z],
                           'radius_raw':getattr(wheel,'radius',None)})
    return {'actor_id':actor.id,'blueprint_id':actor.type_id,
            'center_xyz_m':[pose.location.x,pose.location.y,pose.location.z],
            'yaw_deg':pose.rotation.yaw,
            'body_xyz_m':[[v.x,v.y,v.z] for v in actor.bounding_box.get_world_vertices(pose)],
            'raw_wheel_geometry':raw_wheels,
            'velocity_xyz_mps':[velocity.x,velocity.y,velocity.z],
            'speed_mps':math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)}


def execute(output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap,seal_capture
    from scenario_pipeline.worker_exchange.world_restore import snapshot,restore
    check()
    output=Path(output).resolve()
    if output != Path.cwd().resolve():
        raise ValueError('Capture requires the fresh materialized exact bundle')
    if any((output/name).exists() for name in ('native-parking.jsonl','video_frames.jsonl','capture-seal.json')):
        raise ValueError('Original acquisition already exists')
    client=carla.Client(host,port);client.set_timeout(180)
    old_world=client.get_world();saved=snapshot(client)
    if old_world.get_settings().synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in old_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned=[];encoders={};cameras={};capture=None;changed=False;restoration=None
    try:
        request=json.loads((output/'request.json').read_text())
        config=json.loads((output/'config.json').read_text())
        world=client.generate_opendrive_world((output/'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,max_road_length=50,
                wall_height=0,additional_width=0,smooth_junctions=False,
                enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;settings.substepping=True
        settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        map_source=world.get_map().to_opendrive()
        lanes=[]
        for lane_id in (-1,-2):
            point=world.get_map().get_waypoint_xodr(149985,lane_id,80)
            if point is None or point.lane_type != carla.LaneType.Driving:
                raise RuntimeError('One-way driving lane missing in Native readback')
            lanes.append({'lane_id':lane_id,'road_id':point.road_id,
                          'heading_deg':point.transform.rotation.yaw})
        if abs(((lanes[0]['heading_deg']-lanes[1]['heading_deg']+180)%360)-180)>1:
            raise RuntimeError('Authored one-way lanes disagree on heading')
        root=ET.fromstring(map_source)
        curbs=[dict(o.attrib) for o in root.findall('.//object') if o.attrib.get('name') in ('left_curb','right_curb')]
        if {c.get('name') for c in curbs}!={'left_curb','right_curb'}:
            raise RuntimeError('Original curb objects not retained')
        blueprints=world.get_blueprint_library()
        center=request['requested_center_xy_m']
        blueprint=blueprints.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name','c149985_parking_subject')
        ego=world.try_spawn_actor(blueprint,carla.Transform(
            carla.Location(x=center[0],y=center[1],z=config['spawn_z_m']),
            carla.Rotation(yaw=request['requested_heading_deg'])))
        if ego is None:raise RuntimeError('Original parking vehicle spawn failed')
        owned.append(ego)
        for name,width,height,x,y,z,pitch in CAMERAS:
            bp=blueprints.find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',85),('sensor_tick',.05)):
                bp.set_attribute(key,str(value))
            sensor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                carla.Rotation(pitch=pitch)))
            owned.append(sensor);q=queue.Queue();sensor.listen(q.put);cameras[name]=q
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                '-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20',
                '-i','-','-frames:v','600','-c:v','ffv1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        capture=PipelineCapture(client,ego,output,config['selected_case_id'],required_observations=())
        with (output/'native-parking.jsonl').open('x') as motion,FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                ego.apply_control(carla.VehicleControl(throttle=0,brake=1,
                    hand_brake=request['rest_mode']=='parked'))
                native_frame=world.tick()
                capture.capture(native_frame,index/20)
                row=actor_row(ego)
                motion.write(json.dumps({'native_frame':native_frame,'video_frame':index,
                    'time_s':index/20,'source_kind':'original_native','ego':row,
                    'rest_mode_request':request['rest_mode'],'legal_verdict':None},allow_nan=False)+'\n')
                mapped={}
                for name,q in cameras.items():
                    image=q.get(timeout=30)
                    while image.frame<native_frame:image=q.get(timeout=30)
                    if image.frame!=native_frame:raise RuntimeError('Camera/native frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                frame_map.append(native_frame,index/20,camera_native_frames=mapped)
        capture.close();capture=None
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            if process.wait(timeout=180):raise RuntimeError('Camera encoder failed: '+name+stderr.decode()[-200:])
        (output/'parking-context.json').write_text(json.dumps({
            'source_kind':'original_native_parking_readback','authored_road_id':149985,
            'native_map_sha256':hashlib.sha256(map_source.encode()).hexdigest(),
            'native_driving_lanes':lanes,'curb_objects':curbs,
            'parking_kind':request['parking_kind'],'right_curb_y_m':request['right_curb_y_m'],
            'left_curb_y_m':request['left_curb_y_m'],
            'local_left_ordinance_status':'pending_original',
            'local_angle_ordinance_status':'pending_original',
            'dot_width_determination_status':'pending_original',
            'authority_source_required':request['authority_request'],
            'original_curb_pixels_reviewed':False,'original_wheel_geometry_reviewed':False,
            'legal_verdict':None},indent=2)+'\n')
    finally:
        if capture is not None:capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception:pass
        if changed:restoration=restore(client,saved)
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,'physical_acceptance_claimed':False})+'\n')
    seal_capture(output,frames=FRAMES,restoration=restoration,errors=[],
        encoder_exit_codes={name:0 for name in cameras},context={'authored_road_id':149985})
    return {'frames':FRAMES,'source_review_complete':False,'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:print(json.dumps(check()))
    else:
        if args.output_dir is None:parser.error('Native output directory required')
        print(json.dumps(execute(args.output_dir,args.host,args.port)))
