"""C101303 first-case Native capture; no CARLA import during CPU --check.

The dedicated local operator supplies --host/--port and a CARLA-capable Python.
This runner never starts a server or accesses campaign state.
"""
import argparse
import json
import math
from pathlib import Path
from queue import Queue, Empty
from contextlib import ExitStack
from following_controller import FollowingController
from body_gap_geometry import native_body_offset
from native_following_setup import discover_hill_crest_route, spawn_following_pair
from camera_setup import source_cameras, SIZES
from camera_encoder import FFV1Writer
from capture_sources import record_sample

CASE='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_base'
CAMERAS=('overview','approach','reference_corner','driver_reference')

def validate_config(config):
    if config.get('selected_case_id')!=CASE or config.get('law_id')!='NRS-484B-127-1' or config.get('cell_id')!='C101303':
        raise ValueError('Exact C101303 case identity required')
    if config.get('rate_hz')!=20 or config.get('duration_s')!=45:
        raise ValueError('Pinned 20 Hz and 45-second capture required')
    camera_rows=config.get('cameras')
    if not isinstance(camera_rows,list) or [row.get('name') for row in camera_rows]!=list(CAMERAS):
        raise ValueError('All four named cameras required')
    if any((row.get('width'),row.get('height'))!=SIZES[row['name']] for row in camera_rows):
        raise ValueError('Pinned source-camera dimensions required')
    for key in ('requested_engineering_gap_m','ego_target_speed_mps','lead_target_speed_mps',
                'minimum_corridor_length_m','minimum_crest_rise_m'):
        v=config.get(key)
        if type(v) not in (int,float) or not math.isfinite(v) or v<=0:
            raise ValueError('Positive finite '+key+' required')
    return config

def camera_transforms(carla,route):
    crest=route['waypoints'][route['crest_waypoint_index']].transform.location
    start=route['waypoints'][0].transform.location
    later=route['waypoints'][1].transform.location
    yaw=math.degrees(math.atan2(later.y-start.y,later.x-start.x))
    def static(x,y,z,heading,pitch):
        return carla.Transform(carla.Location(x=x,y=y,z=z),carla.Rotation(yaw=heading,pitch=pitch))
    return {'overview':static(crest.x,crest.y,crest.z+55,yaw,-75),
            'approach':static(start.x-8,start.y,start.z+7,yaw,-18),
            'reference_corner':static(crest.x,crest.y+16,crest.z+10,yaw-90,-30),
            'driver_reference':static(1.0,0.0,1.65,0.0,-6.0)}

def read_sensor(queue,frame):
    for _ in range(6):
        try:image=queue.get(timeout=10)
        except Empty as error:raise ValueError('Missing source camera frame '+str(frame)) from error
        if image.frame==frame:return image
        if image.frame>frame:raise ValueError('Source camera skipped requested frame '+str(frame))
    raise ValueError('Source camera frame join failed')

