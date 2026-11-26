"""Lazy CARLA owner for the reviewed railroad crossing capture contract.

Packet construction and site authority are supplied and reviewed locally. The
adapter does not choose a railroad, legal highway, centerline or crossing edge.
"""
from __future__ import annotations

import hashlib
import math
import subprocess
import threading
import time
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def numbers(values, length):
    return (isinstance(values, list) and len(values) == length and
            all(type(v) in (int, float) and math.isfinite(v) for v in values))


def pose(carla, values):
    require(numbers(values, 6), 'reviewed six-coordinate pose required')
    x, y, z, pitch, yaw, roll = values
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


class CarlaRailAdapter:
    def __init__(self, client, packet, case_id, output: Path, *, carla_module=None,
                 graph_root=None, graph_capture_class=None):
        self.client, self.packet, self.case_id = client, packet, case_id
        self.output = Path(output)
        self.carla = carla_module
        self.graph_root = Path(graph_root) if graph_root is not None else None
        self.graph_capture_class = graph_capture_class
        self.graph = None
        self.world = client.get_world()
        self.settings = None
        self.actors, self.sensors, self.encoders = [], [], {}
        self.ego = None
        self.route = None
        self.target_station = None
        self.left_side = None
        self.first_time = None
        self.current_frame = None
        self.tick_index = 0
        self.frames = {}
        self.condition = threading.Condition()
        self.release = None

    def live_opendrive(self):
        return self.world.get_map().to_opendrive()

    def _setup(self, scene):
        setup = self.packet.get('native_setup')
        require(isinstance(setup, dict) and setup.get('reviewed') is True and
                setup.get('reviewer') and setup.get('source_citation') and
                setup.get('map_opendrive_sha256') == scene['map_opendrive_sha256'],
                'separately reviewed rail Native setup required')
        ego = setup.get('ego')
        require(isinstance(ego, dict) and str(ego.get('blueprint', '')).startswith('vehicle.') and
                numbers(ego.get('pose'), 6), 'reviewed ego blueprint/pose required')
        lateral = setup.get('lateral_offsets_m')
        require(isinstance(lateral, dict) and all(type(lateral.get(name)) in (int, float)
                and math.isfinite(lateral[name]) for name in ('left', 'right')) and
                lateral['left'] > 0 and lateral['right'] < 0,
                'reviewed centerline lateral offsets required')
        speed = ego.get('target_speed_mps')
        require(type(speed) in (int, float) and math.isfinite(speed) and 0 < speed <= 15,
                'reviewed target speed required')
        cameras = setup.get('cameras')
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
                'four reviewed camera poses required')
        for name in CAMERAS:
            item = cameras[name]
            require(isinstance(item, dict) and numbers(item.get('pose'), 6) and
                    (item.get('width'), item.get('height')) == SIZES[name] and
                    type(item.get('fov_deg')) in (int, float) and 1 <= item['fov_deg'] <= 170,
                    'reviewed camera profile/pose mismatch: ' + name)
        require(math.hypot(ego['pose'][0] - scene['route_xy'][0][0],
                           ego['pose'][1] - scene['route_xy'][0][1]) <= 5,
                'reviewed ego spawn differs from rail route')
        return setup

    def begin(self, scene, case_id):
        require(case_id == self.case_id == self.packet.get('case_id'),
                'exact reviewed Native rail case mismatch')
        require(hashlib.sha256(self.live_opendrive().encode()).hexdigest() ==
                scene['map_opendrive_sha256'], 'live rail map changed after review')
        if self.carla is None:
            import carla
            self.carla = carla
        self.setup = self._setup(scene)
        self.scene = scene
        self.settings = self.world.get_settings()
        active = self.world.get_settings()
        active.synchronous_mode = True
        active.fixed_delta_seconds = .05
        self.world.apply_settings(active)
        library = self.world.get_blueprint_library()
        for name in CAMERAS:
            item = self.setup['cameras'][name]
            command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                       '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s',
                       f"{item['width']}x{item['height']}", '-r', '20', '-i', 'pipe:0',
                       '-an', '-c:v', 'ffv1', '-threads', '1', '-y',
                       str(self.output / (name + '.mkv'))]
            self.encoders[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                   stderr=subprocess.PIPE)
            bp = library.find('sensor.camera.rgb')
            for key, value in (('image_size_x', item['width']),
                               ('image_size_y', item['height']),
                               ('fov', item['fov_deg']), ('sensor_tick', .05)):
                bp.set_attribute(key, str(value))
            sensor = self.world.spawn_actor(bp, pose(self.carla, item['pose']))
            require(sensor is not None, 'reviewed camera spawn failed: ' + name)
            self.sensors.append(sensor)
            sensor.listen(lambda image, camera=name: self._on_image(camera, image))

    def spawn_vehicle(self, position, role):
        require(role == 'ego' and self.ego is None and self.settings is not None,
                'rail ego spawn sequence invalid')
        item = self.setup['ego']
        actor = self.world.try_spawn_actor(
            self.world.get_blueprint_library().find(item['blueprint']),
            pose(self.carla, item['pose']))
        require(actor is not None, 'reviewed rail ego pose could not spawn')
        self.ego = actor
        self.actors.append(actor)
        if self.graph_root is not None:
            if self.graph_capture_class is None:
                from pipeline_capture import PipelineCapture
                self.graph_capture_class = PipelineCapture
            self.graph = self.graph_capture_class(self.client, actor,
                                                  self.graph_root, self.case_id)
        return actor

    def set_rail_route(self, ego, route, station, left_side):
        require(ego is self.ego and route == self.scene['route_xy'] and
                type(station) in (int, float) and math.isfinite(station) and
                type(left_side) is bool, 'reviewed rail route request invalid')
        self.route, self.target_station, self.left_side = route, station, left_side

    def _on_image(self, camera, image):
        item = self.setup['cameras'][camera]
        require((image.width, image.height) == SIZES[camera],
                'original rail camera dimensions changed')
        with self.condition:
            frame = self.frames.setdefault(image.frame, {})
            require(camera not in frame, 'duplicate original rail camera callback')
            self.encoders[camera].stdin.write(bytes(image.raw_data))
            frame[camera] = True
            self.condition.notify_all()

    def tick(self):
        require(self.ego is not None and self.route is not None,
                'reviewed rail route is not active')
        self._control()
        frame = self.world.tick()
        require(type(frame) is int and (self.current_frame is None or frame == self.current_frame + 1),
                'Native rail world frame gap')
        self.current_frame = frame
        self.tick_index += 1
        return frame

    def _control(self):
        here = self.ego.get_location()
        heading = self.scene['centerline_heading_xy']
        length = math.hypot(*heading)
        tx, ty = heading[0] / length, heading[1] / length
        nx, ny = -ty, tx
        offset = self.setup['lateral_offsets_m']['left' if self.left_side else 'right']
        if self.tick_index <= 100:
            origin = self.scene['centerline_point_xy']
            body_front = self.ego.bounding_box.extent.x + self.ego.bounding_box.location.x
            center_station = self.target_station - body_front
            target = [origin[0] + center_station * tx + offset * nx,
                      origin[1] + center_station * ty + offset * ny]
        else:
            last = self.route[-1]
            target = [last[0] + offset * nx, last[1] + offset * ny]
        distance = math.hypot(target[0] - here.x, target[1] - here.y)
        yaw = math.radians(self.ego.get_transform().rotation.yaw)
        desired = math.atan2(target[1] - here.y, target[0] - here.x)
        error = math.atan2(math.sin(desired - yaw), math.cos(desired - yaw))
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        target_speed = self.setup['ego']['target_speed_mps']
        if self.tick_index <= 100:
            target_speed = min(target_speed, max(.1, distance * 2))
        throttle = min(.6, max(0.0, .3 * (target_speed - speed)))
        brake = min(.6, max(0.0, .3 * (speed - target_speed)))
        if distance < .05:
            throttle, brake = 0.0, 1.0
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=throttle, brake=brake, steer=max(-.8, min(.8, error * .7))))

    def _corners(self):
        box = self.ego.bounding_box
        transform = self.ego.get_transform()
        heading = self.scene['centerline_heading_xy']
        length = math.hypot(*heading)
        tx, ty = heading[0] / length, heading[1] / length
        nx, ny = -ty, tx
        origin = self.scene['centerline_point_xy']
        values = []
        for x in (-box.extent.x, box.extent.x):
            for y in (-box.extent.y, box.extent.y):
                world = transform.transform(self.carla.Location(
                    x=x + box.location.x, y=y + box.location.y,
                    z=box.location.z))
                dx, dy = world.x - origin[0], world.y - origin[1]
                values.append((dx * tx + dy * ty, dx * nx + dy * ny))
        return values

    def sample_original(self, frame, scene):
        require(frame == self.current_frame and scene is self.scene,
                'rail sample/frame context mismatch')
        stamp = self.world.get_snapshot().timestamp.elapsed_seconds
        if self.first_time is None:
            self.first_time = stamp
        if self.graph is not None:
            self.graph.capture(frame, stamp - self.first_time)
        corners = self._corners()
        v = self.ego.get_velocity()
        speed = math.sqrt(v.x**2 + v.y**2 + v.z**2)
        source = hashlib.sha256(repr((frame, stamp, corners, speed)).encode()).hexdigest()
        return {'original_frame': frame, 'time_s': stamp - self.first_time,
                'source_sha256': source, 'body_geometry_sha256': source,
                'motion_sha256': source,
                'crossing_geometry_sha256': scene['crossing_near_edge_source_sha256'],
                'centerline_sha256': scene['centerline_source_sha256'],
                'highway_classification_sha256': scene['highway_status_source_sha256'],
                'rail_carrier_sha256': scene['rail_carrier_source_sha256'],
                'crossing_near_edge_source_sha256': scene['crossing_near_edge_source_sha256'],
                'centerline_source_sha256': scene['centerline_source_sha256'],
                'one_way_highway': scene['one_way_highway'],
                'ego_id': str(self.ego.id),
                'leading_body_station_m': max(v[0] for v in corners),
                'trailing_body_station_m': min(v[0] for v in corners),
                'body_leftmost_lateral_m': max(v[1] for v in corners),
                'body_rightmost_lateral_m': min(v[1] for v in corners),
                'ego_speed_mps': speed}

    def camera_frames(self, frame):
        deadline = time.monotonic() + 10
        with self.condition:
            while set(self.frames.get(frame, {})) != set(CAMERAS):
                remain = deadline - time.monotonic()
                require(remain > 0, 'four original rail camera callbacks missing')
                self.condition.wait(remain)
        return {name: frame for name in CAMERAS}

    def write_camera_video(self, camera, path):
        process = self.encoders[camera]
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        process.stdin = None
        _, error = process.communicate(timeout=60)
        require(process.returncode == 0 and Path(path).is_file() and Path(path).stat().st_size,
                'original rail video encoding failed: ' + error.decode(errors='replace'))

    def close(self, owned=()):
        errors = []
        if self.graph is not None:
            try:
                self.graph.close()
            except Exception as error:
                errors.append(str(error))
        for sensor in reversed(self.sensors):
            try:
                sensor.stop(); sensor.destroy()
            except Exception as error:
                errors.append(str(error))
        for actor in reversed(self.actors):
            try:
                actor.destroy()
            except Exception as error:
                errors.append(str(error))
        for process in self.encoders.values():
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
        if self.settings is not None:
            try:
                self.world.apply_settings(self.settings)
            except Exception as error:
                errors.append(str(error))
        current = self.world.get_settings()
        restored = (self.settings is None or
                    (current.synchronous_mode == self.settings.synchronous_mode and
                     current.fixed_delta_seconds == self.settings.fixed_delta_seconds))
        self.release = {'world_restored': restored, 'actors_released': all(
            not actor.is_alive for actor in self.actors), 'sensors_released': all(
            not sensor.is_alive for sensor in self.sensors),
            'encoders_closed': all(process.poll() is not None for process in self.encoders.values()),
            'errors': errors}
        require(not errors and all(self.release[key] for key in (
            'world_restored', 'actors_released', 'sensors_released',
            'encoders_closed')), 'Native rail owner release/readback failed')

    def release_receipt(self):
        require(self.release is not None, 'Native rail owner has not released')
        return self.release
