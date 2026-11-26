"""Original Native C129273 capture draft; marker appearance needs independent review."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive

FRAMES = 600
RATE = 20
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SUFFIXES = ('probe_1', 'probe_2', 'white_wholly', 'white_partial',
            'assisted', 'early_release')


def check(config):
    geometry = geometry_check()
    if config['case_id'].rsplit('__', 1)[-1] not in SUFFIXES:
        raise ValueError('unknown selected case')
    request = config.get('source_context_request', {})
    if request.get('cane_or_assistance') not in (
            'white_red_tipped_cane', 'white_cane', 'assisted_person') or \
            request.get('blindness_extent') not in ('wholly', 'partially') or \
            request.get('driver_behavior') not in ('stop_clear', 'no_stop', 'early_release'):
        raise ValueError('source-specific person and driver request absent')
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C129273', 'LVMC-11-30-140-B', 'motor_vehicle_driver'):
        raise ValueError('source identity changed')
    if config['rate_hz'] != RATE or config['duration_s'] != 30:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four source cameras required')
    return {'geometry': geometry, 'camera_names': CAMERAS, 'frames': FRAMES,
            'native_imported': False, 'physical_acceptance_claimed': False}


def survey(carla, mapping):
    points = []
    for x in (-80, -40, 0, 40, 80):
        z = 25 + .025 * (x + 120) + .5
        wp = mapping.get_waypoint(carla.Location(x=x, y=-1.75, z=z),
                                  project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or wp.road_id != 1 or wp.lane_id != -1 or abs(wp.transform.location.x - x) > 1:
            raise RuntimeError('Native mountain-road lane survey failed')
        points.append({'x_m': x, 'road_id': wp.road_id, 'lane_id': wp.lane_id,
                       'native_xyz_m': [wp.transform.location.x, wp.transform.location.y,
                                        wp.transform.location.z]})
    return points


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'vehicle-person-poses.jsonl').exists():
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
    encoder_exits = {}
    changed = False
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
        (output / 'road-survey.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'cell_id': 'C129273',
            'lane_survey': readback, 'marker_appearance_verified': False}, indent=2) + '\n')
        (output / 'blind-person-context.json').write_text(json.dumps({
            'source_kind': 'original_native',
            'request': config['source_context_request'],
            'blind_person_source_context': config['source_context_request'],
            'blindness_independently_verified': False,
            'cane_or_assistance_independently_verified': False,
            'legal_verdict_claimed': False}, indent=2) + '\n')
        library = world.get_blueprint_library()
        vehicle_bp = sorted(library.filter('vehicle.*'), key=lambda b: b.id)[0]
        vehicle_bp.set_attribute('role_name', 'c129273_subject_driver')
        vehicle = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-80, y=-1.75, z=26.5), carla.Rotation(yaw=0)))
        owned.append(vehicle)
        walker_bp = sorted(library.filter('walker.pedestrian.*'), key=lambda b: b.id)[0]
        walker = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=0, y=-4.6, z=28.1), carla.Rotation(yaw=90)))
        owned.append(walker)
        helper = None
        if config['source_context_request']['cane_or_assistance'] == 'assisted_person':
            helper_bp = sorted(library.filter('walker.pedestrian.*'), key=lambda b: b.id)[-1]
            helper = world.spawn_actor(helper_bp, carla.Transform(
                carla.Location(x=-1.2, y=-4.6, z=28.1), carla.Rotation(yaw=90)))
            owned.append(helper)
        else:
            # Engine debug strokes are an authored marker request, never proof of
            # actual cane pixels, blindness, or legal marker identity.
            position = walker.get_transform().location
            marker = config['source_context_request']['cane_or_assistance']
            world.debug.draw_line(carla.Location(x=position.x, y=position.y, z=position.z + .8),
                                  carla.Location(x=position.x + .35, y=position.y, z=position.z),
                                  thickness=.08, color=carla.Color(255, 255, 255), life_time=31)
            if marker == 'white_red_tipped_cane':
                world.debug.draw_line(carla.Location(x=position.x + .28, y=position.y,
                                                     z=position.z + .15),
                                      carla.Location(x=position.x + .35, y=position.y,
                                                     z=position.z),
                                      thickness=.09, color=carla.Color(255, 0, 0), life_time=31)
        mounts = {'overview': (-12, -24, 40, -35), 'approach': (-34, -12, 32, -15),
                  'reference_corner': (3, -11, 31, -15),
                  'driver_reference': (-7, 8, 33, -20)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            bp = library.find('sensor.camera.rgb')
            bp.set_attribute('image_size_x', str(spec['width']))
            bp.set_attribute('image_size_y', str(spec['height']))
            bp.set_attribute('sensor_tick', str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
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
        capture = PipelineCapture(client, vehicle, output, config['case_id'],
                                  required_observations=[])
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'vehicle-person-poses.jsonl').open('x') as poses, \
                (output / 'camera-frames.jsonl').open('x') as image_rows:
            initial_time = None
            for index in range(FRAMES):
                # Controller targets are engineering requests; observed motion is saved below.
                behavior = config['source_context_request']['driver_behavior']
                stopping_case = behavior != 'no_stop'
                x = vehicle.get_transform().location.x
                brake = 1.0 if stopping_case and x > -15 and not (
                    behavior == 'early_release' and index >= 220) else 0.0
                throttle = 0.0 if brake else .25
                vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake))
                if index >= 100 and index < 360:
                    walker.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(0, 1, 0), speed=.5))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                images = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    images[name] = image.frame
                    image_rows.write(json.dumps({'frame': index, 'camera': name,
                        'native_frame': native_frame,
                        'rgb_sha256': hashlib.sha256(image.raw_data).hexdigest()}) + '\n')
                frame_map.append(native_frame, time_s, camera_native_frames=images)
                vt, vv, wt = vehicle.get_transform(), vehicle.get_velocity(), walker.get_transform()
                extent = vehicle.bounding_box.extent
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'vehicle_id': vehicle.id, 'person_id': walker.id,
                    'assistant_id': helper.id if helper is not None else None,
                    'vehicle_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                    'person_xyz_m': [wt.location.x, wt.location.y, wt.location.z],
                    'vehicle_yaw_deg': vt.rotation.yaw,
                    'bbox_half_length_m': extent.x, 'bbox_half_width_m': extent.y,
                    'speed_mps': math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z),
                    'requested_throttle': throttle, 'requested_brake': brake,
                    'marker_appearance_verified': False,
                    'value': {'vehicle_xyz_m': [vt.location.x, vt.location.y, vt.location.z],
                              'person_xyz_m': [wt.location.x, wt.location.y, wt.location.z],
                              'speed_mps': math.sqrt(vv.x * vv.x + vv.y * vv.y + vv.z * vv.z)}}) + '\n')
                capture.capture(native_frame, time_s, extra={'c129273_blind_person': {
                    'vehicle_id': vehicle.id, 'person_id': walker.id,
                    'camera_native_frames': images}})
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'marker_appearance_verified': False, 'physical_acceptance_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
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
        if changed:
            restored = restore(client, saved)
            if capture is None and len(encoder_exits) == len(CAMERAS):
                seal_capture(output, frames=FRAMES, restoration=restored, errors=[],
                             encoder_exit_codes=encoder_exits,
                             context={'case_id': config['case_id']})
                record_native_exit(output)


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
