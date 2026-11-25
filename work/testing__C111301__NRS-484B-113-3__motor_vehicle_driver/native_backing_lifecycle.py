"""Owned CARLA backing capture with same-tick cameras and lossless source videos.

The reviewed packet and transforms are operator inputs. A synthetic fixture may
exercise this code, but only an original reviewed packet can publish an original
acquisition. Actual visibility and right of way remain independent review tasks.
"""
from __future__ import annotations

import copy
import argparse
import hashlib
import json
import math
from pathlib import Path
from queue import Empty, Queue
import subprocess
from types import SimpleNamespace

from backing_controller import BackingController
from backing_geometry import pedestrian_in_reverse_corridor
from media_decode import PRODUCTION_DIMENSIONS
from native_backing import construct
from native_backing_capture import NativeBackingRecorder
from saved_backing import ASSIGNMENT, CAMERAS, CASES


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FFV1Encoder:
    def __init__(self, path, width, height):
        self.path = Path(path)
        self.width, self.height = width, height
        self.process = subprocess.Popen([
            'ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-f', 'rawvideo',
            '-pix_fmt', 'bgra', '-s', f'{width}x{height}', '-r', '20', '-i', 'pipe:0',
            '-an', '-c:v', 'ffv1', '-level', '3', str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def append(self, image):
        if (image.width, image.height) != (self.width, self.height):
            raise ValueError('original camera dimensions differ')
        raw = bytes(image.raw_data)
        if len(raw) != self.width * self.height * 4:
            raise ValueError('original BGRA camera bytes incomplete')
        self.process.stdin.write(raw)

    def close(self):
        self.process.stdin.close()
        error = self.process.stderr.read().decode(errors='replace')
        self.process.stderr.close()
        if self.process.wait(timeout=120) != 0:
            raise ValueError('lossless camera encoding failed: ' + error[-500:])

    def abort(self):
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=30)
        self.process.stderr.close()


def _source_packet(attempt, packet_path, diagnostic_fixture):
    attempt = Path(attempt).resolve()
    packet_path = Path(packet_path)
    if packet_path.is_symlink() or packet_path.resolve().parent != attempt:
        raise ValueError('adjacent original map packet required')
    packet_path = packet_path.resolve()
    packet = json.loads(packet_path.read_text())
    source = packet.get('map_source')
    if not isinstance(source, dict) or set(source) != {'path', 'sha256'}:
        raise ValueError('sealed original OpenDRIVE source required')
    map_path = attempt / source['path']
    if (map_path.parent != attempt or map_path.is_symlink() or
            not map_path.is_file() or _sha(map_path) != source['sha256'] or
            _sha(map_path) != packet.get('map_sha256')):
        raise ValueError('original OpenDRIVE source differs from packet')
    if not diagnostic_fixture and packet.get('review_status') != 'reviewed_original':
        raise ValueError('reviewed original Native site required')
    return packet, map_path


def _pose(carla, value, label):
    if not isinstance(value, dict):
        raise ValueError('reviewed Native pose missing: ' + label)
    location, rotation = value.get('location'), value.get('rotation')
    if not isinstance(location, dict) or not isinstance(rotation, dict):
        raise ValueError('reviewed Native pose missing: ' + label)
    def number(source, key):
        result = source.get(key)
        if type(result) not in (int, float) or not math.isfinite(result):
            raise ValueError('finite reviewed Native pose required: ' + label + ' ' + key)
        return float(result)
    return carla.Transform(
        carla.Location(x=number(location, 'x'), y=number(location, 'y'), z=number(location, 'z')),
        carla.Rotation(pitch=number(rotation, 'pitch'), yaw=number(rotation, 'yaw'),
                       roll=number(rotation, 'roll')))


class CarlaCameraFactory:
    """Spawn four source-positioned RGB sensors owned by the capture lifecycle."""
    def __init__(self, carla, packet):
        self.carla = carla
        self.packet = packet
        sources = packet.get('camera_extrinsics')
        if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
            raise ValueError('four reviewed original camera extrinsics required')
        for name in CAMERAS:
            _pose(carla, sources[name], name)
            if sources[name].get('fov_deg') != 90:
                raise ValueError('reviewed original camera field of view differs: ' + name)

    def __call__(self, world, vehicle, name, dimensions):
        blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
        blueprint.set_attribute('image_size_x', str(dimensions[0]))
        blueprint.set_attribute('image_size_y', str(dimensions[1]))
        blueprint.set_attribute('sensor_tick', '.05')
        blueprint.set_attribute('fov', '90')
        sensor = world.spawn_actor(blueprint,
                                   _pose(self.carla, self.packet['camera_extrinsics'][name], name),
                                   attach_to=vehicle)
        if sensor is None:
            raise ValueError('Native camera spawn failed: ' + name)
        return sensor


def run(world, *, attempt, packet_path, case_id, control_factory,
        carla=None, transforms=None, camera_factory=None,
        encoder_factory=FFV1Encoder, diagnostic_fixture=False,
        expected_frames=900):
    """Capture into a fresh attempt, releasing all owned actors before receipt."""
    if case_id not in CASES or expected_frames != 900:
        raise ValueError('exact 900-frame backing case required')
    root = Path(attempt).resolve()
    if not root.is_dir() or (root / 'acquisition.json').exists():
        raise ValueError('fresh Native attempt directory required')
    packet, map_path = _source_packet(root, packet_path, diagnostic_fixture)
    if not diagnostic_fixture:
        if not (root / 'construction.json').is_file() or not (root / 'runner.py').is_file():
            raise ValueError('selected original Native construction and runner required')
        if carla is None or transforms is not None or camera_factory is not None:
            raise ValueError('production Native transforms and cameras must come from reviewed packet')
        poses = packet.get('actor_transforms')
        if not isinstance(poses, dict) or set(poses) != {'vehicle', 'pedestrian'}:
            raise ValueError('two reviewed original actor transforms required')
        transforms = {name: _pose(carla, poses[name], name) for name in poses}
        camera_factory = CarlaCameraFactory(carla, packet)
    elif transforms is None or camera_factory is None:
        raise ValueError('diagnostic Native fixture requires explicit actor and camera adapters')
    loaded_map = world.get_map().to_opendrive().encode()
    if hashlib.sha256(loaded_map).hexdigest() != _sha(map_path):
        raise ValueError('loaded Native map differs from reviewed original')
    saved_settings = copy.copy(world.get_settings())
    settings = copy.copy(saved_settings)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    actors = None
    cameras = {}
    encoders = {}
    queues = {}
    first_time = None
    capture_error = None
    receipt = None
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        if readback.synchronous_mode is not True or readback.fixed_delta_seconds != .05:
            raise ValueError('Native 20 Hz world settings readback differs')
        actors = construct(world, packet, transforms)
        recorder = NativeBackingRecorder(packet, actors['vehicle'], actors['pedestrian'])
        controller = BackingController(yield_for_pedestrian=case_id.endswith('pedestrian_yield'),
                                       control_factory=control_factory)
        for name in CAMERAS:
            sensor = camera_factory(world, actors['vehicle'], name, PRODUCTION_DIMENSIONS[name])
            cameras[name] = sensor
            inbox = Queue(maxsize=2)
            sensor.listen(inbox.put)
            queues[name] = inbox
            encoders[name] = encoder_factory(root / (name + '.mkv'), *PRODUCTION_DIMENSIONS[name])
        prior_frame = None
        for index in range(expected_frames):
            person = actors['pedestrian'].get_transform().location
            corridor = pedestrian_in_reverse_corridor(packet, [person.x, person.y])['in_corridor']
            controller.step(actors['vehicle'], pedestrian_in_corridor=corridor,
                            phase='backing')
            frame = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != frame or (prior_frame is not None and frame != prior_frame + 1):
                raise ValueError('original Native world frame drift')
            prior_frame = frame
            stamp = snapshot.timestamp.elapsed_seconds
            if first_time is None:
                first_time = stamp
            images = {}
            for name in CAMERAS:
                try:
                    image = queues[name].get(timeout=5)
                except Empty as exc:
                    raise ValueError('original camera callback missing: ' + name) from exc
                if image.frame != frame or abs(image.timestamp - stamp) > .001:
                    raise ValueError('original camera frame/time differs: ' + name)
                images[name] = image
            recorder_images = {name: SimpleNamespace(frame=image.frame,
                                                     timestamp=image.timestamp - first_time)
                               for name, image in images.items()}
            recorder.append(frame, stamp - first_time, recorder_images)
            for name in CAMERAS:
                encoders[name].append(images[name])
        source = recorder.write(root)
        for encoder in encoders.values():
            encoder.close()
        encoders.clear()
        receipt = {'assignment_id': ASSIGNMENT, 'case_id': case_id,
                   'source_kind': 'synthetic_fixture' if diagnostic_fixture else 'native_original',
                   'diagnostic': bool(diagnostic_fixture),
                   'source_id': 'original-native-world-frames',
                   'vehicle_actor_id': actors['vehicle'].id,
                   'pedestrian_actor_id': actors['pedestrian'].id,
                   'map_packet': {'path': Path(packet_path).name, 'sha256': _sha(packet_path)},
                   'telemetry': {'path': Path(source['telemetry']).name, 'sha256': _sha(source['telemetry'])},
                   'frame_map': {'path': Path(source['frame_map']).name, 'sha256': _sha(source['frame_map'])},
                   'trace': {'path': Path(source['trace']).name, 'sha256': _sha(source['trace'])},
                   'video_frame_map': {'path': Path(source['video_frame_map']).name,
                                       'sha256': _sha(source['video_frame_map'])},
                   'media': {name: {'path': name + '.mkv', 'sha256': _sha(root / (name + '.mkv'))}
                             for name in CAMERAS}}
    except BaseException as exc:
        capture_error = exc
    finally:
        cleanup_errors = []
        for encoder in encoders.values():
            try:
                encoder.abort()
            except BaseException as exc:
                cleanup_errors.append('encoder abort: ' + str(exc))
        for sensor in reversed(list(cameras.values())):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as exc:
                cleanup_errors.append('camera release: ' + str(exc))
        if actors is not None:
            try:
                actors['cleanup']()
            except BaseException as exc:
                cleanup_errors.append('actor release: ' + str(exc))
        try:
            world.apply_settings(saved_settings)
        except BaseException as exc:
            cleanup_errors.append('world restore: ' + str(exc))
        if cleanup_errors:
            raise RuntimeError('Native owner release failed: ' + '; '.join(cleanup_errors)) from capture_error
    restored = world.get_settings()
    if (restored.synchronous_mode != saved_settings.synchronous_mode or
            restored.fixed_delta_seconds != saved_settings.fixed_delta_seconds):
        raise ValueError('Native world settings restoration readback failed') from capture_error
    if capture_error is not None:
        raise capture_error
    if world.get_map().to_opendrive().encode() != loaded_map:
        raise ValueError('Native map changed during capture')
    (root / 'acquisition.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not diagnostic_fixture:
        from worker_exchange.native_output import seal_capture
        (root / 'acquisition-provenance.json').write_text(json.dumps({
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'case_id': case_id, 'assignment_id': ASSIGNMENT}, indent=2) + '\n')
        seal_capture(root, frames=expected_frames,
                     restoration={'restored': True, 'world_settings_readback': True},
                     errors=[], encoder_exit_codes={name: 0 for name in CAMERAS})
    return receipt


def main():
    parser = argparse.ArgumentParser(description='Capture one reviewed original C111301 backing case')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--packet', required=True)
    parser.add_argument('--case', choices=sorted(CASES), required=True)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    receipt = run(client.get_world(), attempt=args.attempt,
                  packet_path=args.packet, case_id=args.case,
                  control_factory=carla.VehicleControl, carla=carla)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
