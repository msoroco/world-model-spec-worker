"""Config-driven C125745 stop-sign Native capture; --check stays CPU-only."""
import argparse
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from shapely.geometry import MultiPoint, Polygon

from camera_encoder import FFV1Writer
from capture_sources import CAMERAS, record_sample, source_cameras
from median_route_control import validate_scene
from native_pair import construct_pair, step_pair
from site_packet import verify_site_packet

ASSIGNMENT='testing__C125745__NRS-484B-250-2__motor_vehicle_driver'
CASE_IDS={ASSIGNMENT+'__'+suffix for suffix in (
    'stop_ego_left_near_time','stop_ego_right_near_time',
    'stop_ego_left_separated','stop_opposite_left_turn')}


def load_config(path):
    path=Path(path)
    config=json.loads(path.read_text())
    if (config.get('assignment_id')!=ASSIGNMENT or
        config.get('law_id')!='NRS-484B-250-2' or
        config.get('cell_id')!='C125745' or
        config.get('actor')!='motor_vehicle_driver' or
        config.get('selected_case_id') not in CASE_IDS):
        raise ValueError('Exact C125745 assignment identity required')
    if config.get('rate_hz')!=20 or type(config.get('frames')) is not int or config['frames']<60:
        raise ValueError('20 Hz and positive planned duration required')
    if (type(config.get('duration_s')) not in (int,float) or
        not math.isclose(config['duration_s'],config['frames']/20,abs_tol=1e-9)):
        raise ValueError('Duration must match the planned 20 Hz frames')
    if type(config.get('other_release_frame')) is not int or not 0<=config['other_release_frame']<config['frames']:
        raise ValueError('Other release frame required')
    if not isinstance(config.get('required_atoms'),list):
        raise ValueError('Pinned required atoms list required')
    if not isinstance(config.get('recording_description'),dict):
        raise ValueError('Recording description required')
    scene=verify_site_packet(config,path.parent)
    validate_scene(scene)
    if not scene.get('native_map_name') or type(scene.get('intersection_id')) is not int:
        raise ValueError('Native map and junction identity required')
    if set(scene.get('camera_poses',{}))!=set(CAMERAS):
        raise ValueError('Four named camera poses required')
    for name,pose in scene['camera_poses'].items():
        if not isinstance(pose,list) or len(pose)!=6 or any(type(v) not in (int,float) or not math.isfinite(v) for v in pose):
            raise ValueError('Finite six-value camera pose required: '+name)
    for role in ('ego','other'):
        pose=scene['approaches'][role].get('spawn_pose')
        if not isinstance(pose,list) or len(pose)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in pose):
            raise ValueError('Finite four-value Native spawn pose required: '+role)
    return config,scene


def _transform(carla,pose):
    return carla.Transform(carla.Location(x=pose[0],y=pose[1],z=pose[2]),
                           carla.Rotation(yaw=pose[3],pitch=pose[4] if len(pose)>4 else 0,
                                          roll=pose[5] if len(pose)>5 else 0))


def _sensor_frame(queue,frame):
    for _ in range(6):
        try:image=queue.get(timeout=10)
        except Empty as exc:raise ValueError('Missing camera frame '+str(frame)) from exc
        if image.frame==frame:return image
        if image.frame>frame:raise ValueError('Camera skipped Native frame '+str(frame))
    raise ValueError('Camera frame join failed')


def _other_conflict_clear(other,polygon,buffer_m=8):
    vertices=other.bounding_box.get_world_vertices(other.get_transform())
    body=MultiPoint([(v.x,v.y) for v in vertices]).convex_hull
    if body.area<=0:raise ValueError('Complete other body required for conflict check')
    return body.distance(polygon)>buffer_m


def _context(scene):
    sources=scene['source_refs']
    required=('crossing_geometry_source','all_entrances_source','sign_governance_source',
              'sign_face_video_source','median_spacing_source')
    if any(not sources.get(name) for name in required):
        raise ValueError('Reviewed crossing and sign source references required')
    ego,other=scene['approaches']['ego'],scene['approaches']['other']
    return {'native_map_id':scene['native_map_name'],
            'intersection_id':scene['intersection_id'],
            'ego_highway_id':ego['highway_id'],'other_highway_id':other['highway_id'],
            'ego_road_id':ego['road_id'],'other_road_id':other['road_id'],
            'crossing_geometry_source':sources['crossing_geometry_source'],
            'all_entrances_source':sources['all_entrances_source'],
            'sign_governance_source':sources['sign_governance_source'],
            'sign_face_video_source':sources['sign_face_video_source'],
            'median_spacing_source':sources['median_spacing_source'],
            'native_stop_sign_id':scene['stop_sign']['native_id'],
            'same_statutory_crossing':True,
            'intersection_polygon_xy_m':scene['crossing_polygon_xy_m'],
            'ego_approach_forward_xy':ego['forward_xy'],
            'other_approach_forward_xy':other['forward_xy'],
            'approach_relation':scene['approach_relation'],
            'turn_intent_source':'controller_history.jsonl' if scene['approach_relation']=='opposite_directions' else None,
            'physical_acceptance_claimed':False,
            'legal_conclusion':'unresolved'}


