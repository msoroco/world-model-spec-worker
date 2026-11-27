"""Source-gated one-way roadway stop plan and original-motion measurements.

Controller targets below are engineering settings. None defines the statutory
meaning of normal and reasonable movement, necessity, or compliance with law.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C150640__NRS-484B-627-2__motor_vehicle_driver"
LAW = "NRS-484B-627-2"


@dataclass(frozen=True)
class Case:
    name: str
    stop_surface: str
    stop_reason: str
    follower_action: str
    complete_stop_requested: bool


CASES = (
    Case("destination_follower_halts", "roadway", "destination", "follow_and_halt", True),
    Case("destination_follower_passes", "roadway", "destination", "pass", True),
    Case("safety_conflict_stop", "roadway", "safety_conflict", "follow_and_halt", True),
    Case("law_direction_stop", "roadway", "official_direction", "follow_and_halt", True),
    Case("destination_off_roadway", "shoulder", "destination", "follow_and_halt", True),
    Case("destination_slow_roll", "roadway", "destination", "follow_and_halt", False),
)
BY_NAME = {case.name: case for case in CASES}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewed_scene(packet: Path, case_id: str) -> dict:
    """Demand original byte-hashed geometry/context; a case name proves nothing."""
    packet = Path(packet).resolve()
    value = json.loads(packet.read_text(encoding="utf-8"))
    if (value.get("format") != "c150640-roadway-stop-original-v1"
            or value.get("case_id") != case_id
            or value.get("source_kind") != "original_reviewed"
            or value.get("diagnostic_fixture") is not False
            or not value.get("reviewer")):
        raise ValueError("reviewed original stop scene identity missing")
    required = ("map", "roadway_boundary", "shoulder_boundary", "one_way_direction",
                "ego_driver", "ego_vehicle", "follower_vehicle", "follower_driver",
                "stop_purpose", "conflict_context", "official_direction",
                "jurisdiction", "passing_space")
    sources = value.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed stop source inventory missing")
    for role in required:
        source = sources.get(role)
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise ValueError("reviewed source missing: " + role)
        item = packet.parent / source["path"]
        resolved = item.resolve()
        if item.is_symlink() or not resolved.is_relative_to(packet.parent) or not resolved.is_file():
            raise ValueError("reviewed source escapes packet: " + role)
        if sha(resolved) != source["sha256"]:
            raise ValueError("reviewed source hash differs: " + role)
    if not value.get("map_id") or not value.get("ego_blueprint_id") or not value.get("follower_blueprint_id"):
        raise ValueError("reviewed map or participant blueprint missing")
    if not value.get("one_way_route") or len(value["one_way_route"]) < 2:
        raise ValueError("reviewed one-way route missing")
    if value.get("route_direction_confirmed") is not True:
        raise ValueError("one-way direction not reviewed")
    if not value.get("roadway_polygon") or not value.get("shoulder_polygon"):
        raise ValueError("roadway and shoulder boundaries missing")
    return value


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            intersect = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < intersect:
                inside = not inside
        j = i
    return inside


def footprint_surface(corners: list[list[float]], scene: dict) -> str:
    if len(corners) != 4 or any(len(point) != 2 for point in corners):
        raise ValueError("four original vehicle footprint corners required")
    on_roadway = [point_in_polygon(tuple(point), scene["roadway_polygon"]) for point in corners]
    on_shoulder = [point_in_polygon(tuple(point), scene["shoulder_polygon"]) for point in corners]
    if all(on_roadway):
        return "roadway"
    if all(on_shoulder) and not any(on_roadway):
        return "shoulder"
    return "boundary_or_unresolved"


def longitudinal_gap(ego_xy, follower_xy, route_heading_rad, ego_length_m, follower_length_m):
    dx = ego_xy[0] - follower_xy[0]
    dy = ego_xy[1] - follower_xy[1]
    centre_gap = dx * math.cos(route_heading_rad) + dy * math.sin(route_heading_rad)
    return centre_gap - (ego_length_m + follower_length_m) / 2


def controller_target(case: Case, frame: int, ego_speed: float, follower_speed: float,
                      body_gap_m: float) -> dict:
    """Return separate ego/follower actuation requests; no teleportation."""
    if frame < 200:
        ego = {"throttle": 0.36 if ego_speed < 8 else 0.0, "brake": 0.0}
    elif case.complete_stop_requested:
        ego = {"throttle": 0.0, "brake": 0.85}
    else:
        ego = {"throttle": 0.10 if ego_speed < 1.5 else 0.0,
               "brake": 0.25 if ego_speed > 1.8 else 0.0}
    if case.follower_action == "follow_and_halt":
        follower = {"throttle": 0.3 if follower_speed < 7 and body_gap_m > 12 else 0.0,
                    "brake": 0.8 if body_gap_m < 11 else 0.0}
    else:
        follower = {"throttle": 0.3 if follower_speed < 7 else 0.0,
                    "brake": 0.8 if body_gap_m < 6 else 0.0}
    return {"ego": ego, "follower": follower}


def measure_original(rows: list[dict], scene: dict, case: Case) -> dict:
    if len(rows) < 3:
        raise ValueError("original frame history too short")
    previous = None
    for row in rows:
        if row.get("ego_id") is None or row.get("follower_id") is None:
            raise ValueError("two original vehicle IDs required")
        if row["ego_id"] == row["follower_id"]:
            raise ValueError("ego and follower identities collapse")
        key = (row["original_frame"], row["time_s"])
        if previous is not None and (key[0] <= previous[0] or key[1] <= previous[1]):
            raise ValueError("original frame/time history is nonmonotone")
        previous = key
        if row.get("ego_speed_mps") is None or row.get("follower_speed_mps") is None:
            raise ValueError("original participant speed missing")
        if row.get("ego_footprint_xy") is None or row.get("follower_route_station_m") is None:
            raise ValueError("original footprint or follower station missing")
    stationary = [row for row in rows if row["ego_speed_mps"] <= 0.05]
    stopped = len(stationary) >= 4 and stationary[-1]["time_s"] - stationary[0]["time_s"] >= .15
    surfaces = sorted({footprint_surface(row["ego_footprint_xy"], scene)
                       for row in stationary}) if stationary else []
    follower_progress = rows[-1]["follower_route_station_m"] - rows[0]["follower_route_station_m"]
    pre_stop = [row for row in rows if row["time_s"] < stationary[0]["time_s"]] if stationary else rows
    return {
        "case_id": ASSIGNMENT + "__" + case.name,
        "frame_count": len(rows),
        "actual_complete_stop": stopped,
        "stop_surfaces": surfaces,
        "follower_progress_m": follower_progress,
        "pre_stop_follower_speed_mps": [row["follower_speed_mps"] for row in pre_stop],
        "post_stop_follower_speed_mps": [row["follower_speed_mps"] for row in rows if row not in pre_stop],
        "post_stop_body_gap_m": [row.get("body_gap_m") for row in rows if row not in pre_stop],
        "follower_passed_ego": any(row.get("follower_ahead_of_ego") is True for row in rows),
        "collision_or_conflict": [row.get("conflict_readback") for row in rows],
        "official_direction_readback": [row.get("official_direction_readback") for row in rows],
        "stop_purpose_source_sha256": scene["sources"]["stop_purpose"]["sha256"],
        "jurisdiction_source_sha256": scene["sources"]["jurisdiction"]["sha256"],
        "normal_reasonable_movement_judgment": None,
        "safety_necessity_judgment": None,
        "legal_compliance_judgment": None,
        "statutory_verdict": None,
    }
