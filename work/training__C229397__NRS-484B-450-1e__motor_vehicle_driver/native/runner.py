"""Crosswalk parking Native capture draft; --check is CARLA-free.

The requested branch state is a control input. Recorded geometry and source
context remain separate from any legal conclusion.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess

from geometry import check as geometry_check, open_drive, target_center

FRAMES = 600
CAMERAS = (
    ('overview', 1920, 1080, 0, -19, 25, -70),
    ('approach', 1280, 720, -25, -12, 8, -25),
    ('reference_corner', 1280, 720, 0, -14, 10, -45),
    ('driver_reference', 1280, 720, 8, -12, 7, -35),
)
PREFIX = 'training__C229397__NRS-484B-450-1e__motor_vehicle_driver__'
SUFFIXES = ('witness_1', 'witness_2', 'stop_1', 'stop_2', 'stand_1', 'stand_2',
            'exception_1_1', 'exception_1_2', 'exception_2_1', 'exception_2_2',
            'exception_3_1', 'exception_3_2', 'exception_4_1', 'exception_4_2')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(config='config.json'):
    config = Path(config)
    cfg = json.loads(config.read_text())
    source = json.loads((config.parent / 'assignment-source.json').read_text())
    plan = json.loads((config.parent / 'case-plan.json').read_text())
    if source['assignment_id'] != plan['assignment_id'] or source['law']['text'] != plan['source_law']['text']:
        raise ValueError('Exact source law differs')
    if source['law_sha256'] != plan['source_law']['sha256']:
        raise ValueError('Exact source law hash differs')
    if cfg['case_id'] not in {case['case_id'] for case in plan['cases']}:
        raise ValueError('Exact case absent from plan')
    suffix = cfg['case_id'].removeprefix(PREFIX)
    if cfg['case_id'] != PREFIX + suffix or suffix not in SUFFIXES:
        raise ValueError('Exact case identity differs')
    if cfg['cell_id'] != 'C229397' or cfg['law_id'] != 'NRS-484B-450-1e':
        raise ValueError('Frozen cell or law differs')
    if cfg['rate_hz'] != 20 or cfg['frames'] != FRAMES or cfg['duration_s'] != 30:
        raise ValueError('Capture policy differs')
    occupied = suffix not in ('witness_1', 'stop_1', 'stand_1')
    if cfg['authored_target_xy_m'] != list(target_center(occupied)):
        raise ValueError('Authored target differs from exact case')
    if suffix.startswith('exception_') and cfg['exception_context_source_required'] is not True:
        raise ValueError('Exception source context required')
    return {'passed': True, 'case_id': cfg['case_id'], 'geometry': geometry_check(),
            'native_imported': False, 'physical_acceptance_claimed': False}


def body_xy(actor):
    transform = actor.get_transform()
    points = {(round(v.x, 5), round(v.y, 5))
              for v in actor.bounding_box.get_world_vertices(transform)}
    if len(points) != 4:
        raise RuntimeError('Original Native body has no horizontal footprint')
    cx = sum(p[0] for p in points) / 4
    cy = sum(p[1] for p in points) / 4
    return [list(p) for p in sorted(points,
            key=lambda p: math.atan2(p[1] - cy, p[0] - cx))]


def load_context(path, case_id):
    path = Path(path)
    record = json.loads(path.read_text())
    if record.get('case_id') != case_id or record.get('source_kind') not in (
            'reviewed_authority_context', 'synthetic_cpu'):
        raise ValueError('Context case or provenance differs')
    if record.get('traffic_conflict') not in (True, False, None):
        raise ValueError('Invalid traffic conflict source')
    if record.get('law_compliance') not in (True, False, None):
        raise ValueError('Invalid other-law source')
    if record.get('officer_direction') not in (True, False, None):
        raise ValueError('Invalid officer direction source')
    if record.get('device_direction') not in (True, False, None):
        raise ValueError('Invalid device direction source')
    suffix = case_id.removeprefix(PREFIX)
    expected_activity = ('stop' if suffix.startswith('stop_') else
                         'stand' if suffix.startswith('stand_') else 'park')
    if record.get('activity') != expected_activity:
        raise ValueError('Cited stop/stand/park activity source differs')
    field = {'exception_1': 'traffic_conflict',
             'exception_2': 'law_compliance',
             'exception_3': 'officer_direction',
             'exception_4': 'device_direction'}
    if suffix.startswith('exception_'):
        branch = suffix.rsplit('_', 1)[0]
        requested = suffix.endswith('_2')
        if record[field[branch]] is not requested:
            raise ValueError('Cited exception source differs from selected comparison target')
        if any(record[other] not in (None, False) for other in field.values()
               if other != field[branch]):
            raise ValueError('Non-target exception source changes comparison')
    elif any(record[item] not in (None, False) for item in field.values()):
        raise ValueError('Baseline activity case has an asserted exception source')
    sources = record.get('sources', {})
    if record['source_kind'] == 'reviewed_authority_context':
        if not sources:
            raise ValueError('Reviewed exception context needs source hashes')
        for name, item in sources.items():
            if not isinstance(name, str) or not name or not isinstance(item, dict):
                raise ValueError('Reviewed exception context needs named source records')
            if not item.get('citation') or not item.get('sha256') or not item.get('path'):
                raise ValueError('Reviewed exception context needs source hashes')
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Reviewed source path must remain beside context')
            source_path = (path.parent / relative).resolve()
            if path.parent.resolve() not in source_path.parents or not source_path.is_file():
                raise ValueError('Reviewed source file missing')
            if sha(source_path) != item['sha256']:
                raise ValueError('Reviewed source hash differs')
    return record, sha(path)


def execute(config, output, host, port, context):
    import carla
    from shapely.geometry import MultiPoint
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import snapshot, restore

    cfg = json.loads(Path(config).read_text())
    check(config)
    context_record, context_sha = load_context(context, cfg['case_id'])
    if context_record['source_kind'] != 'reviewed_authority_context':
        raise ValueError('Original Native execution requires reviewed source context')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use a fresh original Native output directory')
    client = carla.Client(host, port)
    client.set_timeout(180)
    original_world = client.get_world()
    saved = snapshot(client)
    if original_world.get_settings().synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.', 'controller.'))
            for actor in original_world.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous Native world required')
    output.mkdir(parents=True)
    actors, encoders, cameras = [], {}, {}
    capture = None
    changed = False
    encoder_exits = {}
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        crosswalks = world.get_map().get_crosswalks()
        if not crosswalks:
            raise RuntimeError('Original Native map has no crosswalk readback')
        source_points = [(p.x, p.y) for p in crosswalks
                         if -5 <= p.x <= 5 and -13 <= p.y <= -7]
        source_hull = MultiPoint(source_points).convex_hull
        if len(source_points) < 4 or source_hull.geom_type != 'Polygon' or source_hull.area <= 0:
            raise RuntimeError('Original Native crosswalk geometry incomplete')
        waypoint = world.get_map().get_waypoint(carla.Location(x=1.75, y=-10, z=1),
                                                project_to_road=True,
                                                lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != 1:
            raise RuntimeError('Original Native crosswalk lane readback differs')
        blueprint = world.get_blueprint_library().find('vehicle.tesla.model3')
        vehicle = world.try_spawn_actor(blueprint, carla.Transform(
            carla.Location(x=1.75, y=-40, z=1.2), carla.Rotation(yaw=90)))
        if vehicle is None:
            raise RuntimeError('Original vehicle spawn failed')
        actors.append(vehicle)
        for name, width, height, x, y, z, pitch in CAMERAS:
            bp = world.get_blueprint_library().find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 85), ('sensor_tick', .05)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            actors.append(sensor)
            received = queue.Queue()
            sensor.listen(received.put)
            cameras[name] = received
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{width}x{height}',
                '-r', '20', '-i', '-', '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                str(output / (name + '.mkv'))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = PipelineCapture(client, vehicle, output, cfg['case_id'],
                                  required_observations=[])
        target_y = cfg['authored_target_xy_m'][1]
        with (output / 'actor-sources.jsonl').open('x') as motion, \
                (output / 'camera-frames.jsonl').open('x') as camera_rows, \
                FrameMap(output / 'video_frames.jsonl') as frame_map:
            for index in range(FRAMES):
                pre_y = vehicle.get_transform().location.y
                vehicle.set_target_velocity(carla.Vector3D(
                    x=0, y=4 if pre_y < target_y else 0, z=0))
                native = world.tick()
                transform = vehicle.get_transform()
                velocity = vehicle.get_velocity()
                row = {'case_id': cfg['case_id'], 'frame': index,
                       'native_frame': native, 'time_s': index / 20,
                       'ego_speed_mps': math.hypot(velocity.x, velocity.y),
                       'ego_footprint_xy_m': body_xy(vehicle),
                       'center_xy_m': [transform.location.x, transform.location.y],
                       'source_kind': 'original_native',
                       'context_sha256': context_sha}
                capture.capture(native, index / 20,
                                extra={'c229397_crosswalk': row})
                motion.write(json.dumps(row, allow_nan=False) + '\n')
                joined = {}
                for name, received in cameras.items():
                    image = received.get(timeout=30)
                    while image.frame < native:
                        image = received.get(timeout=30)
                    if image.frame != native:
                        raise RuntimeError('Original camera frame join differs')
                    encoders[name].stdin.write(image.raw_data)
                    joined[name] = image.frame
                    camera_rows.write(json.dumps({
                        'frame': index, 'native_frame': native, 'camera': name,
                        'rgb_sha256': hashlib.sha256(image.raw_data).hexdigest(),
                        'source_kind': 'original_native'}) + '\n')
                frame_map.append(native, index / 20, camera_native_frames=joined)
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            encoder_exits[name] = process.wait(timeout=180)
            if encoder_exits[name] or not (output / (name + '.mkv')).is_file():
                raise RuntimeError('Original camera encoding failed: ' + name + error.decode()[-300:])
        capture.close(confirmed=True)
        capture = None
        (output / 'road.xodr').write_text(open_drive())
        (output / 'crosswalk-source.json').write_text(json.dumps({
            'case_id': cfg['case_id'], 'crosswalk_source_kind': 'map_geometry',
            'crosswalk_polygon_xy_m': [list(p) for p in source_hull.exterior.coords[:-1]],
            'native_crosswalk_points_xy_m': [list(p) for p in source_points],
            'source_kind': 'original_native', 'context_sha256': context_sha,
            'law_scope_unverified': True}, sort_keys=True) + '\n')
        (output / 'exception-context.json').write_text(json.dumps({
            'case_id': cfg['case_id'], 'context': context_record,
            'source_sha256': context_sha,
            'legal_verdict': None}, sort_keys=True) + '\n')
        return {'frames': FRAMES, 'camera_names': list(cameras),
                'native_map_readback_observed': True,
                'physical_acceptance_claimed': False}
    finally:
        if capture is not None:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(actors):
            try:
                if hasattr(actor, 'stop'):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        if changed:
            restored = restore(client, saved)
            if capture is None and len(encoder_exits) == 4:
                seal_capture(output, frames=FRAMES, restoration=restored,
                             errors=[], encoder_exit_codes=encoder_exits,
                             context={'case_id': cfg['case_id']})
                record_native_exit(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--config', type=Path, default=Path('config.json'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--context', type=Path)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.config)))
    else:
        if args.output_dir is None or args.context is None:
            parser.error('Original capture needs output and source context')
        print(json.dumps(execute(args.config, args.output_dir, args.host,
                                 args.port, args.context)))
