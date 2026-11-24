"""Unselected original-source C230222 curbside driving capture proposal."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

FRAMES = 600
RATE = 20
PREFIX = 'training__C245490__NRS-484B-223-1b__motor_vehicle_driver__'
VIEWS = ('overview', 'approach', 'target_lane', 'driver_reference')


def check(config):
    case = config.get('case_id')
    if (case not in (PREFIX + 'signal_before_draft', PREFIX + 'signal_after_draft') or
            config.get('selected_case_id') != case or
            config.get('law_id') != 'NRS-484B-223-1b' or
            config.get('cell_id') != 'C245490' or
            config.get('actor') != 'motor_vehicle_driver' or
            config.get('candidate_id') != 'primary' or
            config.get('duration_s') != 30 or config.get('rate_hz') != RATE or
            config.get('vehicle_blueprint') != 'vehicle.tesla.model3' or
            config.get('legal_verdict') is not None or
            type(config.get('signal_start_frame')) is not int or
            not 0 <= config['signal_start_frame'] < FRAMES or
            type(config.get('target_vehicle_ahead_m')) not in (int, float) or
            not 5 <= config['target_vehicle_ahead_m'] <= 100 or
            type(config.get('spawn_point_index')) is not int or
            config['spawn_point_index'] < 0):
        raise ValueError('Exact draft Native identity or duration differs')
    cameras = config.get('cameras')
    if (type(cameras) is not list or len(cameras) != 4 or
            tuple(camera.get('name') for camera in cameras) != VIEWS):
        raise ValueError('Four named source cameras required')
    for camera in cameras:
        if (type(camera.get('width')) is not int or camera['width'] < 16 or
                type(camera.get('height')) is not int or camera['height'] < 16 or
                type(camera.get('fov_deg')) not in (int, float) or
                not 1 <= camera['fov_deg'] <= 170 or
                type(camera.get('location_xyz_m')) is not list or
                type(camera.get('rotation_pyr_deg')) is not list or
                len(camera['location_xyz_m']) != 3 or
                len(camera['rotation_pyr_deg']) != 3 or
                not all(type(v) in (int, float) and math.isfinite(v) for v in
                        camera['location_xyz_m'] + camera['rotation_pyr_deg'])):
            raise ValueError('Incomplete camera geometry')
    phases = config.get('control_phases')
    if type(phases) is not list or not phases:
        raise ValueError('Control schedule required')
    cursor = 0
    for phase in phases:
        if (phase.get('first_frame') != cursor or
                type(phase.get('last_frame')) is not int or
                not cursor <= phase['last_frame'] < FRAMES or
                any(type(phase.get(key)) not in (int, float) for key in
                    ('throttle', 'steer', 'brake')) or
                not 0 <= phase['throttle'] <= 1 or
                not -1 <= phase['steer'] <= 1 or
                not 0 <= phase['brake'] <= 1):
            raise ValueError('Control schedule invalid or discontinuous')
        cursor = phase['last_frame'] + 1
    if cursor != FRAMES:
        raise ValueError('Control schedule shorter than 600 frames')
    return {'case_id': case, 'frames': FRAMES, 'rate_hz': RATE,
            'camera_views': list(VIEWS), 'simulation_started': False,
            'legal_verdict': None}


def phase_at(config, index):
    if not 0 <= index < FRAMES:
        raise ValueError('Frame outside 600-frame window')
    return next(p for p in config['control_phases']
                if p['first_frame'] <= index <= p['last_frame'])


def xyz(value):
    return [value.x, value.y, value.z]


def execute(config, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    check(config)
    output = Path(output)
    if any(not (output / name).is_file() for name in
           ('config.json', 'construction.json', 'runner.py')):
        raise ValueError('Materialized construction required')
    client = carla.Client(host, port)
    client.set_timeout(15.0)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors = [], []
    packets = queue.Queue()
    errors, encoders = [], {}
    restoration, count, failure = {'restored': False}, 0, None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        spawns = world.get_map().get_spawn_points()
        if len(spawns) <= config['spawn_point_index']:
            raise RuntimeError('Requested spawn unavailable')
        blueprint = world.get_blueprint_library().find(config['vehicle_blueprint'])
        ego = world.try_spawn_actor(blueprint, spawns[config['spawn_point_index']])
        if ego is None:
            raise RuntimeError('Requested spawn occupied')
        actors.append(ego)
        occupied_lane = world.get_map().get_waypoint(ego.get_location())
        target_lane = occupied_lane.get_left_lane()
        if target_lane is None or target_lane.lane_id * occupied_lane.lane_id <= 0:
            raise RuntimeError('A marked same-direction target lane is required')
        target_future = target_lane.next(config['target_vehicle_ahead_m'])
        if not target_future:
            raise RuntimeError('Target lane lacks planned vehicle position')
        target_vehicle = world.try_spawn_actor(blueprint, target_future[0].transform)
        if target_vehicle is None:
            raise RuntimeError('Target-lane vehicle spawn occupied')
        actors.append(target_vehicle)
        for camera in config['cameras']:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(camera['width']))
            bp.set_attribute('image_size_y', str(camera['height']))
            bp.set_attribute('fov', str(camera['fov_deg']))
            x, y, z = camera['location_xyz_m']
            pitch, yaw, roll = camera['rotation_pyr_deg']
            pose = carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))
            sensor = world.spawn_actor(bp, pose, attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            (output / camera['name']).mkdir(exist_ok=False)
            sensor.listen(lambda image, name=camera['name']: packets.put((name, image)))
        (output / 'driving-context.json').write_text(json.dumps({
            'source_kind': 'original_native', 'cell_id': 'C245490',
            'law_id': 'NRS-484B-223-1b', 'actor': 'motor_vehicle_driver',
            'map_name': world.get_map().name, 'vehicle_id': str(ego.id),
            'highway_in_city_evidence': None, 'legal_verdict': None,
            'camera_sources': {view: view + '.mkv' for view in VIEWS}}, indent=2) + '\n')
        with PipelineCapture(client, ego, output, config['case_id'],
                             required_observations=config['required_atoms']) as capture, \
                FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-ego-frames.jsonl').open('x', buffering=1) as motion:
            for index in range(FRAMES):
                phase = phase_at(config, index)
                target_vehicle.apply_control(carla.VehicleControl(throttle=0, brake=1))
                signal_on = index >= config['signal_start_frame']
                ego.set_light_state(carla.VehicleLightState.LeftBlinker if signal_on
                                    else carla.VehicleLightState.NONE)
                ego.apply_control(carla.VehicleControl(
                    throttle=phase['throttle'], steer=phase['steer'], brake=phase['brake']))
                native = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    view, image = packets.get(timeout=15)
                    if image.frame != native or view in seen:
                        continue
                    image.save_to_disk(str(output / view / f'{index:06d}.png'))
                    seen.add(view)
                capture.capture(native, index / RATE,
                                extra={'video_frame': index, 'control_phase': phase['name']})
                frame_map.append(native, index / RATE,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                pose = ego.get_transform()
                lane = world.get_map().get_waypoint(pose.location)
                if lane.road_id != occupied_lane.road_id:
                    raise RuntimeError('Ego left the planned same-road lane-change segment')
                lane_reference = world.get_map().get_waypoint_xodr(
                    occupied_lane.road_id, occupied_lane.lane_id, lane.s)
                if lane_reference is None:
                    raise RuntimeError('Occupied-lane reference unavailable at current road station')
                occupied_center = lane_reference.transform.location
                occupied_right = lane_reference.transform.get_right_vector()
                occupied_half_width = lane_reference.lane_width / 2
                lateral = pose.location - occupied_center
                offset = lateral.x * occupied_right.x + lateral.y * occupied_right.y
                target_delta = target_vehicle.get_location() - pose.location
                target_axis = occupied_lane.transform.get_forward_vector()
                center_distance = (target_delta.x ** 2 + target_delta.y ** 2) ** 0.5
                surface_gap = max(0, center_distance - ego.bounding_box.extent.x -
                                  target_vehicle.bounding_box.extent.x)
                relative_velocity = ego.get_velocity() - target_vehicle.get_velocity()
                closing_speed = max(0, relative_velocity.x * target_axis.x +
                                    relative_velocity.y * target_axis.y)
                marked_same_direction = [occupied_lane]
                candidate = occupied_lane.get_left_lane()
                while candidate is not None and candidate.lane_type == carla.LaneType.Driving:
                    if candidate.lane_id * occupied_lane.lane_id <= 0:
                        break
                    marked_same_direction.append(candidate)
                    candidate = candidate.get_left_lane()
                motion.write(json.dumps({
                    'source_kind': 'original_native', 'native_frame': native,
                    'video_frame': index, 'time_s': index / RATE,
                    'position_m': xyz(pose.location),
                    'velocity_mps': xyz(ego.get_velocity()),
                    'acceleration_mps2': xyz(ego.get_acceleration()),
                    'yaw_deg': pose.rotation.yaw,
                    'same_direction_marked_lane_count': len(marked_same_direction),
                    'occupied_lane_id': occupied_lane.lane_id,
                    'current_lane_id': lane.lane_id,
                    'occupied_lane_half_width_m': occupied_half_width,
                    'ego_body_half_width_m': ego.bounding_box.extent.y,
                    'ego_lateral_offset_from_occupied_lane_center_m': offset,
                    'target_direction_indicator_on': signal_on,
                    'target_lane_min_surface_gap_m': surface_gap,
                    'target_lane_closing_speed_mps': closing_speed,
                    'driver_safety_ascertainment': None}) + '\n')
                count += 1
        for view in VIEWS:
            result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error',
                                     '-framerate', str(RATE), '-i',
                                     str(output / view / '%06d.png'),
                                     '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                                     str(output / (view + '.mkv'))], timeout=300)
            encoders[view] = result.returncode
            if result.returncode:
                raise RuntimeError(view + ' encoder failed')
    except BaseException as error:
        failure = error
        errors.append(f'{type(error).__name__}: {error}')
    finally:
        for sensor in sensors:
            try:
                sensor.stop()
            except BaseException as error:
                errors.append(f'sensor stop: {error}')
        for actor in reversed(actors):
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(f'actor destroy: {error}')
        try:
            restoration = restore(client, original)
        except BaseException as error:
            errors.append(f'world restore: {error}')
        (output / 'native-run-status.json').write_text(json.dumps({
            'case_id': config['case_id'], 'frames': count, 'errors': errors,
            'restoration': restoration, 'encoder_exit_codes': encoders,
            'capture_finished': count == FRAMES and failure is None,
            'acceptance_claimed': False}, indent=2) + '\n')
    if failure is not None:
        raise failure
    if errors:
        raise RuntimeError('; '.join(errors))
    seal_capture(output, frames=count, restoration=restoration, errors=errors,
                 encoder_exit_codes=encoders,
                 context={'case_id': config['case_id'],
                          'source': 'original Native CARLA capture',
                          'legal_verdict': None})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    configuration = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(configuration)))
    else:
        if args.output_dir is None:
            parser.error('--output-dir required')
        execute(configuration, args.output_dir, args.host, args.port)
