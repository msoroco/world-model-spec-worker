"""Lazy CARLA binding for a reviewed C111304 intersection source packet.

The packet must contain numeric original map poses and actor blueprints. This
module does not infer highway status, occupancy, or legal state from map names.
"""
from __future__ import annotations

from copy import deepcopy
import io
import math
import threading
from pathlib import Path

from PIL import Image

from native_acquisition import CAMERAS


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + ' finite source required')
    return float(value)


def _pose(carla, value):
    if not isinstance(value, dict):
        raise ValueError('reviewed transform missing')
    return carla.Transform(
        carla.Location(x=_number(value.get('x'), 'x'),
                       y=_number(value.get('y'), 'y'),
                       z=_number(value.get('z'), 'z')),
        carla.Rotation(yaw=_number(value.get('yaw'), 'yaw'),
                       pitch=_number(value.get('pitch', 0), 'pitch'),
                       roll=_number(value.get('roll', 0), 'roll')))


class CarlaEncounterAdapter:
    """Own both vehicles, visible occupant/property actors and four cameras."""

    def __init__(self, world, carla, site, camera_plan):
        self.world, self.carla, self.site = world, carla, site
        self.camera_plan = camera_plan
        self.owned = []
        self.cameras = {}
        self.images = {name: {} for name in CAMERAS}
        self.condition = threading.Condition()
        self.callback_error = None
        self.original_settings = None
        self.routes = {}
        self.current_frame = None
        self.current_elapsed = None
        self.start_elapsed = None
        self.commands = {}
        self.occupant_vehicle_id = None
        self.occupant_id = None
        self.camera_output = None

    def start(self):
        cameras = self.camera_plan.get('cameras')
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
            raise ValueError('four reviewed camera sources required')
        for name in CAMERAS:
            row = cameras[name]
            if not isinstance(row, dict) or row.get('blueprint_id') != 'sensor.camera.rgb':
                raise ValueError(name + ' reviewed RGB camera source required')
            if type(row.get('width')) is not int or type(row.get('height')) is not int or min(row['width'], row['height']) < 1:
                raise ValueError(name + ' camera dimensions missing')
            _pose(self.carla, row.get('transform'))
        self.original_settings = deepcopy(self.world.get_settings())
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        readback = self.world.get_settings()
        if not readback.synchronous_mode or readback.fixed_delta_seconds != 0.05:
            self.cleanup()
            raise ValueError('20 Hz synchronous world readback failed')

    def _spawn(self, blueprint_id, transform, *, attach_to=None, attributes=None):
        if not isinstance(blueprint_id, str) or not blueprint_id:
            raise ValueError('reviewed actor blueprint missing')
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        for key, value in (attributes or {}).items():
            blueprint.set_attribute(key, str(value))
        pose = _pose(self.carla, transform)
        actor = (self.world.try_spawn_actor(blueprint, pose, attach_to=attach_to)
                 if attach_to is not None else self.world.try_spawn_actor(blueprint, pose))
        if actor is None:
            raise ValueError('reviewed actor spawn failed: ' + blueprint_id)
        self.owned.append(actor)
        return actor

    def spawn_vehicle(self, waypoint, role):
        if role not in ('ego', 'crossing') or not isinstance(waypoint, dict):
            raise ValueError('reviewed lane waypoint missing')
        if not waypoint.get('source_sha256'):
            raise ValueError('lane waypoint source hash missing')
        blueprints = self.site.get('actor_blueprints', {})
        return self._spawn(blueprints.get(role), waypoint.get('transform'))

    def register_occupant(self, vehicle, descriptor):
        if not isinstance(descriptor, dict) or not descriptor.get('source_sha256'):
            raise ValueError('reviewed occupant source missing')
        actor = self._spawn(descriptor.get('blueprint_id'), descriptor.get('relative_transform'), attach_to=vehicle)
        self.occupant_vehicle_id = str(vehicle.id)
        self.occupant_id = actor.id
        return actor

    def spawn_property(self, anchor, offset_m):
        if not isinstance(anchor, dict) or not anchor.get('source_sha256'):
            raise ValueError('reviewed property anchor missing')
        transform = deepcopy(anchor.get('transform'))
        axis = anchor.get('offset_axis_xy')
        if not isinstance(transform, dict) or not isinstance(axis, list) or len(axis) != 2:
            raise ValueError('reviewed property offset axis missing')
        ux, uy = (_number(axis[0], 'property axis'), _number(axis[1], 'property axis'))
        if abs(math.hypot(ux, uy) - 1) > 0.001:
            raise ValueError('property offset axis must be unit length')
        transform['x'] = _number(transform.get('x'), 'property x') + _number(offset_m, 'property offset') * ux
        transform['y'] = _number(transform.get('y'), 'property y') + offset_m * uy
        return self._spawn(anchor.get('blueprint_id'), transform)

    def set_route(self, actor, route, *, target_speed_mps, release_s=0):
        if not isinstance(route, list) or len(route) < 2 or any(
            not isinstance(row, dict) or not row.get('source_sha256') or
            not isinstance(row.get('transform'), dict) for row in route
        ):
            raise ValueError('reviewed route geometry missing')
        speed = _number(target_speed_mps, 'target speed')
        release = _number(release_s, 'release time')
        if speed <= 0 or release < 0:
            raise ValueError('target speed or release time invalid')
        self.routes[actor.id] = {'actor': actor, 'route': route, 'index': 1,
                                 'target_speed_mps': speed, 'release_s': release}

    def start_cameras(self, ego, output: Path | None = None):
        if len(self.routes) != 2 or not self.original_settings:
            raise ValueError('vehicles and synchronous world required before cameras')
        if output is not None:
            if not output.is_dir() or (output / 'cameras').exists():
                raise ValueError('fresh original camera output required')
            self.camera_output = output
            for name in CAMERAS:
                (output / 'cameras' / name).mkdir(parents=True)
        try:
            for name in CAMERAS:
                spec = self.camera_plan['cameras'][name]
                sensor = self._spawn('sensor.camera.rgb', spec['transform'], attach_to=ego,
                                     attributes={'image_size_x': spec['width'],
                                                 'image_size_y': spec['height'],
                                                 'sensor_tick': '0.05'})
                self.cameras[name] = sensor
                sensor.listen(self._callback(name, spec))
        except BaseException:
            self.cleanup()
            raise

    def _callback(self, name, spec):
        def receive(image):
            try:
                if (image.width, image.height) != (spec['width'], spec['height']):
                    raise ValueError(name + ' camera dimensions changed')
                raw = bytes(image.raw_data)
                if len(raw) != image.width * image.height * 4:
                    raise ValueError(name + ' camera BGRA bytes missing')
                picture = Image.frombytes('RGBA', (image.width, image.height), raw,
                                          'raw', 'BGRA')
                stream = io.BytesIO()
                picture.save(stream, format='PNG')
                encoded = stream.getvalue()
                with self.condition:
                    if image.frame in self.images[name]:
                        raise ValueError(name + ' duplicate original camera frame')
                    self.images[name][image.frame] = encoded
                    self.condition.notify_all()
            except BaseException as exc:
                with self.condition:
                    self.callback_error = exc
                    self.condition.notify_all()
        return receive

    def _control(self, item, elapsed):
        actor = item['actor']
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        route = item['route']
        index = item['index']
        target = route[index]['transform']
        dx = _number(target.get('x'), 'route x') - transform.location.x
        dy = _number(target.get('y'), 'route y') - transform.location.y
        if math.hypot(dx, dy) < 2 and index + 1 < len(route):
            index += 1
            item['index'] = index
            target = route[index]['transform']
            dx = _number(target.get('x'), 'route x') - transform.location.x
            dy = _number(target.get('y'), 'route y') - transform.location.y
        heading = math.degrees(math.atan2(dy, dx))
        error = (heading - transform.rotation.yaw + 180) % 360 - 180
        steer = max(-1.0, min(1.0, error / 35))
        active = elapsed >= item['release_s']
        throttle = max(0.0, min(0.6, (item['target_speed_mps'] - speed) * 0.25)) if active else 0.0
        brake = 1.0 if not active else (min(1.0, (speed - item['target_speed_mps']) * 0.25) if speed > item['target_speed_mps'] else 0.0)
        actor.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
        return {'target_speed_mps': item['target_speed_mps'], 'release_s': item['release_s'],
                'throttle': throttle, 'brake': brake, 'steer': steer}

    def tick(self):
        if len(self.cameras) != 4 or len(self.routes) != 2:
            raise ValueError('owned actors and cameras required')
        elapsed = (0.0 if self.current_elapsed is None else
                   self.current_elapsed - self.start_elapsed + 0.05)
        self.commands = {actor_id: self._control(item, elapsed) for actor_id, item in self.routes.items()}
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError('world frame/snapshot mismatch')
        self.current_frame = frame
        self.current_elapsed = float(snapshot.timestamp.elapsed_seconds)
        if self.start_elapsed is None:
            self.start_elapsed = self.current_elapsed
        return frame, self.current_elapsed

    def read_actor(self, actor):
        if self.current_frame is None:
            raise ValueError('original frame missing')
        transform, velocity = actor.get_transform(), actor.get_velocity()
        result = {'original_frame': self.current_frame, 'id': actor.id,
                  'xy': [float(transform.location.x), float(transform.location.y)],
                  'z': float(transform.location.z),
                  'heading_deg': float(transform.rotation.yaw),
                  'speed_mps': math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                  'blueprint': actor.type_id}
        if actor.id == self.occupant_id:
            result['vehicle_id'] = self.occupant_vehicle_id
        return result

    def read_control(self, ego, crossing):
        if self.current_frame is None or ego.id not in self.commands or crossing.id not in self.commands:
            raise ValueError('original control readback missing')
        return {'original_frame': self.current_frame,
                'ego_target_speed_mps': self.commands[ego.id]['target_speed_mps'],
                'crossing_target_speed_mps': self.commands[crossing.id]['target_speed_mps'],
                'crossing_release_s': self.commands[crossing.id]['release_s'],
                'ego_command': self.commands[ego.id],
                'crossing_command': self.commands[crossing.id]}

    def read_camera(self, name):
        if name not in CAMERAS or self.current_frame is None:
            raise ValueError('original camera/frame missing')
        with self.condition:
            if not self.condition.wait_for(lambda: self.callback_error is not None or
                                           self.current_frame in self.images[name], timeout=5):
                raise ValueError(name + ' original camera callback timed out')
            if self.callback_error is not None:
                raise ValueError(name + ' original camera callback failed') from self.callback_error
            encoded = self.images[name].pop(self.current_frame)
            if self.camera_output is not None:
                path = self.camera_output / 'cameras' / name / f'{self.current_frame:06d}.png'
                if path.exists():
                    raise ValueError(name + ' original camera frame already exists')
                path.write_bytes(encoded)
            return self.current_frame, encoded

    def brake(self, ego):
        ego.apply_control(self.carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))

    def destroy(self, actor):
        if actor in self.owned:
            if actor in self.cameras.values():
                actor.stop()
            actor.destroy()
            self.owned.remove(actor)

    def cleanup(self):
        for actor in reversed(tuple(self.owned)):
            self.destroy(actor)
        if self.original_settings is not None:
            self.world.apply_settings(self.original_settings)
            self.original_settings = None
