"""CARLA-lazy two-vehicle station reversal construction for C111706."""

import argparse
import json
from math import atan2, cos, hypot, radians, sin
from pathlib import Path

from fire_station_camera_capture import CAMERAS, FFmpegSourceSink, FireStationCameraCapture
from fire_station_geometry import validate_entrance
from fire_station_sources import StationSourceRecorder


BRANCHES = {'front_entrance_turn', 'front_approach_turn',
            'driveway_use_turn', 'remote_reference'}


def check_config(config):
    branch = config.get('case_branch')
    if branch not in BRANCHES or not config.get('selected_case_id', '').endswith('__'+branch):
        raise ValueError('Exact C111706 station branch required')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-12-060', 'C111706', 'motor_vehicle_driver'):
        raise ValueError('Wrong frozen C111706 law/cell/actor identity')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20,240,12):
        raise ValueError('Original 240-frame 20 Hz capture required')
    if {camera.get('name') for camera in config.get('cameras', [])} != set(CAMERAS):
        raise ValueError('Four named original cameras required')
    if config.get('required_atoms') != []:
        raise ValueError('Unreviewed station observation terms are not Core atoms')
    survey = config.get('station_survey')
    if not isinstance(survey, dict) or not survey.get('map_name'):
        raise ValueError('Source-bound Native station survey required')
    source = survey.get('station_source', {})
    if (source.get('kind') not in ('operator_survey','map_landmark','authored_diagnostic')
            or not source.get('asset_id') or len(source.get('source_sha256','')) != 64):
        raise ValueError('Station asset identity and source SHA256 required')
    for key in ('public_before','public_at','public_after','driveway_at'):
        ref = survey.get(key, {})
        if not all(item in ref for item in ('road_id','lane_id','s')):
            raise ValueError('Station survey lacks Native waypoint: '+key)
    route = survey.get('routes', {}).get(branch)
    other = survey.get('other_route')
    if not isinstance(route, list) or len(route) < 3 or not isinstance(other,list) or len(other)<3:
        raise ValueError('Subject and other-vehicle connected routes required')
    if branch == 'driveway_use_turn' and not any(
            point.get('road_id') == survey['driveway_at']['road_id'] for point in route):
        raise ValueError('Driveway-use route never enters mapped driveway')
    if not 0 < config.get('target_speed_mps',0) <= 10 or not 0 < config.get('other_speed_mps',0) <= 10:
        raise ValueError('Bounded two-vehicle speeds required')
    if not .2 <= config.get('spawn_height_m',.3) <= .6:
        raise ValueError('Station spawn height outside engineering bounds')
    if not 1. <= config.get('waypoint_arrival_m',2.) <= 4.:
        raise ValueError('Station waypoint arrival radius outside engineering bounds')
    if not 0 <= config.get('overview_height_delta_m',0.) <= 2.:
        raise ValueError('Station overview height outside engineering bounds')
    return True


def _waypoint(world_map, ref):
    wp = world_map.get_waypoint_xodr(int(ref['road_id']),int(ref['lane_id']),float(ref['s']))
    if wp is None:
        raise ValueError('Survey waypoint absent from Native map')
    return wp


def _original_anchor(wp):
    location = wp.transform.location
    return {'xy':[float(location.x),float(location.y)],
            'road_id':int(wp.road_id),'lane_id':int(wp.lane_id),
            'lane_width':float(wp.lane_width)}


def resolve_survey(world_map, survey, branch):
    if world_map.name != survey['map_name']:
        raise ValueError('Native map differs from source-bound station survey')
    anchors = {key:_waypoint(world_map,survey[key]) for key in
               ('public_before','public_at','public_after','driveway_at')}
    validate_entrance(*(anchors[key] for key in
                        ('public_before','public_at','public_after','driveway_at')),
                      source=survey['station_source'])
    route = [_waypoint(world_map,ref) for ref in survey['routes'][branch]]
    other = [_waypoint(world_map,ref) for ref in survey['other_route']]
    def identities(path):
        return {(wp.road_id,wp.lane_id,round(float(wp.s),2)) for wp in path}
    if len(identities(route)) < 3 or len(identities(other)) < 3:
        raise ValueError('Two Native routes need distinct physical waypoints')
    original_survey = {'map_name':world_map.name,
                       'station_source':survey['station_source'],
                       **{key:_original_anchor(wp) for key,wp in anchors.items()}}
    return route, other, original_survey


