"""Lazy CARLA adapter for source-gated crosswalk parking construction.

The world and CARLA API are injected so CPU tests can exercise calls. Original
crosswalk and residence sources must be supplied by local site review.
"""
from __future__ import annotations

import hashlib
import io
import math
import threading
import time

from PIL import Image

from crosswalk import require
from native_capture import CAMERAS, CAMERA_SIZES


def spawn_reviewed_cameras(world, api, site, camera_plan):
    """Spawn original RGB sensors at separately reviewed, fixed site poses."""
    poses = site.get('camera_poses')
    require(isinstance(poses, dict) and set(poses) == set(CAMERAS) and
            site.get('camera_pose_review_sha256'), 'reviewed four-camera poses required')
    require([c['name'] for c in camera_plan] == list(CAMERAS), 'camera plan identity mismatch')
    sensors = {}
    try:
        for spec in camera_plan:
            name = spec['name']
            width, height = CAMERA_SIZES[name]
            require((spec['width'], spec['height']) == (width, height),
                    'camera plan dimensions mismatch')
            pose = poses[name]
            require(set(pose) == {'x', 'y', 'z', 'pitch', 'yaw', 'roll'} and
                    all(math.isfinite(float(v)) for v in pose.values()),
                    'reviewed camera transform invalid')
            blueprint = world.get_blueprint_library().find('sensor.camera.rgb')
            blueprint.set_attribute('image_size_x', str(width))
            blueprint.set_attribute('image_size_y', str(height))
            blueprint.set_attribute('fov', str(spec['fov_deg']))
            transform = api.Transform(api.Location(x=pose['x'], y=pose['y'], z=pose['z']),
                                      api.Rotation(pitch=pose['pitch'], yaw=pose['yaw'], roll=pose['roll']))
            sensor = world.spawn_actor(blueprint, transform)
            require(sensor is not None and sensor.id, 'Native camera spawn failed')
            sensors[name] = sensor
        return sensors
    except Exception:
        for sensor in sensors.values():
            sensor.destroy()
        raise


