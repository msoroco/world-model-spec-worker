"""Source-bound CARLA actor and camera owner for one surveyed left turn.

The packet supplies numerical spawn, route and four camera poses. This module
does not infer a public-highway status from a CARLA map name or image.
"""
from __future__ import annotations

import io
import math
import threading
from copy import deepcopy
from pathlib import Path

from PIL import Image

from construction import control
from saved_delivery import CAMERAS


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite numerical CARLA source required')
    return float(value)


def _pose(carla, value):
    if not isinstance(value, dict):
        raise ValueError('surveyed CARLA pose missing')
    return carla.Transform(
        carla.Location(x=_number(value['x']), y=_number(value['y']),
                       z=_number(value['z'])),
        carla.Rotation(pitch=_number(value.get('pitch', 0)),
                       yaw=_number(value['yaw']), roll=_number(value.get('roll', 0))))


class NativeCarlaAdapter:
    """Own a synchronous world session, ego actor and exact four camera sensors."""

    native_attested = True

    def __init__(self, world, carla, packet, config):
        self.world, self.carla = world, carla
        self.packet, self.config = packet, config
        self.ego_actor = None
        self.sensors = {}
        self.original_settings = None
        self.route = []
        self.route_index = 0
        self.target_speed_mps = None
        self.frames = {name: {} for name in CAMERAS}
        self.condition = threading.Condition()
        self.callback_error = None
        self.current = None

    def start(self, plan):
        if plan['map_name'] != self.world.get_map().name:
            raise ValueError('Native map identity differs from reviewed plan')
        spawn = self.packet.get('spawn_transform')
        if not isinstance(spawn, dict) or any(
                abs(_number(spawn[key]) - plan['spawn_xy_m'][index]) > .1
                for index, key in enumerate(('x', 'y'))):
            raise ValueError('surveyed Native spawn differs from exact construction')
        route = self.packet.get('route_transforms')
        if (not isinstance(route, list) or len(route) < 2 or
                [row.get('waypoint_id') for row in route] !=
                plan['left_turn_route_waypoint_ids']):
            raise ValueError('surveyed Native route differs from exact construction')
        camera_poses = self.packet.get('camera_transforms')
        if not isinstance(camera_poses, dict) or set(camera_poses) != set(CAMERAS):
            raise ValueError('four surveyed Native camera poses required')
        dimensions = {row['name']: (row['width'], row['height'])
                      for row in self.config['cameras']}
        if set(dimensions) != set(CAMERAS):
            raise ValueError('four exact camera dimensions required')
        self.route = [(_number(row['x']), _number(row['y'])) for row in route]
        self.target_speed_mps = _number(plan['controller_policy']['target_speed_mps'])
        if self.target_speed_mps <= 0:
            raise ValueError('Native controller speed must be positive')
        self.original_settings = deepcopy(self.world.get_settings())
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        try:
            library = self.world.get_blueprint_library()
            ego_bp = library.find(plan['ego_blueprint_id'])
            self.ego_actor = self.world.try_spawn_actor(ego_bp, _pose(self.carla, spawn))
            if self.ego_actor is None:
                raise ValueError('Native ego spawn failed')
            for name in sorted(CAMERAS):
                width, height = dimensions[name]
                bp = library.find('sensor.camera.rgb')
                bp.set_attribute('image_size_x', str(width))
                bp.set_attribute('image_size_y', str(height))
                bp.set_attribute('sensor_tick', '0.05')
                sensor = self.world.try_spawn_actor(
                    bp, _pose(self.carla, camera_poses[name]))
                if sensor is None:
                    raise ValueError('Native camera spawn failed: ' + name)
                self.sensors[name] = sensor
                sensor.listen(self._callback(name, width, height))
        except BaseException:
            self.cleanup()
            raise

    def _callback(self, name, width, height):
        def receive(image):
            try:
                if (image.width, image.height) != (width, height):
                    raise ValueError('Native camera dimensions differ: ' + name)
                raw = bytes(image.raw_data)
                if len(raw) != width * height * 4:
                    raise ValueError('Native camera BGRA byte count differs: ' + name)
                picture = Image.frombytes('RGBA', (width, height), raw,
                                          'raw', 'BGRA').convert('RGB')
                stream = io.BytesIO()
                picture.save(stream, format='PNG')
                with self.condition:
                    if image.frame in self.frames[name]:
                        raise ValueError('duplicate Native camera frame: ' + name)
                    self.frames[name][image.frame] = {
                        'frame': image.frame, 'time_s': image.timestamp,
                        'png': stream.getvalue()}
                    self.condition.notify_all()
            except BaseException as error:
                with self.condition:
                    self.callback_error = error
                    self.condition.notify_all()
        return receive

    def tick(self):
        if self.ego_actor is None:
            raise ValueError('Native ego actor is not owned')
        transform = self.ego_actor.get_transform()
        location = transform.location
        velocity = self.ego_actor.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        while (self.route_index + 1 < len(self.route) and
               math.hypot(location.x - self.route[self.route_index][0],
                          location.y - self.route[self.route_index][1]) < 1):
            self.route_index += 1
        command = control((location.x, location.y), math.radians(transform.rotation.yaw),
                          self.route[self.route_index], speed,
                          target_speed_mps=self.target_speed_mps)
        self.ego_actor.apply_control(self.carla.VehicleControl(**command))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError('Native world tick and snapshot differ')
        self.current = {'frame': frame, 'time_s': snapshot.timestamp.elapsed_seconds}
        return dict(self.current)

    def _body(self, frame):
        if self.current is None or self.current['frame'] != frame:
            raise ValueError('Native ego readback frame differs')
        transform = self.ego_actor.get_transform()
        vertices = self.ego_actor.bounding_box.get_world_vertices(transform)
        if len(vertices) < 4:
            raise ValueError('Native full body vertices missing')
        body = [[_number(v.x), _number(v.y), _number(v.z)] for v in vertices]
        waypoint = self.world.get_map().get_waypoint(transform.location)
        if waypoint is None:
            raise ValueError('Native ego road identity missing')
        return body, waypoint.road_id, transform

    def read_ego(self, frame):
        body, road_id, transform = self._body(frame)
        context = self.packet['context']
        phase = ('approach' if road_id == context['approach_road_id'] else
                 'departure' if road_id == context['departure_road_id'] else
                 'connector')
        return {'frame': frame, 'case_id': self.config['selected_case_id'],
                'phase': phase, 'road_id': road_id,
                'ego_heading_rad': math.radians(transform.rotation.yaw),
                'ego_body_vertices_xy_m': [v[:2] for v in body]}

    def read_body(self, frame):
        body, road_id, _ = self._body(frame)
        velocity = self.ego_actor.get_velocity()
        return {'frame': frame, 'road_id': road_id, 'body_vertices_m': body,
                'velocity_mps': [_number(velocity.x), _number(velocity.y),
                                 _number(velocity.z)],
                'velocity_source': 'original_trace_actor_get_velocity'}

    def read_participants(self, frame):
        """Retain same-tick source bodies and motion for every live road user."""
        if self.current is None or self.current['frame'] != frame:
            raise ValueError('Native participant readback frame differs')
        actors = sorted((actor for actor in self.world.get_actors()
                         if getattr(actor, 'is_alive', False) and
                         isinstance(getattr(actor, 'type_id', None), str) and
                         actor.type_id.startswith(('vehicle.', 'walker.'))),
                        key=lambda actor: actor.id)
        if sum(actor.id == self.ego_actor.id for actor in actors) != 1:
            raise ValueError('Native participant stream missing subject')
        if len({actor.id for actor in actors}) != len(actors):
            raise ValueError('Native participant IDs duplicated')
        result = []
        for actor in actors:
            transform = actor.get_transform()
            velocity = actor.get_velocity()
            vector = [_number(velocity.x), _number(velocity.y),
                      _number(velocity.z)]
            vertices = actor.bounding_box.get_world_vertices(transform)
            if len(vertices) < 4:
                raise ValueError('Native participant full body missing')
            result.append({'actor_id': actor.id, 'blueprint': actor.type_id,
                           'velocity_mps': vector,
                           'speed_mps': math.sqrt(sum(value * value for value in vector)),
                           'heading_deg': _number(transform.rotation.yaw),
                           'body_vertices_m': [[_number(vertex.x), _number(vertex.y),
                                               _number(vertex.z)] for vertex in vertices]})
        return result

    def read_cameras(self, frame):
        with self.condition:
            if not self.condition.wait_for(lambda: self.callback_error is not None or
                                           all(frame in self.frames[name] for name in CAMERAS),
                                           timeout=5):
                raise ValueError('Native four-camera callbacks timed out')
            if self.callback_error is not None:
                raise ValueError('Native camera callback failed') from self.callback_error
            return {name: self.frames[name].pop(frame) for name in CAMERAS}

    def read_road_geometry(self):
        geometry = self.packet.get('road_geometry')
        if not isinstance(geometry, dict):
            raise ValueError('surveyed Native road geometry missing')
        return geometry

    def brake(self):
        if self.ego_actor is not None:
            self.ego_actor.apply_control(self.carla.VehicleControl(throttle=0,
                                                                   brake=1, steer=0))

    def cleanup(self):
        errors = []
        for sensor in reversed(list(self.sensors.values())):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as error:
                errors.append(error)
        self.sensors.clear()
        if self.ego_actor is not None:
            try:
                self.ego_actor.destroy()
            except BaseException as error:
                errors.append(error)
            self.ego_actor = None
        if self.original_settings is not None:
            try:
                self.world.apply_settings(self.original_settings)
            except BaseException as error:
                errors.append(error)
            self.original_settings = None
        if errors:
            raise RuntimeError('Native CARLA owner cleanup failed') from errors[0]
