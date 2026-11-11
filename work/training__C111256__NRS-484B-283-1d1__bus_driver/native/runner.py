"""C111256 bus/Walk Native construction proposal with an offline check path.

A debug Walk request is a capture aid, never an observed official pedestrian
indication. Saved source and pixel/governance review must establish that later.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from cameras import camera_plan
from controller import EngineeringKnobs, PathController, WalkFrame, WalkYieldController
from engineering import parameters
from geometry import check as geometry_check, open_drive, pedestrian_route, route

HERE=Path(__file__).resolve().parent
ASSIGNMENT='training__C111256__NRS-484B-283-1d1__bus_driver'


def write_new(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def check(config):
    suffix=config.get('case_suffix');candidate=config.get('candidate_id')
    plan=parameters(suffix,candidate)
    if config.get('case_id')!=ASSIGNMENT+'__'+suffix or config.get('cell_id')!='C111256' or \
       config.get('law_id')!='NRS-484B-283-1d1' or config.get('actor')!='bus_driver':
        raise ValueError('Exact Walk case, law, cell or actor differs')
    if config.get('rate_hz')!=20 or config.get('duration_s')!=24 or config.get('knobs')!=plan['knobs']:
        raise ValueError('Exact Walk profile or candidate knobs differ')
    geom=geometry_check()
    cameras=camera_plan(candidate)
    if [row['name'] for row in cameras]!=plan['knobs']['camera_profile'] or \
       [(row['width'],row['height']) for row in cameras]!=[(1920,1080),(1280,720)]*1+[(1280,720)]*2:
        raise ValueError('Current four-camera source profile differs')
    PathController(route(),3.8,35,EngineeringKnobs(
        lookahead_base_m=plan['knobs']['route_tracking_lookahead_m']))
    WalkYieldController(PathController(route(),3.8,35,EngineeringKnobs()),
                        policy=plan['yield_policy'],
                        hold_margin_m=plan['knobs']['crosswalk_hold_margin_m'])
    return {'case_id':config['case_id'],'candidate_id':candidate,
            'geometry':geom,'camera_count':4,'bus_route_samples':len(route()),
            'pedestrian_route_samples':len(pedestrian_route()),
            'carla_imported':False,'physical_walk_observed':False,
            'legal_outcome_claimed':False}


def body_xy(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=sorted({(round(v.x,5),round(v.y,5)) for v in vertices})
    if len(points)!=4:raise RuntimeError('Native actor lacks a four-corner body footprint')
    return [list(p) for p in points]


def camera_transform(carla,spec):
    x,y,z=spec['xyz_m']
    if spec['attachment']=='world':
        yaw=math.degrees(math.atan2(-y,-x));pitch=math.degrees(math.atan2(-z,math.hypot(x,y)))
    else:yaw=0;pitch=-5
    return carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(yaw=yaw,pitch=pitch))


def execute(config,output,host,port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore

    check(config)
    output=Path(output).resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use a newly materialized exact case directory')
    client=carla.Client(host,int(port));client.set_timeout(180)
    saved=snapshot(client);old=client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.','walker.','sensor.','controller.')) for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    owned=[];encoders={};logs={};queues={}
    capture=None;changed=False;restored=None;error=None;frames=0
    try:
        world=client.generate_opendrive_world(open_drive(),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        native_map_hash=hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
        approach=world.get_map().get_waypoint(carla.Location(x=1.75,y=-30,z=.2),
                         project_to_road=False,lane_type=carla.LaneType.Driving)
        if approach is None or approach.road_id!=1:
            raise RuntimeError('Native through-bus lane readback differs')
        signals=list(world.get_actors().filter('traffic.traffic_light*'))
        if not signals:
            raise RuntimeError('Authored pedestrian signal has no Native device actor readback')
        signal=min(signals,key=lambda actor:math.dist(
            (actor.get_location().x,actor.get_location().y),(4.3,-11)))
        library=world.get_blueprint_library()
        buses=library.filter('vehicle.mitsubishi.fusorosa')
        if not buses:
            raise RuntimeError('Exact bus blueprint unavailable in Native library')
        bus_bp=buses[0];bus_bp.set_attribute('role_name','c111256_bus_ego')
        bus=world.spawn_actor(bus_bp,carla.Transform(
            carla.Location(x=1.75,y=-40,z=.6),carla.Rotation(yaw=90)))
        owned.append(bus);bus.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        walkers=sorted(library.filter('walker.pedestrian.*'),key=lambda bp:bp.id)
        if not walkers:raise RuntimeError('No Native pedestrian blueprint available')
        pedestrian=world.spawn_actor(walkers[0],carla.Transform(
            carla.Location(x=-6.5,y=-11,z=.5),carla.Rotation(yaw=0)))
        owned.append(pedestrian)
        for _ in range(20):world.tick()
        wheels=bus.get_physics_control().wheels
        if len(wheels)<4:raise RuntimeError('Bus wheel geometry absent')
        wheelbase=(max(w.position.x for w in wheels)-min(w.position.x for w in wheels))/100
        steer=max(w.max_steer_angle for w in wheels)
        knobs=config['knobs'];plan=parameters(config['case_suffix'],config['candidate_id'])
        controller=WalkYieldController(PathController(route(),wheelbase,steer,
            EngineeringKnobs(lookahead_base_m=knobs['route_tracking_lookahead_m'])),
            policy=plan['yield_policy'],hold_margin_m=knobs['crosswalk_hold_margin_m'])
        geometry={'cell_id':'C111256','native_map_sha256':native_map_hash,
                  'bus_approach_road_id':approach.road_id,'bus_approach_lane_id':approach.lane_id,
                  'authored_walk_signal_id':620,'walk_signal_id':signal.id,
                  'crosswalk_y_range_m':[-12.0,-10.0],
                  'bus_lane_x_range_m':[0.0,3.5],
                  'signal_governance_verified':False,'walk_pixels_verified':False,
                  'synthetic_diagnostic':False}
        write_new(output/'road_geometry.json',geometry)
        write_new(output/'native-construction-context.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'bus_blueprint':bus.type_id,'pedestrian_blueprint':pedestrian.type_id,
            'bus_actor_id':bus.id,'pedestrian_actor_id':pedestrian.id,
            'pedestrian_device_actor_id':signal.id,'native_map_sha256':native_map_hash,
            'initial_bus_body_xy_m':body_xy(bus),'knobs':knobs,
            'display_source':'authored debug request, original pixels and governance pending',
            'physical_completion_claimed':False})
        for spec in camera_plan(config['candidate_id']):
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',spec['width']),('image_size_y',spec['height']),
                              ('fov',spec['fov_deg']),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            sensor=world.spawn_actor(bp,camera_transform(carla,spec),
                                     attach_to=bus if spec['attachment']=='ego' else None)
            owned.append(sensor);queues[spec['name']]=queue.Queue()
            sensor.listen(queues[spec['name']].put)
            logs[spec['name']]=(output/(spec['name']+'.encoder.log')).open('x')
            encoders[spec['name']]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f"{spec['width']}x{spec['height']}",
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(spec['name']+'.mkv'))],stdin=subprocess.PIPE,
                stderr=logs[spec['name']])
        capture=PipelineCapture(client,bus,output,config['case_id'],visibility=False,
                                required_observations=config.get('required_atoms',[]))
        start=world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native_samples.jsonl').open('x') as sample_file, \
             (output/'body_history.jsonl').open('x') as body_file, \
             (output/'video_frames.jsonl').open('x') as frame_file:
            for index in range(480):
                if 70<=index<=290:
                    pedestrian.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(x=1),speed=1.2))
                else:
                    pedestrian.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(x=0),speed=0))
                bus_pose=bus.get_transform();ped_pose=pedestrian.get_transform()
                velocity=bus.get_velocity();speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                ped_xy=(ped_pose.location.x,ped_pose.location.y)
                walk_request=60<=index<=330
                if walk_request:
                    world.debug.draw_string(carla.Location(x=5,y=-11,z=2.4),'WALK',
                        draw_shadow=True,color=carla.Color(255,255,255),life_time=.06)
                observation=WalkFrame(native_frame=max(0,world.get_snapshot().frame),
                    signal_actor_id=signal.id,pedestrian_actor_id=pedestrian.id,
                    display='Walk' if walk_request else 'Wait',
                    pedestrian_facing_signal=True,
                    pedestrian_in_crosswalk=-12<=ped_xy[1]<=-10 and -3.5<=ped_xy[0]<=3.5,
                    pedestrian_xy_m=ped_xy,bus_front_y_m=max(p[1] for p in body_xy(bus)),
                    provenance='authored_display_request')
                command=controller.step(observation=observation,
                    position_xy_m=(bus_pose.location.x,bus_pose.location.y),
                    yaw_rad=math.radians(bus_pose.rotation.yaw),speed_mps=speed,dt_s=.05)
                bus.apply_control(carla.VehicleControl(throttle=command['throttle'],
                    brake=command['brake'],steer=command['steer'],hand_brake=command['hand_brake']))
                frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                bus_pose=bus.get_transform();ped_pose=pedestrian.get_transform()
                velocity=bus.get_velocity();speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                bus_body=body_xy(bus);ped_body=body_xy(pedestrian)
                sample={'native_frame':frame,'time_s':time_s,
                        'walk_signal_actor_id':signal.id,'pedestrian_actor_id':pedestrian.id,
                        'bus_actor_id':bus.id,'walk_signal_display_observed':'Unknown',
                        'walk_display_request':'Walk' if walk_request else 'Wait',
                        'display_source':'authored_debug_text_pending_original_pixel_review',
                        'pedestrian_facing_signal':True,
                        'pedestrian_facing_source':'authored_route_pending_original_heading_review',
                        'bus_body_xy_m':bus_body,'pedestrian_body_xy_m':ped_body,
                        'bus_speed_mps':speed,'speed_provenance':'native_measured',
                        'controller_request':command}
                capture.capture(frame,time_s,extra={'c111256_native':sample})
                sample_file.write(json.dumps(sample,allow_nan=False)+'\n')
                body_file.write(json.dumps({'frame':frame,'time_s':time_s,
                    'bus_body_xy_m':bus_body,'pedestrian_body_xy_m':ped_body},
                    allow_nan=False)+'\n')
                pixel_hashes={}
                for spec in camera_plan(config['candidate_id']):
                    image=queues[spec['name']].get(timeout=30)
                    while image.frame<frame:image=queues[spec['name']].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Original camera/Native frame join differs')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(
                        spec['height'],spec['width'],4)[:,:,:3][:,:,::-1]
                    data=rgb.tobytes();pixel_hashes[spec['name']]=hashlib.sha256(data).hexdigest()
                    encoders[spec['name']].stdin.write(data)
                frame_file.write(json.dumps({'video_frame':index,'native_frame':frame,
                    'carla_frame':frame,'time_s':time_s,'source_rgb_sha256':pixel_hashes})+'\n')
                frames+=1
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0:raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:actor.stop()
                actor.destroy()
            except BaseException as exc:error=error or {'owned_actor_cleanup_error':str(exc)}
        if changed:
            try:restored=restore(client,saved)
            except BaseException as exc:error=error or {'world_restore_error':str(exc)}
        write_new(output/'native-capture-report.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'frames':frames,'expected_frames':480,'restoration':restored,'error':error,
            'accepted':False,'walk_governance_verified':False,
            'required_saved_checks':['official pedestrian-facing Walk pixels and governance',
                'actual bus/pedestrian body conflict and driver control',
                'full original camera/frame join','independent delivery and comparison audits']})
    if error:raise RuntimeError('Native capture failed; inspect native-capture-report.json: '+str(error))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--config',type=Path,default=HERE/'config.json')
    parser.add_argument('--output-dir',type=Path);parser.add_argument('--host')
    parser.add_argument('--port',type=int);args=parser.parse_args()
    config=json.loads(args.config.read_text())
    if args.check:print(json.dumps(check(config),allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Supply new materialized case directory, host and port')
        execute(config,args.output_dir,args.host,args.port)


if __name__=='__main__':main()
