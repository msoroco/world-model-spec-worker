"""Native original opposite-direction meeting capture; --check is CPU only."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from check import check as check_request

CAMERAS = (('overview', 1920, 1080, 0, -16, 25, -65),
           ('approach', 1280, 720, -25, -8, 8, -25),
           ('reference_corner', 1280, 720, 0, 12, 9, -25),
           ('driver_reference', 1280, 720, -15, -2, 3, -5))
FRAMES = 600


def check():
    return check_request(Path.cwd())


def actor_row(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(pose)
    return {'actor_id': actor.id, 'blueprint_id': actor.type_id,
            'center_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
            'body_xyz_m': [[v.x, v.y, v.z] for v in vertices],
            'velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)}


def execute(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.native_output import FrameMap, seal_capture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore
    check()
    output = Path(output).resolve()
    if output != Path.cwd().resolve():
        raise ValueError('Capture requires a fresh materialized exact bundle')
    if any((output / name).exists() for name in ('native-motion.jsonl','video_frames.jsonl','capture-seal.json')):
        raise ValueError('Original acquisition already exists')
    client = carla.Client(host, port)
    client.set_timeout(180)
    old_world = client.get_world()
    saved = snapshot(client)
    if old_world.get_settings().synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in old_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, cameras = [], {}, {}
    capture = None
    changed = False
    restoration = None
    try:
        world = client.generate_opendrive_world((output/'road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        for lane in (-1, 1):
            point = world.get_map().get_waypoint_xodr(111294, lane, 100)
            if point is None or point.lane_type != carla.LaneType.Driving:
                raise RuntimeError('Native opposing driving lane missing')
        blueprints = world.get_blueprint_library()
        config = json.loads((output/'config.json').read_text())
        z = config.get('spawn_z_m', 1.5)
        if z not in (1.5, 1.8):
            raise ValueError('Unreviewed spawn height')
        requests = [json.loads(line) for line in (output/'request.jsonl').read_text().splitlines()]
        first = requests[0]
        def spawn(blueprint, xyz, yaw):
            actor = world.try_spawn_actor(blueprints.find(blueprint), carla.Transform(
                carla.Location(x=xyz[0],y=xyz[1],z=z),carla.Rotation(yaw=yaw)))
            if actor is None: raise RuntimeError('Original actor spawn failed')
            owned.append(actor)
            return actor
        ego = spawn('vehicle.tesla.model3',first['ego_center_xyz_m'],0)
        other = spawn('vehicle.audi.tt',first['oncoming_center_xyz_m'],180)
        for name,width,height,x,y,cam_z,pitch in CAMERAS:
            bp = blueprints.find('sensor.camera.rgb')
            for key,value in (('image_size_x',width),('image_size_y',height),('fov',85),('sensor_tick',.05)):
                bp.set_attribute(key,str(value))
            sensor = world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=cam_z),
                carla.Rotation(pitch=pitch)))
            owned.append(sensor)
            q = queue.Queue();sensor.listen(q.put);cameras[name]=q
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                '-n','-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r','20',
                '-i','-','-frames:v','600','-c:v','ffv1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        capture = PipelineCapture(client,ego,output,config['selected_case_id'],required_observations=())
        with (output/'native-motion.jsonl').open('x') as motion, FrameMap(output/'video_frames.jsonl') as frame_map:
            for index,request in enumerate(requests):
                ego.set_target_velocity(carla.Vector3D(x=5,y=0,z=0))
                other.set_target_velocity(carla.Vector3D(x=-5,y=0,z=0))
                native_frame = world.tick()
                capture.capture(native_frame,index/20)
                ego_source,other_source=actor_row(ego),actor_row(other)
                motion.write(json.dumps({'native_frame':native_frame,'video_frame':index,
                    'time_s':index/20,'source_kind':'original_native',
                    'ego':ego_source,'oncoming':other_source,'legal_verdict':None},allow_nan=False)+'\n')
                camera_frames={}
                for name in cameras:
                    image=cameras[name].get(timeout=30)
                    while image.frame<native_frame:image=cameras[name].get(timeout=30)
                    if image.frame!=native_frame:raise RuntimeError('Camera/native frame join failed')
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name]=image.frame
                frame_map.append(native_frame,index/20,camera_native_frames=camera_frames)
        capture.close();capture=None
        for name,process in encoders.items():
            process.stdin.close();stderr=process.stderr.read()
            if process.wait(timeout=180):raise RuntimeError('Source camera encoder failed: '+name+stderr.decode()[-200:])
        (output/'pavement-survey.json').write_text(json.dumps({
            'source_kind':'original_native','authored_road_id':111294,
            'native_opposing_lanes_read_back':True,
            'authored_paved_bounds_y_m':[-4,4],
            'original_pavement_edges_reviewed':False,
            'as_nearly_as_possible_reviewed':False,
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
        encoder_exit_codes={name:0 for name in cameras},context={'authored_road_id':111294})
    return {'frames':FRAMES,'source_review_complete':False,'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host',default='localhost')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:print(json.dumps(check()))
    else:
        if args.output_dir is None:parser.error('Native output directory required')
        print(json.dumps(execute(args.output_dir,args.host,args.port)))
