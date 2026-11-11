"""CARLA-lazy C109749 Native left-turn capture candidate.

The CPU --check validates authored configuration only. Native motion and pixel
coverage require an authorized local run and independent source review.
"""
import argparse
import json
import math
from contextlib import ExitStack
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE, source_cameras
from capture_sources import record_sample
from construction import select_intersection, spawn_reciprocal_vehicle
from inside_oncoming_setup import (spawn_inside_pair, verify_inside_body,
                                  opposing_target_speed)
from controller import LeftTurnController
from native_scene import control_inputs, junction_context

CASE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__signal_omitted'
CAMERAS = tuple(PROFILE)


def validate_config(config):
    if (config.get('selected_case_id') != CASE or config.get('law_id') != 'NRS-484B-253'
            or config.get('cell_id') != 'C109749'):
        raise ValueError('Exact C109749 case identity required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Pinned 20 Hz and 45-second capture required')
    camera_rows = config.get('cameras')
    if not isinstance(camera_rows, list) or [row.get('name') for row in camera_rows] != list(CAMERAS):
        raise ValueError('Four named source-camera rows required')
    if any((row.get('width'),row.get('height')) != PROFILE[row['name']] for row in camera_rows):
        raise ValueError('Pinned source-camera dimensions required')
    for field in ('controller_release_ttc_s','approach_speed_mps',
                  'reciprocal_approach_speed_mps','inside_oncoming_travel_m'):
        value = config.get(field)
        if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
            raise ValueError('Positive finite controller tuning required: '+field)
    if config.get('signal_policy') != 'omit' or 'sig.turn_indicator' not in config.get('required_atoms',[]):
        raise ValueError('Selected indicator observation required')
    if config['inside_oncoming_travel_m'] < 4.0:
        raise ValueError('Inside-junction waypoint travel must be at least 4 m')
    return config


def camera_transforms(carla, selected, context):
    x,y = context['conflict_point_xy_m']
    ego_start = selected['ego']['outside'].transform.location
    other_start = selected['oncoming']['outside'].transform.location
    def at(px,py,pz,yaw,pitch):
        return carla.Transform(carla.Location(x=px,y=py,z=pz),
                               carla.Rotation(yaw=yaw,pitch=pitch))
    heading = math.degrees(math.atan2(y-other_start.y,x-other_start.x))
    return {'overview':at(x,y,ego_start.z+45,heading,-75),
            'approach':at(other_start.x,other_start.y,other_start.z+6,heading,-16),
            'reference_corner':at(x+16,y+16,ego_start.z+9,heading-130,-28),
            'driver_reference':at(1.0,0.0,1.65,0.0,-6.0)}


