"""C110919 pedestrian-conflict pair; capture runs only with an owned endpoint.

The offline --check path never imports CARLA or starts a server. A later capture
must be audited from original Native and pixel sources before selection.
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
from controller import EngineeringKnobs, PathController
from engineering import parameters
from engineering import CASES
from geometry import route
from variant_geometry import check_for as geometry_check_for, open_drive_for
from yield_branch import POLICIES, decide

ROOT=Path(__file__).resolve().parent

def write_new(path: Path, value: object):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')

def check(config: dict) -> dict:
    suffix=config.get('case_suffix')
    candidate=config.get('candidate_id')
    if suffix not in POLICIES or candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown exact case or candidate')
    if config.get('case_id')!='training__C110919__NRS-484B-307-8a__motor_vehicle_driver__'+suffix:
        raise ValueError('Case identity differs')
    if config.get('cell_id')!='C110919' or config.get('law_id')!='NRS-484B-307-8a':
        raise ValueError('Cell or law differs')
    if config.get('rate_hz')!=20 or config.get('duration_s')!=24:
        raise ValueError('Capture profile differs')
    if config.get('actor')!='motor_vehicle_driver':
        raise ValueError('Actor differs')
    settings=parameters('reference',candidate)
    if config.get('knobs')!=settings['knobs']:
        raise ValueError('Candidate knobs differ')
    geom=geometry_check_for('reference')
    cameras=camera_plan(candidate)
    if len(cameras)!=4 or cameras[0]['width']!=1920 or cameras[0]['height']!=1080:
        raise ValueError('Original camera profile differs')
    EngineeringKnobs(lookahead_base_m=settings['knobs']['route_tracking_lookahead_m']).validate()
    PathController(route(),2.8,70.0,EngineeringKnobs(
        lookahead_base_m=settings['knobs']['route_tracking_lookahead_m']))
    return {'offline_geometry':geom,'candidate':candidate,'case':suffix,
            'camera_count':4,'route_samples':len(route()),
            'native_imported':False,'physical_success_claimed':False}

def body_xy(actor):
    vertices=actor.bounding_box.get_world_vertices(actor.get_transform())
    points=sorted({(round(v.x,5),round(v.y,5)) for v in vertices})
    if len(points)!=4:raise RuntimeError('Native body has no four-corner horizontal footprint')
    return [list(point) for point in points]

def camera_transform(carla,spec):
    x,y,z=spec['xyz_m']
    if spec['attachment']=='world':
        yaw=math.degrees(math.atan2(-y,-x))
        pitch=math.degrees(math.atan2(-z,math.hypot(x,y)))
    else:
        yaw=0;pitch=-5
    return carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(yaw=yaw,pitch=pitch))

def survey(carla,mapping,native_hash,case_suffix):
    requests={'approach_right':(1.75,-30,1),
              'approach_left':(-1.75,-30,1),
              'destination_right':(30,-1.75,2),
              'destination_left':(30,1.75,2)}
    observed={}
    for name,(x,y,road) in requests.items():
        waypoint=mapping.get_waypoint(carla.Location(x=x,y=y,z=.2),project_to_road=False,
                                      lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id!=road:
            raise RuntimeError('Native road/lane readback failed: '+name)
        vec=waypoint.transform.get_forward_vector()
        observed[name]={'road_id':waypoint.road_id,'lane_id':waypoint.lane_id,
                        'forward_xy':[vec.x,vec.y]}
    if observed['approach_right']['lane_id']!=-1 or observed['destination_right']['lane_id']!=-1:
        raise RuntimeError('Extreme-right Native lane mapping differs')
    absent=case_suffix.startswith('absent_reference')
    return {'native_map_sha256':native_hash,'lanes':observed,
            'stop_line_y_m':None if absent else -14.0,
            'nearest_crosswalk_y_m':None if absent else -11.0,
            'intersection_near_y_m':-7.0,
            'stopping_reference_kind':'intersection_boundary' if absent else 'marked_stop_line',
            'stopping_reference_y_m':-7.0 if absent else -14.0,
            'native_absence_observed':False,
            'destination_crosswalk_x_m':10.0,
            'authored_reference_only':True,'pixels_verified':False}

def execute(config: dict,output: Path,host: str,port: int):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot,restore
    check(config)
    output=output.resolve()
    if not output.is_dir() or not (output/'config.json').is_file():
        raise ValueError('Use exact materialized case directory')
    client=carla.Client(host,port);client.set_timeout(180)
    saved=snapshot(client)
    old=client.get_world()
    if saved['settings'].synchronous_mode or [a for a in old.get_actors()
        if a.type_id.startswith(('vehicle.','walker.','sensor.','controller.'))]:
        raise RuntimeError('Requires exclusive idle asynchronous Native world')
    owned=[];camera_queues={};encoders={};encoder_logs={};channels={}
    capture=None;changed=False;restored=None;error=None;frames=0
    try:
        world=client.generate_opendrive_world(open_drive_for('reference'),carla.OpendriveGenerationParameters(
            vertex_distance=.25,max_road_length=50,wall_height=0,additional_width=0,
            smooth_junctions=False,enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed=True
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        settings.substepping=True;settings.max_substep_delta_time=.01;settings.max_substeps=10
        world.apply_settings(settings);world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping=world.get_map();native_xml=mapping.to_opendrive()
        native_hash=hashlib.sha256(native_xml.encode()).hexdigest()
        readback=survey(carla,mapping,native_hash,config['case_suffix'])
        traffic_lights=list(world.get_actors().filter('traffic.traffic_light*'))
        if not traffic_lights:
            raise RuntimeError('Authored OpenDRIVE signal has no Native traffic-light actor')
        signal_actor=min(traffic_lights,key=lambda actor:math.dist(
            (actor.get_location().x,actor.get_location().y),(0,-13)))
        signal_actor.set_state(carla.TrafficLightState.Red)
        signal_actor.freeze(True)
        readback['signal_actor_id']=signal_actor.id
        write_new(output/'road_geometry.json',readback)
        write_new(output/'context.json',{'surveyed_right_turn':readback})
        library=world.get_blueprint_library()
        blueprint=library.find('vehicle.lincoln.mkz_2020')
        blueprint.set_attribute('role_name','c110919_ego')
        ego=world.spawn_actor(blueprint,carla.Transform(
            carla.Location(x=1.75,y=-40,z=.5),carla.Rotation(yaw=90)))
        owned.append(ego)
        ego.apply_control(carla.VehicleControl(brake=1,hand_brake=True))
        for _ in range(40):world.tick()
        physics=ego.get_physics_control();wheels=physics.wheels
        if len(wheels)!=4:raise RuntimeError('Native four-wheel geometry absent')
        wheelbase=(max(w.position.x for w in wheels)-min(w.position.x for w in wheels))/100
        steer=max(w.max_steer_angle for w in wheels)
        knobs=config['knobs']
        controller=PathController(route(),wheelbase,steer,EngineeringKnobs(
            lookahead_base_m=knobs['route_tracking_lookahead_m']))
        # A destination-crosswalk walker is an actor proposal. Observed conflict
        # occupancy and clearance are measured from saved actor history later.
        walker_bp=next(bp for bp in library.filter('walker.pedestrian.*'))
        walker=world.spawn_actor(walker_bp,carla.Transform(
            carla.Location(x=10,y=5,z=.4),carla.Rotation(yaw=-90)))
        owned.append(walker)
        write_new(output/'native-construction-context.json',{
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'native_map_sha256':native_hash,'vehicle_blueprint':ego.type_id,
            'walker_blueprint':walker.type_id,'wheelbase_m':wheelbase,'max_steer_deg':steer,
            'initial_body_xy_m':body_xy(ego),'knobs':knobs,
            'authored_intent':'controlled pedestrian conflict comparison after the same red-signal stop',
            'yield_policy':config['case_suffix'],
            'physical_completion_claimed':False})
        for spec in camera_plan(config['candidate_id']):
            bp=library.find('sensor.camera.rgb')
            for key,value in (('image_size_x',spec['width']),('image_size_y',spec['height']),
                              ('fov',spec['fov_deg']),('sensor_tick',0)):
                bp.set_attribute(key,str(value))
            sensor=world.spawn_actor(bp,camera_transform(carla,spec),
                attach_to=ego if spec['attachment']=='ego' else None)
            owned.append(sensor);camera_queues[spec['name']]=queue.Queue()
            sensor.listen(camera_queues[spec['name']].put)
            encoder_logs[spec['name']]=(output/(spec['name']+'.encoder.log')).open('x')
            encoders[spec['name']]=subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f"{spec['width']}x{spec['height']}",
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(spec['name']+'.mkv'))],stdin=subprocess.PIPE,
                stderr=encoder_logs[spec['name']])
        capture=PipelineCapture(client,ego,output,config['case_id'],visibility=False,
                                required_observations=config.get('required_atoms',[]))
        (output/'channels').mkdir()
        for name in config['mandatory_channels']:
            channels[name]=(output/'channels'/(name+'.jsonl')).open('x')
        start=world.get_snapshot().timestamp.elapsed_seconds
        held=0;yield_clear=0
        stop_boundary=readback['stopping_reference_y_m']
        with (output/'native_samples.jsonl').open('x') as native_file, \
             (output/'body_history.jsonl').open('x') as body_file, \
             (output/'video_frames.jsonl').open('x') as frame_file:
            for index in range(config['rate_hz']*config['duration_s']):
                green_release=config['case_suffix'].startswith('green_release_')
                if green_release and index==160:
                    signal_actor.set_state(carla.TrafficLightState.Green)
                pose=ego.get_transform();velocity=ego.get_velocity()
                speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                command=controller.step(position_xy_m=(pose.location.x,pose.location.y),
                    yaw_rad=math.radians(pose.rotation.yaw),speed_mps=speed,dt_s=.05)
                pedestrian=walker.get_transform().location
                occupied=8<=pedestrian.x<=12 and -4<=pedestrian.y<=4
                if 115<=index<=195:
                    walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(0,-1,0),speed=3.0))
                else:
                    walker.apply_control(carla.WalkerControl(direction=carla.Vector3D(0,0,0),speed=0.0))
                full_stop=True
                wait_for_green=(config['case_suffix']=='green_release_wait' and
                                signal_actor.get_state()!=carla.TrafficLightState.Green)
                stop_needed=full_stop and (held<30 or wait_for_green) and pose.location.y>-25
                if stop_needed:
                    command.update(throttle=0.0,brake=1.0,hand_brake=speed<.05)
                    if speed<.05 and max(p[1] for p in body_xy(ego))<stop_boundary:held+=1
                yield_decision=decide(config['case_suffix'],
                    red_stop_completed=held>=30,
                    in_turn_approach=pose.location.y>-10 and pose.location.x<10,
                    conflict_occupied=occupied,
                    previous_clearance_frames=yield_clear,
                    required_clearance_frames=round(knobs['yield_clearance_margin_s']*20))
                yield_clear=yield_decision.clearance_frames
                if yield_decision.brake:
                    command.update(throttle=0.0,brake=1.0,hand_brake=speed<.05)
                ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                    brake=command['brake'],steer=command['steer'],hand_brake=command['hand_brake']))
                frame=world.tick();time_s=world.get_snapshot().timestamp.elapsed_seconds-start
                pose=ego.get_transform();velocity=ego.get_velocity()
                speed=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
                body=body_xy(ego);ped=walker.get_transform().location
                sample={'time_s':time_s,'native_frame':frame,'native_center_xy_m':[pose.location.x,pose.location.y],
                        'native_yaw_deg':pose.rotation.yaw,'native_body_xy_m':body,'speed_mps':speed,
                        'walker_center_xy_m':[ped.x,ped.y],
                        'walker_conflict_occupied':8<=ped.x<=12 and -4<=ped.y<=4,
                        'signal_state_observed':str(signal_actor.get_state()),
                        'controller_request':command,
                        'yield_policy':config['case_suffix'],
                        'yield_decision_reason':yield_decision.reason}
                capture.capture(frame,time_s,extra={'c110919_native':sample})
                native_file.write(json.dumps(sample,allow_nan=False)+'\n')
                body_file.write(json.dumps({'frame':frame,'time_s':time_s,
                    'body_vertices_m':[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(pose)]},
                    allow_nan=False)+'\n')
                values={'dev.traffic_signal':{'authored_request':('red_until_frame_160_then_green'
                                                    if green_release else 'steady_red'),
                                               'observed_state':sample['signal_state_observed'],
                                               'native_actor_id':signal_actor.id},
                        'st.stop_line':readback['stop_line_y_m'],'st.crosswalk':readback['nearest_crosswalk_y_m'],
                        'drv.stopped':speed<.05,'kin.velocity':speed,
                        'drv.extreme_lane':readback['lanes']['approach_right'],
                        'st.one_way_roadway':readback['lanes'],
                        'drv.yields_to':{'walker_xy_m':[ped.x,ped.y],
                                         'conflict_occupied':sample['walker_conflict_occupied']},
                        'native_body_pose_control':sample,
                        'camera_frame_join':{'native_frame':frame,'video_frame':index}}
                for name,stream in channels.items():
                    stream.write(json.dumps({'time_s':time_s,'value':values[name]},allow_nan=False)+'\n')
                for spec in camera_plan(config['candidate_id']):
                    image=camera_queues[spec['name']].get(timeout=30)
                    while image.frame<frame:image=camera_queues[spec['name']].get(timeout=30)
                    if image.frame!=frame:raise RuntimeError('Camera/Native frame join failed')
                    rgb=np.frombuffer(image.raw_data,dtype=np.uint8).reshape(spec['height'],spec['width'],4)[:,:,:3][:,:,::-1]
                    encoders[spec['name']].stdin.write(rgb.tobytes())
                frame_file.write(json.dumps({'video_frame':index,'native_frame':frame,
                                             'carla_frame':frame,'time_s':time_s})+'\n')
                frames+=1
        if frames!=480:raise RuntimeError('Incomplete original capture frame count')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        for stream in channels.values():stream.close()
        if capture is not None:
            try:capture.close(confirmed=error is None)
            except BaseException as exc:error=error or {'capture_close_error':str(exc)}
        for name,encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180)!=0:raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:error=error or {'encoder_error':str(exc)}
            encoder_logs[name].close()
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
            'frames':frames,'expected_frames':480,'restoration':restored,
            'error':error,'accepted':False,
            'required_saved_checks':['actual signal state and governing direction',
                'Native stop-line and crosswalk readback','original full body and walker conflict',
                'full video/frame join and independent audit']})
    if error:raise RuntimeError('Native attempt failed; see native-capture-report.json: '+str(error))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port',type=int)
    args=parser.parse_args()
    config=json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check(config),allow_nan=False))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error('Supply materialized output directory, host and port')
        execute(config,args.output_dir,args.host,args.port)

if __name__=='__main__':main()
