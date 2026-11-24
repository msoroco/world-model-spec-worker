"""Own a source-bound CARLA vehicle and four original camera sensors.

The reviewed packet selects a loaded map, actor, straight approach and camera
poses. It never supplies a legal conclusion. CARLA is imported only when a
Native capture is explicitly launched.
"""
from __future__ import annotations

from contextlib import contextmanager
import io
import json
import math
import threading
import time
from pathlib import Path

from native_map import bind


VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _triple(value, name):
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(item) not in (int, float) or not math.isfinite(item)
                for item in value)):
        raise ValueError("Reviewed Native packet lacks finite " + name)
    return tuple(float(item) for item in value)


def validate_packet(packet_path):
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    if not packet.get("vehicle_blueprint_id") or not packet.get("reviewer"):
        raise ValueError("Reviewed Native actor selection is missing")
    spawn = packet.get("vehicle_spawn_world")
    if not isinstance(spawn, dict):
        raise ValueError("Reviewed Native vehicle spawn is missing")
    _triple(spawn.get("location_xyz_m"), "vehicle spawn location")
    _triple(spawn.get("rotation_rpy_deg"), "vehicle spawn rotation")
    transform = packet.get("local_transform")
    if not isinstance(transform, dict):
        raise ValueError("Reviewed Native local transform is missing")
    _triple(transform.get("origin_xyz_m"), "local transform origin")
    if type(transform.get("yaw_deg")) not in (int, float) or not math.isfinite(transform["yaw_deg"]):
        raise ValueError("Reviewed Native local transform yaw is missing")
    cameras = packet.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        raise ValueError("Reviewed four-camera plan is missing")
    for (name, width, height), camera in zip(VIEWS, cameras):
        if (camera.get("name") != name or camera.get("width") != width or
                camera.get("height") != height or
                camera.get("attachment") not in ("world", "ego") or
                not camera.get("pose_source_citation") or not camera.get("reviewer")):
            raise ValueError("Reviewed four-camera identity, size or provenance differs")
        _triple(camera.get("location_xyz_m"), name + " camera location")
        _triple(camera.get("rotation_rpy_deg"), name + " camera rotation")
        fov = camera.get("fov_deg")
        if type(fov) not in (int, float) or not 1 <= fov <= 170:
            raise ValueError("Reviewed camera field of view is invalid")
    return packet


def _transform(carla, location, rotation):
    x, y, z = _triple(location, "world position")
    roll, pitch, yaw = _triple(rotation, "world rotation")
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(roll=roll, pitch=pitch, yaw=yaw))


class _CameraFrames:
    def __init__(self):
        self.condition = threading.Condition()
        self.frames = {}
        self.errors = []

    def receive(self, name, width, height, image):
        try:
            if (type(image.frame) is not int or image.frame < 0 or
                    image.width != width or image.height != height or
                    len(image.raw_data) != width * height * 4):
                raise ValueError("Original Native camera frame size or identity differs")
            from PIL import Image
            rgb = Image.frombytes("RGBA", (width, height), bytes(image.raw_data),
                                  "raw", "BGRA").convert("RGB")
            stream = io.BytesIO()
            rgb.save(stream, format="PNG")
            with self.condition:
                key = (name, image.frame)
                if key in self.frames:
                    raise ValueError("Duplicate original Native camera frame")
                self.frames[key] = stream.getvalue()
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
                    raise ValueError("Original Native camera frame missing: " + name)
                self.condition.wait(remaining)
            if self.errors:
                raise ValueError("Original Native camera callback failed: " + str(self.errors[0]))
            return frame, self.frames.pop((name, frame))