class CarlaCrosswalkAdapter:
    def __init__(self, world, api, *, case_id, cameras=None, exception_packet=None, timeout_s=3.0):
        self.world, self.api = world, api
        self.cameras = {} if cameras is None else dict(cameras)
        self.exception_packet = exception_packet
        self.timeout_s = timeout_s
        self.owned = []
        self.vehicle = None
        require(isinstance(case_id, str) and case_id, 'exact case identity required')
        self.case_id = case_id
        self.route = None
        self.action = None
        self.destination = None
        self.exception = 'none'
        self.target_index = 1
        self.frame = None
        self.last_snapshot = None
        self.at_end = False
        self.images = {name: {} for name in CAMERAS}
        self.condition = threading.Condition()
        self.closed = False
        if cameras is not None:
            require(set(cameras) == set(CAMERAS), 'four original RGB cameras required')
            for name, sensor in self.cameras.items():
                require(getattr(sensor, 'type_id', None) == 'sensor.camera.rgb', 'original RGB camera required')
                attrs = sensor.attributes
                width, height = CAMERA_SIZES[name]
                require(str(attrs.get('image_size_x')) == str(width) and
                        str(attrs.get('image_size_y')) == str(height), 'original camera profile mismatch')
                sensor.listen(lambda image, key=name: self._receive(key, image))

    def _receive(self, name, image):
        with self.condition:
            if not self.closed and type(getattr(image, 'frame', None)) is int:
                self.images[name][image.frame] = image
                self.condition.notify_all()

    def verify_crosswalk(self, site):
        native_map = self.world.get_map()
        require(native_map.name == site['map_name'], 'Native map mismatch')
        opendrive = native_map.to_opendrive().encode()
        require(site.get('native_opendrive_sha256') == hashlib.sha256(opendrive).hexdigest(),
                'reviewed Native road-map digest required')
        require(site.get('frontage_review_sha256') and site.get('highway_review_sha256'),
                'residence district and highway source reviews required')
        points = [(float(p.x), float(p.y)) for p in native_map.get_crosswalks()]
        require(points, 'Native map has no crosswalk geometry')
        for x, y in site['crosswalk_polygon']:
            require(any(math.hypot(x-px, y-py) <= 0.5 for px, py in points),
                    'reviewed polygon differs from Native crosswalk')
        for x, y in site['parking_route']:
            loc = self.api.Location(x=float(x), y=float(y), z=0.0)
            require(native_map.get_waypoint(loc, project_to_road=False) is not None,
                    'parking route leaves Native road')
        self.site = site
        return {'map_name': native_map.name, 'crosswalk_polygon': site['crosswalk_polygon']}

    def spawn_vehicle(self, vehicle, start):
        require(vehicle['blueprint'].startswith('vehicle.'), 'vehicle blueprint required')
        bp = self.world.get_blueprint_library().find(vehicle['blueprint'])
        require(bp.id == vehicle['blueprint'], 'Native blueprint mismatch')
        point = self.world.get_map().get_waypoint(self.api.Location(x=float(start[0]),
                                                             y=float(start[1]), z=0.0),
                                                  project_to_road=False)
        require(point is not None, 'Native vehicle start off road')
        ego = self.world.try_spawn_actor(bp, point.transform)
        require(ego is not None and type(ego.id) is int, 'Native ego spawn failed')
        ego.set_autopilot(False)
        self.vehicle = ego
        self.owned.append(ego)
        return {'actor_id': str(ego.id), 'blueprint': bp.id}

    def configure_route(self, actor_id, route, destination, action):
        require(self.vehicle and str(self.vehicle.id) == actor_id, 'Native subject mismatch')
        require(destination in {'on', 'off'} and action in {'stop', 'stand', 'park'},
                'crosswalk route case invalid')
        require(len(route) >= 2, 'route missing')
        self.route = [[float(x), float(y)] for x, y in route]
        if destination == 'off':
            start, end = self.route[-2:]
            length = math.hypot(end[0]-start[0], end[1]-start[1])
            require(length >= 8.0, 'off-crosswalk approach too short for separated stop')
            self.route[-1] = [end[0]-6.0*(end[0]-start[0])/length,
                              end[1]-6.0*(end[1]-start[1])/length]
        self.destination, self.action = destination, action
        self.target_index = 1

    def configure_exception(self, actor_id, exception):
        require(self.vehicle and str(self.vehicle.id) == actor_id, 'Native subject mismatch')
        require(exception in {'none', 'traffic_conflict', 'law', 'police_direction', 'device_direction'},
                'unknown exception')
        if exception != 'none':
            packet = self.exception_packet
            require(isinstance(packet, dict) and packet.get('kind') == exception and
                    packet.get('source_id') and packet.get('source_sha256') and
                    packet.get('reviewed_instruction_sha256'), 'reviewed exception packet required')
            require(type(packet.get('first_frame')) is int and
                    type(packet.get('last_frame')) is int and
                    packet['first_frame'] <= packet['last_frame'], 'exception source window required')
            if exception == 'traffic_conflict':
                require(type(packet.get('other_actor_id')) is int, 'conflicting Native actor required')
            if exception == 'police_direction':
                require(type(packet.get('officer_actor_id')) is int,
                        'original police actor source required')
            if exception == 'device_direction':
                require(type(packet.get('native_object_id')) is int and
                        any(obj.id == packet['native_object_id'] for obj in self.world.get_environment_objects()),
                        'original official device source required')
        self.exception = exception

    def _control(self):
        require(self.vehicle is not None and self.route, 'Native route not configured')
        pose = self.vehicle.get_transform()
        velocity = self.vehicle.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        require(math.isfinite(speed), 'Native velocity invalid')
        here = pose.location
        target = self.route[self.target_index]
        distance = math.hypot(target[0]-here.x, target[1]-here.y)
        if distance < 1.5 and self.target_index < len(self.route)-1:
            self.target_index += 1
            target = self.route[self.target_index]
            distance = math.hypot(target[0]-here.x, target[1]-here.y)
        at_end = self.target_index == len(self.route)-1 and distance < 1.5
        if at_end:
            control = self.api.VehicleControl(throttle=0.0, brake=1.0,
                                              hand_brake=self.action == 'park')
        else:
            bearing = math.degrees(math.atan2(target[1]-here.y, target[0]-here.x))
            error = (bearing - pose.rotation.yaw + 180) % 360 - 180
            control = self.api.VehicleControl(throttle=max(0.0, min(0.5, (4.0-speed)*0.2)),
                                              brake=max(0.0, min(1.0, (speed-4.0)*0.3)),
                                              steer=max(-0.8, min(0.8, error/45)))
        self.vehicle.apply_control(control)
        return at_end

    def tick(self):
        self.at_end = self._control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        require(snapshot.frame == frame and math.isfinite(snapshot.timestamp.elapsed_seconds),
                'Native snapshot identity mismatch')
        self.frame, self.last_snapshot = frame, snapshot
        return {'frame': frame, 'time_s': snapshot.timestamp.elapsed_seconds}

    def read_subject(self, actor_id, frame):
        require(self.vehicle and str(self.vehicle.id) == actor_id and frame == self.frame,
                'Native subject frame mismatch')
        actor = self.vehicle
        transform = actor.get_transform()
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        require(math.isfinite(speed), 'Native speed invalid')
        box = actor.bounding_box
        corners = box.get_world_vertices(transform)
        require(len(corners) == 8, 'Native body corners missing')
        polygon = list({(round(float(p.x), 5), round(float(p.y), 5)) for p in corners})
        require(len(polygon) == 4, 'Native body footprint vertices invalid')
        polygon = [list(p) for p in polygon]
        cx = sum(p[0] for p in polygon)/4
        cy = sum(p[1] for p in polygon)/4
        polygon.sort(key=lambda p: math.atan2(p[1]-cy, p[0]-cx))
        flags = {'traffic_conflict': False, 'law_direction': False,
                 'police_direction': False, 'device_direction': False}
        packet = self.exception_packet
        if self.exception != 'none' and packet['first_frame'] <= frame <= packet['last_frame']:
            active = True
            if self.exception == 'traffic_conflict':
                other = self.world.get_actor(packet['other_actor_id'])
                require(other is not None, 'conflicting Native actor missing')
                other_pose = other.get_transform().location
                other_velocity = other.get_velocity()
                gap = math.hypot(other_pose.x-transform.location.x,
                                other_pose.y-transform.location.y)
                moving = math.hypot(other_velocity.x, other_velocity.y) > 0.5
                active = gap < 8 and moving
            elif self.exception == 'police_direction':
                active = self.world.get_actor(packet['officer_actor_id']) is not None
            key = {'traffic_conflict': 'traffic_conflict', 'law': 'law_direction',
                   'police_direction': 'police_direction',
                   'device_direction': 'device_direction'}[self.exception]
            flags[key] = active
        return {'frame': frame, 'case_id': self.case_id, 'subject_id': actor_id,
                'speed_mps': speed, 'halt_activity': self.action if self.at_end and speed < 0.1 else 'travel',
                'body_corners_xy': polygon, 'crosswalk_id': self.site['crosswalk_id'],
                'marking_status': self.site['marking_status'], **flags}

    def read_cameras(self, frame):
        require(frame == self.frame and set(self.cameras) == set(CAMERAS),
                'Native camera frame or sensors missing')
        deadline = time.monotonic() + self.timeout_s
        with self.condition:
            while not all(frame in self.images[name] for name in CAMERAS):
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'original Native camera callback missing')
                self.condition.wait(remaining)
            captured = {name: self.images[name].pop(frame) for name in CAMERAS}
        result = {}
        for name, image in captured.items():
            width, height = CAMERA_SIZES[name]
            require((image.width, image.height) == (width, height) and
                    abs(image.timestamp-self.last_snapshot.timestamp.elapsed_seconds) <= 0.001,
                    'Native camera timestamp or dimensions mismatch')
            raw = bytes(image.raw_data)
            require(len(raw) == width*height*4, 'Native camera BGRA length mismatch')
            output = io.BytesIO()
            Image.frombytes('RGB', (width, height), raw, 'raw', 'BGRX').save(output, format='PNG')
            result[name] = {'frame': frame, 'source_id': str(self.cameras[name].id),
                            'png_bytes': output.getvalue()}
        return result

    def brake(self, actor_id):
        if self.vehicle and str(self.vehicle.id) == actor_id:
            self.vehicle.apply_control(self.api.VehicleControl(throttle=0, brake=1))

    def cleanup(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        for actor in reversed(self.owned):
            if hasattr(actor, 'stop'):
                actor.stop()
            actor.destroy()
        self.owned.clear()
