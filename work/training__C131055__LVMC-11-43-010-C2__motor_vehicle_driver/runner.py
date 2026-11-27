"""Lazy original Native right-exit roundabout capture; no legal verdict."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive
from roundabout_scene import LANES, intent

RATE = 20
FRAMES = 600
ASSIGNMENT = 'training__C131055__LVMC-11-43-010-C2__motor_vehicle_driver'
CAMERAS = (('overview',1920,1080,0,0,45,-90),
           ('approach',1280,720,0,-30,15,-35),
           ('reference_corner',1280,720,-24,-12,18,-35),
           ('driver_reference',1280,720,0,-18,9,-18))


def check(config=None):
    if FRAMES != RATE*30 or len(CAMERAS) != 4:
        raise ValueError('Source capture profile differs')
    if config is not None:
        case_id=config.get('selected_case_id')
        if case_id not in {ASSIGNMENT+'__'+name for name in LANES}:
            raise ValueError('Unknown exact selected case')
        if (config.get('assignment_id'),config.get('law_id'),config.get('cell_id'),config.get('actor')) != (
                ASSIGNMENT,'LVMC-11-43-010-C2','C131055','motor_vehicle_driver'):
            raise ValueError('Frozen identity differs')
        if (config.get('rate_hz'),config.get('duration_s'),config.get('frames')) != (20,30,600):
            raise ValueError('Full 30-second capture missing')
        if [c.get('name') for c in config.get('cameras',[])] != [c[0] for c in CAMERAS]:
            raise ValueError('Four source cameras differ')
        if config.get('physical_acceptance_claimed') or config.get('legal_verdict') is not None:
            raise ValueError('Premature physical or legal claim')
        if config.get('case',{}).get('case_id') != case_id:
            raise ValueError('Selected case and description differ')
    return {'native_executed':False,'frames':FRAMES,'camera_names':[c[0] for c in CAMERAS],
            'geometry':geometry_check(),'physical_completion_claimed':False}


def target(case, t):
    radius=LANES[case]
    intent(case)
    ring_end=10
    if t<4:
        return (0,-40+(40-radius)*t/4),5.2,'entry'
    if t<ring_end:
        sweep=math.pi/2
        angle=-math.pi/2+sweep*(t-4)/(ring_end-4)
        return (radius*math.cos(angle),radius*math.sin(angle)),5.2,'circulation'
    distance=(t-ring_end)*5.2
    east_x=min(radius+distance,55)
    return (east_x,0),0 if east_x>=55 else 5.2,'exit'


def speed(actor):
    v=actor.get_velocity()
    return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)


def control(actor, xy, wanted, carla, steer_gain=1.3):
    pose=actor.get_transform()
    wanted_yaw=math.atan2(xy[1]-pose.location.y,xy[0]-pose.location.x)
    error=math.atan2(math.sin(wanted_yaw-math.radians(pose.rotation.yaw)),
                     math.cos(wanted_yaw-math.radians(pose.rotation.yaw)))
    delta=wanted-speed(actor)
    return carla.VehicleControl(throttle=max(0,min(.60,delta*.24)),
                                brake=max(0,min(1,-delta*.42)),
                                steer=max(-.85,min(.85,error*steer_gain)))


def survey(world,carla):
    samples=[]
    for road,x,y in ((1,9,-9),(2,9,9),(3,-9,9),(4,-9,-9),
                     (5,0,-40),(6,-25,0),(7,0,-25),(8,25,0)):
        waypoint=world.get_map().get_waypoint(carla.Location(x=x,y=y,z=1),
                     project_to_road=True,lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id!=road:
            raise RuntimeError('Original Native roundabout road readback missing: '+str(road))
        samples.append({'road_id':waypoint.road_id,'lane_id':waypoint.lane_id,
                        'x_m':waypoint.transform.location.x,'y_m':waypoint.transform.location.y})
    return samples


def execute(output_dir,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot,restore
    config=json.loads(Path('config.json').read_text())
    check(config)
    case=config['selected_case_id'].split('__')[-1]
    output=Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Original Native source path already occupied')
    client=carla.Client(host,port)
    client.set_timeout(180)
    saved=snapshot(client)
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in client.get_world().get_actors()):
        raise RuntimeError('Requires exclusive idle asynchronous Native world')
    owned=[];encoders={};cameras={};changed=False;errors=[];encoder_codes={}
    failure=None;restoration={'restored':False};completed=0
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.5,max_road_length=25,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=1/RATE
        settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings)
        map_rows=survey(world,carla)
        output.mkdir(parents=True,exist_ok=True)
        (output/'road.xodr').write_text(world.get_map().to_opendrive())
        (output/'roundabout-map-readback.json').write_text(json.dumps({
            'source_kind':'native_map_readback','samples':map_rows,
            'full_boundary_review_complete':False},indent=2)+'\n')
        blueprints=sorted(world.get_blueprint_library().filter('vehicle.*'),key=lambda b:b.id)
        if not blueprints:raise RuntimeError('Vehicle blueprint missing')
        blueprint=blueprints[0];blueprint.set_attribute('role_name','c131055_c2_ego')
        ego=world.spawn_actor(blueprint,carla.Transform(carla.Location(x=0,y=-40,z=.6),
                                                        carla.Rotation(yaw=90)))
        owned.append(ego)
        for name,width,height,x,y,z,pitch in CAMERAS:
            bp=world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x',str(width));bp.set_attribute('image_size_y',str(height))
            bp.set_attribute('fov','85');bp.set_attribute('sensor_tick',str(1/RATE))
            camera=world.spawn_actor(bp,carla.Transform(carla.Location(x=x,y=y,z=z),
                                                          carla.Rotation(pitch=pitch)))
            owned.append(camera);frames=queue.Queue();camera.listen(frames.put);cameras[name]=frames
            encoders[name]=subprocess.Popen(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pix_fmt','bgra','-s',f'{width}x{height}','-r',str(RATE),'-i','-',
                '-frames:v',str(FRAMES),'-c:v','ffv1','-level','1',str(output/(name+'.mkv'))],
                stdin=subprocess.PIPE,stderr=subprocess.PIPE)
        with PipelineCapture(client,ego,output,config['selected_case_id'],
                 required_observations=config.get('required_atoms',[])) as capture, (
                 FrameMap(output/'video_frames.jsonl')) as frame_map, (
                 output/'native-raw-actors.jsonl').open('x') as raw, (
                 output/'control-intent.jsonl').open('x') as controls, (
                 output/'trace.jsonl').open('x') as trace:
            first_elapsed=None
            for index in range(FRAMES):
                xy,wanted,phase=target(case,index/RATE)
                command=control(ego,xy,wanted,carla,config.get('steer_gain',1.3))
                ego.apply_control(command)
                native=world.tick();snap=world.get_snapshot()
                if snap.frame!=native:raise RuntimeError('Original Native frame identity differs')
                absolute=snap.timestamp.elapsed_seconds
                if first_elapsed is None:first_elapsed=absolute
                elapsed=absolute-first_elapsed
                pose=ego.get_transform();extent=ego.bounding_box.extent
                waypoint=world.get_map().get_waypoint(pose.location,project_to_road=True,
                                                       lane_type=carla.LaneType.Driving)
                observed={'role':'ego','actor_id':ego.id,'blueprint_id':ego.type_id,
                    'x_m':pose.location.x,'y_m':pose.location.y,'yaw_deg':pose.rotation.yaw,
                    'speed_mps':speed(ego),'bbox_half_length_m':extent.x,'bbox_half_width_m':extent.y,
                    'road_id':waypoint.road_id if waypoint else None,
                    'lane_id':waypoint.lane_id if waypoint else None,'requested_phase':phase}
                mapped={}
                for name,frames in cameras.items():
                    image=frames.get(timeout=30)
                    while image.frame<native:image=frames.get(timeout=30)
                    if image.frame!=native:raise RuntimeError('Original camera frame join failed: '+name)
                    encoders[name].stdin.write(image.raw_data);mapped[name]=image.frame
                frame_map.append(native,elapsed,camera_native_frames=mapped)
                capture.capture(native,elapsed,extra={'video_frame':index})
                raw.write(json.dumps({'video_frame':index,'native_frame':native,'time_s':elapsed,
                    'case_id':config['selected_case_id'],'actors':[observed]})+'\n')
                controls.write(json.dumps({'video_frame':index,'native_frame':native,'time_s':elapsed,
                    'target_xy_m':xy,'target_speed_mps':wanted,'requested_phase':phase,
                    'exit_intent':intent(case),
                    'throttle':command.throttle,'brake':command.brake,'steer':command.steer})+'\n')
                trace.write(json.dumps({'frame':native,'time_s':elapsed,
                    'position':{'x':observed['x_m'],'y':observed['y_m'],'z':0},
                    'heading_deg':observed['yaw_deg'],'speed_mps':observed['speed_mps']})+'\n')
                completed+=1
        for name,process in encoders.items():
            process.stdin.close();error=process.stderr.read();encoder_codes[name]=process.wait(timeout=180)
            if encoder_codes[name] or not (output/(name+'.mkv')).is_file():
                raise RuntimeError('Camera encoding failed: '+name+': '+error.decode()[-400:])
    except BaseException as error:
        failure=error;errors.append(f'{type(error).__name__}: {error}')
    finally:
        for process in encoders.values():
            if process.poll() is None:process.kill();process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor,'stop'):actor.stop()
                actor.destroy()
            except Exception as error:errors.append('actor destroy: '+str(error))
        if changed:
            try:restoration=restore(client,saved)
            except Exception as error:errors.append('world restore: '+str(error))
        if output.exists():
            (output/'native-run-status.json').write_text(json.dumps({
                'case_id':config['selected_case_id'],'frames':completed,'errors':errors,
                'restoration':restoration,'encoder_exit_codes':encoder_codes,
                'capture_finished':completed==FRAMES and failure is None,
                'acceptance_claimed':False},indent=2)+'\n')
    if failure is not None:raise failure
    if errors:raise RuntimeError('; '.join(errors))
    seal_capture(output,frames=completed,restoration=restoration,errors=errors,
                 encoder_exit_codes=encoder_codes,
                 context={'case_id':config['selected_case_id'],'source':'original Native CARLA capture',
                          'legal_verdict':None})
    return {'native_frames':completed,'camera_names':list(cameras),
            'map_readback':map_rows,'physical_completion_claimed':False,'legal_verdict':None}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000);args=parser.parse_args()
    if args.check:print(json.dumps(check(),sort_keys=True))
    else:
        if not args.output_dir:raise SystemExit('--output-dir required')
        print(json.dumps(execute(args.output_dir,args.host,args.port)))
