"""Source-gated Native lane-change construction and controller.

The reviewed site packet is supplied by the local operator. Authored control
requests are retained separately from Native signal and driver-action readbacks.
No controller request is evidence of legal ascertainment or safe movement.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C144550__NRS-484B-223-1b__motor_vehicle_driver"
VARIANTS = {"both_observed": (True, True),
            "signal_missing": (False, True),
            "check_missing": (True, False)}


def _point(value):
    if not isinstance(value, list) or len(value) != 3 or not all(
            type(v) in (int, float) and math.isfinite(v) for v in value):
        raise ValueError("reviewed three-dimensional route point required")
    return tuple(float(v) for v in value)


def load_reviewed_site(path: str | Path, expected_sha256: str, case_id: str) -> dict:
    """Validate original reviewed map/lane facts before changing a Native world."""
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact lane-change case identity required")
    variant = case_id[len(ASSIGNMENT) + 2:]
    if variant not in VARIANTS:
        raise ValueError("only the three planned controlled cases are constructible")
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("separately reviewed original site packet required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed site packet SHA256 differs")
    packet = json.loads(raw)
    provenance = packet.get("reviewed_provenance")
    if not isinstance(provenance, dict) or not all(provenance.get(key) for key in (
            "reviewer", "source_citation", "native_map_name", "opendrive_sha256",
            "highway_dedication_source", "public_access_source", "lane_marking_source")):
        raise ValueError("reviewed highway, map and lane-marking provenance required")
    lanes = packet.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != {"source", "destination"}:
        raise ValueError("reviewed source and destination lanes required")
    for name in ("source", "destination"):
        lane = lanes[name]
        if (not lane.get("lane_id") or lane.get("travel_direction") != "forward" or
                lane.get("lane_type") != "driving" or
                lane.get("marking_visibility") != "clearly_marked"):
            raise ValueError("two clearly marked same-direction driving lanes required")
        center = lane.get("centerline_world_xyz_m")
        if not isinstance(center, list) or len(center) < 3:
            raise ValueError("reviewed lane centerline missing")
        points = [_point(row) for row in center]
        if any(math.dist(a, b) > 12 or math.dist(a, b) < 0.1
               for a, b in zip(points, points[1:])):
            raise ValueError("reviewed lane route disconnected")
    if lanes["source"]["lane_id"] == lanes["destination"]["lane_id"]:
        raise ValueError("lane movement requires distinct lane identities")
    source = [_point(v) for v in lanes["source"]["centerline_world_xyz_m"]]
    target = [_point(v) for v in lanes["destination"]["centerline_world_xyz_m"]]
    if len(source) != len(target):
        raise ValueError("paired lane station samples required")
    separations = [math.dist(a, b) for a, b in zip(source, target)]
    if min(separations) < 2.5 or max(separations) > 5.0:
        raise ValueError("adjacent marked-lane width not source-supported")
    if not packet.get("ego_blueprint", "").startswith("vehicle."):
        raise ValueError("reviewed motor-vehicle blueprint required")
    if not packet.get("target_vehicle_blueprint", "").startswith("vehicle."):
        raise ValueError("reviewed target-lane traffic blueprint required")
    if not isinstance(packet.get("ego_spawn_xyz_yaw"), list) or len(packet["ego_spawn_xyz_yaw"]) != 4:
        raise ValueError("reviewed vehicle spawn required")
    if not isinstance(packet.get("target_spawn_xyz_yaw"), list) or len(packet["target_spawn_xyz_yaw"]) != 4:
        raise ValueError("reviewed target-lane traffic spawn required")
    if not all(type(v) in (int, float) and math.isfinite(v) for v in
               packet["ego_spawn_xyz_yaw"] + packet["target_spawn_xyz_yaw"]):
        raise ValueError("reviewed vehicle spawn invalid")
    station = packet.get("change_station_index")
    if type(station) is not int or station < 1 or station > len(source) - 2:
        raise ValueError("reviewed lane-change station required")
    poses = packet.get("camera_poses_xyz_pitch_yaw")
    if not isinstance(poses, dict) or set(poses) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four reviewed original camera poses required")
    for name, pose in poses.items():
        if (not isinstance(pose, list) or len(pose) != 5 or
                not all(type(v) in (int, float) and math.isfinite(v) for v in pose)):
            raise ValueError("reviewed camera pose invalid: " + name)
    return packet


def check_live_world(world, packet: dict):
    provenance = packet["reviewed_provenance"]
    native_map = world.get_map()
    if native_map.name != provenance["native_map_name"]:
        raise ValueError("live Native map differs from reviewed site")
    digest = hashlib.sha256(native_map.to_opendrive().encode("utf-8")).hexdigest()
    if digest != provenance["opendrive_sha256"]:
        raise ValueError("live OpenDRIVE bytes differ from reviewed site")


def lane_change_route(packet: dict) -> list[tuple[float, float, float]]:
    source = [_point(v) for v in packet["lanes"]["source"]["centerline_world_xyz_m"]]
    target = [_point(v) for v in packet["lanes"]["destination"]["centerline_world_xyz_m"]]
    station = packet["change_station_index"]
    transition = 4
    if station + transition >= len(source):
        raise ValueError("reviewed route lacks lane-change clearance")
    route = []
    for i in range(len(source)):
        fraction = min(1.0, max(0.0, (i - station) / transition))
        ease = fraction * fraction * (3 - 2 * fraction)
        route.append(tuple(a * (1 - ease) + b * ease for a, b in zip(source[i], target[i])))
    return route


class LaneChangeController:
    """Route-following actuation; independent readbacks are acquired elsewhere."""

    def __init__(self, packet: dict, variant: str, carla):
        if variant not in VARIANTS:
            raise ValueError("unknown exact lane-change variant")
        self.route = lane_change_route(packet)
        self.signal_requested, self.check_requested = VARIANTS[variant]
        self.change_station = packet["change_station_index"]
        self.carla = carla
        self.next_index = 1

    def step(self, actor):
        transform = actor.get_transform()
        here = transform.location
        while (self.next_index < len(self.route) - 1 and
               math.hypot(self.route[self.next_index][0] - here.x,
                          self.route[self.next_index][1] - here.y) < 2.0):
            self.next_index += 1
        target = self.route[self.next_index]
        heading = math.radians(transform.rotation.yaw)
        error = (math.atan2(target[1] - here.y, target[0] - here.x) - heading + math.pi) % (2 * math.pi) - math.pi
        steer = max(-0.65, min(0.65, 1.2 * error))
        arrived = math.hypot(self.route[-1][0] - here.x, self.route[-1][1] - here.y) < 1.0
        actor.apply_control(self.carla.VehicleControl(throttle=0.0 if arrived else 0.3,
                                                       brake=1.0 if arrived else 0.0,
                                                       steer=steer))
        # The signal request is separate from later Native API readback.
        left = self.carla.VehicleLightState.LeftBlinker if self.signal_requested else 0
        actor.set_light_state(self.carla.VehicleLightState(left))
        return {"route_target_index": self.next_index,
                "signal_requested": self.signal_requested,
                "driver_check_requested": self.check_requested,
                "requested_steer": steer,
                "arrived": arrived}


class TargetTrafficController:
    """Hold a reviewed target-lane actor on its actual lane centerline."""

    def __init__(self, packet, carla):
        self.route = [_point(v) for v in packet["lanes"]["destination"]["centerline_world_xyz_m"]]
        self.carla = carla
        self.next_index = 1

    def step(self, actor):
        transform = actor.get_transform()
        here = transform.location
        while (self.next_index < len(self.route) - 1 and
               math.hypot(self.route[self.next_index][0] - here.x,
                          self.route[self.next_index][1] - here.y) < 2.0):
            self.next_index += 1
        target = self.route[self.next_index]
        heading = math.radians(transform.rotation.yaw)
        error = (math.atan2(target[1] - here.y, target[0] - here.x) - heading + math.pi) % (2 * math.pi) - math.pi
        arrived = math.hypot(self.route[-1][0] - here.x, self.route[-1][1] - here.y) < 1.0
        actor.apply_control(self.carla.VehicleControl(
            throttle=0.0 if arrived else 0.25, brake=1.0 if arrived else 0.0,
            steer=max(-0.65, min(0.65, 1.2 * error))))
