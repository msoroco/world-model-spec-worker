"""Map-bound approach and destination controller for the nine exact cases.

The route packet must be prepared from reviewed Native lane geometry. This
controller requests travel and a destination halt; original motion, activity,
intersection contact and exception evidence are measured independently.
"""
from __future__ import annotations

import math

from intersection_observables import _require, footprint_intersects_boundary


CASE_VARIANTS = {
    "outside_reference": ("outside", "halt"),
    "inside_stop": ("inside", "halt"),
    "inside_stand": ("inside", "halt"),
    "inside_park": ("inside", "halt"),
    "traffic_conflict": ("inside", "halt"),
    "law_direction": ("inside", "halt"),
    "officer_direction": ("inside", "halt"),
    "device_direction": ("inside", "halt"),
    "through_motion": ("through", "drive"),
}


def destination_footprint(target: dict, vehicle_extent: dict):
    x, y, yaw = target["x"], target["y"], math.radians(target["yaw_deg"])
    length, width = vehicle_extent["half_length_m"], vehicle_extent["half_width_m"]
    _require(all(math.isfinite(v) for v in (x, y, yaw, length, width)) and
             length > 0 and width > 0, "invalid destination or body extent")
    c, s = math.cos(yaw), math.sin(yaw)
    return [[x + c*dx - s*dy, y + s*dx + c*dy]
            for dx, dy in ((-length, -width), (length, -width),
                           (length, width), (-length, width))]


def validate_route(route: dict, boundary: dict, case_id: str):
    variant = case_id.rsplit("__", 1)[-1]
    _require(variant in CASE_VARIANTS, "unknown exact case variant")
    _require(route.get("case_id") == case_id and route.get("map_id") == boundary.get("map_id"),
             "route case/map identity differs")
    _require(route.get("source_refs") and route.get("approach_lane") and
             route.get("lane_direction_reviewed") is True,
             "reviewed Native approach lane source missing")
    _require(route.get("vehicle_blueprint") and route.get("spawn") and
             route.get("destination") and route.get("vehicle_extent"),
             "route construction inputs missing")
    _require(boundary.get("highway_status") == "reviewed_highway" and
             boundary.get("joining_roadways") is True and
             boundary.get("intersection_polygon") and boundary.get("source_refs"),
             "reviewed intersection boundary missing")
    target = route["destination"]
    footprint = destination_footprint(target, route["vehicle_extent"])
    contact = footprint_intersects_boundary(footprint, boundary["intersection_polygon"])
    expected, _ = CASE_VARIANTS[variant]
    if expected == "inside":
        _require(contact, "inside destination misses reviewed intersection")
    else:
        _require(not contact, "outside/through destination contacts reviewed intersection")
    _require(isinstance(route.get("speed_limit_mps"), (int, float)) and
             0 < route["speed_limit_mps"] <= 13.5,
             "engineering approach speed missing or out of range")
    return {"variant": variant, "destination_contact_predicted": contact,
            "approach_lane": route["approach_lane"],
            "source_refs": route["source_refs"] + boundary["source_refs"],
            "physical_contact_verified": False}


class DestinationController:
    def __init__(self, route: dict, boundary: dict, case_id: str, control_factory,
                 profile=None):
        self.plan = validate_route(route, boundary, case_id)
        self.target = route["destination"]
        self.speed_limit = route["speed_limit_mps"]
        self.control_factory = control_factory
        self.profile = profile or {"brake_distance_m": 2.0,
                                   "throttle_gain": 0.2,
                                   "through_speed_floor_mps": 2.0}
        _require(set(self.profile) == {"brake_distance_m", "throttle_gain",
                                      "through_speed_floor_mps"} and
                 1.0 <= self.profile["brake_distance_m"] <= 5.0 and
                 0.1 <= self.profile["throttle_gain"] <= 0.3 and
                 1.0 <= self.profile["through_speed_floor_mps"] <= 4.0,
                 "bounded engineering controller profile required")
        self.stopped = False

    def step(self, frame_index, actor):
        _require(not self.stopped, "controller already stopped")
        pose = actor.get_transform()
        dx = self.target["x"] - pose.location.x
        dy = self.target["y"] - pose.location.y
        distance = math.hypot(dx, dy)
        yaw = math.radians(pose.rotation.yaw)
        forward = dx * math.cos(yaw) + dy * math.sin(yaw)
        cross = dy * math.cos(yaw) - dx * math.sin(yaw)
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        _require(all(math.isfinite(v) for v in (distance, forward, cross, speed)),
                 "invalid Native controller observation")
        through = self.plan["variant"] == "through_motion"
        if not through and (distance < self.profile["brake_distance_m"] or forward < -0.5):
            throttle, brake, steer, phase = 0.0, 1.0, 0.0, "destination_brake"
        else:
            target_speed = min(self.speed_limit,
                               max(self.profile["through_speed_floor_mps"], distance * 0.7))
            throttle = min(0.5, max(0.0, self.profile["throttle_gain"] * (target_speed - speed)))
            brake = min(0.8, max(0.0, 0.3 * (speed - target_speed)))
            steer = max(-0.5, min(0.5, math.atan2(cross, max(2.0, forward)) * 0.7))
            phase = "approach"
        actor.apply_control(self.control_factory(throttle=throttle, brake=brake, steer=steer))
        return {"source": "original_controller_request", "frame_index": frame_index,
                "phase": phase, "throttle": throttle, "brake": brake, "steer": steer,
                "target_distance_m": distance, "observed_speed_mps": speed,
                "physical_completion_claimed": False}

    def stop(self, actor):
        self.stopped = True
        actor.apply_control(self.control_factory(throttle=0.0, brake=1.0, steer=0.0))
