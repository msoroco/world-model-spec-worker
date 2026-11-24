"""Original Native at-grade pedestrian crossing acquisition draft; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive
from path import CROSSING_X_M, FRAMES, RATE_HZ, target

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CASES = {'probe_1': 'crosswalk', 'probe_2': 'outside'}


def check(config):
    if (config['cell_id'], config['law_id'], config['actor']) != ('C188094', 'LVMC-11-30-070-B', 'pedestrian'):
        raise ValueError('exact assignment identity changed')
    suffix = config['case_id'].rsplit('__', 1)[-1]
    if suffix not in CASES or config['crossing_case'] != CASES[suffix]:
        raise ValueError('unknown exact crossing case')
    if config['rate_hz'] != RATE_HZ or config['duration_s'] != FRAMES / RATE_HZ:
        raise ValueError('30-second 20-Hz recording required')
    if tuple(c['name'] for c in config['cameras']) != CAMERAS:
        raise ValueError('four original source cameras required')
    return {'geometry': geometry_check(), 'frames': FRAMES, 'camera_names': CAMERAS,
            'crossing_x_m': CROSSING_X_M[config['crossing_case']],
            'native_imported': False, 'business_district_sourced': False,
            'legal_outcome_claimed': False}


def survey(carla, mapping):
    rows = []
    for x in (0, 12, 30):
        for y in (-3, 3):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=0.5),
                                      project_to_road=True, lane_type=carla.LaneType.Driving)
            if wp is None or wp.road_id != 1 or abs(wp.transform.location.x - x) > 1:
                raise RuntimeError('Native at-grade road survey failed')
            rows.append({'x_m': x, 'y_m': y, 'road_id': wp.road_id, 'lane_id': wp.lane_id})
    return rows


def execute(config, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / 'actor-poses.jsonl').exists():
        raise ValueError('new materialized attempt required')
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior_world = client.get_world()
    if saved['settings'].synchronous_mode or any(a.type_id.startswith(
            ('vehicle.', 'walker.', 'sensor.', 'controller.')) for a in prior_world.get_actors()):
        raise RuntimeError('exclusive idle Native world required')
    owned, encoders, queues = [], {}, {}
    capture = None
    succeeded = False
    changed = False
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=25, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=True))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        readback = survey(carla, world.get_map())
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        library = world.get_blueprint_library()
        walkers = sorted(library.filter('walker.pedestrian.*'), key=lambda b: b.id)
        if not walkers:
            raise RuntimeError('Native pedestrian blueprint unavailable')
        walkers[0].set_attribute('role_name', 'c188094_subject')
        walker = world.spawn_actor(walkers[0], carla.Transform(
            carla.Location(x=CROSSING_X_M[config['crossing_case']], y=-6, z=0.5),
            carla.Rotation(yaw=90)))
        owned.append(walker)
        (output / 'crossing-survey.json').write_text(json.dumps({
            'source_kind': 'native_saved_sample', 'roadway_survey': readback,
            'crosswalk': geometry_check()['crosswalk_bounds_m'],
            'overpass_deck_height_m': 5, 'business_district_evidence': None,
            'unmarked_crosswalk_survey_complete': False,
            'pedestrian_blueprint_id': walker.type_id}, indent=2) + '\n')
        (output / 'crossing-context.json').write_text(json.dumps({
            'source_kind': 'native_pedestrian_crossing_and_district_readback',
            'native_map_sha256': hashlib.sha256((output / 'road.xodr').read_bytes()).hexdigest(),
            'crosswalk_survey_sha256': hashlib.sha256((output / 'crossing-survey.json').read_bytes()).hexdigest(),
            'business_district_evidence_sha256': None,
            'overpass_geometry_sha256': hashlib.sha256((output / 'road.xodr').read_bytes()).hexdigest(),
            'pedestrian_identity_sha256': hashlib.sha256(walker.type_id.encode()).hexdigest(),
            'business_district_review': 'unverified',
            'roadway_bounds_m': geometry_check()['roadway_bounds_m'],
            'crosswalks': [{'kind': 'marked', 'bounds_m': geometry_check()['crosswalk_bounds_m']}],
            'intersection_inventory': [],
            'complete_crosswalk_inventory': False}, indent=2) + '\n')
        mounts = {'overview': (3, -18, 18, -35), 'approach': (0, 0, 1.7, 0),
                  'reference_corner': (2, 10, 8, -25), 'driver_reference': (32, -12, 16, -30)}
        for name in CAMERAS:
            x, y, z, pitch = mounts[name]
            spec = next(c for c in config['cameras'] if c['name'] == name)
            cbp = library.find('sensor.camera.rgb')
            cbp.set_attribute('image_size_x', str(spec['width']))
            cbp.set_attribute('image_size_y', str(spec['height']))
            cbp.set_attribute('sensor_tick', str(1 / RATE_HZ))
            camera = world.spawn_actor(cbp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)),
                attach_to=walker if name == 'approach' else None)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            queues[name] = q
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                f"{spec['width']}x{spec['height']}", '-r', str(RATE_HZ), '-i', '-',
                '-frames:v', str(FRAMES), '-c:v', 'ffv1', '-level', '1',
                str(output / (name + '.mkv'))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        capture = PipelineCapture(client, walker, output, config['case_id'],
                                  visibility=False,
                                  required_observations=config.get('required_atoms', []))
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'actor-poses.jsonl').open('x') as poses:
            initial_time = None
            for index in range(FRAMES):
                request = target(config['crossing_case'], index)
                pose = walker.get_transform()
                x_error = request['x_m'] - pose.location.x
                direction = carla.Vector3D(x=max(-0.2, min(0.2, x_error)), y=1, z=0)
                walker.apply_control(carla.WalkerControl(
                    direction=direction, speed=request['target_speed_mps']))
                native_frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != native_frame:
                    raise RuntimeError('Native snapshot/frame mismatch')
                if initial_time is None:
                    initial_time = snap.timestamp.elapsed_seconds
                time_s = snap.timestamp.elapsed_seconds - initial_time
                capture.capture(native_frame, time_s,
                                extra={'crossing_request': request})
                camera_frames = {}
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('source camera/frame mismatch: ' + name)
                    encoders[name].stdin.write(image.raw_data)
                    camera_frames[name] = image.frame
                frame_map.append(native_frame, time_s, camera_native_frames=camera_frames)
                pose = walker.get_transform()
                poses.write(json.dumps({'video_frame': index, 'native_frame': native_frame,
                    'time_s': time_s, 'pedestrian_id': walker.id,
                    'pedestrian_x_m': pose.location.x, 'pedestrian_y_m': pose.location.y,
                    'pedestrian_z_m': pose.location.z, 'pedestrian_on_overpass_deck': pose.location.z > 3,
                    'requested_path': request, 'camera_native_frames': camera_frames}) + '\n')
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180) or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('source video encoding failed: ' + name + ': ' + stderr.decode()[-300:])
        capture.close(confirmed=True)
        succeeded = True
        return {'frames': FRAMES, 'source_cameras': list(CAMERAS),
                'business_district_sourced': False, 'legal_outcome_claimed': False}
    finally:
        if capture is not None and not capture.closed:
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
            restoration = restore(client, saved)
            if succeeded:
                seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                             encoder_exit_codes={name: process.returncode
                                                 for name, process in encoders.items()},
                             context={'business_district_sourced': False,
                                      'complete_crosswalk_inventory': False})


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
