"""Native reversible-lane source capture for one exact C223016 construction.

The configured period and direction are synthetic test premises. The captured
cone, vehicle, governed lane and clock readings remain original Native sources;
municipal adoption, sign legibility and statutory judgment remain unresolved.
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from math import atan2, cos, hypot, radians, sin
from pathlib import Path
from threading import Condition
from time import monotonic

from reversible_direction import CASE_SUFFIXES, measure_direction


CAMERAS = {
    'overview': ((-10, 0, 8), (-12, 0, 0), (1920, 1080), 100),
    'approach': ((1.2, 0, 2), (0, 0, 0), (1280, 720), 90),
    'reference_corner': ((-5, 2.5, 3.5), (-8, 0, 0), (1280, 720), 100),
    'driver_reference': ((.6, -.35, 1.6), (0, 0, 0), (1280, 720), 85),
}


def check_config(config):
    prefix = 'heldout__C223016__LVMC-11-42-030__motor_vehicle_driver__'
    case_id = config.get('selected_case_id', '')
    if case_id != prefix + 'morning_east_with':
        raise ValueError('runner currently supports the first exact C223016 case')
    if (config.get('cell_id'), config.get('law_id'), config.get('actor')) != (
            'C223016', 'LVMC-11-42-030', 'motor_vehicle_driver'):
        raise ValueError('runner law/cell/actor mismatch')
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 160, 8):
        raise ValueError('runner requires 160 original 20 Hz frames')
    if type(config.get('governed_lane_id')) is not int or config['governed_lane_id'] == 0:
        raise ValueError('governed Native lane identity required')
    if config.get('period_id') not in ('morning', 'evening') or config.get('period_direction_xy') not in ([1, 0], [-1, 0]):
        raise ValueError('explicit synthetic period/direction premise required')
    if not config.get('period_premise_source'):
        raise ValueError('period premise source reference required')
    if (config['period_id'], config['period_direction_xy'],
            config.get('subject_direction_xy')) != ('morning', [1, 0], [1, 0]):
        raise ValueError('first exact case direction or period differs')
    if {x.get('name') for x in config.get('cameras', [])} != set(CAMERAS):
        raise ValueError('four named source cameras required')
    if config.get('target_speed_mps', 0) <= 0 or config.get('target_speed_mps', 0) > 12:
        raise ValueError('target speed outside construction bounds')
    if type(config.get('spawn_candidate_index')) is not int or not 0 <= config['spawn_candidate_index'] <= 3:
        raise ValueError('spawn candidate index outside construction bounds')
    if not 5 <= config.get('device_forward_m', 0) <= 12:
        raise ValueError('barrier forward distance outside construction bounds')
    if not 0.05 <= config.get('speed_kp', 0) <= 0.4:
        raise ValueError('speed gain outside construction bounds')
    return True


def _spawn_subject(world, carla, config):
    road = world.get_map()
    heading = config['subject_direction_xy']
    candidates = []
    for spawn in road.get_spawn_points():
        waypoint = road.get_waypoint(spawn.location)
        if waypoint is None or waypoint.lane_id != config['governed_lane_id']:
            continue
        yaw = radians(spawn.rotation.yaw)
        if cos(yaw) * heading[0] + sin(yaw) * heading[1] >= .9:
            candidates.append(spawn)
    index = config['spawn_candidate_index']
    if len(candidates) <= index:
        raise ValueError('No Native driving spawn at selected governed-lane candidate')
    bp = world.get_blueprint_library().filter('vehicle.*')[0]
    actor = world.try_spawn_actor(bp, candidates[index])
    if actor is None:
        raise ValueError('Native subject spawn failed')
    return actor


def _spawn_device(world, carla, subject, config):
    library = world.get_blueprint_library()
    cones = library.filter('*trafficcone*')
    if not cones:
        raise ValueError('Native traffic-cone barrier blueprint unavailable')
    pose = subject.get_transform()
    yaw = radians(pose.rotation.yaw)
    forward = config['device_forward_m']
    location = pose.location + carla.Location(x=forward * cos(yaw) - 1.8 * sin(yaw),
                                               y=forward * sin(yaw) + 1.8 * cos(yaw), z=.1)
    actor = world.try_spawn_actor(cones[0], carla.Transform(location, pose.rotation))
    if actor is None:
        raise ValueError('Native barrier spawn failed')
    return actor


def _control(actor, carla, target_speed, speed_kp):
    velocity = actor.get_velocity()
    error = target_speed - hypot(velocity.x, velocity.y)
    actor.apply_control(carla.VehicleControl(
        throttle=min(.6, max(0., speed_kp * error)),
        brake=min(.8, max(0., -.25 * error)), steer=0.))


class CameraCapture:
    def __init__(self, world, carla, subject, output):
        self.condition = Condition()
        self.frames = {name: set() for name in CAMERAS}
        self.errors = []
        self.sensors = []
        self.encoders = {}
        self.closed = False
        library = world.get_blueprint_library()
        for name, (position, rotation, size, fov) in CAMERAS.items():
            width, height = size
            path = output / (name + '.mkv')
            if path.exists():
                raise ValueError('Retain prior source video: ' + name)
            encoder = subprocess.Popen([
                'ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'rawvideo',
                '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
                '-framerate', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1', str(path)],
                stdin=subprocess.PIPE)
            self.encoders[name] = encoder
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', width), ('image_size_y', height),
                               ('fov', fov), ('sensor_tick', .05)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(*position), carla.Rotation(*rotation)), attach_to=subject)
            self.sensors.append(sensor)
            sensor.listen(lambda image, n=name, s=size: self._on_image(n, s, image))

    def _on_image(self, name, size, image):
        with self.condition:
            if self.closed:
                return
            try:
                if image.frame in self.frames[name] or (image.width, image.height) != size:
                    raise ValueError('Duplicate or resized original camera frame')
                self.encoders[name].stdin.write(image.raw_data)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait(self, frame, timeout_s=15):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError('Source camera callback failed') from self.errors[0]
                if all(frame in rows for rows in self.frames.values()):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError('Four source cameras did not join original frame')
                self.condition.wait(remaining)

    def verify(self, frames):
        for observed in self.frames.values():
            if observed != set(frames):
                raise ValueError('Missing or extra source camera frame')

    def close(self):
        if self.closed:
            return
        self.closed = True
        for sensor in self.sensors:
            sensor.stop()
            sensor.destroy()
        for encoder in self.encoders.values():
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise ValueError('Source camera encoder failed')


def run(output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    output = Path(output)
    config = json.loads((output / 'config.json').read_text())
    check_config(config)
    client = carla.Client(host, port)
    client.set_timeout(30.)
    world = client.get_world()
    old_settings = world.get_settings()
    subject = device = camera = pipeline = frame_map = stream = None
    frames = []
    errors = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        subject = _spawn_subject(world, carla, config)
        device = _spawn_device(world, carla, subject, config)
        camera = CameraCapture(world, carla, subject, output)
        pipeline = PipelineCapture(client, subject, output, config['selected_case_id'],
                                   required_observations=config.get('required_atoms', []))
        frame_map = FrameMap(output / 'video_frames.jsonl')
        stream = (output / 'direction_state.jsonl').open('x')
        first_time = None
        for _ in range(config['frames']):
            _control(subject, carla, config['target_speed_mps'], config['speed_kp'])
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame:
                raise ValueError('Native snapshot differs from completed tick')
            if first_time is None:
                first_time = snapshot.timestamp.elapsed_seconds
            time_s = snapshot.timestamp.elapsed_seconds - first_time
            camera.wait(frame)
            waypoint = world.get_map().get_waypoint(subject.get_location())
            if waypoint is None or waypoint.lane_id != config['governed_lane_id'] or not device.is_alive:
                raise ValueError('Subject lane or barrier source changed')
            velocity = subject.get_velocity()
            row = {'frame': frame, 'time_s': time_s, 'lane_id': waypoint.lane_id,
                   'civil_time': {'source': 'capture host UTC clock',
                                  'iso8601': datetime.now(timezone.utc).isoformat()},
                   'device': {'kind': 'barrier', 'source_id': str(device.id),
                              'governs_lane_id': waypoint.lane_id,
                              'period_id': config['period_id'], 'effective': True,
                              'direction_xy': config['period_direction_xy']},
                   'subject_velocity_xy': [velocity.x, velocity.y]}
            original = pipeline.capture(frame, time_s)
            if (original.get('frame'), original.get('time_s')) != (frame, time_s):
                raise ValueError('Pipeline source tick differs')
            stream.write(json.dumps(row) + '\n')
            stream.flush()
            frame_map.append(frame, time_s)
            frames.append(frame)
        camera.verify(frames)
        # This validates observed travel against the explicit synthetic premise.
        rows = [json.loads(line) for line in (output / 'direction_state.jsonl').read_text().splitlines()]
        measure_direction(rows, case_suffix=config['selected_case_id'].rsplit('__', 1)[1],
                          lane_id=config['governed_lane_id'])
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if stream is not None:
            stream.close()
        if frame_map is not None:
            frame_map.close()
        if pipeline is not None:
            pipeline.close(confirmed=not errors)
        if camera is not None:
            camera.close()
        if device is not None:
            device.destroy()
        if subject is not None:
            subject.destroy()
        world.apply_settings(old_settings)
        restored = world.get_settings()
        if (restored.synchronous_mode, restored.fixed_delta_seconds) != (
                old_settings.synchronous_mode, old_settings.fixed_delta_seconds):
            raise ValueError('Native world setting restoration failed')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_frames': len(frames), 'period_authority': 'synthetic premise only'}) + '\n')
    seal_capture(output, frames=len(frames), restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'native_map_name': world.get_map().name,
                          'device_actor_id': int(device.id),
                          'period_premise_source': config['period_premise_source']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        if Path('config.json').is_file():
            check_config(json.loads(Path('config.json').read_text()))
        return
    if not args.output_dir:
        parser.error('--output-dir required')
    run(args.output_dir, args.host, args.port)


if __name__ == '__main__':
    main()
