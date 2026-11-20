"""Four original RGB camera sources for the selected school-bus scenes.

These mounts are construction geometry. Whether the bus, signs, pupils and
front/rear warning lamps are legible is decided from retained Native footage.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from threading import Condition
from time import monotonic

# Parent, location in metres, rotation in degrees, pixels and horizontal FOV.
CAMERAS = {
    'overview': ('bus', (-10, -12, 9), (-18, 50, 0), (1920, 1080), 95),
    'approach': ('subject', (1.2, 0, 2), (0, 0, 0), (1280, 720), 90),
    'reference_corner': ('bus', (8, 0, 2.5), (0, 180, 0), (1280, 720), 60),
    'driver_reference': ('bus', (-8, 0, 2.5), (0, 0, 0), (1280, 720), 75),
}


class LosslessSourceSink:
    def __init__(self, output, name, *, popen=subprocess.Popen):
        if name not in CAMERAS:
            raise ValueError('Unknown school-bus source camera')
        path = Path(output) / (name + '.mkv')
        if path.exists():
            raise ValueError('Retain prior school-bus source camera')
        width, height = CAMERAS[name][3]
        self.frame_bytes = width * height * 4
        self.process = popen(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y',
                              '-f', 'rawvideo', '-pixel_format', 'bgra',
                              '-video_size', f'{width}x{height}', '-framerate', '20',
                              '-i', 'pipe:0', '-an', '-c:v', 'ffv1', str(path)],
                             stdin=subprocess.PIPE)
        self.closed = False

    def write(self, image):
        if self.closed or len(image.raw_data) != self.frame_bytes:
            raise ValueError('Original school-bus camera byte count changed')
        self.process.stdin.write(image.raw_data)

    def close(self):
        if not self.closed:
            self.closed = True
            self.process.stdin.close()
            if self.process.wait() != 0:
                raise ValueError('School-bus source encoder failed')


class SchoolBusCameraCapture:
    def __init__(self, world, carla_module, subject, bus, sinks):
        if set(sinks) != set(CAMERAS):
            raise ValueError('Exactly four named school-bus camera sinks required')
        self.sinks = sinks
        self.frames = {name: set() for name in CAMERAS}
        self.condition = Condition()
        self.errors = []
        self.sensors = []
        self.closed = False
        try:
            for name, (parent, location, rotation, size, fov) in CAMERAS.items():
                blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
                for key, value in (('image_size_x', size[0]), ('image_size_y', size[1]),
                                   ('fov', fov), ('sensor_tick', .05)):
                    blueprint.set_attribute(key, str(value))
                transform = carla_module.Transform(carla_module.Location(*location),
                                                   carla_module.Rotation(*rotation))
                sensor = world.spawn_actor(blueprint, transform,
                                           attach_to=bus if parent == 'bus' else subject)
                self.sensors.append(sensor)
                sensor.listen(lambda image, source=name: self._receive(source, image))
        except BaseException:
            self.close()
            raise

    def _receive(self, name, image):
        with self.condition:
            if self.closed:
                return
            try:
                if image.frame in self.frames[name]:
                    raise ValueError('Duplicate original school-bus camera frame')
                if (image.width, image.height) != CAMERAS[name][3]:
                    raise ValueError('Original school-bus camera dimensions changed')
                self.sinks[name].write(image)
                self.frames[name].add(image.frame)
            except BaseException as error:
                self.errors.append(error)
            finally:
                self.condition.notify_all()

    def wait_for_frame(self, frame, *, timeout_s=10):
        deadline = monotonic() + timeout_s
        with self.condition:
            while True:
                if self.errors:
                    raise ValueError('School-bus source camera callback failed') from self.errors[0]
                if all(frame in rows for rows in self.frames.values()):
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise ValueError('Missing original school-bus camera frame')
                self.condition.wait(remaining)

    def verify(self, frames):
        expected = set(frames)
        if not expected or any(rows != expected for rows in self.frames.values()):
            raise ValueError('Missing or extra original school-bus camera frame')
        return {name: len(expected) for name in CAMERAS}

    def close(self):
        if not self.closed:
            self.closed = True
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()
