"""Prospective Native taxi/light-express curb acquisition, without legal findings."""
import json
import queue
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from freight_plan import check_request

HERE = Path(__file__).resolve().parent


def offline_check(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    result = check_request(config, (root / 'yellow-freight-road.xodr').read_text())
    rows = [json.loads(line) for line in (root / 'requested-track.jsonl').read_text().splitlines()]
    if len(rows) != 600 or any(
            row.get('video_frame') != i or
            row.get('requested_purpose') != config['requested_purpose'] or
            row.get('source_kind') != 'authored_native_request' or
            row.get('requested_cargo_proxy') != config['cargo_blueprint_filter']
            for i, row in enumerate(rows)):
        raise ValueError('Full source-shaped light-express request missing')
    result['request_frames'] = 600
    return result


def capture(config, output_dir, host='127.0.0.1', port=2000):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check_request(config, (HERE / 'yellow-freight-road.xodr').read_text())
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'freight-native.jsonl').exists():
        raise ValueError('New empty original freight attempt required')
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
    first_error = None
    try:
        world = client.generate_opendrive_world((HERE / 'yellow-freight-road.xodr').read_text(),
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
        parking = road_map.get_waypoint(carla.Location(x=5.25, y=10, z=1),
            project_to_road=True, lane_type=carla.LaneType.Parking)
        if parking is None or parking.road_id != 1 or parking.lane_id != -2:
            raise RuntimeError('Freight yellow parking lane readback failed')
        (output / 'road.xodr').write_text(road_map.to_opendrive())
        (output / 'sign-authority-pending.json').write_text(json.dumps({
            'source_kind': 'original_native',
            'authored_sign_proposal': 'COMMERCIAL FREIGHT 09:00-17:00 PROPOSAL',
            'actual_sign_authority_source': None,
            'commercial_vehicle_classification_source': None,
            'actual_freight_purpose_source': None,
            'legal_verdict': None}, indent=2) + '\n')
        library = world.get_blueprint_library()
        vehicles = sorted(library.filter('vehicle.*'), key=lambda bp: bp.id)
        cargo_props = sorted(library.filter(config['cargo_blueprint_filter']), key=lambda bp: bp.id)
        if not vehicles or not cargo_props:
            raise RuntimeError('Taxi or cargo proxy blueprint unavailable')
        taxi_bp = vehicles[0]
        taxi_bp.set_attribute('role_name', 'c150173_taxi_commercial_identity_pending')
        taxi = world.spawn_actor(taxi_bp, carla.Transform(
            carla.Location(x=5.25, y=10, z=2), carla.Rotation(yaw=90)))
        cargo_bp = cargo_props[0]
        initial_x = 5.5 if config['requested_purpose'] == 'unloading_light_express' else 8.0
        cargo = world.spawn_actor(cargo_bp, carla.Transform(
            carla.Location(x=initial_x, y=10, z=2), carla.Rotation()))
        owned.extend((taxi, cargo))
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
            image_queue = queue.Queue()
            camera.listen(image_queue.put)
            camera_queues[spec['name']] = image_queue
            encoders[spec['name']] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', '20', '-i', '-',
                '-frames:v', '600', '-c:v', 'ffv1', '-level', '1',
                str(output / (spec['name'] + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        civil_start = datetime.fromisoformat(config['civil_start_local'])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'freight-native.jsonl').open('x') as rows, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(600):
                taxi.apply_control(carla.VehicleControl(
                    throttle=0, brake=1, hand_brake=True))
                transferring = 150 <= index < 300 and config['requested_purpose'] != 'waiting_without_transfer'
                if config['requested_purpose'] == 'loading_light_express':
                    cargo_x = 8.0 - 2.5 * min(max(index - 150, 0), 150) / 150
                elif config['requested_purpose'] == 'unloading_light_express':
                    cargo_x = 5.5 + 2.5 * min(max(index - 150, 0), 150) / 150
                else:
                    cargo_x = 8.0
                cargo.set_transform(carla.Transform(
                    carla.Location(x=cargo_x, y=10, z=2), carla.Rotation()))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError('Native frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds - .05
                time_s = (index + 1) / 20
                if abs(snap.timestamp.elapsed_seconds - initial_time - time_s) > .001:
                    raise RuntimeError('Native 20 Hz time mismatch')
                pipeline.capture(frame, time_s)
                camera_frames = {}
                for name, image_queue in camera_queues.items():
                    image = image_queue.get(timeout=30)
                    while image.frame < frame:
                        image = image_queue.get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Original camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(frame, time_s, camera_native_frames=camera_frames)
                taxi_pose, velocity = taxi.get_transform(), taxi.get_velocity()
                cargo_pose = cargo.get_transform()
                taxi_vertices = taxi.bounding_box.get_world_vertices(taxi_pose)
                cargo_vertices = cargo.bounding_box.get_world_vertices(cargo_pose)
                row = {'video_frame': index, 'native_frame': frame,
                       'time_s': time_s, 'source_kind': 'original_native',
                       'civil_time_local': (civil_start + timedelta(seconds=time_s)).isoformat(timespec='milliseconds'),
                       'taxi_actor_id': taxi.id, 'taxi_blueprint_id': taxi.type_id,
                       'taxi_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in taxi_vertices],
                       'taxi_velocity_xyz_mps': [velocity.x, velocity.y, velocity.z],
                       'cargo_actor_id': cargo.id, 'cargo_blueprint_id': cargo.type_id,
                       'cargo_body_vertices_xyz_m': [[v.x, v.y, v.z] for v in cargo_vertices],
                       'cargo_transfer_motion_observed': transferring,
                       'observed_purpose': config['requested_purpose'],
                       'source_cameras': camera_frames,
                       'commercial_status_verified': False,
                       'freight_purpose_verified': False,
                       'sign_authority_verified': False}
                rows.write(json.dumps(row) + '\n')
                trace.write(json.dumps({'frame': frame, 'time_s': time_s,
                    'position_m': [taxi_pose.location.x, taxi_pose.location.y, taxi_pose.location.z],
                    'heading_deg': taxi_pose.rotation.yaw,
                    'velocity_mps': row['taxi_velocity_xyz_mps'],
                    'speed_mps': sum(v * v for v in row['taxi_velocity_xyz_mps']) ** .5,
                    'source_kind': 'original_native'}) + '\n')
        for name, encoder in encoders.items():
            encoder.stdin.close()
            error = encoder.stderr.read()
            if encoder.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + ': ' + error.decode()[-300:])
        complete = True
        return {'frames': 600, 'source_cameras': list(camera_queues),
                'commercial_freight_or_legal_acceptance': False}
    except Exception as error:
        first_error = error
        raise
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=complete)
            except Exception as error:
                first_error = first_error or error
                complete = False
        for encoder in encoders.values():
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
        for actor in reversed(owned):
            try:
                actor.destroy()
            except Exception as error:
                first_error = first_error or error
                complete = False
        try:
            restored = restore(client, prior) if changed else {'restored': True}
        except Exception as error:
            first_error = first_error or error
            restored = {'restored': False}
            complete = False
        if complete and first_error is None:
            seal_capture(output, frames=600, restoration=restored, errors=[],
                encoder_exit_codes={name: encoder.returncode for name, encoder in encoders.items()},
                context={'case_id': config['case_id'],
                         'freight_classification_and_sign_authority': 'pending'})


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
        print(json.dumps(capture(config, args.output_dir, args.host, args.port), sort_keys=True))
    else:
        parser.error('Supply --check or --output-dir')
