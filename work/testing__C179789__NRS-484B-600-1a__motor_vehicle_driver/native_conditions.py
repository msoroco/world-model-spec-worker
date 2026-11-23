"""CARLA-lazy original condition sampler for the basic-speed comparison.

The caller owns the world, actors, snapshot boundary and TickCapture lifecycle.
No statutory speed decision is made here.
"""

from __future__ import annotations

import math
import hashlib
from xml.etree import ElementTree as ET

from saved_conditions import seal


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _road_lane(world, actor):
    transform = actor.get_transform()
    waypoint = world.get_map().get_waypoint(transform.location, project_to_road=False)
    if waypoint is None or bool(getattr(waypoint, "is_junction", False)):
        raise ValueError("original actor lacks a straight lane waypoint")
    return waypoint, transform


def _driving_width(map_text: str, road_id: int, station: float) -> float:
    """Evaluate both directions' driving-lane widths at the source waypoint."""
    root = ET.fromstring(map_text)
    road = next((item for item in root.findall("road")
                 if item.get("id") == str(road_id)), None)
    if road is None:
        raise ValueError("original OpenDRIVE road ID is missing")
    sections = sorted(road.findall("./lanes/laneSection"), key=lambda item: float(item.get("s", "0")))
    active = [section for section in sections if float(section.get("s", "0")) <= station]
    if not active:
        raise ValueError("original OpenDRIVE lane section is missing")
    section = active[-1]
    offset = station - float(section.get("s", "0"))
    total = 0.0
    for side in ("left", "right"):
        for lane in section.findall("./" + side + "/lane"):
            if lane.get("type") != "driving":
                continue
            records = sorted(lane.findall("width"), key=lambda item: float(item.get("sOffset", "0")))
            active_width = [item for item in records if float(item.get("sOffset", "0")) <= offset]
            if not active_width:
                raise ValueError("original OpenDRIVE driving width is missing")
            record = active_width[-1]
            ds = offset - float(record.get("sOffset", "0"))
            width = sum(float(record.get(name, "0")) * ds ** power
                        for power, name in enumerate(("a", "b", "c", "d")))
            if not math.isfinite(width) or width <= 0:
                raise ValueError("original OpenDRIVE driving width is invalid")
            total += width
    if total <= 0:
        raise ValueError("original OpenDRIVE has no driving width")
    return total


def sample_native(world, ego, leader, snapshot) -> dict:
    """Read one frame from live Native actor/world APIs after a caller's tick."""
    frame = snapshot.frame
    if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
        raise ValueError("Native snapshot frame is invalid")
    time = _finite(snapshot.timestamp.elapsed_seconds, "snapshot time")
    ego_waypoint, ego_transform = _road_lane(world, ego)
    leader_waypoint, leader_transform = _road_lane(world, leader)
    if (ego_waypoint.road_id, ego_waypoint.lane_id) != (leader_waypoint.road_id, leader_waypoint.lane_id):
        raise ValueError("leader is not on the ego's original roadway lane")
    forward = ego_transform.get_forward_vector()
    fx, fy = _finite(forward.x, "heading x"), _finite(forward.y, "heading y")
    magnitude = math.hypot(fx, fy)
    if magnitude <= 0:
        raise ValueError("ego heading is unavailable")
    dx = _finite(leader_transform.location.x - ego_transform.location.x, "leader dx")
    dy = _finite(leader_transform.location.y - ego_transform.location.y, "leader dy")
    along = (dx * fx + dy * fy) / magnitude
    if along <= 0:
        raise ValueError("leader is not ahead of ego")
    ego_extent = _finite(ego.bounding_box.extent.x, "ego longitudinal extent")
    leader_extent = _finite(leader.bounding_box.extent.x, "leader longitudinal extent")
    gap = max(0.0, along - ego_extent - leader_extent)
    velocity = ego.get_velocity()
    speed = math.sqrt(sum(_finite(getattr(velocity, axis), "ego velocity") ** 2
                          for axis in ("x", "y", "z")))
    weather = world.get_weather()
    map_text = world.get_map().to_opendrive()
    width = _driving_width(map_text, ego_waypoint.road_id,
                           _finite(ego_waypoint.s, "road station"))
    if width < _finite(ego_waypoint.lane_width, "lane width"):
        raise ValueError("OpenDRIVE carriageway width is narrower than ego lane")
    wheels = ego.get_physics_control().wheels
    if not wheels:
        raise ValueError("original ego wheel friction is missing")
    tire_friction = min(_finite(wheel.tire_friction, "wheel tire friction") for wheel in wheels)
    return {"frame": frame, "time_s": time, "source_frame": frame,
            "ego_speed_mps": speed, "leader_gap_m": gap,
            "highway_width_m": width,
            "surface_wetness": _finite(weather.wetness, "native wetness") / 100,
            "precipitation_strength": _finite(weather.precipitation, "native precipitation"),
            "fog_density": _finite(weather.fog_density, "native fog density"),
            "tire_friction": tire_friction,
            "source_ids": {"ego_actor_id": ego.id, "leader_actor_id": leader.id,
                           "road_id": ego_waypoint.road_id, "lane_id": ego_waypoint.lane_id,
                           "opendrive_sha256": hashlib.sha256(map_text.encode()).hexdigest()}}


class NativeConditionCapture:
    """Append source frames during one Native attempt, then close exactly once."""

    def __init__(self, attempt, case_id):
        self.attempt = attempt
        self.case_id = case_id
        self.rows = []
        self.closed = False

    def append(self, world, ego, leader, snapshot):
        if self.closed:
            raise ValueError("original condition capture is closed")
        row = sample_native(world, ego, leader, snapshot)
        if self.rows:
            previous = self.rows[-1]
            if row["frame"] != previous["frame"] + 1 or not .049 <= row["time_s"] - previous["time_s"] <= .051:
                raise ValueError("Native condition frames must be contiguous at 20 Hz")
            if row["source_ids"] != previous["source_ids"]:
                raise ValueError("Native condition actor or OpenDRIVE source changed")
        self.rows.append(row)
        return row

    def close(self):
        if self.closed:
            raise ValueError("original condition capture already closed")
        result = seal(self.attempt, self.case_id, self.rows, diagnostic_fixture=False)
        self.closed = True
        return result
