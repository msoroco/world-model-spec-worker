"""Preflight a reviewed original highway and business-district turn site."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FEET_PER_METRE = 3.280839895013123
REQUIRED_CITATIONS = ("highway_source", "district_source", "frontage_source",
                      "building_use_source", "loading_zone_source", "driver_source",
                      "route_source")


def _point(value: object) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("original route point must be three-dimensional")
    point = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in point):
        raise ValueError("nonfinite original route point")
    return point


def validate(site: dict, *, allow_diagnostic: bool = False) -> dict:
    if site.get("source_kind") != "original_local_signal_site_inventory":
        raise ValueError("unverified original signal site source")
    if site.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot stand for an original signal site")
    for key in ("map_name", "ego_blueprint_id", "district_kind", "maneuver",
                "loading_zone_actor_id", "turn_vertex_xyz", "approach_start_xyz",
                "outgoing_target_xyz", "camera_rig_source", "camera_rigs",
                "drive_speed_source", "drive_speed_m_s", *REQUIRED_CITATIONS):
        if not site.get(key):
            raise ValueError("missing original signal site field: " + key)
    if site["district_kind"] != "business" or site["maneuver"] != "right_turn":
        raise ValueError("selected business-district right turn differs")
    speed = float(site["drive_speed_m_s"])
    # One 20 Hz sample must travel less than the one-foot separation between
    # the authored 100 ft and 101 ft probes. This is capture resolution,
    # never a statutory speed or distance threshold.
    resolution_speed_max = 0.3048 / .05
    if not math.isfinite(speed) or not .5 <= speed < resolution_speed_max:
        raise ValueError("reviewed right-turn drive speed outside supported source range")
    from native_capture_contract import CAMERAS, DIMENSIONS
    if set(site["camera_rigs"]) != set(CAMERAS):
        raise ValueError("reviewed four-camera rig incomplete")
    for name, rig in site["camera_rigs"].items():
        if (not isinstance(rig, dict) or not isinstance(rig.get("relative_xyz"), list)
                or not isinstance(rig.get("relative_ypr_deg"), list)
                or len(rig["relative_ypr_deg"]) != 3
                or list(rig.get("dimensions", [])) != list(DIMENSIONS[name])):
            raise ValueError("reviewed camera rig invalid: " + name)
        _point(rig["relative_xyz"])
    start = _point(site["approach_start_xyz"])
    turn = _point(site["turn_vertex_xyz"])
    end = _point(site["outgoing_target_xyz"])
    incoming = (turn[0] - start[0], turn[1] - start[1])
    outgoing = (end[0] - turn[0], end[1] - turn[1])
    approach = math.hypot(*incoming)
    departure = math.hypot(*outgoing)
    if approach * FEET_PER_METRE < 140 or departure < 10:
        raise ValueError("original right-turn route too short")
    cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
    dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
    angle = math.degrees(math.atan2(cross, dot))
    if not -135 <= angle <= -35:
        raise ValueError("original route is not a right turn")
    if not isinstance(site.get("business_district_review"), dict) or not all(
            site["business_district_review"].get(key) for key in
            ("jurisdiction", "frontage_bounds", "building_uses", "reviewer")):
        raise ValueError("reviewed business-district frontage and use source required")
    return {"map_name": site["map_name"], "approach_length_m": approach,
            "departure_length_m": departure, "signed_turn_angle_deg": angle,
            "numeric_probe_resolution_speed_max_m_s": resolution_speed_max,
            "turn_vertex_xyz": list(turn),
            "source_citations": {key: site[key] for key in REQUIRED_CITATIONS}}


def read_site(path: Path, expected_sha256: str, *, allow_diagnostic: bool = False) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original signal site hash mismatch")
    site = json.loads(raw)
    validate(site, allow_diagnostic=allow_diagnostic)
    return site