def _native_approaches(world_map, poses, scene, carla):
    """Match both spawn lanes and locate the sign check at the stop entrance."""
    waypoints={}
    for role in ('ego','other'):
        expected=scene['approaches'][role]
        waypoint=world_map.get_waypoint(poses[role].location,project_to_road=False)
        if (waypoint is None or waypoint.road_id!=expected['road_id'] or
                waypoint.lane_id!=expected['lane_id']):
            raise ValueError(role+' Native spawn road/lane differs from reviewed site')
        waypoints[role]=waypoint
    stop=scene['ego_stop_line_xy_m']
    stop_location=carla.Location(x=stop[0],y=stop[1],z=poses['ego'].location.z)
    entrance=world_map.get_waypoint(stop_location,project_to_road=False)
    if (entrance is None or
            entrance.road_id!=scene['approaches']['ego']['road_id'] or
            entrance.lane_id!=scene['approaches']['ego']['lane_id']):
        raise ValueError('Native stop entrance road/lane differs from reviewed site')
    return waypoints,entrance


def capture(args,config,scene):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap,seal_capture
    from worker_exchange.world_restore import snapshot as save_world,restore

    output=Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Use runtime.py capture for an exact construction first')
    client=carla.Client(args.host,args.port);client.set_timeout(30)
    saved=save_world(client)
    world=client.get_world();encoders={};capture_helper=None;frames=0;failed=False
    try:
        settings=world.get_settings();settings.synchronous_mode=True
        settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        world_map=world.get_map()
        if world_map.name!=scene['native_map_name']:
            raise ValueError('Native map differs from reviewed site packet')
        poses={role:_transform(carla,scene['approaches'][role]['spawn_pose']) for role in ('ego','other')}
        _,stop_entrance=_native_approaches(world_map,poses,scene,carla)
        blueprints=world.get_blueprint_library().filter('vehicle.*')
        if not blueprints:raise ValueError('Native vehicle blueprint missing')
        polygon=Polygon(scene['crossing_polygon_xy_m'])
        with construct_pair(world,scene,blueprints[0],blueprints[0],poses['ego'],poses['other'],stop_entrance) as (ego,other,sign):
            (output/'junction_context.json').write_text(json.dumps(_context(scene),indent=2)+'\n')
            camera_poses={name:_transform(carla,pose) for name,pose in scene['camera_poses'].items()}
            with source_cameras(world,ego,camera_poses) as sensors:
                queues={name:Queue() for name in CAMERAS}
                for name,sensor in sensors.items():
                    sensor.listen(lambda image,name=name:queues[name].put(image))
                with ExitStack() as stack:
                    for name,(width,height) in CAMERAS.items():
                        encoders[name]=stack.enter_context(FFV1Writer(output/(name+'.mkv'),width,height))
                    frame_map=stack.enter_context(FrameMap(output/'video_frames.jsonl'))
                    history=stack.enter_context((output/'crossing_history.jsonl').open('x',buffering=1))
                    controls=stack.enter_context((output/'controller_history.jsonl').open('x',buffering=1))
                    capture_helper=PipelineCapture(client,ego,output,config['selected_case_id'],
                                                   required_observations=config['required_atoms'])
                    try:
                        progress={'ego':1,'other':1};stopped=False
                        for i in range(config['frames']):
                            clear=_other_conflict_clear(other,polygon)
                            progress,stopped,commands=step_pair(
                                carla,ego,other,scene,progress,stopped,clear,
                                i>=config['other_release_frame'])
                            world.tick();snap=world.get_snapshot()
                            camera_frames={}
                            for name in CAMERAS:
                                image=_sensor_frame(queues[name],snap.frame)
                                encoders[name].write(bytes(image.raw_data))
                                camera_frames[name]=image.frame
                            capture_helper.capture(snap.frame,snap.timestamp.elapsed_seconds)
                            record_sample(frame_map,history,snap,world_map,ego,other,sign,
                                          camera_frames,scene,
                                          scene['approach_relation']=='opposite_directions')
                            controls.write(json.dumps({'frame':snap.frame,
                                'time_s':snap.timestamp.elapsed_seconds,
                                'ego_stopped_once':stopped,'other_conflict_clear':clear,
                                'other_left_turn_intended':scene['approach_relation']=='opposite_directions',
                                'commands':commands,'route_target_index':progress})+'\n')
                            frames+=1
                    except BaseException:
                        capture_helper.close(confirmed=False)
                        capture_helper=None
                        raise
                    else:
                        capture_helper.close()
                        capture_helper=None
    except BaseException:
        failed=True;raise
    finally:
        if capture_helper is not None:capture_helper.close(confirmed=False)
        restoration=restore(client,saved)
        if not failed:
            seal_capture(output,frames=frames,restoration=restoration,errors=[],
                         encoder_exit_codes={name:writer.exit_code for name,writer in encoders.items()},
                         context={'physical_acceptance_claimed':False,
                                  'site_packet_sha256':config['site_packet']['sha256']})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    config,scene=load_config(args.config)
    if args.check:
        print(json.dumps({'assignment_id':ASSIGNMENT,'case_id':config['selected_case_id'],
                          'planned_frames':config['frames'],'named_source_cameras':list(CAMERAS),
                          'cpu_check_passed':True,'carla_started':False,
                          'physical_acceptance_claimed':False}))
        return
    if not args.output_dir:raise ValueError('--output-dir required for Native capture')
    capture(args,config,scene)

if __name__=='__main__':main()
