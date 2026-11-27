"""CARLA-lazy source-gated taxi and passenger construction.

Native acquisition must supply independently reviewed original site bytes.
This component owns its actors and cameras; frame capture is a separate step.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from taxi_stand_measurement import VIEWS, finite, polygon, within

SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "curb_reference": (1280, 720), "passenger_side": (1280, 720)}


def pose(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("reviewed Native transform required")
    for name in ("x", "y", "z", "yaw"):
        finite(value.get(name), "transform " + name)
    for name in ("pitch", "roll"):
        finite(value.get(name, 0), "transform " + name)
    return value


def read_site(path: Path, sha256: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("reviewed original taxi site SHA256 differs")
    site = json.loads(raw)
    if site.get("source_kind") != "original_independent_site_review":
        raise ValueError("original independent taxi site review required")
    if site.get("cell_id") != "C378245" or site.get("business_district") is not True:
        raise ValueError("reviewed taxi cell/district differs")
    if not site.get("map_sha256") or not site.get("designation_id"):
        raise ValueError("reviewed map and stand designation required")
    stand = polygon(site.get("stand_polygon_xy_m"), "stand")
    street = polygon(site.get("street_polygon_xy_m"), "street")
    scene = site.get("native_scene")
    if not isinstance(scene, dict):
        raise ValueError("reviewed Native taxi scene required")
    if not str(scene.get("taxi_blueprint_id", "")).startswith("vehicle."):
        raise ValueError("reviewed taxi vehicle blueprint required")
    if not str(scene.get("passenger_blueprint_id", "")).startswith("walker.pedestrian."):
        raise ValueError("reviewed passenger blueprint required")
    transforms = scene.get("halt_poses")
    if not isinstance(transforms, dict) or set(transforms) != {"in_stand", "outside_stand"}:
        raise ValueError("reviewed in/out stand poses required")
    for location, transform in transforms.items():
        pose(transform)
        xy = (transform["x"], transform["y"])
        if not within(xy, street):
            raise ValueError("reviewed halt pose outside street")
        if within(xy, stand) != (location == "in_stand"):
            raise ValueError("reviewed halt pose differs from stand boundary")
    for name in ("passenger_start_pose", "passenger_door_pose"):
        pose(scene.get(name))
    cameras = scene.get("camera_mounts")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four reviewed taxi camera mounts required")
    for name, value in cameras.items():
        if value.get("attach_to") not in ("taxi", "world"):
            raise ValueError("reviewed taxi camera parent required")
        pose(value.get("transform"))
        fov = finite(value.get("fov_deg"), name + " camera fov")
        if not 0 < fov < 180:
            raise ValueError("reviewed taxi camera fov invalid")
    return site


class NativeTaxiOperator:
    def __init__(self, world, carla, site: dict):
        self.world, self.carla, self.site = world, carla, site
        self.owned = []
        self.taxi = self.passenger = None
        self.cameras = {}

    def transform(self, value: dict):
        p = pose(value)
        return self.carla.Transform(
            self.carla.Location(x=p["x"], y=p["y"], z=p["z"]),
            self.carla.Rotation(yaw=p["yaw"], pitch=p.get("pitch", 0), roll=p.get("roll", 0)))

    def spawn(self, blueprint_id: str, transform: dict, **kwargs):
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.spawn_actor(blueprint, self.transform(transform), **kwargs)
        if actor is None:
            raise ValueError("Native taxi actor spawn failed: " + blueprint_id)
        self.owned.append(actor)
        return actor

    def setup(self, case: dict) -> dict:
        location = case.get("location_request")
        activity = case.get("halt_activity_request")
        exchange = case.get("passenger_exchange_request")
        if location not in ("in_stand", "outside_stand") or activity not in ("park", "stand", "temporary_stop"):
            raise ValueError("unselected taxi location/activity request")
        if exchange not in ("none", "loading", "unloading"):
            raise ValueError("unselected taxi passenger request")
        if activity != "temporary_stop" and exchange != "none":
            raise ValueError("taxi halt/activity pairing differs")
        if activity == "temporary_stop" and exchange == "none" and not case["case_id"].endswith("__outside_stand_idle_stop"):
            raise ValueError("taxi halt/activity pairing differs")
        raw_map = self.world.get_map().to_opendrive().encode("utf-8")
        if hashlib.sha256(raw_map).hexdigest() != self.site["map_sha256"]:
            raise ValueError("reviewed taxi OpenDRIVE differs from Native world")
        scene = self.site["native_scene"]
        try:
            self.taxi = self.spawn(scene["taxi_blueprint_id"], scene["halt_poses"][location])
            if exchange != "none":
                self.passenger = self.spawn(scene["passenger_blueprint_id"],
                                            scene["passenger_start_pose"])
            for view in VIEWS:
                spec = scene["camera_mounts"][view]
                blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
                width, height = SIZES[view]
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", str(spec["fov_deg"]))
                kwargs = {"attach_to": self.taxi} if spec["attach_to"] == "taxi" else {}
                sensor = self.world.spawn_actor(blueprint, self.transform(spec["transform"]), **kwargs)
                if sensor is None:
                    raise ValueError("Native taxi camera spawn failed: " + view)
                self.owned.append(sensor)
                self.cameras[view] = sensor
            loc = self.taxi.get_transform().location
            center = (finite(loc.x, "taxi readback x"), finite(loc.y, "taxi readback y"))
            if within(center, polygon(self.site["stand_polygon_xy_m"], "stand")) != (location == "in_stand"):
                raise ValueError("Native taxi halt location differs from reviewed stand")
            return {"taxi_actor_id": self.taxi.id,
                    "passenger_actor_id": self.passenger.id if self.passenger else None,
                    "camera_actor_ids": {name: actor.id for name, actor in self.cameras.items()},
                    "reviewed_location": location, "requested_activity": activity,
                    "requested_exchange": exchange}
        except BaseException:
            self.close()
            raise

    def close(self):
        errors = []
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except BaseException as error:
                errors.append(error)
        self.owned.clear()
        self.cameras.clear()
        self.taxi = self.passenger = None
        if errors:
            raise ValueError("Native taxi ownership cleanup failed") from errors[0]
