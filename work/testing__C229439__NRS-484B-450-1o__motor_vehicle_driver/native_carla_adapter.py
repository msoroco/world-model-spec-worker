"""Source-gated CARLA construction for the reviewed C229439 road and sign.

The site and device packets must identify original map geometry and a physical
sign object. The adapter does not infer official authority from a CARLA prop.
"""
from __future__ import annotations

import hashlib
import math


def _require(condition, message):
    if not condition:
        raise ValueError(message)


class NativeParkingAdapter:
    def __init__(self, world, api, *, owned=None, exception_packets=None):
        self.world = world
        self.api = api
        self.owned = [] if owned is None else owned
        self.exception_packets = {} if exception_packets is None else exception_packets
        self.device = None
        self.mode = None
        self.ego = None
        self.route = None
        self.cause = None

    def verify_site(self, site):
        carla_map = self.world.get_map()
        _require(carla_map.name == site["map_name"], "original Native map differs")
        digest = hashlib.sha256(carla_map.to_opendrive().encode()).hexdigest()
        _require(site.get("native_opendrive_sha256") == digest,
                 "reviewed original map digest missing or differs")
        for x, y in site["approach_waypoints"]:
            location = self.api.Location(x=float(x), y=float(y), z=0.0)
            _require(carla_map.get_waypoint(location, project_to_road=False) is not None,
                     "reviewed parking approach absent from Native road")
        return {"map_name": carla_map.name, "parking_polygon": site["parking_polygon"],
                "native_opendrive_sha256": digest}

    def install_and_read_device(self, device):
        _require(isinstance(device.get("native_object_id"), int),
                 "reviewed original Native sign object id required")
        _require(device.get("instruction_review_sha256") and
                 device.get("authority_review_sha256"),
                 "independent sign instruction and authority reviews required")
        objects = self.world.get_environment_objects()
        matches = [obj for obj in objects if obj.id == device["native_object_id"]]
        _require(len(matches) == 1, "original Native sign object missing")
        obj = matches[0]
        _require(obj.name == device.get("native_object_name"),
                 "original Native sign identity differs")
        self.device = device
        return {key: device[key] for key in
                ("device_id", "exact_instruction", "governed_polygon")}

    def configure_effective_window(self, device_id, mode, intervals):
        _require(self.device and self.device["device_id"] == device_id,
                 "original sign not established")
        _require(mode in {"effective", "not_effective"} and intervals,
                 "effective window source missing")
        self.mode = mode

    def read_device_effective(self, device_id):
        _require(self.device and self.device["device_id"] == device_id,
                 "original sign differs")
        return self.mode == "effective"

    def spawn_driver_vehicle(self, vehicle, waypoint):
        _require(vehicle["blueprint"].startswith("vehicle."),
                 "reviewed vehicle blueprint required")
        bp = self.world.get_blueprint_library().find(vehicle["blueprint"])
        _require(bp.id == vehicle["blueprint"], "Native vehicle blueprint differs")
        x, y = waypoint
        location = self.api.Location(x=float(x), y=float(y), z=0.0)
        road_point = self.world.get_map().get_waypoint(location, project_to_road=False)
        _require(road_point is not None, "original driver spawn off road")
        actor = self.world.try_spawn_actor(bp, road_point.transform)
        _require(actor is not None and actor.id, "original driver actor spawn failed")
        actor.set_autopilot(False)
        self.owned.append(actor)
        self.ego = actor
        return {"actor_id": str(actor.id), "blueprint": bp.id}

    def configure_parking_route(self, actor_id, waypoints, polygon, action):
        _require(self.ego is not None and str(self.ego.id) == actor_id,
                 "original driver actor differs")
        _require(action in {"park", "stop", "stand"}, "halt action invalid")
        _require(len(waypoints) >= 2 and len(polygon) >= 3,
                 "parking route geometry missing")
        self.route = (waypoints, polygon, action)

    def configure_exception_cause(self, actor_id, cause):
        _require(self.ego is not None and str(self.ego.id) == actor_id,
                 "original driver actor differs")
        _require(cause == "none" or self.exception_packets.get(cause),
                 "reviewed exception cause packet required")
        self.cause = cause

    def read_exception_cause(self, actor_id):
        _require(self.ego is not None and str(self.ego.id) == actor_id,
                 "original driver actor differs")
        return self.cause

    def control_step(self, *, target_speed_mps=3.0):
        """Request motion toward the next reviewed waypoint, then brake at end.

        Later original rows measure actual movement; this command is not evidence.
        """
        _require(self.route and self.ego, "original parking route not configured")
        _require(math.isfinite(target_speed_mps) and 0 < target_speed_mps <= 8,
                 "controller speed outside bounded envelope")
        waypoints, _, _ = self.route
        here = self.ego.get_transform().location
        target = waypoints[-1]
        distance = math.hypot(target[0] - here.x, target[1] - here.y)
        speed = self.ego.get_velocity().length()
        _require(math.isfinite(speed), "original Native velocity invalid")
        brake = 1.0 if distance < 1.5 else max(0.0, min(1.0, (speed - target_speed_mps) * 0.4))
        throttle = 0.0 if brake else max(0.0, min(0.5, (target_speed_mps - speed) * 0.2))
        self.ego.apply_control(self.api.VehicleControl(throttle=throttle, brake=brake))