def _actor_source(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    location = transform.location
    return {"actor_id": str(actor.id), "type_id": actor.type_id,
            "location_xyz_m": [float(location.x), float(location.y), float(location.z)],
            "heading_deg": float(transform.rotation.yaw),
            "velocity_xyz_mps": [float(velocity.x), float(velocity.y), float(velocity.z)]}


class Session:
    def __init__(self, client, world, ego, sensors, previous_settings, packet, case_id, carla):
        self.client, self.world, self.ego, self.sensors = client, world, ego, sensors
        self.previous_settings = previous_settings
        self.packet, self.case_id, self.carla = packet, case_id, carla
        self.restored = False
        self.frames = _CameraFrames()
        self.attempt_id = case_id + "-native-original"
        self.recording_id = case_id + "-pending-review"
        for name, sensor, width, height in sensors:
            sensor.listen(lambda image, name=name, width=width, height=height:
                          self.frames.receive(name, width, height, image))

    def world_to_local(self, transform):
        origin = self.packet["local_transform"]["origin_xyz_m"]
        angle = math.radians(float(self.packet["local_transform"]["yaw_deg"]))
        dx = float(transform.location.x) - origin[0]
        dy = float(transform.location.y) - origin[1]
        x = dx * math.cos(angle) + dy * math.sin(angle)
        y = -dx * math.sin(angle) + dy * math.cos(angle)
        heading = float(transform.rotation.yaw) - math.degrees(angle)
        return x, y, heading

    def read_camera(self, name, frame):
        return self.frames.read(name, frame)

    def read_context(self, frame):
        actors = self.world.get_actors()
        participants = []
        directions = {}
        for actor in actors:
            if actor.id == self.ego.id or actor.type_id.startswith(("vehicle.", "walker.pedestrian.")):
                participants.append(_actor_source(actor))
            if actor.type_id.startswith("traffic.traffic_light"):
                state = actor.get_state()
                directions[str(actor.id)] = {"kind": "native_traffic_light",
                                              "state": str(state),
                                              "source_actor": _actor_source(actor)}
        return {"world_frame": frame, "participants": participants,
                "directions": directions,
                "police_direction_judgment": "unresolved_from_original_pixels",
                "necessity_judgment": "unresolved"}

    def close(self):
        errors = []
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
            self.world.apply_settings(self.previous_settings)
            current = self.world.get_settings()
            self.restored = (current.synchronous_mode == self.previous_settings.synchronous_mode and
                             current.no_rendering_mode == self.previous_settings.no_rendering_mode and
                             current.fixed_delta_seconds == self.previous_settings.fixed_delta_seconds)
            if not self.restored:
                errors.append(ValueError("Native world settings differ after restoration"))
        except Exception as error:
            errors.append(error)
        if errors:
            raise RuntimeError("Native cleanup/restoration failed: " + "; ".join(map(str, errors)))


@contextmanager
def open_session(case_id, packet_path, host, port):
    """Connect only to the leased server; restore exactly the settings we changed."""
    packet = validate_packet(packet_path)
    import carla
    client = carla.Client(host, int(port))
    client.set_timeout(30.0)
    world = client.get_world()
    bind(world, packet_path, case_id)
    previous = world.get_settings()
    if previous.no_rendering_mode:
        raise ValueError("Native world rendering is disabled")
    ego = None
    sensors = []
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        vehicle = blueprints.find(packet["vehicle_blueprint_id"])
        if vehicle is None:
            raise ValueError("Reviewed vehicle blueprint absent")
        vehicle.set_attribute("role_name", "scenario-intersection-ego")
        spawn = packet["vehicle_spawn_world"]
        ego = world.try_spawn_actor(vehicle, _transform(carla, spawn["location_xyz_m"],
                                                      spawn["rotation_rpy_deg"]))
        if ego is None:
            raise ValueError("Reviewed intersection vehicle spawn failed")
        extent = ego.bounding_box.extent
        if (abs(2 * extent.x - packet["vehicle_length_m"]) > 0.15 or
                abs(2 * extent.y - packet["vehicle_width_m"]) > 0.15):
            raise ValueError("Native vehicle dimensions differ from reviewed packet")
        for camera in packet["cameras"]:
            blueprint = blueprints.find("sensor.camera.rgb")
            for key, value in (("image_size_x", camera["width"]),
                               ("image_size_y", camera["height"]),
                               ("fov", camera["fov_deg"]), ("sensor_tick", "0.0")):
                blueprint.set_attribute(key, str(value))
            pose = _transform(carla, camera["location_xyz_m"],
                              camera["rotation_rpy_deg"])
            options = {"attach_to": ego} if camera["attachment"] == "ego" else {}
            sensor = world.spawn_actor(blueprint, pose, **options)
            if sensor is None:
                raise ValueError("Native camera spawn failed: " + camera["name"])
            sensors.append((camera["name"], sensor, camera["width"], camera["height"]))
        session = Session(client, world, ego, sensors, previous, packet, case_id, carla)
        try:
            yield session
        finally:
            session.close()
    except Exception:
        if ego is not None and not isinstance(locals().get("session"), Session):
            for _, sensor, _, _ in reversed(sensors):
                try:
                    sensor.stop()
                    sensor.destroy()
                except Exception:
                    pass
            ego.destroy()
        world.apply_settings(previous)
        raise
