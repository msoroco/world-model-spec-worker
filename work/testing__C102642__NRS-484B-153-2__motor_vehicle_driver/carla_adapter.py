"""Lazy CARLA adapter for original door-action capture.

The operator supplies a surveyed packet, a world and an independent driver-act
observer. The observer must report original board/alight and door vertices;
commands alone cannot establish a measured action.
"""
from __future__ import annotations

import io
import math
import threading
from pathlib import Path

from PIL import Image

from door_interaction import request_door_open


CAMERA_SIZE = {"front": (1920, 1080), "rear": (1280, 720),
               "left": (1280, 720), "right": (1280, 720)}


class CarlaDoorAdapter:
    def __init__(self, world, carla_module, *, map_sha256, actor_factory,
                 driver_act_controller, original_observer):
        self.world = world
        self.carla = carla_module
        self._map_sha256 = map_sha256
        self.actor_factory = actor_factory
        self.driver_act_controller = driver_act_controller
        self.original_observer = original_observer
        self.owned = []
        self.frames = {}
        self.condition = threading.Condition()
        self.site = None
        self.parked = None
        self.passing = None
        self.driver = None
        self.pending_act = None
        self.camera_sensor_ids = {}

    def map_sha256(self):
        # Source reader must hash the loaded original map, not its display name.
        return self._map_sha256()

    def configure_site(self, packet, site):
        if self.map_sha256() != packet["map_sha256"] or site["loading_site_id"] != packet["loading_site_id"]:
            raise ValueError("surveyed Native site readback mismatch")
        self.site = site

    def _spawn(self, role, packet, variant=None):
        actor = self.actor_factory(role, packet, variant)
        if actor is None or not getattr(actor, "id", None) or not actor.is_alive:
            raise ValueError("Native actor spawn/readback failed: " + role)
        self.owned.append(actor)
        return actor

    def spawn_parked(self, packet):
        self.parked = self._spawn("parked", packet)
        return self.parked

    def spawn_passing(self, packet, variant):
        self.passing = self._spawn("passing", packet, variant)
        return self.passing

    def spawn_driver(self, packet):
        self.driver = self._spawn("driver", packet)
        if len({self.parked.id, self.passing.id, self.driver.id}) != 3:
            raise ValueError("Native actor identity collision")
        return self.driver

    def attach_cameras(self, parked, views):
        if parked is not self.parked or set(views) != set(CAMERA_SIZE):
            raise ValueError("four original parked-vehicle cameras required")
        library = self.world.get_blueprint_library()
        for view in views:
            sensor_bp = library.find("sensor.camera.rgb")
            width, height = CAMERA_SIZE[view]
            sensor_bp.set_attribute("image_size_x", str(width))
            sensor_bp.set_attribute("image_size_y", str(height))
            sensor_bp.set_attribute("fov", "90")
            # Local review must verify these views cover the act and passing body.
            yaw = {"front": 0, "rear": 180, "left": -90, "right": 90}[view]
            transform = self.carla.Transform(self.carla.Location(x=0, z=2.2),
                                             self.carla.Rotation(yaw=yaw))
            sensor = self.world.spawn_actor(sensor_bp, transform, attach_to=parked)
            if sensor is None or not sensor.is_alive:
                raise ValueError("Native camera spawn/readback failed: " + view)
            self.owned.append(sensor)
            self.camera_sensor_ids[view] = sensor.id
            sensor.listen(lambda image, name=view: self._receive(name, image))

    def _receive(self, view, image):
        if view not in CAMERA_SIZE or type(image.frame) is not int:
            return
        with self.condition:
            self.frames[(view, image.frame)] = image
            self.condition.notify_all()

    def command_act(self, driver, parked, act, side):
        if driver is not self.driver or parked is not self.parked or side not in ("left", "right"):
            raise ValueError("selected original driver or door side mismatch")
        if act == "open":
            request_door_open(parked, self.carla, side)
        elif act in ("board", "alight"):
            if not self.driver_act_controller(driver, parked, act, side):
                raise ValueError("original driver act controller refused")
        else:
            raise ValueError("unsupported driver act")
        self.pending_act = (act, side)

    def tick(self):
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if frame != snapshot.frame:
            raise ValueError("Native world tick/snapshot mismatch")
        return frame, float(snapshot.timestamp.elapsed_seconds)

    def observe(self, frame_id, driver, parked, passing):
        if (driver, parked, passing) != (self.driver, self.parked, self.passing):
            raise ValueError("Native participant identity changed")
        for actor in (driver, parked, passing):
            if not actor.is_alive:
                raise ValueError("Native participant disappeared")
        raw = self.original_observer(frame_id, driver, parked, passing, self.pending_act)
        if not isinstance(raw, dict) or raw.get("source_frame_id") != frame_id:
            raise ValueError("original act observer frame mismatch")
        if raw.get("selected_driver_id") != str(driver.id):
            raise ValueError("original driver-act source identity mismatch")
        if raw.get("observed_act") not in ("none", "open", "board", "alight"):
            raise ValueError("original observed driver act missing")
        if raw["observed_act"] != "none" and self.pending_act != (raw["observed_act"], raw.get("act_side")):
            raise ValueError("observed act differs from issued selection")
        # Passing center/speed come from Native actor state, not a case label.
        loc = passing.get_location()
        vel = passing.get_velocity()
        values = (loc.x, loc.y, vel.x, vel.y)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("nonfinite original passing state")
        raw["passing_center_xy"] = [float(loc.x), float(loc.y)]
        raw["passing_speed_mps"] = math.hypot(vel.x, vel.y)
        passing_transform = passing.get_transform()
        passing_body = passing.bounding_box.get_world_vertices(passing_transform)
        if len(passing_body) < 4:
            raise ValueError("original passing body vertices are missing")
        raw["passing_position_m"] = [float(passing_transform.location.x),
                                       float(passing_transform.location.y),
                                       float(passing_transform.location.z)]
        raw["passing_heading_deg"] = float(passing_transform.rotation.yaw)
        raw["passing_velocity_mps"] = [float(vel.x), float(vel.y), float(vel.z)]
        raw["passing_body_vertices_m"] = [
            [float(v.x), float(v.y), float(v.z)] for v in passing_body]
        raw["passing_blueprint"] = passing.type_id
        raw["parked_blueprint"] = parked.type_id
        raw["passing_blueprint_attributes"] = dict(passing.attributes)
        raw["parked_blueprint_attributes"] = dict(parked.attributes)
        driver_transform = driver.get_transform()
        driver_velocity = driver.get_velocity()
        driver_body = driver.bounding_box.get_world_vertices(driver_transform)
        if len(driver_body) < 4 or not driver.type_id.startswith("walker."):
            raise ValueError("original selected driver body or pedestrian blueprint missing")
        raw["driver_blueprint"] = driver.type_id
        raw["driver_blueprint_attributes"] = dict(driver.attributes)
        raw["driver_heading_deg"] = float(driver_transform.rotation.yaw)
        raw["driver_velocity_mps"] = [float(driver_velocity.x), float(driver_velocity.y),
                                      float(driver_velocity.z)]
        raw["driver_speed_mps"] = math.sqrt(driver_velocity.x ** 2 + driver_velocity.y ** 2 +
                                             driver_velocity.z ** 2)
        raw["driver_body_vertices_m"] = [
            [float(v.x), float(v.y), float(v.z)] for v in driver_body]
        # Bind the ordinary trace and Core evidence to the same live parked
        # actor observed by the door controller. No requested pose is reused.
        transform = parked.get_transform()
        parked_vel = parked.get_velocity()
        body = parked.bounding_box.get_world_vertices(transform)
        if len(body) < 4:
            raise ValueError("original parked body vertices are missing")
        raw["parked_position_m"] = [float(transform.location.x),
                                      float(transform.location.y),
                                      float(transform.location.z)]
        raw["parked_heading_deg"] = float(transform.rotation.yaw)
        raw["parked_speed_mps"] = math.sqrt(parked_vel.x ** 2 + parked_vel.y ** 2 + parked_vel.z ** 2)
        raw["parked_velocity_mps"] = [float(parked_vel.x), float(parked_vel.y), float(parked_vel.z)]
        raw["parked_body_vertices_m"] = [
            [float(v.x), float(v.y), float(v.z)] for v in body]
        settings = self.world.get_settings()
        if settings.no_rendering_mode is not False or set(self.camera_sensor_ids) != set(CAMERA_SIZE):
            raise ValueError("four live RGB sensors and enabled rendering required")
        raw["world_settings"] = {"no_rendering_mode": settings.no_rendering_mode}
        raw["rgb_sensors"] = [{"view": view, "actor_id": self.camera_sensor_ids[view],
                               "source_frame_id": frame_id} for view in CAMERA_SIZE]
        return raw

    def camera_frame(self, view, frame_id):
        with self.condition:
            if not self.condition.wait_for(lambda: (view, frame_id) in self.frames, timeout=5):
                raise ValueError("original camera callback missing: " + view)
            image = self.frames.pop((view, frame_id))
        width, height = CAMERA_SIZE[view]
        if (image.width, image.height) != (width, height) or len(image.raw_data) != width * height * 4:
            raise ValueError("original camera dimensions or BGRA bytes mismatch")
        rgb = Image.frombytes("RGB", (width, height), bytes(image.raw_data), "raw", "BGRX")
        output = io.BytesIO()
        rgb.save(output, format="PNG")
        return output.getvalue()

    def cleanup(self):
        for actor in reversed(self.owned):
            if hasattr(actor, "stop"):
                actor.stop()
            actor.destroy()
        self.owned.clear()