def steer_toward(actor, target, speed_mps, carla, *, gain=.22):
    pose = actor.get_transform()
    p, q = pose.location, target.transform.location
    desired = atan2(q.y-p.y,q.x-p.x)
    yaw = radians(pose.rotation.yaw)
    error = atan2(sin(desired-yaw),cos(desired-yaw))
    velocity = actor.get_velocity()
    speed = hypot(velocity.x,velocity.y)
    delta = speed_mps-speed
    actor.apply_control(carla.VehicleControl(
        throttle=min(.55,max(0.,gain*delta)),
        brake=min(.7,max(0.,-.3*delta)),
        steer=min(.6,max(-.6,error/.8))))


def _advance(actor, route, index, arrival_m=2.):
    p = actor.get_transform().location
    q = route[index].transform.location
    if hypot(p.x-q.x,p.y-q.y) < arrival_m and index < len(route)-1:
        index += 1
    return index, route[index]


def run(output, host='127.0.0.1', port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture

    output = Path(output)
    config = json.loads((output/'config.json').read_text())
    check_config(config)
    if config['station_survey']['station_source']['kind']=='authored_diagnostic':
        raise ValueError('Native capture requires a real source-bound station asset')
    client = carla.Client(host,port)
    client.set_timeout(30)
    world = client.get_world()
    original_settings = world.get_settings()
    actors=[];sinks={};camera=pipeline=frame_map=recorder=None
    frames=[];failed=False;restored=False
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        world_map=world.get_map()
        subject_route,other_route,original_survey=resolve_survey(
            world_map,config['station_survey'],config['case_branch'])
        blueprint=world.get_blueprint_library().find(
            config.get('vehicle_blueprint','vehicle.tesla.model3'))
        for route in (subject_route,other_route):
            first=route[0].transform
            spawn=carla.Transform(carla.Location(
                x=first.location.x,y=first.location.y,
                z=first.location.z+config.get('spawn_height_m',.3)),
                first.rotation)
            actor=world.try_spawn_actor(blueprint,spawn)
            if actor is None:
                raise ValueError('C111706 subject or other Native vehicle spawn failed')
            actors.append(actor)
        for name in CAMERAS:
            sinks[name]=FFmpegSourceSink(output,name)
        camera=FireStationCameraCapture(world,carla,actors[0],sinks,
            overview_height_delta_m=config.get('overview_height_delta_m',0.))
        pipeline=PipelineCapture(client,actors[0],output,config['selected_case_id'],
                                 required_observations=config['required_atoms'])
        frame_map=FrameMap(output/'video_frames.jsonl')
        recorder=StationSourceRecorder(output,original_survey)
        indices=[1,1];start=None
        for _ in range(config['frames']):
            for index,(actor,route,speed) in enumerate(zip(
                    actors,(subject_route,other_route),
                    (config['target_speed_mps'],config['other_speed_mps']))):
                indices[index],target=_advance(actor,route,indices[index],
                    arrival_m=config.get('waypoint_arrival_m',2.))
                steer_toward(actor,target,speed,carla)
            frame=world.tick();snapshot=world.get_snapshot()
            if frame!=snapshot.frame:
                raise ValueError('Native station frame differs from completed tick')
            if start is None:start=snapshot.timestamp.elapsed_seconds
            time_s=snapshot.timestamp.elapsed_seconds-start
            camera.wait_for_frame(frame)
            trace=pipeline.capture(frame,time_s)
            if trace.get('frame')!=frame or trace.get('time_s')!=time_s:
                raise ValueError('Original C111706 trace/frame join differs')
            frame_map.append(frame,time_s)
            recorder.append(frame,time_s,actors[0],actors[1],world_map)
            frames.append(frame)
        camera.verify_frames(frames)
        if indices[0]!=len(subject_route)-1:
            raise ValueError('Subject did not reach selected station reversal route end')
    except BaseException:
        failed=True
        raise
    finally:
        if recorder:recorder.close()
        if frame_map:frame_map.close()
        if pipeline:pipeline.close(confirmed=not failed)
        if camera:camera.close()
        for sink in sinks.values():sink.close()
        for actor in reversed(actors):actor.destroy()
        world.apply_settings(original_settings)
        current=world.get_settings()
        restored=(current.synchronous_mode==original_settings.synchronous_mode and
                  current.fixed_delta_seconds==original_settings.fixed_delta_seconds)
        if not restored:
            raise ValueError('Original C111706 world restoration differs')
    (output/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,
        'original_frames':len(frames)})+'\n')
    seal_capture(output,frames=len(frames),restoration={'restored':restored},
                 errors=[],encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'native_map_name':world.get_map().name,
                          'station_source':config['station_survey']['station_source']})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--config',default='config.json')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.check:
        check_config(json.loads(Path(args.config).read_text()))
    elif args.output_dir:
        run(args.output_dir,args.host,args.port)
    else:
        parser.error('--output-dir required without --check')


if __name__=='__main__':main()
