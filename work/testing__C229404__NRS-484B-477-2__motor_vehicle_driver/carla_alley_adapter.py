"""Lazy CARLA adapter for an operator-reviewed connected alley packet.

The packet is an original source claim that local review must corroborate. A
successful simulation never proves the legal status of the road or blocking.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import threading
import time
from pathlib import Path

from access_measurement import ASSIGNMENT
from parking_controller import ParkingController

VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _triple(value, label):
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError("reviewed alley packet lacks " + label)
    return tuple(float(v) for v in value)


def _source(value, label):
    if not isinstance(value, dict) or not value.get("path") or not value.get("sha256"):
        raise ValueError("reviewed alley packet lacks " + label + " source")
    path = Path(value["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != value["sha256"]:
        raise ValueError("reviewed alley " + label + " source changed")
    return path


def validate_packet(packet_path: Path, case_id: str) -> dict:
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("alley packet exact case mismatch")
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    if packet.get("case_id") != case_id or not packet.get("reviewer"):
        raise ValueError("reviewed alley packet case or reviewer missing")
    if not packet.get("vehicle_blueprint_id") or not packet.get("ego_vehicle_id"):
        raise ValueError("reviewed alley vehicle identity missing")
    _source(packet.get("opendrive_source"), "OpenDRIVE")
    for field in ("highway_source", "alley_classification_source", "cul_de_sac_source",
                  "start_connection_source", "end_connection_source",
                  "property_abutting_source", "driveway_ownership_source",
                  "vehicular_use_source"):
        _source(packet.get(field), field)
    if packet.get("highway_status") is not True or packet.get("cul_de_sac") is not False:
        raise ValueError("qualifying connected highway alley unverified")
    if not packet.get("property_id") or packet.get("access_kind") not in ("driveway", "entrance"):
        raise ValueError("abutting property access identity missing")
    _triple(packet.get("spawn_xyz_m"), "vehicle spawn")
    _triple(packet.get("spawn_rpy_deg"), "vehicle spawn rotation")
    cameras = packet.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("reviewed four-camera plan missing")
    for expected, camera in zip(VIEWS, cameras):
        if (camera.get("name"), camera.get("width"), camera.get("height")) != expected:
            raise ValueError("reviewed camera identity or dimensions differ")
        if not camera.get("pose_source") or not camera.get("reviewer"):
            raise ValueError("reviewed camera pose provenance missing")
        _triple(camera.get("location_xyz_m"), camera["name"] + " position")
        _triple(camera.get("rotation_rpy_deg"), camera["name"] + " rotation")
        if type(camera.get("fov_deg")) not in (int, float) or not 1 <= camera["fov_deg"] <= 170:
            raise ValueError("reviewed camera field of view invalid")
    return packet


def _transform(carla, location, rotation):
    x, y, z = _triple(location, "position")
    roll, pitch, yaw = _triple(rotation, "rotation")
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(roll=roll, pitch=pitch, yaw=yaw))


class CameraBuffer:
    def __init__(self):
        self.condition = threading.Condition()
        self.frames = {}
        self.errors = []

    def receive(self, name, width, height, image):
        try:
            if (type(image.frame) is not int or image.width != width or
                    image.height != height or len(image.raw_data) != width * height * 4):
                raise ValueError("original camera shape or frame invalid")
            from PIL import Image
            rgb = Image.frombytes("RGBA", (width, height), bytes(image.raw_data),
                                  "raw", "BGRA").convert("RGB")
            data = io.BytesIO()
            rgb.save(data, format="PNG")
            with self.condition:
                key = (name, image.frame)
                if key in self.frames:
                    raise ValueError("duplicate original camera frame")
                self.frames[key] = data.getvalue()
                self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.errors.append(error)
                self.condition.notify_all()

    def read(self, name, frame, timeout_s=15):
        deadline = time.monotonic() + timeout_s
        with self.condition:
            while (name, frame) not in self.frames and not self.errors:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("original camera frame missing: " + name)
                self.condition.wait(remaining)
            if self.errors:
                raise ValueError("original camera callback failed: " + str(self.errors[0]))
            return self.frames.pop((name, frame))


class Session:
    native_attested = True

    def __init__(self, client, world, ego, sensors, prior, packet, carla, direction):
        self.client, self.world, self.ego = client, world, ego
        self.sensors, self.prior, self.packet, self.carla = sensors, prior, packet, carla
        self.direction = direction
        self.cameras = CameraBuffer()
        self.controller = None
        self.last = None
        self.last_state = None
        self.restored = False
        self.closed = False
        self.pipeline_capture = None
        self.capture_complete = False
        for name, sensor, width, height in sensors:
            sensor.listen(lambda image, n=name, w=width, h=height:
                          self.cameras.receive(n, w, h, image))

    def get_map_packet(self, case_id):
        if case_id != self.packet["case_id"]:
            raise ValueError("alley case differs from reviewed packet")
        excluded = ("cameras", "opendrive_source", "spawn_xyz_m", "spawn_rpy_deg",
                    "vehicle_blueprint_id", "reviewer")
        packet = {k: v for k, v in self.packet.items() if k not in excluded}
        packet["source_kind"] = "original_native_geometry"
        packet["map_sha256"] = self.packet["opendrive_source"]["sha256"]
        return packet

    def get_opendrive_bytes(self):
        return self.world.get_map().to_opendrive().encode("utf-8")

    def start(self, plan):
        if plan["case_id"] != self.packet["case_id"]:
            raise ValueError("parking plan case differs from reviewed packet")
        self.controller = ParkingController(plan)

    def tick(self):
        if self.controller is None:
            raise ValueError("parking plan not started")
        transform = self.ego.get_transform()
        velocity = self.ego.get_velocity()
        xy = [float(transform.location.x), float(transform.location.y)]
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        before = self.world.get_snapshot()
        control = self.controller.step(xy_m=xy,
                                       yaw_rad=math.radians(transform.rotation.yaw),
                                       speed_mps=speed, time_s=float(before.timestamp.elapsed_seconds))
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=control["throttle"], brake=control["brake"], steer=control["steer"]))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native tick/snapshot frame mismatch")
        self.last = (int(frame), float(snapshot.timestamp.elapsed_seconds))
        self.last_state = control["phase"]
        return {"frame": self.last[0], "time_s": self.last[1]}

    def read_footprint(self, frame):
        if self.last is None or frame != self.last[0]:
            raise ValueError("original vehicle footprint frame mismatch")
        vertices = self.ego.bounding_box.get_world_vertices(self.ego.get_transform())
        xy = [(float(v.x), float(v.y)) for v in vertices]
        if len(xy) != 8:
            raise ValueError("original ego bounding box incomplete")
        # Four unique ground-plane corners; the native box may repeat upper vertices.
        corners = sorted(set((round(x, 6), round(y, 6)) for x, y in xy))
        if len(corners) != 4:
            raise ValueError("original ego ground footprint invalid")
        cx = sum(x for x, _ in corners) / 4
        cy = sum(y for _, y in corners) / 4
        corners.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        return {"frame": frame, "time_s": self.last[1],
                "vehicle_id": self.packet["ego_vehicle_id"],
                "polygon_m": [[x, y] for x, y in corners]}

    def read_activity(self, frame):
        if self.last is None or frame != self.last[0]:
            raise ValueError("original activity frame mismatch")
        velocity = self.ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        phase = {"approach": "approaching", "braking": "stopping",
                 "hold": "parked", "depart": "departing", "done": "departing"}[self.last_state]
        return {"frame": frame, "time_s": self.last[1], "state": phase,
                "speed_mps": float(speed)}

    def read_cameras(self, frame):
        if self.last is None or frame != self.last[0]:
            raise ValueError("original camera time mismatch")
        return {name: {"frame": frame, "time_s": self.last[1],
                       "png": self.cameras.read(name, frame)} for name, _, _, _ in self.sensors}

    def brake(self):
        self.ego.apply_control(self.carla.VehicleControl(throttle=0, brake=1))

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        errors = []
        if self.pipeline_capture is not None:
            try:
                self.pipeline_capture.close(confirmed=self.capture_complete)
            except Exception as error:
                errors.append(error)
        for _, sensor, _, _ in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception as error:
                errors.append(error)
        try:
            self.ego.destroy()
        except Exception as error:
            errors.append(error)
        try:
            self.world.apply_settings(self.prior)
            now = self.world.get_settings()
            self.restored = (now.synchronous_mode == self.prior.synchronous_mode and
                             now.fixed_delta_seconds == self.prior.fixed_delta_seconds and
                             now.no_rendering_mode == self.prior.no_rendering_mode)
            if not self.restored:
                errors.append(ValueError("world settings restoration readback differs"))
        except Exception as error:
            errors.append(error)
        if errors:
            raise RuntimeError("CARLA alley cleanup failed: " + "; ".join(map(str, errors)))


def open_session(case_id: str, packet_path: Path, host: str, port: int,
                 direction: int = 1) -> Session:
    """Connect only to a leased server and return an owned session."""
    packet = validate_packet(packet_path, case_id)
    if direction not in (-1, 1):
        raise ValueError("reviewed alley approach direction invalid")
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    if world.get_settings().no_rendering_mode:
        raise ValueError("Native world rendering disabled")
    loaded = world.get_map().to_opendrive().encode("utf-8")
    if hashlib.sha256(loaded).hexdigest() != packet["opendrive_source"]["sha256"]:
        raise ValueError("loaded OpenDRIVE differs from reviewed alley source")
    prior = world.get_settings()
    ego = None
    sensors = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        vehicle_bp = blueprints.find(packet["vehicle_blueprint_id"])
        vehicle_bp.set_attribute("role_name", "scenario-alley-ego")
        ego = world.try_spawn_actor(vehicle_bp,
                                    _transform(carla, packet["spawn_xyz_m"], packet["spawn_rpy_deg"]))
        if ego is None:
            raise ValueError("reviewed alley ego spawn failed")
        if packet["ego_vehicle_id"] != "ego":
            raise ValueError("reviewed ego role must be ego")
        for camera in packet["cameras"]:
            bp = blueprints.find("sensor.camera.rgb")
            for key, value in (("image_size_x", camera["width"]),
                               ("image_size_y", camera["height"]),
                               ("fov", camera["fov_deg"]), ("sensor_tick", "0.0")):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, _transform(carla, camera["location_xyz_m"],
                                                      camera["rotation_rpy_deg"]))
            sensors.append((camera["name"], sensor, camera["width"], camera["height"]))
        return Session(client, world, ego, sensors, prior, packet, carla, direction)
    except BaseException:
        for _, sensor, _, _ in reversed(sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception:
                pass
        if ego is not None:
            ego.destroy()
        world.apply_settings(prior)
        raise
