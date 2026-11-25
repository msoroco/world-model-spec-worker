"""Survey-gated Native rack-parking capture; --check uses no CARLA."""
import argparse
import json
import math
import queue
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C229388__LVMC-11-40-170__cycle_or_scooter_operator'
CASE = AID + '__probe_01'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600


def config_check():
    cfg = json.loads((HERE/'config.json').read_text())
    if (cfg.get('assignment_id') != AID or cfg.get('case_id') != CASE or cfg.get('selected_case_id') != CASE or
            cfg.get('cell_id') != 'C229388' or cfg.get('law_id') != 'LVMC-11-40-170' or
            cfg.get('actor') != 'cycle_or_scooter_operator' or cfg.get('candidate_id') != 'primary' or
            cfg.get('rate_hz') != 20 or cfg.get('duration_s') != 30 or cfg.get('frames') != COUNT or
            [c.get('name') for c in cfg.get('cameras', [])] != list(CAMERAS) or
            [(c.get('width'), c.get('height')) for c in cfg['cameras']] !=
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)] or
            cfg.get('physical_acceptance_claimed') is not False or cfg.get('legal_verdict') is not None):
        raise ValueError('Exact rack-parking capture contract differs')
    return cfg


def survey_check(survey):
    for key in ('map_name', 'survey_source', 'rack_support_source', 'sidewalk_geometry_source',
                'pedestrian_corridor_source', 'device_subtype_source', 'device_blueprint',
                'operator_blueprint', 'rack_blueprint', 'device_spawn_xyz_m', 'obstructing_device_spawn_xyz_m', 'fallback_device_spawn_xyz_m', 'fallback_obstructing_device_spawn_xyz_m', 'device_spawn_yaw_deg',
                'operator_spawn_xyz_m', 'rack_spawn_xyz_m', 'rack_spawn_yaw_deg', 'camera_world_transforms'):
        if not survey.get(key) and survey.get(key) != 0:
            raise ValueError('Missing reviewed Native survey source: ' + key)
    if survey.get('device_subtype') not in ('bicycle', 'electric_bicycle', 'electric_scooter'):
        raise ValueError('Unsupported surveyed device subtype')
    if set(survey['camera_world_transforms']) != set(CAMERAS):
        raise ValueError('Four surveyed source cameras required')
    for key in ('device_spawn_xyz_m', 'obstructing_device_spawn_xyz_m', 'fallback_device_spawn_xyz_m', 'fallback_obstructing_device_spawn_xyz_m', 'operator_spawn_xyz_m', 'rack_spawn_xyz_m'):
        xyz = survey[key]
        if len(xyz) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in xyz):
            raise ValueError('Invalid surveyed transform: ' + key)
    for item in survey['camera_world_transforms'].values():
        if len(item.get('xyz_m', [])) != 3 or len(item.get('rotation_deg', [])) != 3:
            raise ValueError('Invalid surveyed camera transform')
    return survey


def transform(carla, xyz, yaw=0, rotation=None):
    rot = rotation or [0, yaw, 0]
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(pitch=rot[0], yaw=rot[1], roll=rot[2]))


def footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise RuntimeError('Native device bounding box unavailable')
    xs, ys = [v.x for v in vertices], [v.y for v in vertices]
    return [[min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)], [min(xs), max(ys)]]


