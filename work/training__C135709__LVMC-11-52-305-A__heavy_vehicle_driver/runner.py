"""Original Native parking-frontage capture draft; no legal classification is inferred."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess

from controller import STATIONS_M, command
from geometry import check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check(config):
    geometry = geometry_check()
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C135709', 'LVMC-11-52-305-A', 'heavy_vehicle_driver'):
        raise ValueError('exact assignment identity changed')
    if config['parking_case'] not in STATIONS_M or config['case_id'].rsplit('__', 1)[-1] not in ('probe_1', 'probe_2'):
        raise ValueError('unknown exact parking case')
    if config['rate_hz'] != RATE or config['duration_s'] != 30:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original source cameras required')
    return {'geometry': geometry, 'frames': FRAMES, 'camera_names': CAMERAS,
            'native_imported': False, 'public_park_status_observed': False,
            'physical_acceptance_claimed': False}


def survey(carla, mapping):
    points = []
    for x in (-80, -30, 25, 40, 55):
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=1.4),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.x - x) > 1:
            raise RuntimeError('Native narrow-road lane survey failed')
        points.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'native_xyz_m': [wp.transform.location.x, wp.transform.location.y,
                                        wp.transform.location.z]})
    return points


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'vehicle-poses.jsonl').exists():
        raise ValueError('new materialized attempt required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
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
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        (output / 'frontage-inventory.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C135709',
            'native_lane_survey': readback,
            'street_bounds_m': geometry_check()['street_bounds_m'],
            'park_bounds_m': geometry_check()['park_bounds_m'],
            'public_park_status': None, 'park_status_document_sha256': None,
            'posted_permission_source': None, 'vehicle_specification_source': None,
            'external_status_review_required': True}, indent=2) + '\n')
        library = world.get_blueprint_library()
        bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        bp.set_attribute('role_name', 'c135709_heavy_vehicle_class_unverified')
        vehicle = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=-80, y=-1.75, z=2.0), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        capture = PipelineCapture(client, vehicle, output, config['case_id'],
                                  visibility=False, required_observations=config.get('required_atoms', []))
        (output / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'physical_acceptance_claimed': False}, indent=2) + '\n')
        mounts = {'overview': (15, -25, 24, -35), 'approach': (0, -11, 9, -15),
                  'reference_corner': (40, 8, 10, -20), 'driver_reference': (-45, 8, 10, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(cbp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'vehicle-poses.jsonl').open('x') as poses, \
                (output / 'trace.jsonl').open('x') as trace:
            initial_time = None
            for index in range(FRAMES):
                vt, vv = vehicle.get_transform(), vehicle.get_velocity()
                speed = math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z)
                request = command(config['parking_case'], index, vt.location.x, speed)
                vehicle.apply_control(carla.VehicleControl(
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
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                vt, vv = vehicle.get_transform(), vehicle.get_velocity()
                extent = vehicle.bounding_box.extent
                trace.write(json.dumps({'frame': native_frame, 'time_s': time_s,
                    'position': {'x': vt.location.x, 'y': vt.location.y, 'z': vt.location.z},
                    'position_m': [vt.location.x, vt.location.y, vt.location.z],
                    'heading_deg': vt.rotation.yaw,
                    'speed_mps': math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z)}) + '\n')
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'vehicle_id': vehicle.id,
                    'vehicle_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                    'vehicle_yaw_deg': vt.rotation.yaw,
                    'bbox_half_length_m': extent.x, 'bbox_half_width_m': extent.y,
                    'observed_speed_mps': math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z),
                    'requested_control': request, 'camera_native_frames': camera_frames,
                    'vehicle_class_verified': False, 'public_park_status_verified': False}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        complete = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'external_status_review_required': True, 'physical_acceptance_claimed': False}
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
                context={'case_id': config['case_id'],
                         'candidate_id': config.get('candidate_id', 'primary'),
                         'park_and_vehicle_external_review': 'pending'})


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
