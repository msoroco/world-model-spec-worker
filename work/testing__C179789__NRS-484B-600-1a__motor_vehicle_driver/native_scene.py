"""CARLA-lazy actor and condition construction for seven exact speed cases.

The reviewed source packet is supplied by the local operator. This module does
not invent a roadway, weather measurement, or reasonable/proper speed cutoff.
"""

from __future__ import annotations

import hashlib
import json
import math
import copy
from pathlib import Path

from comparison_audit import DIRECTION
from native_conditions import _cross_section_widths


VARIABLES = ("ego_speed_request_mps", "leader_initial_gap_m",
             "surface_wetness_request", "highway_width_m",
             "native_precipitation_request", "native_fog_request")


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return float(value)


def validate(packet_path: Path, plan_path: Path, case_id: str) -> tuple[dict, dict, dict]:
    """Bind the exact case and one reviewed numerical construction packet."""
    packet = json.loads(Path(packet_path).read_bytes())
    plan = json.loads(Path(plan_path).read_bytes())
    cases = {case["case_id"] for case in plan["cases"]}
    if case_id not in cases or set(packet.get("cases", {})) != cases:
        raise ValueError("reviewed Native packet lacks seven exact cases")
    if (packet.get("assignment_id") != plan["assignment_id"] or
            not packet.get("source_citation") or not packet.get("reviewer") or
            not isinstance(packet.get("map_sha256"), str) or
            len(packet["map_sha256"]) != 64 or
            not packet.get("ego_blueprint_id") or not packet.get("leader_blueprint_id")):
        raise ValueError("reviewed Native source or identity missing")
    if packet.get("duration_frames") != 900 or packet.get("camera_profile") != "four-view":
        raise ValueError("fixed duration or four-view profile differs")
    if packet.get("paved_road") is not True or not packet.get("travel_direction"):
        raise ValueError("reviewed paved road or travel direction missing")
    _finite(packet.get("leader_speed_request_mps"), "leader speed request")
    entries = packet["cases"]
    for key, item in entries.items():
        if (item.get("case_id") != key or not item.get("source_citation") or
                not item.get("reviewer") or set(item.get("variables", {})) != set(VARIABLES)):
            raise ValueError("exact case source or authored variables missing")
        for name, value in item["variables"].items():
            _finite(value, name)
        if item["variables"]["leader_initial_gap_m"] < 4:
            raise ValueError("leader initial clearance too short for safe Native spawn")
        if not 0 <= item["variables"]["surface_wetness_request"] <= 1:
            raise ValueError("wetness request outside Native range")
        for name in ("native_precipitation_request", "native_fog_request"):
            if item["variables"][name] > 100:
                raise ValueError("Native weather request outside range")
        if (not isinstance(item.get("road_id"), int) or
                not isinstance(item.get("lane_id"), int) or item["lane_id"] == 0):
            raise ValueError("reviewed road and lane IDs missing")
        _finite(item.get("ego_station_m"), "ego station")
    for comparison in plan["comparisons"]:
        first, second = (entries[key] for key in comparison["case_ids"])
        variable = comparison["deliberate_differences"][0]
        changed = {name for name in VARIABLES if first["variables"][name] != second["variables"][name]}
        if changed != {variable}:
            raise ValueError("Native packet changes an undeclared comparison variable")
        if DIRECTION[comparison["comparison_id"]] * (
                second["variables"][variable] - first["variables"][variable]) <= 0:
            raise ValueError("Native packet comparison direction differs")
        if comparison["comparison_id"] != "width" and any(
                first[name] != second[name] for name in ("road_id", "lane_id", "ego_station_m")):
            raise ValueError("Native packet changes a fixed roadway or station")
    return packet, entries[case_id], plan


class NativeScene:
    def __init__(self, world, weather, ego, leader, spawned, source, targets):
        self.world, self.weather = world, weather
        self.ego, self.leader, self.spawned, self.source = ego, leader, spawned, source
        self.targets = targets

    def close(self):
        for actor in reversed(self.spawned):
            actor.destroy()
        self.spawned.clear()
        self.world.set_weather(self.weather)


def create(world, packet_path: Path, plan_path: Path, case_id: str, velocity_factory):
    """Spawn aligned participants and apply requested Native condition controls."""
    packet, item, _ = validate(packet_path, plan_path, case_id)
    map_text = world.get_map().to_opendrive()
    map_hash = hashlib.sha256(map_text.encode()).hexdigest()
    if map_hash != packet["map_sha256"]:
        raise ValueError("reviewed OpenDRIVE source differs from Native world")
    waypoint = world.get_map().get_waypoint_xodr(
        item["road_id"], item["lane_id"], item["ego_station_m"])
    if waypoint is None or waypoint.is_junction or waypoint.lane_type.name != "Driving":
        raise ValueError("reviewed Native ego spawn is not on a driving lane")
    realized_width = _cross_section_widths(
        map_text, waypoint.road_id, item["ego_station_m"])["mapped_cross_section_width_m"]
    if abs(realized_width - item["variables"]["highway_width_m"]) > .05:
        raise ValueError("OpenDRIVE mapped cross-section width differs from reviewed Native request")
    gap = _finite(item["variables"]["leader_initial_gap_m"], "leader gap")
    ahead = waypoint.next(gap + 5.0)
    if len(ahead) != 1 or (ahead[0].road_id, ahead[0].lane_id) != (waypoint.road_id, waypoint.lane_id):
        raise ValueError("leader route is not ahead on the same driving lane")
    blueprints = world.get_blueprint_library()
    spawned = []
    previous_weather = copy.copy(world.get_weather())
    try:
        def spawn(blueprint_id, position):
            actor = world.try_spawn_actor(blueprints.find(blueprint_id), position.transform)
            if actor is None:
                raise ValueError("reviewed Native vehicle spawn failed")
            spawned.append(actor)
            return actor
        ego = spawn(packet["ego_blueprint_id"], waypoint)
        leader = spawn(packet["leader_blueprint_id"], ahead[0])
        weather = world.get_weather()
        wetness = item["variables"]["surface_wetness_request"] * 100
        weather.wetness = wetness
        weather.precipitation = item["variables"]["native_precipitation_request"]
        weather.fog_density = item["variables"]["native_fog_request"]
        world.set_weather(weather)
        friction = item.get("tire_friction_request")
        if friction is not None:
            friction = _finite(friction, "tire friction")
            if friction <= 0:
                raise ValueError("tire friction must be positive")
            physics = ego.get_physics_control()
            if not physics.wheels:
                raise ValueError("ego wheel physics unavailable")
            for wheel in physics.wheels:
                wheel.tire_friction = friction
            ego.apply_physics_control(physics)
        direction = waypoint.transform.get_forward_vector()
        speed = item["variables"]["ego_speed_request_mps"]
        ego.set_target_velocity(velocity_factory(direction.x * speed,
                                                 direction.y * speed,
                                                 direction.z * speed))
        source = {"packet_sha256": hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(),
                  "opendrive_sha256": map_hash, "case_id": case_id,
                  "ego_actor_id": ego.id, "leader_actor_id": leader.id,
                  "road_id": waypoint.road_id, "lane_id": waypoint.lane_id}
        targets = {"ego_speed_mps": speed,
                   "leader_speed_mps": packet["leader_speed_request_mps"]}
        return NativeScene(world, previous_weather, ego, leader, spawned, source, targets)
    except Exception:
        world.set_weather(previous_weather)
        for actor in reversed(spawned):
            actor.destroy()
        raise