def read_sensor(queue, native_frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Source camera frame missing: '+str(native_frame)) from error
        if image.frame == native_frame:
            return image
        if image.frame > native_frame:
            raise ValueError('Source camera skipped Native frame: '+str(native_frame))
    raise ValueError('Source camera frame join failed')


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as save_world, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output/'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction first')
    client = carla.Client(args.host,args.port)
    client.set_timeout(30)
    saved = save_world(client)
    world = client.get_world()
    encoders = {}
    capture_helper = None
    actors = ()
    frames = 0
    error = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        selected = select_intersection(world.get_map())
        context = junction_context(selected)
        context['native_map_id'] = world.get_map().name
        context['legal_intersection_status'] = 'original-source review required'
        (output/'intersection_geometry.json').write_text(json.dumps(context,indent=2)+'\n')
        ego,oncoming = actors = spawn_inside_pair(
            world,selected,travel_m=config['inside_oncoming_travel_m'])
        verify_inside_body(oncoming, context)
        reciprocal = spawn_reciprocal_vehicle(world,selected)
        actors = (*actors,reciprocal)
        controller = LeftTurnController(release_ttc_s=config['controller_release_ttc_s'],
                                        approach_speed_mps=config['approach_speed_mps'])
        transforms = camera_transforms(carla,selected,context)
        seen_other = seen_ego = False
        with source_cameras(world,ego,transforms,config['cameras']) as sensors:
            queues = {name:Queue() for name in CAMERAS}
            for name,sensor in sensors.items():
                sensor.listen(lambda image,name=name:queues[name].put(image))
            with ExitStack() as stack:
                for name,(width,height) in PROFILE.items():
                    encoders[name] = stack.enter_context(FFV1Writer(output/(name+'.mkv'),width,height))
                frame_map = stack.enter_context(FrameMap(output/'video_frames.jsonl'))
                history = stack.enter_context((output/'interaction_history.jsonl').open('x',buffering=1))
                capture_helper = PipelineCapture(client,ego,output,CASE,
                                                 required_observations=config['required_atoms'])
                try:
                    for _ in range(config['duration_s']*config['rate_hz']):
                        measured = control_inputs(selected,ego,oncoming,context,
                                                  seen_oncoming_inside=seen_other,
                                                  seen_ego_inside=seen_ego)
                        seen_other = measured.pop('seen_oncoming_inside')
                        seen_ego = measured.pop('seen_ego_inside')
                        command = controller.step(**measured)
                        light = carla.VehicleLightState.NONE  # authored omitted-signal policy; read back from actor
                        ego.set_light_state(light)
                        ego.apply_control(carla.VehicleControl(throttle=command['throttle'],
                                    brake=command['brake'],steer=command['steer']))
                        speed = math.hypot(*record_velocity(oncoming))
                        target = opposing_target_speed(
                            ego_body_seen_in_junction=seen_ego,
                            authored_approach_speed_mps=config['approach_speed_mps'])
                        oncoming.apply_control(carla.VehicleControl(
                            throttle=min(0.5,max(0.0,0.15*(target-speed))),
                            brake=min(1.0,max(0.0,0.25*(speed-target))),steer=0.0))
                        later_speed = math.hypot(*record_velocity(reciprocal))
                        later_target = (0.0 if command['state'] in ('turn','complete')
                                        else config['reciprocal_approach_speed_mps'])
                        reciprocal.apply_control(carla.VehicleControl(
                            throttle=min(0.4,max(0.0,0.15*(later_target-later_speed))),
                            brake=min(1.0,max(0.0,0.4*(later_speed-later_target))),steer=0.0))
                        world.tick()
                        snapshot = world.get_snapshot()
                        for name in CAMERAS:
                            encoders[name].write(bytes(read_sensor(queues[name],snapshot.frame).raw_data))
                        capture_helper.capture(snapshot.frame,snapshot.timestamp.elapsed_seconds)
                        frame_map.append(snapshot.frame,snapshot.timestamp.elapsed_seconds)
                        record_sample(history,snapshot=snapshot,ego=ego,oncoming=oncoming,
                                      reciprocal=reciprocal,
                                      left_indicator_mask=int(carla.VehicleLightState.LeftBlinker))
                        frames += 1
                finally:
                    capture_helper.close()
                    capture_helper = None
    except BaseException as caught:
        error = caught
        raise
    finally:
        cleanup_errors = []
        if capture_helper is not None:
            try:
                capture_helper.close(confirmed=False)
            except BaseException as caught:
                cleanup_errors.append(str(caught))
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as caught:
                cleanup_errors.append(str(caught))
        restoration = restore(client,saved)
        if error is None and not cleanup_errors:
            seal_capture(output,frames=frames,restoration=restoration,errors=[],
                         encoder_exit_codes={name:encoders[name].exit_code for name in CAMERAS},
                         context={'native_junction_candidate':True,
                                  'legal_intersection_status':'original-source review required'})
        if error is None and cleanup_errors:
            raise ValueError('Native resource cleanup failed: '+'; '.join(cleanup_errors))


def record_velocity(actor):
    velocity = actor.get_velocity()
    values = (float(velocity.x),float(velocity.y))
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Nonfinite Native opposing velocity')
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args = parser.parse_args()
    config = validate_config(json.loads((Path(__file__).parent/'config.json').read_text()))
    if args.check:
        print(json.dumps({'case_id':CASE,'cpu_check_passed':True,'carla_started':False}))
        return
    if not args.output_dir:
        raise ValueError('--output-dir required for Native capture')
    capture(args,config)


if __name__ == '__main__':
    main()
