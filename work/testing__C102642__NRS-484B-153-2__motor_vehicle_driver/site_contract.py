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
}


def read_packet(path: Path, sha256: str) -> dict:
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("site survey source hash mismatch")
    packet = json.loads(data)
    if packet.get("source_kind") != "original_map_survey":
        raise ValueError("site survey is not an original map measurement")
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
    selected_side = passing if side_relation == "near" else (
        "right" if passing == "left" else "left")
    return {"case_key": case_key, "observed_map_sha256": packet["map_sha256"],
            "loading_site_id": packet["loading_site_id"],
            "governing_zone_source": packet["governing_zone_source"],
            "crest_measurement": crest, "passing_side": passing,
            "selected_act": act, "selected_door_side": selected_side,
            "clearance_variant": clearance_variant,
            "physical_feasibility": "unverified_until_native_capture"}
