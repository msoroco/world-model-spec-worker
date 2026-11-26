"""Source-bound hill-crest loading-site preflight for exact door cases.

The operator must supply an original surveyed map packet. A test packet only
proves that the checks work; it cannot establish a real loading site.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from door_interaction import Point, inspect_loading_crest, traffic_side


CASE_ACTIONS = {
    "open_near_overlap": ("open", "near", "overlap"),
    "open_near_clear": ("open", "near", "clear"),
    "open_far_side": ("open", "far", "overlap"),
    "board_near": ("board", "near", "overlap"),
    "alight_near": ("alight", "near", "overlap"),
    "door_interference_physical_range-0000": ("open", "near", "clearance_m:0.25"),
    "door_interference_physical_range-0001": ("open", "near", "clearance_m:1.25"),
    "door_interference_physical_range-0002": ("open", "near", "clearance_m:0.75"),
}


def read_packet(path: Path, sha256: str) -> dict:
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("site survey source hash mismatch")
    packet = json.loads(data)
    if packet.get("source_kind") != "original_map_survey":
        raise ValueError("site survey is not an original map measurement")
    route = packet.get("passing_clearance_route_source")
    if route is not None:
        if not isinstance(route, dict) or not route.get("path") or not route.get("sha256"):
            raise ValueError("reviewed passing clearance route source is incomplete")
        route_path = Path(route["path"])
        if not route_path.is_absolute():
            route_path = Path(path).parent / route_path
        if not route_path.is_file() or hashlib.sha256(route_path.read_bytes()).hexdigest() != route["sha256"]:
            raise ValueError("reviewed passing clearance route source hash mismatch")
        if json.loads(route_path.read_text()).get("source_kind") != "original_surveyed_passing_route":
            raise ValueError("original surveyed passing route source is required")
    return packet


def validate_site(packet: dict, case_key: str) -> dict:
    if case_key not in CASE_ACTIONS:
        raise ValueError("unknown exact case")
    if packet.get("source_kind") != "original_map_survey":
        raise ValueError("original map survey is required")
    if not all(packet.get(key) for key in (
            "map_sha256", "map_name", "lane_id", "loading_site_id", "governing_zone_source",
            "parked_vehicle_blueprint", "passing_vehicle_blueprint", "driver_actor_id")):
        raise ValueError("map, actor, or loading-governance source is missing")
    if packet.get("loading_zone_status") != "permitted_for_authored_loading":
        raise ValueError("loading governance has not been established")
    def point(value):
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("survey XY point is missing")
        return Point(*value)
    crest = inspect_loading_crest(
        [tuple(row) for row in packet["route_grade_samples"]],
        packet["loading_station_m"], point(packet["loading_xy"]),
        tuple(point(value) for value in packet["road_edge_xy"]))
    if crest["loading_to_road_edge_m"] > packet["maximum_loading_edge_offset_m"]:
        raise ValueError("loading pose is outside the surveyed loading edge")
    passing = traffic_side(point(packet["parked_heading_xy"]),
                           point(packet["parked_center_xy"]),
                           [point(value) for value in packet["passing_route_xy"]])
    act, side_relation, clearance_variant = CASE_ACTIONS[case_key]
    if clearance_variant.startswith("clearance_m:"):
        source = packet.get("passing_clearance_route_source")
        feasible = packet.get("passing_clearance_feasible_range_m")
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise ValueError("reviewed passing clearance route source is required")
        if not isinstance(feasible, list) or len(feasible) != 2 or not all(
                type(value) in (int, float) for value in feasible):
            raise ValueError("reviewed clearance feasibility range is required")
        request = float(clearance_variant.partition(":")[2])
        if not feasible[0] <= request <= feasible[1]:
            raise ValueError("requested engineering clearance is outside reviewed route feasibility")
    selected_side = passing if side_relation == "near" else (
        "right" if passing == "left" else "left")
    return {"case_key": case_key, "observed_map_sha256": packet["map_sha256"],
            "loading_site_id": packet["loading_site_id"],
            "governing_zone_source": packet["governing_zone_source"],
            "crest_measurement": crest, "passing_side": passing,
            "selected_act": act, "selected_door_side": selected_side,
            "clearance_variant": clearance_variant,
            "requested_engineering_clearance_m": (
                float(clearance_variant.partition(":")[2])
                if clearance_variant.startswith("clearance_m:") else None),
            "physical_feasibility": "unverified_until_native_capture"}
