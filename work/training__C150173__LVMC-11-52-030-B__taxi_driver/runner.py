"""Prospective original Native taxi yellow-curb capture; no legal findings."""
import json
import queue
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from yellow_plan import check, read_requested

HERE = Path(__file__).resolve().parent


def finish_owned_capture(pipeline, encoders, owned, client, prior, changed,
                         complete, output, config, restore, seal_capture):
    """Attempt every owned cleanup step, even when an earlier step fails."""
    first_error = None
    if pipeline is not None:
        try:
            pipeline.close(confirmed=complete)
        except Exception as error:
            first_error = error
            complete = False
    for encoder in encoders.values():
        try:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
        except Exception as error:
            first_error = first_error or error
            complete = False
    for actor in reversed(owned):
        try:
            if hasattr(actor, 'stop'):
                actor.stop()
            actor.destroy()
        except Exception as error:
            first_error = first_error or error
            complete = False
    try:
        restored = restore(client, prior) if changed else {
            'restored': True, 'world_unchanged': True}
    except Exception as error:
        first_error = first_error or error
        restored = {'restored': False}
        complete = False
    if complete and first_error is None:
        try:
            seal_capture(output, frames=600, restoration=restored, errors=[],
                encoder_exit_codes={name: encoder.returncode
                                    for name, encoder in encoders.items()},
                context={'case_id': config['case_id'],
                         'taxicab_sign_passenger_authority': 'pending'})
        except Exception as error:
            first_error = error
    if first_error is not None and sys.exc_info()[0] is None:
        raise first_error


