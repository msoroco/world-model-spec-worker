"""Source-gated CARLA actors, controls and four synchronized camera readers.

The caller supplies a reviewed original site and exception packet. This module
does not turn the nominal scene coordinates into claims about an actual map.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path
from queue import Empty, Full, Queue

from PIL import Image

import crosswalk
from native_capture import CAMERAS, DIMENSIONS
from native_setup import construct


CAMERA_POSES = {
    "overview": ((-8.0, 0.0, 6.0), (-17.0, 0.0, 0.0)),
    "approach": ((-5.0, 0.0, 2.5), (-5.0, 0.0, 0.0)),
    "reference_corner": ((0.0, 3.0, 2.4), (-8.0, -45.0, 0.0)),
    "driver_reference": ((0.6, 0.0, 1.6), (0.0, 0.0, 0.0)),
}


def _require(value, message):
    if not value:
        raise ValueError(message)
    return value


def _image_png(image, dimensions):
    _require(image.width == dimensions[0] and image.height == dimensions[1],
             "original camera dimensions changed")
    _require(len(image.raw_data) == image.width * image.height * 4,
             "original camera BGRA payload incomplete")
    rendered = Image.frombytes("RGBA", (image.width, image.height),
                               bytes(image.raw_data), "raw", "BGRA").convert("RGB")
    out = io.BytesIO()
    rendered.save(out, format="PNG")
    return out.getvalue()


class CameraReader:
    """Retain original sensor frame IDs; reject missing and out-of-order images."""

    def __init__(self, sensor, dimensions):
        self.queue = Queue(maxsize=8)
        self.dimensions = dimensions
        self.overflow = False
        sensor.listen(self._receive)

    def _receive(self, image):
        try:
            self.queue.put_nowait(image)
        except Full:
            # Overflow must fail capture, never silently select a newer frame.
            self.overflow = True

    def __call__(self, frame):
        _require(not self.overflow, "original camera queue overflow")
        try:
            image = self.queue.get(timeout=10)
        except Empty as exc:
            raise ValueError("original camera frame missing") from exc
        _require(image is not None and image.frame == frame,
                 "original camera frame mismatch")
        return {"frame": image.frame,
                "png_bytes": _image_png(image, self.dimensions)}


class TurnYieldController:
    """Bounded engineering control; physical yield and legality stay unverified."""

    def __init__(self, api, scene, site, exception):
        self.api = api
        self.scene = scene
        self.site = site
        self.exception = exception
        self.route = [tuple(map(float, point)) for point in site["turn_route"]]
        self.route_index = 1
        self.pedestrian_route = [tuple(map(float, point)) for point in
                                 site["pedestrian_route"]]
        self.pedestrian_index = 1
        self.target_speed_mps = float(scene.get("engineering_target_speed_mps", 4.0))
        _require(0 < self.target_speed_mps <= 10, "engineering speed envelope invalid")

    def __call__(self, world, ego, pedestrian):
        frame = world.get_snapshot().frame
        ego_xy = [ego.get_transform().location.x, ego.get_transform().location.y]
        pedestrian_xy = [pedestrian.get_transform().location.x,
                         pedestrian.get_transform().location.y]
        measured = crosswalk.measure_frame(
            self.site, frame,
            {"frame": frame, "source_ref": "original_native_ego",
             "actor_id": ego.id, "classification": "motor_vehicle_driver",
             "body_center_xy_m": ego_xy, "brake": ego.get_control().brake >= .5},
            {"frame": frame, "source_ref": "original_native_pedestrian",
             "actor_id": pedestrian.id, "classification": "pedestrian",
             "body_center_xy_m": pedestrian_xy}, self.exception)
        _require(measured["device_condition"] == self.scene["official_device_condition"],
                 "original official-device condition differs from planned case")
        hold = (measured["device_condition"] == "operating" or
                self.exception["status"] != "none_identified" or
                measured["pedestrian_in_crosswalk"] and
                measured["pedestrian_on_destination_half"] or
                self.scene["pedestrian_half"] == "opposite")
        here = ego.get_transform().location
        while self.route_index < len(self.route)-1 and math.dist(
                (here.x, here.y), self.route[self.route_index]) < 2.0:
            self.route_index += 1
        target = self.route[self.route_index]
        desired = math.atan2(target[1]-here.y, target[0]-here.x)
        forward = ego.get_transform().get_forward_vector()
        heading = math.atan2(forward.y, forward.x)
        error = math.atan2(math.sin(desired-heading), math.cos(desired-heading))
        steer = max(-1.0, min(1.0, error / .6))
        velocity = ego.get_velocity()
        speed = math.hypot(float(velocity.x), float(velocity.y))
        _require(math.isfinite(speed), "original ego speed invalid")
        at_end = self.route_index == len(self.route)-1 and math.dist(
            (here.x, here.y), target) < 1.5
        demand = 0.0 if hold or at_end else self.target_speed_mps
        throttle = min(.5, max(0.0, .2 * (demand-speed)))
        brake = min(1.0, max(0.0, .5 * (speed-demand)))
        if demand == 0.0:
            brake = max(brake, .8)
        ego.apply_control(self.api.VehicleControl(throttle=throttle,
                                                  brake=brake, steer=steer))
        p_here = pedestrian.get_transform().location
        while self.pedestrian_index < len(self.pedestrian_route)-1 and math.dist(
                (p_here.x, p_here.y), self.pedestrian_route[self.pedestrian_index]) < .4:
            self.pedestrian_index += 1
        p_target = self.pedestrian_route[self.pedestrian_index]
        dx, dy = p_target[0]-p_here.x, p_target[1]-p_here.y
        remaining = math.hypot(dx, dy)
        p_speed = 0.0 if self.pedestrian_index == len(self.pedestrian_route)-1 and remaining < .4 else 1.0
        pedestrian.apply_control(self.api.WalkerControl(
            direction=self.api.Vector3D(x=dx/remaining if remaining else 0.0,
                                        y=dy/remaining if remaining else 0.0,
                                        z=0.0), speed=p_speed))


def make_scene_factory(api, *, dimensions=None):
    """Return the factory consumed by live_crosswalk.run."""
    dims = DIMENSIONS if dimensions is None else dimensions
    _require(set(dims) == set(CAMERAS), "four camera dimensions required")

    def scene_factory(*, world, scene_path, site_path, exception_path, register):
        scene = json.loads(Path(scene_path).read_text(encoding="utf-8"))
        packet = json.loads(Path(site_path).read_text(encoding="utf-8"))
        exception = json.loads(Path(exception_path).read_text(encoding="utf-8"))
        _require(packet.get("map_name") == world.get_map().name,
                 "original map and reviewed site mismatch")
        _require(exception.get("case_id") == scene.get("case_id") and
                 exception.get("source_refs") and
                 exception.get("status") in ("none_identified", "possible", "applies"),
                 "source-backed exception review missing")
        site = crosswalk.bind_site(packet, world.get_map().name, scene["turn_direction"])
        route_info = packet.get("pedestrian_routes", {}).get(scene["case_id"], {})
        _require(route_info.get("source") == "original_map_and_local_review" and
                 isinstance(route_info.get("waypoints"), list) and
                 len(route_info["waypoints"]) >= 2,
                 "reviewed original pedestrian route missing for exact case")
        route = route_info["waypoints"]
        _require(all(isinstance(point, list) and len(point) == 2 and
                     all(isinstance(value, (int, float)) and math.isfinite(value)
                         for value in point) for point in route),
                 "reviewed pedestrian route coordinates invalid")
        _require(math.dist(route[0], scene["pedestrian_start_xy_m"]) <= .25,
                 "reviewed pedestrian route does not start at exact case spawn")
        start_in_crosswalk = crosswalk.polygon_contains(route[0], site["crosswalk_polygon"])
        start_on_destination = any(crosswalk.polygon_contains(route[0], lane)
                                   for lane in site["destination_half"])
        _require(start_in_crosswalk == (scene["crosswalk_position"] == "in_crosswalk"),
                 "reviewed pedestrian route starts in wrong crosswalk region")
        _require(start_on_destination == (scene["pedestrian_half"] == "destination"),
                 "reviewed pedestrian route starts on wrong directional half")
        site["pedestrian_route"] = route
        _require(crosswalk.device_condition(site["device_entries"],
                                            world.get_snapshot().frame) ==
                 scene["official_device_condition"],
                 "original device condition differs from planned case")
        built = construct(world, api, scene, site)
        ego = register(built["ego"])
        pedestrian = register(built["pedestrian"])
        sensors = {}
        readers = {}
        library = world.get_blueprint_library()
        for name in CAMERAS:
            blueprint = library.find("sensor.camera.rgb")
            _require(blueprint is not None, "original RGB camera blueprint missing")
            for key, value in (("image_size_x", dims[name][0]),
                               ("image_size_y", dims[name][1]),
                               ("fov", 90), ("sensor_tick", .05)):
                blueprint.set_attribute(key, str(value))
            offset, rotation = CAMERA_POSES[name]
            pose = api.Transform(api.Location(*offset), api.Rotation(*rotation))
            sensor = register(world.spawn_actor(blueprint, pose, attach_to=ego))
            _require(sensor is not None, "original RGB camera spawn failed")
            sensors[name] = sensor
            readers[name] = CameraReader(sensor, tuple(dims[name]))
        return {"ego": ego, "pedestrian": pedestrian, "sensors": sensors,
                "camera_readers": readers,
                "controller": TurnYieldController(api, scene, site, exception)}

    return scene_factory
