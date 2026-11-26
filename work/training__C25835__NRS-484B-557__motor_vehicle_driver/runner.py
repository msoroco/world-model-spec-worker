"""Original Native acquisition request for the C25835 grade crossing.

The prop and road readback are observations. Administrative designation,
official sign authority, physical completion and due care require later review.
"""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from rail_stop_controller import RailStopController, STOP_CENTER_DISTANCE_FT
from rail_stop_scene import scene_request, validate_request

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600
RATE_HZ = 20


def check(config):
    if (config['law_id'], config['cell_id'], config['actor']) != (
            'NRS-484B-557', 'C25835', 'motor_vehicle_driver'):
        raise ValueError('Exact rail assignment identity differs')
    suffix = config['case_id'].rsplit('__', 1)[-1]
    if suffix not in STOP_CENTER_DISTANCE_FT or config['requested_stop_center_ft'] != STOP_CENTER_DISTANCE_FT[suffix]:
        raise ValueError('Exact rail stop case target differs')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != 30:
        raise ValueError('600-frame original capture required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('Four source cameras required')
    request = scene_request(suffix)
    validate_request(request)
    return {'frames': FRAMES, 'requested_stop_center_ft': STOP_CENTER_DISTANCE_FT[suffix],
            'native_motion_verified': False, 'administrative_designation_verified': False}


def bounds(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not vertices:
        raise RuntimeError('Original vehicle extent missing')
    return {'front_x_m': max(point.x for point in vertices),
            'rear_x_m': min(point.x for point in vertices),
            'centre_x_m': actor.get_transform().location.x,
            'length_m': max(point.x for point in vertices) - min(point.x for point in vertices)}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'rail-trace.jsonl').exists():
        raise ValueError('Fresh materialized attempt required')
    suffix = config['case_id'].rsplit('__', 1)[-1]
    request = scene_request(suffix)
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    previous_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in previous_world.get_actors()):
        raise RuntimeError('Exclusive idle Native world required')
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(request['road_opendrive'],
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=25, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        mapping = world.get_map()
        survey = []
        for x in (-65, -25, -15, 0, 2):
            wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1.4),
                project_to_road=True, lane_type=carla.LaneType.Driving)
            if wp is None or abs(wp.transform.location.x - x) > 2:
                raise RuntimeError('Original crossing approach road survey failed')
            survey.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                           'waypoint_x_m': wp.transform.location.x})
        (output / 'road.xodr').write_text(mapping.to_opendrive())
        library = world.get_blueprint_library()
        cars = library.filter(request['vehicle']['blueprint'])
        if not cars:
            raise RuntimeError('Original motor vehicle blueprint unavailable')
        car_bp = cars[0]
        car_bp.set_attribute('role_name', 'c25835_subject')
        subject = world.spawn_actor(car_bp, carla.Transform(
            carla.Location(*request['vehicle']['start_xyz']), carla.Rotation(yaw=0)))
        if subject is None:
            raise RuntimeError('Original motor vehicle failed to spawn')
        owned.append(subject)
        capture = PipelineCapture(client, subject, output, config['case_id'],
            visibility=False, required_observations=config.get('required_atoms', []))
        def prop(spec, xyz, yaw):
            candidates = library.filter(spec)
            if not candidates:
                raise RuntimeError('Requested Native prop blueprint unavailable: ' + spec)
            actor = world.spawn_actor(candidates[0], carla.Transform(
                carla.Location(*xyz), carla.Rotation(yaw=yaw)))
            if actor is None:
                raise RuntimeError('Requested Native prop failed to spawn: ' + spec)
            owned.append(actor)
            return actor
        rails = [prop(request['rails']['blueprint'], [x, 0, .2], 90)
                 for x in (request['rails']['nearest_track_x_m'], request['rails']['far_track_x_m'])]
        sign = prop(request['stop_sign']['blueprint'], request['stop_sign']['xyz'],
                    request['stop_sign']['heading_deg'])
        occluder = prop(request['occluder']['blueprint'], request['occluder']['xyz'],
                        request['occluder']['heading_deg'])
        (output / 'rail-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C25835',
            'road_survey': survey, 'vehicle_actor_id': subject.id,
            'vehicle_blueprint_id': subject.type_id,
            'rail_actor_ids': [actor.id for actor in rails],
            'rail_blueprint_ids': [actor.type_id for actor in rails],
            'rail_track_x_m': [actor.get_transform().location.x for actor in rails],
            'sign_actor_id': sign.id, 'sign_blueprint_id': sign.type_id,
            'sign_pose': [sign.get_transform().location.x, sign.get_transform().location.y],
            'occluder_actor_id': occluder.id,
            'occluder_pose': [occluder.get_transform().location.x, occluder.get_transform().location.y],
            'designation_reviewed': False, 'official_sign_reviewed': False,
            'physical_crossing_status_reviewed': False}, indent=2) + '\n')
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'administrative_designation_reviewed': False,
            'official_sign_authority_reviewed': False,
            'legal_outcome_claimed': False}, indent=2) + '\n')
        mounts = {'overview': (-18, -13, 25, -50),
                  'approach': (-30, -11, 10, -20),
                  'reference_corner': (1, -12, 9, -30),
                  'driver_reference': (-5, 12, 9, -25)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            bp.set_attribute('fov', str(spec['fov_deg']))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            if camera is None:
                raise RuntimeError('Source camera failed to spawn: ' + name)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        controller = RailStopController(suffix, rails[0].get_transform().location.x,
                                        config['brake_gain'])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'rail-trace.jsonl').open('x') as trace, \
                (output / 'trace.jsonl').open('x') as motion:
            initial_time = None
            for index in range(FRAMES):
                tr, velocity = subject.get_transform(), subject.get_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                eye = tr.location + carla.Location(z=1.4)
                target = carla.Location(x=rails[0].get_transform().location.x,
                                        y=tr.location.y, z=1.4)
                hits = world.cast_ray(eye, target) if hasattr(world, 'cast_ray') else []
                visibility = 'clear' if not hits else 'occluded'
                command = controller.command(index, tr.location.x, speed, visibility)
                subject.apply_control(carla.VehicleControl(
                    throttle=command['throttle'], brake=command['brake'],
                    steer=command['steer']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native frame/snapshot mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s)
                camera_frames = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                pose, vel = subject.get_transform(), subject.get_velocity()
                extent = bounds(subject)
                row = {'native_frame': native_frame, 'video_frame': index,
                    'time_s': time_s, 'vehicle_actor_id': subject.id,
                    'vehicle_center_x_m': pose.location.x,
                    'vehicle_extent': extent,
                    'observed_speed_mps': math.hypot(vel.x, vel.y),
                    'rail_approach_visibility': visibility,
                    'train_state': 'none_observed',
                    'source_cameras': {name: index for name in CAMERAS},
                    'camera_native_frames': camera_frames,
                    'controller_request': command}
                trace.write(json.dumps(row) + '\n')
                motion.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position_m': [pose.location.x, pose.location.y, pose.location.z],
                    'speed_mps': row['observed_speed_mps']}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'native_frame_join': True,
                'original_sign_authority_verified': False,
                'legal_outcome_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=complete)
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
        restoration = restore(client, saved) if changed else {'restored': True, 'world_unchanged': True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
                         'designation_and_sign_authority': 'pending_independent_review'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path('config.json').read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        print(json.dumps(execute(config, args.output_dir, args.host, args.port)))
