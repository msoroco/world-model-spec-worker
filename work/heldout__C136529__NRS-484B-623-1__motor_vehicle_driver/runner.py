"""Native entrypoint for C136529 slow traffic interaction primary case.

The local operator supplies an already owned CARLA endpoint. No legal outcome
is asserted; saved processing measures the original participant histories.
"""
import argparse
from copy import deepcopy
import json
from math import atan2,cos,hypot,radians,sin
from pathlib import Path
from slow_route import select_route
from slow_camera_capture import CAMERAS,SlowCameraCapture,FFmpegSourceSink
from slow_capture_session import SlowCaptureSession

CASE_SUFFIXES={'flowing_reference','slow_with_following_traffic','slow_for_obstruction'}

def check_config(config):
    branch=config.get('case_branch')
    if branch not in CASE_SUFFIXES or not config.get('selected_case_id','').endswith('__'+branch):
        raise ValueError('Runner bound to an exact supported slow-speed case')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor')) != (
            'NRS-484B-623-1','C136529','motor_vehicle_driver'):
        raise ValueError('Runner law/cell/actor identity differs')
    if config.get('rate_hz')!=20 or config.get('frames')!=160 or config.get('duration_s')!=8:
        raise ValueError('Runner requires 160 original 20 Hz frames')
    if {x.get('name') for x in config.get('cameras',[])}!=set(CAMERAS):
        raise ValueError('Four named source cameras required')
    for key in ('route_step_m','follower_gain','speed_kp','speed_brake_gain'):
        value=config.get(key)
        if value is not None and (not isinstance(value,(int,float)) or value<=0):
            raise ValueError('Invalid engineering control knob: '+key)
    if config.get('obstruction_index',12) not in (11,12,13,14):
        raise ValueError('Invalid obstruction site index')
    if config.get('obstruction_brake_gain',.4)<=0:
        raise ValueError('Invalid obstruction braking gain')
    if not isinstance(config.get('case',{}).get('recording_description'),dict):
        raise ValueError('Selected recording description required')
    return True


def _spawn(world,blueprint_id,waypoint):
    bp=world.get_blueprint_library().find(blueprint_id)
    transform=deepcopy(waypoint.transform)
    transform.location.z+=.3
    actor=world.try_spawn_actor(bp,transform)
    if actor is None:raise ValueError('Native actor spawn failed: '+blueprint_id)
    return actor


def _lane_control(world_map,actor,target_mps,carla,*,speed_kp=.22,brake_gain=.3):
    if target_mps<0:raise ValueError('negative target speed')
    transform=actor.get_transform()
    waypoint=world_map.get_waypoint(transform.location)
    if waypoint is None or waypoint.is_junction:
        raise ValueError('vehicle left measured narrow route')
    choices=[w for w in waypoint.next(6.0) if w.road_id==waypoint.road_id
             and w.lane_id==waypoint.lane_id and not w.is_junction]
    if len(choices)!=1:raise ValueError('vehicle lost unique lane target')
    target=choices[0].transform.location
    angle=atan2(target.y-transform.location.y,target.x-transform.location.x)
    yaw=radians(transform.rotation.yaw)
    error_angle=atan2(sin(angle-yaw),cos(angle-yaw))
    velocity=actor.get_velocity()
    speed=hypot(velocity.x,velocity.y)
    error=target_mps-speed
    throttle=min(.6,max(0.,speed_kp*error))
    brake=min(.8,max(0.,-brake_gain*error))
    actor.apply_control(carla.VehicleControl(throttle=throttle,brake=brake,
                          steer=min(.45,max(-.45,error_angle/.6))))


def _follower_target(ego,follower,*,gain=.4):
    ep=ego.get_transform().location;fp=follower.get_transform().location
    gap=hypot(ep.x-fp.x,ep.y-fp.y)
    ev=ego.get_velocity();ego_speed=hypot(ev.x,ev.y)
    return min(8.0,max(0.0,ego_speed+gain*(gap-9.0)))


