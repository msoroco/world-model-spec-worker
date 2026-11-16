"""Exact red-curb Native entrypoint; static check does not import CARLA."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = (
    ('overview', 1920, 1080, 85, (-6, -5, 35), -70),
    ('approach', 1280, 720, 90, (4, 0, 2.1), -5),
    ('reference_corner', 1280, 720, 90, (1, -1.4, 1.8), -12),
    ('driver_reference', 1280, 720, 90, (.2, -.35, 1.6), -4),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    cfg = json.loads((ROOT / 'config.json').read_text())
    tracks = (ROOT / 'requested-tracks.jsonl').read_text().splitlines()
    marks = ET.parse(ROOT / 'red-curb-road.xodr').findall(
        './/laneSection/right/lane[@id="-2"]/roadMark')
    if cfg['road_sha256'] != sha(ROOT / 'red-curb-road.xodr') or \
       cfg['controller_sha256'] != sha(ROOT / 'parking_controller.py') or \
       cfg['tracks_sha256'] != sha(ROOT / 'requested-tracks.jsonl') or \
       cfg['assignment_sha256'] != sha(ROOT / 'assignment-source.json') or \
       cfg['case_plan_sha256'] != sha(ROOT / 'case-plan.json'):
        raise ValueError('Selected red-curb sources changed')
    if [(float(m.attrib['sOffset']), m.attrib['color']) for m in marks] != \
       [(0, 'white'), (30, 'red'), (50, 'white')]:
        raise ValueError('Red-painted curb construction changed')
    if cfg['selected_case_id'] != cfg['case_id'] or cfg['candidate_id'] != 'primary' or \
       cfg['rate_hz'] != 20 or cfg['duration_s'] != 12 or len(tracks) != 240 or \
       [c['name'] for c in cfg['cameras']] != list(VIEWS):
        raise ValueError('Selected case or four-view capture contract changed')
    for i, line in enumerate(tracks):
        row = json.loads(line)
        if row['frame'] != i or row['source_kind'] != 'authored_controller_request' or \
           row['observed_native_motion'] is not False:
            raise ValueError('Requested tracks cannot be Native evidence')
    return {'case_id': cfg['case_id'], 'candidate_id': 'primary',
            'frames': 240, 'source_bound': True, 'original_native_observed': False}


def repository():
    for parent in ROOT.parents:
        if (parent / 'batch.json').is_file() and (parent / 'runtime').is_dir():
            return parent
    raise ValueError('Pinned runtime repository unavailable')


def native_pose(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    return {'actor_id': actor.id, 'blueprint': actor.type_id,
            'ego_center_native_xy_m': [transform.location.x, transform.location.y],
            'ego_body_native_xy_m': [[v.x, v.y] for v in vertices],
            'velocity_native_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'yaw_deg': transform.rotation.yaw}


def execute(output, host, port):
    """Capture original Native rows and four encoded source views on an owned server."""
    checked = check()
    cfg = json.loads((ROOT / 'config.json').read_text())
    requests = [json.loads(s) for s in
                (ROOT / 'requested-tracks.jsonl').read_text().splitlines()]
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any((output/name).exists() for name in
           ('native-raw-actors.jsonl','video_frames.jsonl',
            'native-capture-report.json','capture/evidence.jsonl')):
        raise ValueError('Retain prior attempt; choose a new capture directory')
    repo = repository()
    sys.path.insert(0, str(repo / 'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0, str(repo / 'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    from worker_exchange.native_output import seal_capture
    import parking_controller

    client = carla.Client(host, port)
    client.set_timeout(180)
    old = client.get_world()
    saved = snapshot(client)
    if old.get_settings().synchronous_mode or any(
            a.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for a in old.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    target_config = output / 'config.json'
    if target_config.exists():
        if target_config.read_bytes() != (ROOT/'config.json').read_bytes():
            raise ValueError('Materialized capture config differs')
    else:
        target_config.write_bytes((ROOT/'config.json').read_bytes())
    owned, encoders, encoder_logs, image_queues = [], {}, {}, {}
    pipeline = None
    changed = False
    frames = 0
    errors = []
    events = []
    restored = None
    codes = {}
    try:
        world = client.generate_opendrive_world(
            (ROOT / 'red-curb-road.xodr').read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        waypoint = mapping.get_waypoint(carla.Location(x=40, y=-6.8, z=1),
            project_to_road=False, lane_type=carla.LaneType.Parking)
        if waypoint is None or waypoint.road_id != 150142 or waypoint.lane_id != -2:
            raise RuntimeError('Native parking lane readback differs from authored road')
        native_odr = mapping.to_opendrive()
        native_root = ET.fromstring(native_odr)
        marks = native_root.findall(
            './/road[@id="150142"]/lanes/laneSection/right/lane[@id="-2"]/roadMark')
        mark_readback = [(float(mark.attrib['sOffset']),mark.attrib.get('color'))
                         for mark in marks]
        if mark_readback != [(0,'white'),(30,'red'),(50,'white')]:
            raise RuntimeError('Native OpenDRIVE red-paint readback differs')
        (output / 'native-map-readback.json').write_text(json.dumps({
            'source_kind': 'native_readback', 'road_sha256': sha(ROOT/'red-curb-road.xodr'),
            'native_map_sha256': hashlib.sha256(native_odr.encode()).hexdigest(),
            'road_id': waypoint.road_id, 'parking_lane_id': waypoint.lane_id,
            'road_mark_readback': mark_readback,
            'red_curb_start_x_m': 30, 'red_curb_end_x_m': 50,
            'curb_y_m': -7, 'paint_color': 'red', 'legal_verdict': None},
            indent=2) + '\n')
        library = world.get_blueprint_library()
        vehicle_bp = library.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'c150142_ego')
        ego = world.try_spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=5, y=-6.8, z=1.5), carla.Rotation(yaw=0)))
        if ego is None:
            raise RuntimeError('Red-curb ego spawn failed')
        owned.append(ego)
        for name, width, height, fov, location, pitch in CAMERAS:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(*location), carla.Rotation(pitch=pitch)),
                attach_to=ego)
            owned.append(sensor)
            image_queues[name] = queue.Queue()
            encoder_logs[name] = (output/(name+'.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
                '-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}',
                '-r','20','-i','pipe:0','-an','-c:v','ffv1','-level','1',
                str(output/(name+'.mkv'))], stdin=subprocess.PIPE,
                stderr=encoder_logs[name])
            sensor.listen(image_queues[name].put)
        pipeline = PipelineCapture(client, ego, output, cfg['case_id'],
            visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-actors.jsonl').open('x') as rows, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i, request in enumerate(requests):
                decision = parking_controller.apply(ego, carla,
                    cfg['requested_target_x_m'], request['requested_ego_y_m'])
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                native = native_pose(ego)
                row = {'frame': i, 'native_frame': frame, 'time_s': time_s,
                       'source_kind': 'original_native', **native,
                       'requested_ego_x_m': request['requested_ego_x_m'],
                       'requested_ego_y_m': request['requested_ego_y_m'],
                       'controller_phase': decision['phase'],
                       'legal_verdict': None}
                pipeline.capture(frame, time_s, extra={'c150142_red_curb': row})
                rows.write(json.dumps(row, allow_nan=False)+'\n')
                for name, width, height, *_ in CAMERAS:
                    image = image_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = image_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Four-view Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({
                    'video_frame': i, 'native_frame': frame,
                    'carla_frame': frame, 'time_s': time_s,
                    'views': list(VIEWS)}, allow_nan=False)+'\n')
                frames += 1
        events.append('capture_finished')
    except BaseException as exc:
        errors.append({'type': type(exc).__name__, 'message': str(exc),
                       'traceback': traceback.format_exc()})
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=not errors and frames == 240)
            except BaseException as exc:
                errors.append({'pipeline_close_error': str(exc)})
        for name, process in encoders.items():
            try:
                process.stdin.close()
                codes[name] = process.wait(timeout=180)
                if codes[name] != 0:
                    errors.append({'encoder_error': name})
            except BaseException as exc:
                errors.append({'encoder_close_error': name, 'message': str(exc)})
            encoder_logs[name].close()
        if events == ['capture_finished'] and not errors:
            events.append('encoders_closed')
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                errors.append({'cleanup_error': str(exc)})
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                errors.append({'restore_error': str(exc)})
        if events == ['capture_finished','encoders_closed'] and not errors and \
           isinstance(restored, dict) and restored.get('restored') is True:
            events.append('restoration_verified')
        (output/'native-capture-report.json').write_text(json.dumps({
            'case_id': checked['case_id'], 'candidate_id': 'primary',
            'config_sha256': sha(ROOT/'config.json'),
            'requested_frames': 240, 'observed_frames': frames,
            'lifecycle_events': events, 'restoration': restored,
            'closure_failures': errors, 'error': errors[0] if errors else None,
            'accepted': False, 'legal_verdict': None}, indent=2)+'\n')
        if not errors and frames == 240 and events[-1:] == ['restoration_verified']:
            seal_capture(output, frames=frames, restoration=restored, errors=[],
                encoder_exit_codes=codes, context={'case_id':checked['case_id'],
                'candidate_id':'primary', 'legal_verdict':None})
    if errors or frames != 240:
        raise RuntimeError('Red-curb Native capture failed; inspect report')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    result = check()
    if args.check:
        print(json.dumps(result, sort_keys=True))
    else:
        if args.output_dir is None or args.host is None or args.port is None:
            parser.error('Native capture requires --output-dir, --host and --port')
        execute(args.output_dir, args.host, args.port)
