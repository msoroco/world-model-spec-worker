"""Lazy CARLA adapter for the C109171 four-camera pedestrian capture protocol.

The caller supplies an already surveyed world, pedestrian actor, four sensors and
an original-state reader. This module owns only the sensor listeners it starts.
It neither invents official signal status nor a pedestrian permission device.
"""
from __future__ import annotations

import io
from queue import Empty, Queue

from PIL import Image

from native_capture import CAMERAS
from native_scene import SourceError
from pedestrian_control import RouteFollower


class CarlaAdapter:
    def __init__(self, world, walker, sensors, original_state_reader,
                 walker_control_factory, vector_factory, timeout_seconds=5.0):
        if set(sensors) != set(CAMERAS):
            raise SourceError('four camera sensors required')
        self.world = world
        self.walker = walker
        self.sensors = sensors
        self.original_state_reader = original_state_reader
        self.walker_control_factory = walker_control_factory
        self.vector_factory = vector_factory
        self.timeout_seconds = timeout_seconds
        self.queues = {name: Queue() for name in CAMERAS}
        self.listening = []
        self.follower = None
        self.started = False
        self.last_world_frame = None

    def start(self, site, case_id):
        settings = self.world.get_settings()
        if settings.synchronous_mode is not True or abs(settings.fixed_delta_seconds - 0.05) > 1e-8:
            raise SourceError('Native world must use synchronous 20 Hz settings')
        suffix = case_id.rsplit('__', 1)[-1]
        self.follower = RouteFollower(suffix, site)
        try:
            for name in CAMERAS:
                sensor = self.sensors[name]
                sensor.listen(lambda image, camera=name: self.queues[camera].put(image))
                self.listening.append(sensor)
            self.started = True
        except Exception:
            self.close()
            raise

    @staticmethod
    def _camera_png(image):
        width, height = image.width, image.height
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            raise SourceError('invalid original camera dimensions')
        raw = bytes(image.raw_data)
        if len(raw) != width * height * 4:
            raise SourceError('original BGRA camera bytes incomplete')
        rgb = Image.frombytes('RGBA', (width, height), raw, 'raw', 'BGRA').convert('RGB')
        buffer = io.BytesIO()
        rgb.save(buffer, format='PNG')
        return buffer.getvalue()

    def read(self, frame):
        if not self.started:
            raise SourceError('adapter has not started')
        self.follower.apply(self.walker, self.walker_control_factory, self.vector_factory)
        world_frame = self.world.tick()
        if not isinstance(world_frame, int) or (self.last_world_frame is not None and world_frame != self.last_world_frame + 1):
            raise SourceError('Native world frame drift')
        self.last_world_frame = world_frame
        event = self.original_state_reader(frame, world_frame)
        if not isinstance(event, dict) or event.get('frame') != frame:
            raise SourceError('original state reader returned wrong frame')
        cameras = {}
        for name in CAMERAS:
            try:
                image = self.queues[name].get(timeout=self.timeout_seconds)
            except Empty as exc:
                raise SourceError('missing original camera callback: ' + name) from exc
            if image.frame != world_frame:
                raise SourceError('original camera world-frame drift: ' + name)
            cameras[name] = {'frame': frame, 'png': self._camera_png(image)}
        return {'event': event, 'cameras': cameras}

    def close(self):
        for sensor in self.listening:
            sensor.stop()
        self.listening.clear()
        self.started = False
        if self.walker is not None and self.walker_control_factory is not None:
            try:
                self.walker.apply_control(self.walker_control_factory(
                    direction=self.vector_factory(0, 0, 0), speed=0.0, jump=False))
            except Exception:
                pass