def _obstruction_target(ego,obstruction,requested_mps,*,gain=.4):
    ep=ego.get_transform().location;op=obstruction.get_transform().location
    gap=hypot(ep.x-op.x,ep.y-op.y)
    return min(requested_mps,max(0.0,gain*(gap-9.0)))

def run(output,host,port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import seal_capture
    output=Path(output)
    config=json.loads((output/'config.json').read_text())
    check_config(config)
    client=carla.Client(host,port);client.set_timeout(30.)
    world=client.get_world();original=world.get_settings()
    owned=[];sinks={};camera=pipeline=session=None;frames=[];errors=[];restored=False
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        route=select_route(world.get_map(),step_m=config.get('route_step_m',5.0))
        for role in ('ego','follower','opposing'):
            owned.append(_spawn(world,'vehicle.tesla.model3',route[role]))
        ego,follower,opposing=owned
        obstruction=None
        if config['case_branch']=='slow_for_obstruction':
            obstruction=_spawn(world,'vehicle.tesla.model3',route['chain'][config.get('obstruction_index',12)])
            obstruction.set_simulate_physics(False)
            owned.append(obstruction)
        for name in CAMERAS:sinks[name]=FFmpegSourceSink(output,name)
        camera=SlowCameraCapture(world,carla,ego,sinks)
        pipeline=PipelineCapture(client,ego,output,config['selected_case_id'],
                                  required_observations=config.get('required_atoms',[]))
        session=SlowCaptureSession(output,pipeline,ego,follower,opposing,obstruction,None,
                                   {'case_branch':config['case_branch']})
        start=None
        for _ in range(config['frames']):
            target_speed=(_obstruction_target(ego,obstruction,config['ego_target_mps'],
                                               gain=config.get('obstruction_brake_gain',.4))
                          if obstruction is not None else config['ego_target_mps'])
            _lane_control(world.get_map(),ego,target_speed,carla,
                          speed_kp=config.get('speed_kp',.22),brake_gain=config.get('speed_brake_gain',.3))
            _lane_control(world.get_map(),follower,_follower_target(ego,follower,
                          gain=config.get('follower_gain',.4)),carla)
            _lane_control(world.get_map(),opposing,8.0,carla)
            frame=world.tick();snapshot=world.get_snapshot()
            if snapshot.frame!=frame:raise ValueError('Native snapshot differs from completed tick')
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            session.capture(frame,time_s)
            frames.append(frame)
        camera.verify_frames(frames)
    except BaseException as error:
        errors.append(str(error));raise
    finally:
        if session is not None:session.close()
        if pipeline is not None:pipeline.close(confirmed=not errors)
        if camera is not None:camera.close()
        for sink in sinks.values():sink.close()
        for actor in reversed(owned):actor.destroy()
        world.apply_settings(original)
        current=world.get_settings()
        restored=current.synchronous_mode==original.synchronous_mode and current.fixed_delta_seconds==original.fixed_delta_seconds
        if not restored:raise ValueError('Native world settings restoration readback differs')
    if errors or not frames:raise ValueError('Native capture did not finish')
    (output/'acquisition-provenance.json').write_text(json.dumps({
       'provenance_kind':'native','diagnostic_fixture':False,'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':restored},errors=[],
       encoder_exit_codes={name:0 for name in CAMERAS},
       context={'native_map_name':world.get_map().name,'road_id':route['road_id'],
                'ego_lane_id':route['ego_lane_id'],
                'opposing_lane_id':route['opposing_lane_id'],
                'measured_lane_width_m':route['lane_width_m']})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir');parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:
        candidate=Path('config.json')
        if candidate.is_file():check_config(json.loads(candidate.read_text()))
        return
    if not args.output_dir:parser.error('--output-dir required')
    run(args.output_dir,args.host,args.port)
if __name__=='__main__':main()
