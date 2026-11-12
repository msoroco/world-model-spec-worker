"""Native first-case median-entry capture. --check does not import CARLA."""
import argparse
import json
import math
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import PROFILE, source_cameras
from capture_sources import junction_context, record_crossing_sample
from controlled_pair import construct_off_pair
from route_control import steering_command, validate_route, validate_pair_routes


PRIMARY = 'testing__C125697__NRS-484B-250-2__motor_vehicle_driver__off_ego_left_near_time'
POSES = ('ego_approach', 'ego_entry', 'other_approach', 'other_entry')
CAMERAS = tuple(PROFILE)


def _numbers(values, size, label):
    if (not isinstance(values, list) or len(values) != size or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in values)):
        raise ValueError('Finite ' + label + ' required')
    return values


def validate_config(config):
    if (config.get('selected_case_id') != PRIMARY or
            config.get('law_id') != 'NRS-484B-250-2' or
            config.get('cell_id') != 'C125697' or
            config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('Exact first Off-state C125697 case required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Planned 20 Hz, 45-second source capture required')
    if config.get('other_approach_side') != 'right':
        raise ValueError('Other approach must be on ego right for ego-left case')
    if (not isinstance(config.get('required_atoms'), list) or
            not isinstance(config.get('recording_description'), dict)):
        raise ValueError('Pinned observations and recording description required')
    site = config.get('site')
    if not isinstance(site, dict):
        raise ValueError('Reviewed median site required')
    required = ('native_map_name', 'crossing_polygon_source', 'approach_geometry_source',
                'median_spacing_source', 'all_entrances_source',
                'signal_governance_source', 'signal_head_video_source',
                'ego_highway_id', 'other_highway_id')
    if any(not isinstance(site.get(key), str) or not site[key].strip() for key in required):
        raise ValueError('Source-reviewed median site fields required')
    if (site.get('same_statutory_crossing') is not True or
            site['ego_highway_id'] == site['other_highway_id'] or
            type(site.get('crossing_id')) is not int):
        raise ValueError('One sourced crossing of distinct highways required')
    polygon = site.get('crossing_polygon_xy_m')
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError('Crossing polygon required')
    for point in polygon:
        _numbers(point, 2, 'crossing vertex')
    for name in POSES:
        _numbers(site.get(name), 4, name + ' pose')
    cameras = site.get('cameras')
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError('All four source-camera poses required')
    for name, pose in cameras.items():
        _numbers(pose, 6, name + ' camera pose')
    lanes = site.get('entrance_road_lanes')
    if not isinstance(lanes, list) or len(lanes) < 2:
        raise ValueError('All governed entrance lanes required')
    for lane in lanes:
        if (not isinstance(lane, list) or len(lane) != 2 or
                any(type(value) is not int for value in lane)):
            raise ValueError('Native entrance road and lane IDs required')
    if len({tuple(row) for row in lanes}) != len(lanes):
        raise ValueError('Distinct entrance lane inventory required')
    routes = site.get('routes')
    if not isinstance(routes, dict) or set(routes) != {'ego', 'other'}:
        raise ValueError('Both authored crossing routes required')
    for role in ('ego', 'other'):
        validate_route(routes[role], site[role + '_approach'][:2],
                       site[role + '_entry'][:2], polygon, role)
    for key in ('ego_release_frame', 'other_release_frame'):
        if type(config.get(key)) is not int or not 0 <= config[key] < 900:
            raise ValueError('Valid ' + key + ' required')
    for key in ('ego_target_speed_mps', 'other_target_speed_mps'):
        speed = config.get(key)
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 20:
            raise ValueError('Finite positive target speed required')
    return config


def _transform(carla, pose):
    return carla.Transform(carla.Location(x=pose[0], y=pose[1], z=pose[2]),
                           carla.Rotation(yaw=pose[3],
                                          pitch=pose[4] if len(pose) > 4 else 0,
                                          roll=pose[5] if len(pose) > 5 else 0))


def _sensor_frame(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError('Missing source camera frame ' + str(frame)) from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError('Source camera skipped Native frame ' + str(frame))
    raise ValueError('Source camera frame join failed')


@contextmanager
def _spawn_ego(world, blueprint, transform):
    ego = world.try_spawn_actor(blueprint, transform)
    if ego is None:
        raise ValueError('Ego Native spawn failed')
    try:
        yield ego
    finally:
        ego.destroy()


def _drive(carla, actor, speed_target, held, steer):
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    if not math.isfinite(speed):
        raise ValueError('Nonfinite Native speed feedback')
    command = carla.VehicleControl()
    command.steer = steer
    command.throttle = 0.0 if held else max(0.0, min(.65, .18 + .16 * (speed_target - speed)))
    command.brake = 1.0 if held else (min(.4, .3 * (speed - speed_target)) if speed > speed_target else 0.0)
    actor.apply_control(command)


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot as save_world

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / 'construction.json').is_file():
        raise ValueError('Use runtime.py capture to materialize exact construction first')
    site = config['site']
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    world = client.get_world()
    encoders, frames, errors = {}, 0, []
    capture_helper = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        if world.get_map().name != site['native_map_name']:
            raise ValueError('Native map differs from reviewed median site')
        transforms = {name: _transform(carla, site[name]) for name in POSES}
        blueprint = world.get_blueprint_library().filter('vehicle.*')[0]
        with _spawn_ego(world, blueprint, transforms['ego_approach']) as ego:
            with construct_off_pair(world, site, transforms, blueprint,
                                    carla.TrafficLightState, 'right') as (plan, other, lights):
                validate_pair_routes(plan, site['routes'])
                (output / 'junction_context.json').write_text(
                    json.dumps(junction_context(site, plan), indent=2) + '\n')
                camera_poses = {name: _transform(carla, site['cameras'][name])
                                for name in CAMERAS}
                with source_cameras(world, ego, camera_poses) as sensors:
                    queues = {name: Queue() for name in CAMERAS}
                    for name, sensor in sensors.items():
                        sensor.listen(lambda image, name=name: queues[name].put(image))
                    with ExitStack() as stack:
                        for name, (width, height) in PROFILE.items():
                            encoders[name] = stack.enter_context(
                                FFV1Writer(output / (name + '.mkv'), width, height))
                        frame_map = stack.enter_context(FrameMap(output / 'video_frames.jsonl'))
                        history = stack.enter_context((output / 'crossing_history.jsonl').open('x', buffering=1))
                        controls = stack.enter_context((output / 'controller_history.jsonl').open('x', buffering=1))
                        capture_helper = PipelineCapture(
                            client, ego, output, config['selected_case_id'],
                            required_observations=config['required_atoms'])
                        try:
                            progress = {'ego': 1, 'other': 1}
                            for i in range(900):
                                steering = {}
                                for role, actor in (('ego', ego), ('other', other)):
                                    pose = actor.get_transform()
                                    steering[role], progress[role] = steering_command(
                                        float(pose.location.x), float(pose.location.y),
                                        float(pose.rotation.yaw), site['routes'][role],
                                        progress[role])
                                _drive(carla, ego, config['ego_target_speed_mps'],
                                       i < config['ego_release_frame'], steering['ego'])
                                _drive(carla, other, config['other_target_speed_mps'],
                                       i < config['other_release_frame'], steering['other'])
                                world.tick()
                                snapshot = world.get_snapshot()
                                camera_frames = {}
                                for name in CAMERAS:
                                    image = _sensor_frame(queues[name], snapshot.frame)
                                    encoders[name].write(bytes(image.raw_data))
                                    camera_frames[name] = image.frame
                                capture_helper.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                                record_crossing_sample(frame_map, history, snapshot,
                                                       world.get_map(), ego, other, lights,
                                                       carla.TrafficLightState, camera_frames, plan)
                                controls.write(json.dumps({
                                    'frame': snapshot.frame,
                                    'time_s': snapshot.timestamp.elapsed_seconds,
                                    'ego_steer': steering['ego'], 'other_steer': steering['other'],
                                    'route_target_index': progress.copy(),
                                    'ego_held': i < config['ego_release_frame'],
                                    'other_held': i < config['other_release_frame']}) + '\n')
                                frames += 1
                        finally:
                            capture_helper.close()
                            capture_helper = None
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if capture_helper is not None:
            capture_helper.close(confirmed=False)
        restoration = restore(client, saved)
        if not errors:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: writer.exit_code
                                             for name, writer in encoders.items()},
                         context={'median_statutory_review_source':
                                  site['crossing_polygon_source'],
                                  'physical_acceptance_claimed': False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = validate_config(json.loads(Path(args.config).read_text()))
    if args.check:
        print(json.dumps({'case_id': PRIMARY, 'planned_frames': 900,
                          'named_source_cameras': list(CAMERAS),
                          'cpu_check_passed': True, 'carla_started': False,
                          'physical_acceptance_claimed': False}))
        return
    if not args.output_dir:
        raise ValueError('--output-dir required for Native capture')
    capture(args, config)


if __name__ == '__main__':
    main()
