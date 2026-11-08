"""Exact CPU bundle check and source-preserving, unaccepted Native capture."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle/'config.json').read_text())
    assignment = json.loads((bundle/'assignment-source.json').read_text())
    plan = json.loads((bundle/'case-plan.json').read_text())
    if (config['format'] != 'c150916-native-request-v1' or
            assignment['assignment_id'] != config['assignment_id'] or
            plan['assignment_id'] != config['assignment_id'] or
            config['assignment_sha256'] != sha(bundle/'assignment-source.json') or
            config['case_plan_sha256'] != sha(bundle/'case-plan.json') or
            config['road_sha256'] != sha(bundle/'road.xodr') or
            config['tracks_sha256'] != sha(bundle/'requested-tracks.jsonl') or
            config['status'] != 'unselected_native_request'):
        raise ValueError('Exact one-way bundle source binding differs')
    case = config['requested_direction']
    candidate = config['candidate_id']
    if (case not in ('designated','opposite') or
            candidate not in ('primary','fallback1','fallback2','fallback3') or
            config['case_id'] != config['assignment_id']+'__'+case or
            config['case_id'] not in {row['case_id'] for row in plan['cases']}):
        raise ValueError('One-way case or candidate differs')
    road = ET.parse(bundle/'road.xodr').getroot()
    lanes = {int(l.attrib['id']): l.attrib['type'] for l in road.findall('.//lane')}
    signs = {int(s.attrib['id']): s for s in road.findall('.//signal')}
    if lanes != {-2:'driving',-1:'driving',0:'none'} or set(signs) != {101,102} or any(
            s.attrib['type'] != 'R6-1' or s.attrib['orientation'] != '+' for s in signs.values()):
        raise ValueError('One-way road or sign request differs')
    rows = [json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(rows) != 240 or config['rate_hz'] != 20 or config['frames'] != 240:
        raise ValueError('One-way requested frame count differs')
    direction = 1 if case == 'designated' else -1
    start = -20 if case == 'designated' else 220
    lane = -2 if candidate == 'fallback2' else -1
    speed = 4 if candidate == 'fallback1' else 3 if candidate == 'fallback3' else 8
    for i, row in enumerate(rows):
        t = (i+1)/20
        displacement = min(12,speed*t) if candidate == 'fallback3' else speed*t
        if (row['frame'] != i or abs(row['time_s']-t) > 1e-6 or
                abs(row['ego_x_m']-(start+direction*displacement)) > 1e-4 or
                row['ego_y_m'] != (-5.25 if lane == -2 else -1.75) or
                row['ego_heading_deg'] != (0 if direction == 1 else 180) or
                row['lane_id'] != lane or row['requested_direction'] != case):
            raise ValueError('One-way request trajectory differs')
    return {'format':'c150916-copied-runner-cpu-check-v1',
            'case_id':config['case_id'],'candidate_id':candidate,
            'requested_frames':len(rows),'road_sign_requests':sorted(signs),
            'carla_imported':False,'physical_sign_verified':False,
            'designation_authority_verified':False,'delivery_ready':False}


def repository():
    here = Path(__file__).resolve().parent
    for parent in (here, *here.parents):
        if (parent/'batch.json').is_file() and (parent/'runtime').is_dir():
            return parent
    override = os.environ.get('SCENARIO_REPO_ROOT')
    if override and (Path(override)/'runtime').is_dir():
        return Path(override).resolve()
    raise ValueError('Pinned runtime repository unavailable')


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pose_record(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(pose)
    return {'actor_id': actor.id, 'blueprint': actor.type_id,
            'center_native_xyz_m': [pose.location.x, pose.location.y, pose.location.z],
            'yaw_deg': pose.rotation.yaw,
            'velocity_native_xyz_mps': [velocity.x, velocity.y, velocity.z],
            'speed_mps': math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),
            'body_native_xyz_m': [[vertex.x, vertex.y, vertex.z] for vertex in vertices]}


def execute(bundle, output, host, port):
    checked = check(bundle)
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Native output must be a fresh directory')
    root = repository()
    sys.path.insert(0, str(root/'runtime/pipeline/scenario_pipeline'))
    sys.path.insert(0, str(root/'runtime/pipeline/python'))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore
    requests = [json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    config = json.loads((bundle/'config.json').read_text())
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    previous = client.get_world()
    if saved['settings'].synchronous_mode or any(
            actor.type_id.startswith(('vehicle.', 'walker.', 'sensor.'))
            for actor in previous.get_actors()):
        raise RuntimeError('Exclusive idle asynchronous CARLA world required')
    output.mkdir(parents=True)
    owned, encoders, logs, camera_queues = [], {}, {}, {}
    capture, changed, frames, restored, error = None, False, 0, None, None
    try:
        world = client.generate_opendrive_world((bundle/'road.xodr').read_text(),
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
        # Read topology from the generated world. The authored sign ids remain
        # requests until an independent physical camera review identifies them.
        lane_readback = {}
        for lane_id, y in ((-1, -1.75), (-2, -5.25)):
            waypoint = mapping.get_waypoint(carla.Location(x=40, y=-y, z=1),
                project_to_road=False, lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.road_id != 1 or waypoint.lane_id != lane_id:
                raise RuntimeError('Native one-way driving lane readback differs')
            lane_readback[str(lane_id)] = waypoint.lane_id
        write_new(output/'native-map-readback.json', {
            'road_sha256': sha(bundle/'road.xodr'),
            'native_map_sha256': hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            'driving_lane_ids': lane_readback,
            'authored_sign_request_ids': [101, 102],
            'physical_sign_verified': False, 'designation_authority_verified': False})
        library = world.get_blueprint_library()
        blueprint = library.find('vehicle.tesla.model3')
        blueprint.set_attribute('role_name', 'c150916_ego')
        first = requests[0]
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=first['ego_x_m'], y=-first['ego_y_m'], z=2),
            carla.Rotation(yaw=first['ego_heading_deg'])))
        owned.append(ego)
        for _ in range(40):
            world.tick()
        cameras = (('forward', 1280, 720, carla.Transform(
                        carla.Location(x=1.0, y=0, z=1.4))),
                   ('overview', 1280, 720, carla.Transform(
                        carla.Location(x=100, y=25, z=45),
                        carla.Rotation(pitch=-50))))
        for name, width, height, transform in cameras:
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', 90), ('sensor_tick', 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, transform,
                attach_to=ego if name == 'forward' else None)
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            logs[name] = (output/(name+'.encoder.log')).open('x')
            encoders[name] = subprocess.Popen([
                'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '1',
                str(output/(name+'.mkv'))], stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(camera_queues[name].put)
        capture = PipelineCapture(client, ego, output, config['case_id'],
                                  visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output/'native-raw-ego.jsonl').open('x') as observed, \
             (output/'video_frames.jsonl').open('x') as frame_map:
            for i, request in enumerate(requests):
                # Apply the authored track as a requested target velocity; the
                # measured pose and velocity below are kept as original values.
                direction = 1 if config['requested_direction'] == 'designated' else -1
                ego.set_target_velocity(carla.Vector3D(
                    x=direction*request['ego_speed_mps'], y=0, z=0))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds-start
                row = {'frame': i, 'native_frame': frame, 'time_s': time_s,
                       'source_kind': 'original_native', 'ego': pose_record(ego),
                       'physical_sign_review': 'pending',
                       'designation_authority_review': 'pending',
                       'legal_verdict': None}
                capture.capture(frame, time_s, extra={'c150916_one_way': row})
                observed.write(json.dumps(row, allow_nan=False)+'\n')
                for name, width, height, _ in cameras:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError('Camera and Native frame join differs')
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({'video_frame': i, 'native_frame': frame,
                                             'time_s': time_s}, allow_nan=False)+'\n')
                frames += 1
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc),
                 'traceback': traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {'capture_close_error': str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError('Lossless encoder failed: '+name)
            except BaseException as exc:
                error = error or {'encoder_error': str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith('sensor.') and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {'cleanup_error': str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {'restore_error': str(exc)}
        write_new(output/'native-capture-report.json', {
            'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'bundle_config_sha256': sha(bundle/'config.json'),
            'requested_frames': 240, 'observed_frames': frames,
            'restoration': restored, 'error': error, 'accepted': False,
            'physical_sign_reviewed': False,
            'designation_authority_reviewed': False,
            'legal_outcome_claimed': False})
    if error:
        raise RuntimeError('Native attempt failed; see native-capture-report.json')
    return {'output': str(output), 'observed_frames': frames, 'accepted': False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check',action='store_true')
    action.add_argument('--run',action='store_true')
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=2000)
    args=parser.parse_args()
    if args.run and args.output is None:
        parser.error('--run requires --output')
    print(json.dumps(execute(args.bundle,args.output,args.host,args.port)
                     if args.run else check(args.bundle)))
