"""Lazy CARLA session for an operator-reviewed residential driveway packet.

The reviewed packet identifies original map geometry, district and access
sources, actor spawn transforms, participant routes and four camera poses.
No source claim here is a legal verdict or proof of physical visibility.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import threading
import time
from pathlib import Path

from driveway_construction import survey
from driveway_controller import DrivewayController

CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
SOURCE_FIELDS = ("district_source", "frontage_source", "private_driveway_source",
                 "sidewalk_source", "roadway_source", "connection_source")


def _source(value, label):
    if not isinstance(value, dict) or not value.get("path") or not value.get("sha256"):
        raise ValueError("reviewed source missing: " + label)
    path = Path(value["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != value["sha256"]:
        raise ValueError("reviewed source hash changed: " + label)
    return path


def _triple(value, label):
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("reviewed CARLA pose missing: " + label)
    return tuple(float(v) for v in value)


def validate_packet(path, case_id):
    packet = json.loads(Path(path).read_text())
    if packet.get("case_id") != case_id or not packet.get("reviewer"):
        raise ValueError("reviewed exact driveway packet missing")
    _source(packet.get("opendrive_source"), "OpenDRIVE")
    geometry = packet.get("geometry", {})
    if not isinstance(geometry, dict):
        raise ValueError("reviewed driveway geometry missing")
    for key in SOURCE_FIELDS:
        _source(geometry.get(key), key)
    flat = dict(geometry)
    for key in SOURCE_FIELDS:
        flat[key] = geometry[key]["sha256"]
    flat.update(case_id=case_id, source_kind="original_native_geometry",
                map_sha256=packet["opendrive_source"]["sha256"])
    survey(flat)
    for kind in ("ego", "pedestrian", "roadway_vehicle"):
        actor = packet.get("actors", {}).get(kind)
        if not isinstance(actor, dict) or not actor.get("blueprint_id"):
            raise ValueError("reviewed actor missing: " + kind)
        _triple(actor.get("spawn_xyz_m"), kind + " spawn")
        _triple(actor.get("spawn_rpy_deg"), kind + " rotation")
    cameras = packet.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("reviewed four-camera poses missing")
    for (name, width, height), camera in zip(CAMERAS, cameras):
        if (camera.get("name"), camera.get("width"), camera.get("height")) != (name, width, height):
            raise ValueError("reviewed camera profile differs")
        _source(camera.get("pose_source"), name + " pose")
        _triple(camera.get("location_xyz_m"), name + " camera")
        _triple(camera.get("rotation_rpy_deg"), name + " rotation")
        if type(camera.get("fov_deg")) not in (int, float) or not 1 <= camera["fov_deg"] <= 170:
            raise ValueError("reviewed camera FOV invalid")
    return packet, flat


def _transform(carla, xyz, rpy):
    x, y, z = _triple(xyz, "xyz")
    roll, pitch, yaw = _triple(rpy, "rpy")
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(roll=roll, pitch=pitch, yaw=yaw))


def _speed(actor):
    v = actor.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


class CameraBuffer:
    def __init__(self):
        self.condition = threading.Condition()
        self.frames = {}
        self.errors = []

    def receive(self, name, width, height, image):
        try:
            if (image.width, image.height) != (width, height) or len(image.raw_data) != width * height * 4:
                raise ValueError("original camera shape differs")
            from PIL import Image
            rgb = Image.frombytes("RGBA", (width, height), bytes(image.raw_data), "raw", "BGRA").convert("RGB")
            stream = io.BytesIO()
            rgb.save(stream, format="PNG")
            with self.condition:
                key = name, image.frame
                if key in self.frames:
                    raise ValueError("duplicate original camera frame")
                self.frames[key] = stream.getvalue()
                self.condition.notify_all()
        except BaseException as error:
            with self.condition:
                self.errors.append(error)
                self.condition.notify_all()

    def read(self, name, frame, timeout=15):
        end = time.monotonic() + timeout
        with self.condition:
            while (name, frame) not in self.frames and not self.errors:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise ValueError("original camera frame absent: " + name)
                self.condition.wait(remaining)
            if self.errors:
                raise ValueError("original camera callback failed: " + str(self.errors[0]))
            return self.frames.pop((name, frame))


class Session:
    native_attested = True

    def __init__(self, client, world, carla, packet, geometry, actors, sensors, prior):
        self.client, self.world, self.carla = client, world, carla
        self.packet, self.geometry, self.actors = packet, geometry, actors
        self.sensors, self.prior = sensors, prior
        self.buffer = CameraBuffer()
        self.controller = None
        self.last = None
        self.closed = False
        self.restored = False
        self.capture_complete = False
        self.pipeline_capture = None
        for name, sensor, width, height in sensors:
            sensor.listen(lambda image, n=name, w=width, h=height:
                          self.buffer.receive(n, w, h, image))

    def geometry_packet(self, case_id):
        if case_id != self.geometry["case_id"]:
            raise ValueError("exact original case differs")
        return self.geometry

    def opendrive_bytes(self):
        return self.world.get_map().to_opendrive().encode("utf-8")

    def start(self, plan):
        if plan["case_id"] != self.geometry["case_id"]:
            raise ValueError("exact controller plan differs")
        self.controller = DrivewayController(plan)
        self.plan = plan

    def _participant_control(self, actor, route, speed_mps):
        transform = actor.get_transform()
        x, y = transform.location.x, transform.location.y
        end = route[-1]
        target_yaw = math.atan2(end[1] - y, end[0] - x)
        if actor.type_id.startswith("walker."):
            direction = self.carla.Vector3D(x=math.cos(target_yaw), y=math.sin(target_yaw), z=0)
            actor.apply_control(self.carla.WalkerControl(direction=direction, speed=speed_mps))
        else:
            err = (target_yaw - math.radians(transform.rotation.yaw) + math.pi) % (2 * math.pi) - math.pi
            actor.apply_control(self.carla.VehicleControl(
                throttle=max(0.0, min(0.45, .25 * (speed_mps - _speed(actor)))),
                brake=max(0.0, min(.8, .3 * (_speed(actor) - speed_mps))),
                steer=max(-1.0, min(1.0, err))))

    def tick(self):
        if self.controller is None:
            raise ValueError("original controller has not started")
        ego = self.actors["ego"]
        transform = ego.get_transform()
        point = (transform.location.x, transform.location.y)
        ped = self.actors.get("pedestrian")
        road = self.actors.get("roadway_vehicle")
        # Controller guard distances are engineering settings only; the saved
        # audit uses observed participant bodies and does not equate them to law.
        ped_clear = ped is None or math.dist(point, (ped.get_location().x, ped.get_location().y)) > 5
        road_clear = road is None or math.dist(point, (road.get_location().x, road.get_location().y)) > 8
        control = self.controller.step(point, math.radians(transform.rotation.yaw),
                                       _speed(ego), ped_clear, road_clear)
        ego.apply_control(self.carla.VehicleControl(throttle=control["throttle"],
                                                     brake=control["brake"], steer=control["steer"]))
        if ped is not None:
            self._participant_control(ped, self.plan["pedestrian_route_xy_m"], 1.1)
        if road is not None:
            route = self.plan["roadway_approaches"][self.plan["active_roadway_direction"]]["route_xy_m"]
            self._participant_control(road, route, 3.0)
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("original Native tick/snapshot frame differs")
        self.last = int(frame), float(snapshot.timestamp.elapsed_seconds)
        return {"frame": self.last[0], "time_s": self.last[1]}

    def activity(self, frame):
        if self.last is None or self.last[0] != frame:
            raise ValueError("original activity frame differs")
        def packet(actor, source, **extra):
            t = actor.get_transform()
            return {"actor_id": str(actor.id), "xy_m": [float(t.location.x), float(t.location.y)],
                    "speed_mps": float(_speed(actor)), "source": source, **extra}
        row = {"frame": frame, "time_s": self.last[1],
               "ego": packet(self.actors["ego"], "original_native_vehicle_state")}
        ped = self.actors.get("pedestrian")
        road = self.actors.get("roadway_vehicle")
        row["pedestrian"] = packet(ped, "original_native_walker_state") if ped else None
        row["roadway_vehicle"] = (packet(road, "original_native_vehicle_state",
                                          approach_direction=self.plan["active_roadway_direction"])
                                   if road else None)
        return row

    def cameras(self, frame):
        if self.last is None or self.last[0] != frame:
            raise ValueError("original camera frame differs")
        return {name: {"frame": frame, "time_s": self.last[1],
                       "png": self.buffer.read(name, frame)} for name, _, _, _ in self.sensors}

    def brake(self):
        self.actors["ego"].apply_control(self.carla.VehicleControl(throttle=0, brake=1))

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        if self.pipeline_capture is not None:
            try:
                self.pipeline_capture.close(confirmed=self.capture_complete)
            except BaseException as error:
                errors.append(error)
        for _, sensor, _, _ in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as error:
                errors.append(error)
        for actor in self.actors.values():
            try:
                actor.destroy()
            except BaseException as error:
                errors.append(error)
        try:
            self.world.apply_settings(self.prior)
            settings = self.world.get_settings()
            self.restored = (settings.synchronous_mode == self.prior.synchronous_mode and
                             settings.fixed_delta_seconds == self.prior.fixed_delta_seconds and
                             settings.no_rendering_mode == self.prior.no_rendering_mode)
            if not self.restored:
                errors.append(ValueError("original world restoration readback differs"))
        except BaseException as error:
            errors.append(error)
        if errors:
            raise RuntimeError("CARLA driveway cleanup failed: " + "; ".join(map(str, errors)))


def open_session(case, packet_path, host, port, spawn_offset_m=0):
    packet, geometry = validate_packet(packet_path, case["case_id"])
    if not 0 <= spawn_offset_m <= .75:
        raise ValueError("fallback ego spawn offset outside surveyed envelope")
    # CARLA is imported only for the GPU command. CPU proofs use fake sessions.
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(20)
    world = client.get_world()
    if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != geometry["map_sha256"]:
        raise ValueError("live map differs from reviewed original OpenDRIVE")
    prior = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = .05
    settings.no_rendering_mode = False
    world.apply_settings(settings)
    actors = {}
    sensors = []
    try:
        library = world.get_blueprint_library()
        for kind in ("ego", "pedestrian", "roadway_vehicle"):
            if kind == "pedestrian" and case["world_setup"]["pedestrian"] == "pedestrian_absent":
                continue
            if kind == "roadway_vehicle" and case["world_setup"]["roadway_vehicle"] == "roadway_clear":
                continue
            spec = packet["actors"][kind]
            blueprint = library.find(spec["blueprint_id"])
            spawn = list(spec["spawn_xyz_m"])
            if kind == "ego":
                spawn[2] += spawn_offset_m
            transform = _transform(carla, spawn, spec["spawn_rpy_deg"])
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError("original actor spawn failed: " + kind)
            actors[kind] = actor
        geometry["ego_vehicle_id"] = str(actors["ego"].id)
        for camera in packet["cameras"]:
            blueprint = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", camera["width"]),
                               ("image_size_y", camera["height"]),
                               ("fov", camera["fov_deg"])):
                blueprint.set_attribute(key, str(value))
            sensor = world.spawn_actor(blueprint, _transform(carla, camera["location_xyz_m"],
                                                              camera["rotation_rpy_deg"]))
            sensors.append((camera["name"], sensor, camera["width"], camera["height"]))
        return Session(client, world, carla, packet, geometry, actors, sensors, prior)
    except BaseException:
        for _, sensor, _, _ in reversed(sensors):
            sensor.destroy()
        for actor in actors.values():
            actor.destroy()
        world.apply_settings(prior)
        raise