def offline_check(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    result = check(config, (root / 'yellow-road.xodr').read_text())
    result['request_measure'] = read_requested(root / 'requested-track.jsonl', config)
    return result


def capture(config, output_dir, host='127.0.0.1', port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config, (HERE / 'yellow-road.xodr').read_text())
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'yellow-zone-native.jsonl').exists():
        raise ValueError('New empty original attempt directory required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    prior = snapshot(client)
    previous = client.get_world()
    if prior['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in previous.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    pipeline = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world((HERE / 'yellow-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=10, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        road_map = world.get_map()
        parking = road_map.get_waypoint(carla.Location(x=config['taxi_stop_x_m'], y=10, z=1),
            project_to_road=True, lane_type=carla.LaneType.Parking)
        if parking is None or parking.road_id != 1 or parking.lane_id != -2:
            raise RuntimeError('Authored yellow parking lane readback failed')
        (output / 'road.xodr').write_text(road_map.to_opendrive())
        (output / 'sign-authority-pending.json').write_text(json.dumps({
            'source_kind': 'original_native',
            'authored_sign_proposal': 'TAXI PASSENGERS 09:00-17:00 PROPOSAL',
            'actual_sign_authority_source': None,
            'taxicab_license_source': None,
            'passenger_waiting_source': None,
            'outside_hours_ordinary_rules_source': None,
            'legal_verdict': None}, indent=2) + '\n')
        library = world.get_blueprint_library()
        vehicles = sorted(library.filter(config['taxi_blueprint_filter']), key=lambda bp: bp.id)
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda bp: bp.id)
        if not vehicles or not walkers:
            raise RuntimeError('Taxi-role vehicle or passenger-proxy blueprint unavailable')
        taxi_bp = vehicles[0]
        taxi_bp.set_attribute('role_name', 'c150173_taxi_identity_pending')
        taxi = world.spawn_actor(taxi_bp, carla.Transform(
            carla.Location(x=config['taxi_stop_x_m'], y=10, z=2), carla.Rotation(yaw=90)))
        passenger_start_x = (config['taxi_stop_x_m'] + .25
                             if config['requested_purpose'] == 'unloading_passengers'
                             else config['taxi_stop_x_m'] + 2.95)
        passenger = world.spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=passenger_start_x, y=10, z=2), carla.Rotation(yaw=270)))
        owned.extend((taxi, passenger))
        pipeline = PipelineCapture(client, taxi, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        for spec in config['cameras']:
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('sensor_tick', '.05')
            bp.set_attribute('fov', str(spec['fov_deg']))
            x, y, z = spec['location_xyz_m']
            pitch, roll, yaw = spec['rotation_pyr_deg']
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(
                    pitch=pitch, roll=roll, yaw=yaw)),
                attach_to=taxi if spec['name'] == 'driver_reference' else None)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[spec['name']] = q
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', '-',
                '-frames:v', '600', '-c:v', 'ffv1', '-level', '1',
                str(output / (spec['name'] + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        civil_start = datetime.fromisoformat(config['civil_start_local'])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'yellow-zone-native.jsonl').open('x') as rows, \
                (output / 'trace.jsonl').open('x') as trace:
            initial = None
            for index in range(600):
                taxi.apply_control(carla.VehicleControl(
                    throttle=0, brake=1, hand_brake=True))
                activity = 160 <= index < 280
                direction = (1 if config['requested_purpose'] == 'unloading_passengers'
                             else -1 if config['requested_purpose'] == 'loading_passengers'
                             else 0)
                passenger.apply_control(carla.WalkerControl(
                    direction=carla.Vector3D(x=direction if activity else 0, y=0, z=0),
                    speed=.5 if activity and direction else 0))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial is None:
                    initial = snap.timestamp.elapsed_seconds - .05
                time_s = (index + 1) / 20
                if abs(snap.timestamp.elapsed_seconds - initial - time_s) > .001:
                    raise RuntimeError('Native 20 Hz timestamp mismatch')
                pipeline.capture(frame, time_s)
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < frame:
                        image = q.get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(frame, time_s, camera_native_frames=camera_frames)
                pose, velocity = taxi.get_transform(), taxi.get_velocity()
                pp = passenger.get_transform()
                vertices = taxi.bounding_box.get_world_vertices(pose)
                civil = civil_start + timedelta(seconds=time_s)
                row = {'video_frame': index, 'native_frame': frame,
                       'time_s': time_s, 'source_kind': 'original_native',
                       'civil_time_local': civil.isoformat(timespec='milliseconds'),
                       'taxi_actor_id': taxi.id, 'taxi_blueprint_id': taxi.type_id,
                       'taxi_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
                       'taxi_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in vertices],
                       'taxi_yaw_deg': pose.rotation.yaw,
                       'taxi_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
                       'passenger_proxy_id': passenger.id,
                       'passenger_proxy_xyz_m': [pp.location.x, pp.location.y, pp.location.z],
                       'requested_purpose': config['requested_purpose'],
                       'requested_passenger_motion_active': activity and bool(direction),
                       'source_cameras': camera_frames,
                       'taxicab_identity_verified': False,
                       'passenger_waiting_verified': False,
                       'actual_sign_authority_verified': False,
                       'outside_hours_ordinary_rules_resolved': False}
                rows.write(json.dumps(row) + '\n')
                trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                    'position': {'x': pose.location.x, 'y': pose.location.y,
                                 'z': pose.location.z},
                    'position_m': row['taxi_xyz_m'], 'heading_deg': pose.rotation.yaw,
                    'velocity_mps': row['taxi_velocity_xyz_mps'],
                    'speed_mps': sum(v * v for v in row['taxi_velocity_xyz_mps']) ** .5,
                    'control': {'throttle': 0, 'brake': 1, 'hand_brake': True},
                    'source_kind': 'original_native'}) + '\n')
        for name, encoder in encoders.items():
            encoder.stdin.close()
            error = encoder.stderr.read()
            if encoder.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + error.decode()[-300:])
        complete = True
        return {'frames': 600, 'source_cameras': list(camera_queues),
                'taxi_sign_and_passenger_verified': False,
                'physical_completion_claimed': False}
    finally:
        finish_owned_capture(pipeline, encoders, owned, client, prior, changed,
                             complete, output, config, restore, seal_capture)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(offline_check(HERE), sort_keys=True))
    elif args.output_dir:
        config = json.loads((HERE / 'config.json').read_text())
        print(json.dumps(capture(config, args.output_dir, args.host, args.port),
                         sort_keys=True))
    else:
        parser.error('Supply --check or --output-dir')
