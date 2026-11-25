"""Lazy, source-gated Native walker and four-camera adapter for C111329.

The reviewed site binder supplies an original device reader, an exact walker
blueprint and four already placed RGB sensors. This class controls the actor and
owns sensor listeners; the binder remains responsible for world restoration.
"""
from __future__ import annotations

import io
import math
from queue import Empty, Queue

from PIL import Image

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


class CarlaCrossingAdapter:
    is_diagnostic = False

    def __init__(self, world, sensors, device_reader, *, blueprint_library,
                 location_factory, transform_factory, vector_factory,
                 walker_control_factory, spawn_z, speed_mps=1.2,
                 timeout_seconds=5.0):
        if set(sensors) != set(CAMERAS) or len(sensors) != 4:
            raise ValueError('four named original camera sensors required')
        if not callable(device_reader) or not all(callable(f) for f in
            (location_factory, transform_factory, vector_factory, walker_control_factory)):
            raise ValueError('Native source and CARLA factories required')
        if not math.isfinite(spawn_z) or not 0 < speed_mps <= 2.5:
            raise ValueError('source-bound walker height and speed required')
        self.world, self.sensors, self.device_reader = world, sensors, device_reader
        self.blueprints = blueprint_library
        self.location_factory, self.transform_factory = location_factory, transform_factory
        self.vector_factory, self.control_factory = vector_factory, walker_control_factory
        self.spawn_z, self.speed_mps, self.timeout_seconds = spawn_z, speed_mps, timeout_seconds
        self.queues = {name: Queue() for name in CAMERAS}
        self.listening = []
        self.route = None
        self.route_index = 0
        self.images = {}
        self.frame = None
        settings = world.get_settings()
        if settings.synchronous_mode is not True or abs(settings.fixed_delta_seconds - 0.05) > 1e-8:
            raise ValueError('synchronous original 20 Hz world required')
        try:
            for name in CAMERAS:
                sensor = sensors[name]
                sensor.listen(lambda image, camera=name: self.queues[camera].put(image))
                self.listening.append(sensor)
        except Exception:
            self.close()
            raise

    def spawn_walker(self, blueprint_id, xy):
        if not blueprint_id.startswith('walker.pedestrian.'):
            raise ValueError('pedestrian blueprint required')
        blueprint = self.blueprints.find(blueprint_id)
        location = self.location_factory(x=float(xy[0]), y=float(xy[1]), z=float(self.spawn_z))
        actor = self.world.try_spawn_actor(blueprint, self.transform_factory(location))
        if actor is None:
            raise ValueError('source-bound pedestrian spawn failed')
        self.actor = actor
        return actor

    def drive_walker_route(self, actor, route):
        if len(route) < 2:
            raise ValueError('complete pedestrian crossing route required')
        self.route = [tuple(map(float, p)) for p in route]
        self.route_index = 1

    def walker_id(self, actor):
        return actor.id

    def walker_xy(self, actor):
        location = actor.get_location()
        return (float(location.x), float(location.y))

    def _control(self, actor):
        if self.route is None:
            raise ValueError('pedestrian route not installed')
        x, y = self.walker_xy(actor)
        while self.route_index < len(self.route):
            goal = self.route[self.route_index]
            dx, dy = goal[0] - x, goal[1] - y
            distance = math.hypot(dx, dy)
            if distance > 0.35:
                vector = self.vector_factory(x=dx / distance, y=dy / distance, z=0.0)
                actor.apply_control(self.control_factory(direction=vector,
                                                         speed=self.speed_mps, jump=False))
                return
            self.route_index += 1
        self.stop_walker(actor)

    def tick(self):
        actor = getattr(self, 'actor', None)
        if actor is None:
            raise ValueError('Native pedestrian actor not owned')
        self._control(actor)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError('Native world snapshot frame differs')
        self.frame = frame
        self.images = {}
        for name in CAMERAS:
            try:
                image = self.queues[name].get(timeout=self.timeout_seconds)
            except Empty as exc:
                raise ValueError('Native original camera frame missing') from exc
            if image.frame != frame:
                raise ValueError('Native original camera frame mismatch')
            self.images[name] = image
        return {'original_frame': frame,
                'elapsed_seconds': float(snapshot.timestamp.elapsed_seconds)}

    def camera_frames(self):
        if self.frame is None or set(self.images) != set(CAMERAS):
            raise ValueError('Native original four-camera frame unavailable')
        return {name: image.frame for name, image in self.images.items()}

    def camera_png(self, camera, frame):
        if camera not in CAMERAS or frame != self.frame or camera not in self.images:
            raise ValueError('Native original camera image unavailable')
        image = self.images[camera]
        raw = bytes(image.raw_data)
        if len(raw) != image.width * image.height * 4:
            raise ValueError('Native original BGRA dimensions mismatch')
        rgb = Image.frombytes('RGBA', (image.width, image.height), raw, 'raw', 'BGRA').convert('RGB')
        stream = io.BytesIO()
        rgb.save(stream, format='PNG')
        return stream.getvalue()

    def actor_state(self, actor):
        transform = actor.get_transform()
        vertices = actor.bounding_box.get_world_vertices(transform)
        velocity = actor.get_velocity()
        if len(vertices) < 4:
            raise ValueError('Native walker body geometry incomplete')
        return {'actor_id': actor.id, 'blueprint': actor.type_id,
                'body_vertices_m': [[float(v.x), float(v.y), float(v.z)] for v in vertices],
                'velocity_mps': [float(velocity.x), float(velocity.y), float(velocity.z)],
                'heading_deg': float(transform.rotation.yaw)}

    def read_devices(self):
        value = self.device_reader(self.world, self.frame)
        if not isinstance(value, list):
            raise ValueError('original official device readback missing')
        return value

    def stop_walker(self, actor):
        vector = self.vector_factory(x=0.0, y=0.0, z=0.0)
        actor.apply_control(self.control_factory(direction=vector, speed=0.0, jump=False))

    def destroy_actor(self, actor):
        try:
            actor.destroy()
        finally:
            self.close()

    def close(self):
        for sensor in self.listening:
            sensor.stop()
        self.listening.clear()
