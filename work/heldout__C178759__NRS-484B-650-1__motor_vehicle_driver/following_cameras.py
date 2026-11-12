"""Four original RGB source views for the road/follow construction.

The caller supplies lossless frame sinks. This helper checks frame identity and
resolution; only subsequent physical review can establish visibility.
"""

from collections import defaultdict
from pathlib import Path
import subprocess
from threading import Condition
from time import monotonic


CAMERAS = {
    'overview': ((-8.0, 0.0, 7.0), (-20.0, 0.0, 0.0), (1920, 1080), 95),
    'approach': ((1.5, 0.0, 2.0), (0.0, 0.0, 0.0), (1280, 720), 90),
    'reference_corner': ((1.5, 1.0, 1.6), (0.0, 0.0, 0.0), (1280, 720), 100),
    'driver_reference': ((0.3, -0.3, 1.5), (0.0, 0.0, 0.0), (1280, 720), 85),
}


class LosslessSourceSink:
    def __init__(self, output, name, *, popen=subprocess.Popen):
        if name not in CAMERAS:
            raise ValueError('Unknown following source camera')
        path = Path(output) / (name + '.mkv')
        if path.exists():
            raise ValueError('Retain prior following camera source')
        width, height = CAMERAS[name][2]
        self.frame_bytes = width * height * 4
        self.process = popen([
            'ffmpeg', '-nostdin', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pixel_format', 'bgra',
            '-video_size', f'{width}x{height}', '-framerate', '20',
            '-i', 'pipe:0', '-an', '-c:v', 'ffv1', str(path)],
            stdin=subprocess.PIPE)
        self.closed = False

    def write(self, image):
        if self.closed or len(image.raw_data) != self.frame_bytes:
            raise ValueError('Original following camera byte count changed')
        self.process.stdin.write(image.raw_data)

    def close(self):
        if not self.closed:
            self.closed = True
            self.process.stdin.close()
            if self.process.wait() != 0:
                raise ValueError('Following source encoder failed')


class FollowingCameraCapture:
    def __init__(self, world, carla, ego, sinks):
        if set(sinks) != set(CAMERAS):
            raise ValueError('Four named source-camera sinks required')
        self.sensors = []
        self.frames = defaultdict(list)
        self.sinks = sinks
        self.condition = Condition()
        self.errors = []
        self.closed = False
        try:
            for name, (location, rotation, size, fov) in CAMERAS.items():
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                blueprint.set_attribute('image_size_x', str(size[0]))
                blueprint.set_attribute('image_size_y', str(size[1]))
                blueprint.set_attribute('fov', str(fov))
                blueprint.set_attribute('sensor_tick', '0.05')
                transform = carla.Transform(carla.Location(*location),
                                            carla.Rotation(*rotation))
                sensor = world.spawn_actor(blueprint, transform, attach_to=ego)
                if sensor is None:
                    raise ValueError('Could not spawn source camera: ' + name)
                self.sensors.append(sensor)
                sensor.listen(self._listener(name, size))
        except BaseException:
            self.close()
            raise

    def _listener(self, name, size):
        def receive(image):
            with self.condition:
                if self.closed:
                    return
                try:
                    if (image.width, image.height) != size:
                        raise ValueError('Source camera resolution changed: ' + name)
                    if image.frame in self.frames[name]:
                        raise ValueError('Duplicate original source camera frame: ' + name)
                    self.sinks[name].write(image)
                    self.frames[name].append(image.frame)
                except BaseException as error:
                    self.errors.append(error)
                finally:
                    self.condition.notify_all()
        return receive

    def wait_for_frame(self, frame, *, timeout_s=10):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError('Source camera callback failed') from self.errors[0]
                if all(frame in self.frames[name] for name in CAMERAS):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError('Missing original source camera frame')
                self.condition.wait(remaining)

    def verify(self, expected_frames):
        if not expected_frames or self.errors:
            raise ValueError('No original Native frames to verify')
        for name in CAMERAS:
            if self.frames[name] != expected_frames:
                raise ValueError('Missing or extra original source camera frames: ' + name)
        return {name: len(expected_frames) for name in CAMERAS}

    def close(self):
        if not self.closed:
            self.closed = True
            for sensor in reversed(self.sensors):
                try:
                    sensor.stop()
                finally:
                    sensor.destroy()