def capture(args,config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as save_world, restore
    output=Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction first')
    client=carla.Client(args.host,args.port);client.set_timeout(30)
    saved=save_world(client);world=client.get_world();restoration=None
    errors=[];encoders={};capture_helper=None;frames=0
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05
        world.apply_settings(settings)
        native_map=world.get_map()
        route=discover_hill_crest_route(native_map,
             minimum_length_m=config['minimum_corridor_length_m'],
             minimum_crest_rise_m=config['minimum_crest_rise_m'])
        waypoints=route['waypoints'];lead_index=min(5,len(waypoints)-1)
        if lead_index<=0:raise ValueError('No Native lead spawn waypoint')
        blueprint=world.get_blueprint_library().filter('vehicle.*')[0]
        with spawn_following_pair(world,blueprint,waypoints[0].transform,waypoints[lead_index].transform) as pair:
            ego,lead=pair['ego'],pair['lead']
            context={'native_map_id':native_map.name,'highway_id':route['road_id'],
                     'road_id':route['road_id'],'following_lane_id':route['following_lane_id'],
                     'target_lane_id':route['target_lane_id'],
                     'hill_crest_source':'Native waypoint elevation plus original cameras',
                     'lane_geometry_source':'Native waypoints','surface_source':'original Native weather',
                     'traffic_source':'original Native actor inventory','route_source':'Native waypoint chain',
                     'following_forward_xy':[waypoints[1].transform.location.x-waypoints[0].transform.location.x,
                                             waypoints[1].transform.location.y-waypoints[0].transform.location.y],
                     'native_crest_rise_m':route['crest_rise_m'],
                     'legal_highway_status':'source review required'}
            (output/'road_context.json').write_text(json.dumps(context,indent=2)+'\n')
            control=FollowingController(carla.VehicleControl,
                target_speed_mps=config['ego_target_speed_mps'],
                target_center_spacing_m=config['requested_engineering_gap_m']+native_body_offset(
                     ego,lead,context['following_forward_xy']),
                lane_change_start_m=max(1,route['corridor_length_m']*.55),
                lane_change_end_m=max(2,route['corridor_length_m']*.70),
                lead_speed_mps=config['lead_target_speed_mps'])
            transforms=camera_transforms(carla,route)
            with source_cameras(world,ego,transforms) as sensors:
                queues={name:Queue() for name in CAMERAS}
                for name,sensor in sensors.items():sensor.listen(lambda image,name=name:queues[name].put(image))
                with ExitStack() as stack:
                    for name,(width,height) in SIZES.items():
                        encoders[name]=stack.enter_context(FFV1Writer(output/(name+'.mkv'),width,height))
                    frame_map=stack.enter_context(FrameMap(output/'video_frames.jsonl'))
                    history=stack.enter_context((output/'vehicle_history.jsonl').open('x',buffering=1))
                    capture_helper=PipelineCapture(client,ego,output,CASE,
                        required_observations=config['required_atoms'])
                    try:
                        origin=waypoints[0].transform.location
                        target=route['target_lane_waypoint'].transform.location
                        direction=context['following_forward_xy']
                        for _ in range(config['rate_hz']*config['duration_s']):
                            phase=control.step(ego,lead,route_origin_xyz=(origin.x,origin.y,origin.z),
                                route_forward_xy=direction,target_lane_center_xy=(target.x,target.y))
                            world.tick();snap=world.get_snapshot()
                            for name in CAMERAS:
                                image=read_sensor(queues[name],snap.frame)
                                encoders[name].write(bytes(image.raw_data))
                            capture_helper.capture(snap.frame,snap.timestamp.elapsed_seconds)
                            ewp=native_map.get_waypoint(ego.get_location(),project_to_road=False)
                            lwp=native_map.get_waypoint(lead.get_location(),project_to_road=False)
                            if ewp is None or lwp is None:raise ValueError('Native participant left sourced road')
                            weather=world.get_weather()
                            surface='wet' if weather.wetness>0 else 'dry'
                            traffic_ids=sorted(actor.id for actor in world.get_actors().filter('vehicle.*'))
                            record_sample(frame_map,history,snap,ego,lead,road_id=route['road_id'],
                                ego_lane_id=ewp.lane_id,lead_lane_id=lwp.lane_id,
                                surface_condition=surface,traffic_actor_ids=traffic_ids,
                                lane_change_started=phase['lane_change_started'])
                            frames+=1
                    finally:
                        capture_helper.close()
                        capture_helper=None
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if capture_helper is not None:capture_helper.close(confirmed=False)
        restoration=restore(client,saved)
        if not errors:
            seal_capture(output,frames=frames,restoration=restoration,errors=[],
                         encoder_exit_codes={name:encoders[name].exit_code for name in CAMERAS},
                         context={'native_route_review_status':'source review required',
                                  'native_hill_crest_candidate':True})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    config=validate_config(json.loads((Path(__file__).parent/'config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id':CASE,'cpu_check_passed':True,'carla_started':False}))
        return
    if not args.output_dir:raise ValueError('--output-dir required for Native capture')
    capture(args,config)
if __name__=='__main__':main()
