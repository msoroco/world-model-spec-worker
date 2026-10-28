"""C10301 absolute-speed capability acquisition against an operator-owned CARLA server."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def config():
    return json.loads((ROOT / 'config.json').read_text())


def check():
    cfg = config()
    assert cfg['law_id'] == 'NRS-484B-600-1e'
    assert cfg['actor'] == 'motor_vehicle_driver'
    assert cfg['selected_case_id'] == cfg['case']['case_id']
    assert cfg['case']['variable_assignments']['commanded_speed_mps']['value'] > 0
    root = ET.parse(ROOT / 'scene.xodr').getroot()
    road = root.find('road[@id="1"]')
    assert root.tag == 'OpenDRIVE' and road is not None
    assert float(road.get('length')) == 650
    assert road.find('lanes/laneSection/right/lane[@id="-1"]') is not None
    assert road.find('lanes/laneSection/left/lane[@id="1"]') is not None
    assert len(cfg['cameras']) == 4
    assert (cfg['cameras'][0]['width'], cfg['cameras'][0]['height']) == (1920, 1080)
    assert all((c['width'], c['height']) == (1280, 720) for c in cfg['cameras'][1:])
    assert set(cfg['required_atoms']) == {'kin.speed', 'kin.velocity', 'kin.position', 'ru.subject'}
    print(json.dumps({'case_id': cfg['selected_case_id'], 'offline_check': 'passed',
                      'simulator_connected': False}))


def control(carla, actor, target_mps, gain):
    pose = actor.get_transform()
    speed = actor.get_velocity().length()
    error = target_mps - speed
    lateral = pose.location.y + 1.75
    heading = math.radians(pose.rotation.yaw)
    steer = max(-.45, min(.45, -.16*lateral - .9*heading))
    throttle = max(0., min(.75, gain*error))
    brake = max(0., min(.8, -1.1*gain*error))
    if pose.location.x > 470:
        throttle = 0.
        brake = .65
    return carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)


def cleanup_action(errors, label, action):
    try:
        return action()
    except Exception as exc:
        errors.append(label + ': ' + repr(exc))
        return None


def capture_frame(frame_map, frame, time_s, sources):
    return frame_map.append(frame, time_s, source_frames=sources)


def run(args):
    import carla  # no simulator import or connection during --check
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    cfg = config()
    case = cfg['case']
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'video_frames.jsonl').exists():
        raise ValueError('Choose a fresh attempt; original frame records are immutable')
    (output / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    client = carla.Client(args.host, args.port)
    client.set_timeout(120)
    saved = snapshot(client)
    owned = []
    encoders = []
    cameras = []
    streams = {}
    capture = None
    evidence = None
    capture_complete = False
    try:
        world = client.generate_opendrive_world((ROOT / 'scene.xodr').read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        (output / 'road.xodr').write_text(world.get_map().to_opendrive())
        bp = world.get_blueprint_library().find('vehicle.lincoln.mkz_2020')
        bp.set_attribute('role_name', 'subject')
        ego = world.spawn_actor(bp, carla.Transform(carla.Location(x=20, y=-1.75, z=.5)))
        owned.append(ego)
        for i, spec in enumerate(cfg['cameras']):
            cam_bp = world.get_blueprint_library().find('sensor.camera.rgb')
            cam_bp.set_attribute('image_size_x', str(spec['width']))
            cam_bp.set_attribute('image_size_y', str(spec['height']))
            cam_bp.set_attribute('sensor_tick', '0')
            camera = world.spawn_actor(cam_bp, carla.Transform(
                carla.Location(x=spec['x'], y=spec['y'], z=spec['z']),
                carla.Rotation(pitch=spec['pitch'], yaw=spec['yaw'])), attach_to=ego)
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            cameras.append((camera, q, spec))
            log = (output / ('view%d.encoder.log' % i)).open('x')
            encoder = subprocess.Popen(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', '%dx%d' % (spec['width'], spec['height']),
                '-r', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-pix_fmt', 'bgr0',
                str(output / ('view%d.mkv' % i))], stdin=subprocess.PIPE, stderr=log)
            encoders.append((encoder, log))
        for _ in range(5):
            world.tick()
        capture = PipelineCapture(client, ego, output, case['case_id'],
                                  required_observations=cfg['required_atoms'])
        evidence = (output / 'capture/evidence.jsonl').open()
        (output / 'channels').mkdir()
        for channel in case['recording_description']['channels']:
            name = channel['name']
            streams[name] = (output / 'channels' / (name + '.jsonl')).open('x')
        (output / 'authored-context.json').write_text(json.dumps(cfg['authored_test_context'], indent=2) + '\n')
        start = world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output / 'video_frames.jsonl') as frame_map, \
                (output / 'physical_samples.jsonl').open('x') as samples:
            for _ in range(cfg['max_ticks']):
                ego.apply_control(control(carla, ego,
                    case['variable_assignments']['commanded_speed_mps']['value'],
                    cfg['controller']['speed_kp']))
                frame = world.tick()
                now = world.get_snapshot().timestamp.elapsed_seconds - start
                state = capture.capture(frame, now)
                packet = json.loads(evidence.readline())
                if packet['original_frame'] != frame:
                    raise RuntimeError('Original trace and observation frames differ')
                values = {'kin.speed': state['speed_mps'], 'kin.velocity': state['velocity_mps'],
                          'kin.position': state['position_m'],
                          'ru.subject': {'actor_id': packet['actor_id'],
                                         'blueprint': ego.type_id, 'role_name': 'subject'}}
                samples.write(json.dumps({'frame': frame, 'time_s': now,
                    'speed_mps': state['speed_mps'], 'position_m': state['position_m'],
                    'velocity_mps': state['velocity_mps']}) + '\n')
                for name, stream in streams.items():
                    stream.write(json.dumps({'time_s': now, 'value': values[name]}) + '\n')
                sources = {}
                for i, (_, q, spec) in enumerate(cameras):
                    image = q.get(timeout=45)
                    while image.frame < frame:
                        image = q.get(timeout=45)
                    if image.frame != frame:
                        raise RuntimeError('Source camera frame differs')
                    raw = bytes(image.raw_data)
                    encoders[i][0].stdin.write(raw)
                    sources['view%d' % i] = {'width': image.width, 'height': image.height,
                        'source_bgra_sha256': hashlib.sha256(raw).hexdigest()}
                capture_frame(frame_map, frame, now, sources)
                if state['position']['x'] >= 520 and state['speed_mps'] < 2:
                    break
        capture_complete = True
    finally:
        errors = []
        if evidence is not None:
            cleanup_action(errors, 'evidence close', evidence.close)
        for stream in streams.values():
            cleanup_action(errors, 'channel close', stream.close)
        if capture is not None:
            cleanup_action(errors, 'capture close', lambda: capture.close(confirmed=capture_complete))
        for encoder, log in encoders:
            cleanup_action(errors, 'encoder stdin close', encoder.stdin.close)
            cleanup_action(errors, 'encoder wait', lambda encoder=encoder: encoder.wait(timeout=120))
            cleanup_action(errors, 'encoder log close', log.close)
        for actor in reversed(owned):
            if actor.type_id.startswith('sensor.'):
                cleanup_action(errors, 'sensor stop', actor.stop)
            cleanup_action(errors, 'actor destroy', actor.destroy)
        def restore_world():
            receipt = restore(client, saved)
            (output / 'world-restore.json').write_text(json.dumps(receipt, indent=2) + '\n')
        cleanup_action(errors, 'world restore', restore_world)
        if errors:
            (output / 'cleanup-failures.json').write_text(json.dumps(errors, indent=2) + '\n')
            raise RuntimeError('; '.join(errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check:
        check()
    else:
        if not (args.output_dir and args.host and args.port):
            parser.error('Capture requires --output-dir, --host and --port')
        run(args)
