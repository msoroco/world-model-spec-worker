"""CPU-only taxi loading draft entrypoint."""
import json
import queue
import subprocess
from pathlib import Path
from taxi_loading import check_config, read_and_measure


def offline_check(root):
    root = Path(root)
    result = check_config(json.loads((root/'config.json').read_text()),
                          (root/'taxi-road.xodr').read_text())
    result['request_measure'] = read_and_measure(root/'requested-track.jsonl',
                                                 'authored_native_request')
    return result


def capture(config, output_dir, host='127.0.0.1', port=2000):
    """Capture original pixels and motion; leave legal and participant review open."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    root = Path(__file__).resolve().parent
    check_config(config, (root / 'taxi-road.xodr').read_text())
    stop_x = config['taxi_stop_x_m']
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'native-rows.jsonl').exists():
        raise ValueError('New empty attempt directory required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    prior = snapshot(client)
    old_world = client.get_world()
    if prior['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in old_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, cameras = [], {}, {}
    pipeline = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(
            (root / 'taxi-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=10, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=True))
        changed = True
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        waypoint = world.get_map().get_waypoint(
            carla.Location(x=stop_x, y=10, z=1), project_to_road=True,
            lane_type=carla.LaneType.Parking)
        if waypoint is None or abs(waypoint.transform.location.y - 10) > 2:
            raise RuntimeError('Requested outside-stand parking location unavailable')
        library = world.get_blueprint_library()
        taxi_blueprints = sorted(library.filter('vehicle.*'), key=lambda item: item.id)
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda item: item.id)
        if not taxi_blueprints or not walkers:
            raise RuntimeError('Taxicab vehicle or participant blueprint unavailable')
        taxi_blueprint = taxi_blueprints[0]
        taxi_blueprint.set_attribute('role_name', 'c394327_taxi_subject_unverified')
        taxi = world.spawn_actor(taxi_blueprint, carla.Transform(
            carla.Location(x=stop_x, y=10, z=2), carla.Rotation(yaw=90)))
        owned.append(taxi)
        participant = world.spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=8.2, y=10, z=2), carla.Rotation(yaw=270)))
        owned.append(participant)
        pipeline = PipelineCapture(client, taxi, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        (output / 'authority-pending.json').write_text(json.dumps({
            'source_kind': 'original_native',
            'taxi_license_source': None,
            'taxi_stand_designation_authority_source': None,
            'other_stopping_regulations_source': None,
            'passenger_or_merchandise_identity_review': 'pending',
            'physical_completion': False,
            'legal_verdict': None}, indent=2) + '\n')
        for spec in config['cameras']:
            name = spec['name']
            blueprint = library.find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(spec['width']))
            blueprint.set_attribute('image_size_y', str(spec['height']))
            blueprint.set_attribute('sensor_tick', '.05')
            blueprint.set_attribute('fov', str(spec['fov_deg']))
            xyz = spec['location_xyz_m']
            pyr = spec['rotation_pyr_deg']
            sensor = world.spawn_actor(blueprint,
                carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                    carla.Rotation(pitch=pyr[0], yaw=pyr[2], roll=pyr[1])),
                attach_to=taxi if name == 'driver_reference' else None)
            owned.append(sensor)
            camera_queue = queue.Queue()
            sensor.listen(camera_queue.put)
            cameras[name] = camera_queue
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', '-',
                '-frames:v', '600', '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'native-rows.jsonl').open('x') as rows, \
                (output / 'trace.jsonl').open('x') as trace:
            first_time = None
            for index in range(600):
                active = 160 <= index < 400
                taxi.apply_control(carla.VehicleControl(
                    throttle=0, brake=1, hand_brake=True))
                if config['requested_activity'] == 'passenger_loading':
                    participant.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(x=-1 if active else 0, y=0, z=0),
                        speed=.5 if active else 0))
                else:
                    participant.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(x=0, y=0, z=0), speed=0))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if first_time is None:
                    first_time = snap.timestamp.elapsed_seconds - .05
                time_s = (index + 1) / 20
                if abs(snap.timestamp.elapsed_seconds - first_time - time_s) > .001:
                    raise RuntimeError('Native fixed-step timestamp differs')
                pipeline.capture(native_frame, time_s)
                camera_frames = {}
                for name, camera_queue in cameras.items():
                    image = camera_queue.get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queue.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s,
                    camera_native_frames=camera_frames)
                vehicle_pose = taxi.get_transform()
                walker_pose = participant.get_transform()
                velocity = taxi.get_velocity()
                row = {'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'taxi_actor_id': taxi.id,
                    'taxi_blueprint_id': taxi.type_id,
                    'taxi_xyz_m': [vehicle_pose.location.x, vehicle_pose.location.y,
                                   vehicle_pose.location.z],
                    'taxi_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
                    'participant_actor_id': participant.id,
                    'participant_xyz_m': [walker_pose.location.x,
                                          walker_pose.location.y, walker_pose.location.z],
                    'requested_activity': config['requested_activity'],
                    'requested_activity_active': active,
                    'observed_occupant_count': None,
                    'observed_door_open': None,
                    'observed_activity': None,
                    'source_cameras': camera_frames,
                    'taxi_identity_review': 'pending',
                    'stand_designation_review': 'pending',
                    'other_regulations_review': 'pending'}
                rows.write(json.dumps(row) + '\n')
                trace.write(json.dumps({
                    'frame': native_frame, 'time_s': time_s,
                    'position_m': row['taxi_xyz_m'],
                    'heading_deg': vehicle_pose.rotation.yaw,
                    'velocity_mps': row['taxi_velocity_xyz_mps'],
                    'speed_mps': sum(value * value for value in
                                     row['taxi_velocity_xyz_mps']) ** .5,
                    'control': {'brake': 1, 'hand_brake': True},
                    'source_kind': 'original_native',
                    'taxi_actor_id': taxi.id}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Camera encode failed: ' + name + ': ' + error.decode()[-300:])
        complete = True
        return {'frames': 600, 'cameras': list(cameras),
                'taxi_and_stand_authority_verified': False,
                'passenger_or_merchandise_activity_verified': False,
                'physical_completion_claimed': False}
    finally:
        if pipeline is not None:
            pipeline.close(confirmed=complete)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        restoration = restore(client, prior) if changed else {'restored': True,
            'world_unchanged': True}
        if complete:
            seal_capture(output, frames=600, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={'case_id': config['case_id'],
                         'candidate_id': config.get('candidate_id', 'primary'),
                         'taxi_identity_and_stand_review': 'pending'})