def capture(survey, output, host, port):
    import carla
    cfg = config_check()
    survey_check(survey)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Retain prior Native source attempt; use an empty directory')
    client = carla.Client(host, port)
    client.set_timeout(120)
    world = client.get_world()
    if world.get_map().name != survey['map_name']:
        raise ValueError('Live CARLA map differs from reviewed survey')
    settings = world.get_settings()
    old_sync, old_step = settings.synchronous_mode, settings.fixed_delta_seconds
    actors, encoders = [], {}
    try:
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        lib = world.get_blueprint_library()
        def spawn(name, xyz, yaw=0):
            actor = world.try_spawn_actor(lib.find(name), transform(carla, xyz, yaw))
            if actor is None:
                raise RuntimeError('Surveyed actor spawn failed: ' + name)
            actors.append(actor)
            return actor
        rack = spawn(survey['rack_blueprint'], survey['rack_spawn_xyz_m'], survey['rack_spawn_yaw_deg'])
        device = spawn(survey['device_blueprint'], survey[cfg['spawn_key']], survey['device_spawn_yaw_deg'])
        operator = spawn(survey['operator_blueprint'], survey['operator_spawn_xyz_m'])
        queues = {}
        for spec in cfg['cameras']:
            camera = lib.find('sensor.camera.rgb')
            camera.set_attribute('image_size_x', str(spec['width']))
            camera.set_attribute('image_size_y', str(spec['height']))
            camera.set_attribute('fov', '80')
            loc = survey['camera_world_transforms'][spec['name']]
            sensor = world.spawn_actor(camera, transform(carla, loc['xyz_m'], rotation=loc['rotation_deg']))
            actors.append(sensor)
            q = queue.Queue()
            sensor.listen(q.put)
            queues[spec['name']] = q
            encoders[spec['name']] = subprocess.Popen(
                ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'bgra',
                 '-video_size', f"{spec['width']}x{spec['height']}", '-framerate', '20',
                 '-i', '-', '-frames:v', str(COUNT), '-c:v', 'ffv1',
                 str(output/(spec['name']+'.mkv'))], stdin=subprocess.PIPE)
        first_elapsed = None
        with (output/'video_frames.jsonl').open('w') as frame_file, (output/'native_parking_trace.jsonl').open('w') as trace_file:
            for i in range(COUNT):
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError('Native world frame mismatch')
                if first_elapsed is None:
                    first_elapsed = snapshot.timestamp.elapsed_seconds
                velocity = device.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                frame_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'time_s': snapshot.timestamp.elapsed_seconds-first_elapsed})+'\n')
                trace_file.write(json.dumps({'video_frame': i, 'native_frame': native_frame,
                                             'source_kind': 'original_native_pose',
                                             'device_actor_id': device.id, 'operator_actor_id': operator.id,
                                             'rack_actor_id': rack.id, 'device_speed_mps': speed,
                                             'device_footprint_xy_m': footprint(device)})+'\n')
                for name, q in queues.items():
                    image = q.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError('Camera frame does not join Native frame')
                    encoders[name].stdin.write(image.raw_data)
        for proc in encoders.values():
            proc.stdin.close()
            if proc.wait(timeout=120):
                raise RuntimeError('Source camera encoding failed')
        (output/'parking_context.template.json').write_text(json.dumps({
            'assignment_id': AID, 'review_kind': 'original_source_review',
            'device_subtype': survey['device_subtype'], 'device_actor_id': device.id,
            'operator_actor_id': operator.id, 'rack_actor_id': rack.id,
            'camera_sha256': {}, 'parking_context': {'source_kind': 'original_source_review'}, 'review_required': True}, indent=2)+'\n')
        return {'case_id': CASE, 'source_frames': COUNT, 'physical_acceptance_claimed': False}
    finally:
        for actor in reversed(actors):
            try:
                actor.destroy()
            except Exception:
                pass
        for proc in encoders.values():
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        settings.synchronous_mode = old_sync
        settings.fixed_delta_seconds = old_step
        world.apply_settings(settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--survey', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    cfg = config_check()
    if args.check:
        print(json.dumps({'case_id': CASE, 'frames': COUNT, 'cameras': list(CAMERAS),
                          'carla_imported': False, 'physical_acceptance_claimed': False}, sort_keys=True))
    else:
        if args.survey is None or args.output_dir is None:
            parser.error('Supply reviewed --survey and --output-dir')
        print(json.dumps(capture(json.loads(args.survey.read_text()), args.output_dir, args.host, args.port)))
