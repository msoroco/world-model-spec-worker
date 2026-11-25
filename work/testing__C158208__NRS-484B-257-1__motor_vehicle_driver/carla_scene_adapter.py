"""Lazy CARLA scene adapter for the reviewed C158208 nearest-view pair.

The site packet supplies surveyed actor transforms and camera extrinsics. This
adapter reads actual spawned bodies, a world raycast, and sensor image bytes.
It refuses missing source observations instead of filling them from the plan.
"""
from __future__ import annotations

import math
import queue
import hashlib

from camera_sources import CAMERAS, DIMENSIONS


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _pose(carla, data, name):
    if not isinstance(data, dict):
        raise ValueError(f"{name} reviewed pose missing")
    location = data.get("location")
    rotation = data.get("rotation")
    if not isinstance(location, dict) or not isinstance(rotation, dict):
        raise ValueError(f"{name} reviewed location/rotation missing")
    return carla.Transform(
        carla.Location(**{key: _finite(location[key], f"{name} {key}")
                          for key in ("x", "y", "z")}),
        carla.Rotation(**{key: _finite(rotation[key], f"{name} {key}")
                          for key in ("pitch", "yaw", "roll")}))


def validate_native_scene_spec(scene, geometry=None):
    """Check reviewed scene fields before constructing or owning Native actors."""
    if not isinstance(scene, dict):
        raise ValueError("reviewed Native scene source missing")
    for name in ("ego", "through_vehicle"):
        actor = scene.get(name)
        if not isinstance(actor, dict) or not isinstance(actor.get("blueprint_id"), str) or not actor["blueprint_id"]:
            raise ValueError(f"reviewed {name} actor source missing")
        _pose_fields(actor.get("transform"), name)
    ego_xy = scene["ego"]["transform"]["location"]
    through_xy = scene["through_vehicle"]["transform"]["location"]
    if math.hypot(ego_xy["x"] - through_xy["x"],
                  ego_xy["y"] - through_xy["y"]) <= 1.0:
        raise ValueError("reviewed Native vehicle spawn poses overlap")
    if geometry is not None:
        for name, axis_name in (("ego", "ego_route_axis_xy"),
                                ("through_vehicle", "through_route_axis_xy")):
            axis = geometry[axis_name]
            yaw = math.radians(scene[name]["transform"]["rotation"]["yaw"])
            if math.cos(yaw) * axis[0] + math.sin(yaw) * axis[1] <= 0.7:
                raise ValueError(f"{name} spawn heading opposes reviewed route direction")
    cameras = scene.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("four reviewed camera extrinsics required")
    for name in CAMERAS:
        source = cameras[name]
        if not isinstance(source, dict) or source.get("attach_to") not in ("ego", "through_vehicle"):
            raise ValueError(f"{name} reviewed camera parent missing")
        _pose_fields(source.get("transform"), name)
        fov = _finite(source.get("fov_degrees"), f"{name} fov")
        if not 0 < fov < 180:
            raise ValueError(f"{name} reviewed camera fov outside physical range")
    sign_id = scene.get("yield_sign_actor_id")
    landmark_id = scene.get("yield_sign_landmark_id")
    if (sign_id is None) == (landmark_id is None):
        raise ValueError("exactly one reviewed Native yield sign actor or landmark required")
    if sign_id is not None and (isinstance(sign_id, bool) or not isinstance(sign_id, int) or sign_id <= 0):
        raise ValueError("reviewed Native yield sign actor ID required")
    if landmark_id is not None and (not isinstance(landmark_id, str) or not landmark_id):
        raise ValueError("reviewed Native yield sign landmark ID required")


def _pose_fields(data, name):
    if not isinstance(data, dict) or not isinstance(data.get("location"), dict) or not isinstance(data.get("rotation"), dict):
        raise ValueError(f"{name} reviewed location/rotation missing")
    for key in ("x", "y", "z"):
        _finite(data["location"].get(key), f"{name} {key}")
    for key in ("pitch", "yaw", "roll"):
        _finite(data["rotation"].get(key), f"{name} {key}")


