"""Original Native controlled-entry acquisition; official authority remains for review."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive
from route import CROSSING_X, FRAMES, RATE_HZ, target

CAMERAS = ('overview', 'approach', 'indicated_gate', 'highway_side')


def check(config):
    geometry = geometry_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C228131', 'NRS-484B-587-1', 'motor_vehicle_driver'):
        raise ValueError('Exact controlled-entry assignment identity differs')
    if config['entry_mode'] not in CROSSING_X or config['case_id'].rsplit('__', 1)[-1] != config['entry_mode']:
        raise ValueError('Unknown exact entry case')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('600-frame original capture required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('Four source cameras required')
    if not 0 < config['steer_gain'] < 1:
        raise ValueError('Controller steering gain invalid')
    return {'geometry': geometry, 'frames': FRAMES, 'source_cameras': CAMERAS,
            'original_physical_or_legal_status_verified': False}


def footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if not vertices:
        raise RuntimeError('Original vehicle footprint missing')
    return {'min_x': min(p.x for p in vertices), 'max_x': max(p.x for p in vertices),
            'min_y': min(p.y for p in vertices), 'max_y': max(p.y for p in vertices)}


def control(config, frame, subject):
    request = target(config['entry_mode'], frame)
    transform, velocity = subject.get_transform(), subject.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    lateral_error = request['y_m'] - transform.location.y
    heading_target = math.degrees(math.atan2(
        request['y_m'] - transform.location.y,
        request['x_m'] - transform.location.x + 1))
    heading_error = ((heading_target - transform.rotation.yaw + 180) % 360) - 180
    steer = max(-.35, min(.35, config['steer_gain'] * lateral_error + .008 * heading_error))
    throttle = max(0, min(.4, .22 + .08 * (request['target_speed_mps'] - speed)))
    brake = .25 if speed > request['target_speed_mps'] + .6 else 0
    return {'throttle': throttle, 'brake': brake, 'steer': steer,
            'requested_x_m': request['x_m'], 'requested_y_m': request['y_m'],
            'requested_speed_mps': request['target_speed_mps']}


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'actor-poses.jsonl').exists():
        raise ValueError('Fresh materialized attempt required')
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
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
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
        for x, y in ((-20, -9), (0, -3.5), (20, 0), (60, -3.5)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1.4),
                                      project_to_road=True, lane_type=carla.LaneType.Driving)
            if wp is None:
                raise RuntimeError('Native access-point road survey failed')
            survey.append({'x_m': x, 'y_m': y, 'road_id': wp.road_id,
                           'lane_id': wp.lane_id,
                           'waypoint_distance_m': math.hypot(wp.transform.location.x-x,
                                                               wp.transform.location.y-y)})
        (output / 'road.xodr').write_text(mapping.to_opendrive())
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'official_access_authority_reviewed': False,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        library = world.get_blueprint_library()
        cars = library.filter('vehicle.tesla.model3')
        if not cars:
            raise RuntimeError('Ordinary motor-vehicle blueprint unavailable')
        bp = cars[0]
        bp.set_attribute('role_name', 'c228131_subject')
        first = target(config['entry_mode'], 0)
        subject = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=first['x_m'], y=first['y_m'], z=2), carla.Rotation(yaw=0)))
        owned.append(subject)
        capture = PipelineCapture(client, subject, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        signs = library.filter('static.prop.*sign*')
        if not signs:
            raise RuntimeError('Visible sign prop blueprint unavailable; original device cannot be represented')
        sign = world.spawn_actor(sign[0], carla.Transform(
            carla.Location(x=0, y=-5, z=1), carla.Rotation(yaw=0)))
        owned.append(sign)
        (output / 'access-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C228131',
            'subject_id': subject.id, 'subject_blueprint_id': subject.type_id,
            'device_actor_id': sign.id, 'device_blueprint_id': sign.type_id,
            'road_survey': survey, 'highway_road_id_candidate': 1,
            'frontage_road_id_candidate': 2, 'paved_entry_road_id_candidate': 3,
            'official_status_reviewed': False, 'lane_connectivity_reviewed': False}, indent=2) + '\n')
        mounts = {'overview': (30, -20, 38, -45), 'approach': (-15, -13, 10, -18),
                  'indicated_gate': (0, -12, 12, -30), 'highway_side': (35, 10, 22, -35)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            cbp.set_attribute('fov', str(spec['fov_deg']))
            camera = world.spawn_actor(cbp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
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
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'actor-poses.jsonl').open('x') as poses, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(FRAMES):
                request = control(config, index, subject)
                subject.apply_control(carla.VehicleControl(
                    throttle=request['throttle'], brake=request['brake'], steer=request['steer']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
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
                tr, velocity = subject.get_transform(), subject.get_velocity()
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': tr.location.x, 'y': tr.location.y, 'z': tr.location.z},
                    'position_m': [tr.location.x, tr.location.y, tr.location.z],
                    'speed_mps': math.hypot(velocity.x, velocity.y)}) + '\n')
                poses.write(json.dumps({'native_frame': native_frame, 'video_frame': index,
                    'time_s': time_s, 'vehicle_id': subject.id,
                    'center_xy_m': [tr.location.x, tr.location.y],
                    'footprint_half_width_m': (footprint(subject)['max_y']-footprint(subject)['min_y'])/2,
                    'footprint_half_length_m': (footprint(subject)['max_x']-footprint(subject)['min_x'])/2,
                    'footprint_m': footprint(subject), 'camera_native_frames': camera_frames,
                    'requested_control': request}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'official_device_authority_verified': False, 'legal_outcome_claimed': False}
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
                         'access_and_device_authority': 'pending_independent_review'})


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