def _vertices(actor, name):
    box = actor.bounding_box
    vertices = box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError(f"{name} original bounding box must have eight vertices")
    points = [[_finite(vertex.x, f"{name} vertex x"),
               _finite(vertex.y, f"{name} vertex y")] for vertex in vertices]
    # Pitch and roll can give more than four distinct XY points. Use the
    # original eight-vertex projection's convex hull rather than assuming a
    # flat vehicle box or silently dropping corner extrema.
    from shapely.geometry import MultiPoint, Polygon
    hull = MultiPoint(points).convex_hull
    if not isinstance(hull, Polygon) or hull.area <= 0:
        raise ValueError(f"{name} original body footprint is degenerate")
    return [list(point) for point in list(hull.exterior.coords)[:-1]]


class CarlaSceneAdapter:
    """Run a reviewed scene using injected CARLA classes and original callbacks."""

    def __init__(self, carla):
        self.carla = carla
        self.world = None
        self.ego = None
        self.through = None
        self.sign = None
        self.sign_kind = None
        self.sensor_queues = {}
        self.sensor_actors = {}
        self.site = None

    def configure(self, world, site):
        scene = site.get("native_scene")
        validate_native_scene_spec(scene, site.get("capture_geometry"))
        for name in ("ego", "through_vehicle"):
            _pose(self.carla, scene[name]["transform"], name)
        cameras = scene["cameras"]
        for name in CAMERAS:
            _pose(self.carla, cameras[name]["transform"], name)
        sign_id = scene.get("yield_sign_actor_id")
        landmark_id = scene.get("yield_sign_landmark_id")
        if (sign_id is None) == (landmark_id is None):
            raise ValueError("exactly one reviewed Native yield sign actor or landmark required")
        if sign_id is not None:
            if isinstance(sign_id, bool) or not isinstance(sign_id, int) or sign_id <= 0:
                raise ValueError("reviewed Native yield sign actor ID required")
            self.sign = world.get_actor(sign_id)
            if self.sign is None or "yield" not in self.sign.type_id.lower():
                raise ValueError("reviewed governing yield sign not found in Native world")
            self.sign_kind = "actor"
        else:
            if not isinstance(landmark_id, str) or not landmark_id:
                raise ValueError("reviewed Native yield sign landmark ID required")
            matches = [item for item in world.get_map().get_all_landmarks()
                       if str(item.id) == landmark_id]
            if len(matches) != 1 or str(matches[0].type) not in ("205", "YIELD", "Yield"):
                raise ValueError("reviewed governing yield landmark not found in Native map")
            self.sign = matches[0]
            self.sign_kind = "landmark"
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        readback = world.get_settings()
        if readback.synchronous_mode is not True or readback.fixed_delta_seconds != .05:
            raise ValueError("Native 20 Hz synchronous world readback failed")
        self.site = site
        self.world = world

    def spawn(self, world, site):
        if world is not self.world or site is not self.site:
            raise ValueError("Native scene changed after configuration")
        scene = site["native_scene"]
        library = world.get_blueprint_library()
        owned = []
        try:
            for name in ("ego", "through_vehicle"):
                source = scene[name]
                blueprint = library.find(source["blueprint_id"])
                actor = world.spawn_actor(blueprint, _pose(self.carla, source["transform"], name))
                if actor is None:
                    raise ValueError(f"Native {name} spawn failed")
                setattr(self, "ego" if name == "ego" else "through", actor)
                owned.append(actor)
            for name in CAMERAS:
                source = scene["cameras"][name]
                blueprint = library.find("sensor.camera.rgb")
                width, height = DIMENSIONS[name]
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", str(_finite(source["fov_degrees"], f"{name} fov")))
                parent = self.ego if source["attach_to"] == "ego" else self.through
                sensor = world.spawn_actor(blueprint, _pose(self.carla, source["transform"], name), attach_to=parent)
                if sensor is None:
                    raise ValueError(f"Native {name} camera spawn failed")
                inbox = queue.Queue(maxsize=2)
                sensor.listen(inbox.put)
                self.sensor_queues[name] = inbox
                self.sensor_actors[name] = sensor
                owned.append(sensor)
            return owned
        except BaseException:
            for actor in reversed(owned):
                self.destroy(actor)
            raise

    def observe(self, world, actors, frame):
        if world is not self.world or self.ego not in actors or self.through not in actors:
            raise ValueError("Native scene owner/actor mismatch")
        ego_body = _vertices(self.ego, "ego")
        through_body = _vertices(self.through, "through")
        ego_transform = self.ego.get_transform()
        through_transform = self.through.get_transform()
        origin = ego_transform.location
        target = through_transform.location
        hits = world.cast_ray(origin, target)
        if hits is None:
            raise ValueError("Native visibility raycast unavailable")
        hit_ids = [getattr(hit, "actor_id", None) for hit in hits]
        occluded = bool(hit_ids and hit_ids[0] != self.through.id)
        images = {}
        raw_image_hashes = {}
        for name in CAMERAS:
            try:
                image = self.sensor_queues[name].get(timeout=2.0)
            except queue.Empty as exc:
                raise ValueError(f"Native {name} camera frame missing") from exc
            if image.frame != frame:
                raise ValueError(f"Native {name} camera frame differs from world tick")
            if abs(image.timestamp - world.get_snapshot().timestamp.elapsed_seconds) > .001:
                raise ValueError(f"Native {name} camera time differs from world tick")
            if image.width != DIMENSIONS[name][0] or image.height != DIMENSIONS[name][1]:
                raise ValueError(f"Native {name} camera dimensions differ")
            # CARLA supplies BGRA. Preserve original pixels by encoding once as PNG.
            from PIL import Image
            from io import BytesIO
            raw_bytes = bytes(image.raw_data)
            if len(raw_bytes) != image.width * image.height * 4 or any(alpha != 255 for alpha in raw_bytes[3::4]):
                raise ValueError(f"Native {name} BGRA source has invalid length or alpha")
            raw_image_hashes[name] = hashlib.sha256(raw_bytes).hexdigest()
            rgb = Image.frombytes("RGBA", (image.width, image.height), raw_bytes, "raw", "BGRA").convert("RGB")
            stream = BytesIO()
            rgb.save(stream, format="PNG")
            images[name] = stream.getvalue()
        velocity = self.ego.get_velocity()
        through_velocity = self.through.get_velocity()
        if self.sign_kind == "actor":
            sign_present = self.world.get_actor(self.sign.id) is not None
        elif self.sign_kind == "landmark":
            sign_present = any(str(item.id) == str(self.sign.id) and
                               str(item.type) in ("205", "YIELD", "Yield")
                               for item in self.world.get_map().get_all_landmarks())
        else:
            raise ValueError("reviewed governing yield sign source unavailable")
        raw = {"frame": frame,
               "time_s": world.get_snapshot().timestamp.elapsed_seconds,
               "ego": {"body_vertices_xy_m": ego_body,
                       "velocity_xy_mps": [_finite(velocity.x, "ego velocity x"),
                                           _finite(velocity.y, "ego velocity y")]},
               "through_vehicle": {"center_xy_m": [through_transform.location.x,
                                                     through_transform.location.y],
                                   "body_vertices_xy_m": through_body,
                                   "velocity_xy_mps": [_finite(through_velocity.x, "through velocity x"),
                                                       _finite(through_velocity.y, "through velocity y")]},
               "visibility_probe": {"source": "native_raycast", "occluded": occluded,
                                    "origin_xy_m": [origin.x, origin.y],
                                    "target_xy_m": [target.x, target.y],
                                    "hit_actor_ids": hit_ids},
               "camera_raw_bgra_sha256": raw_image_hashes,
               "sign_present": sign_present}
        return {"raw_tick": raw, "cameras": images}

    def apply_control(self, actors, command):
        if self.ego not in actors:
            raise ValueError("ego actor not owned")
        self.ego.apply_control(self.carla.VehicleControl(
            throttle=_finite(command["throttle"], "throttle"),
            brake=_finite(command["brake"], "brake"),
            steer=_finite(command["steer"], "steer")))
        through = command.get("through_control")
        if through is not None:
            if self.through not in actors:
                raise ValueError("through vehicle not owned")
            self.through.apply_control(self.carla.VehicleControl(
                throttle=_finite(through["throttle"], "through throttle"),
                brake=_finite(through["brake"], "through brake"),
                steer=_finite(through["steer"], "through steer")))

    def destroy(self, actor):
        if actor in self.sensor_actors.values():
            actor.stop()
        actor.destroy()
