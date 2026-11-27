"""Reject unreviewed or incompatible original left-turn route packets."""

from __future__ import annotations

from hashlib import sha256
import json
from math import atan2, degrees, hypot, isfinite
from pathlib import Path

METRES_PER_FOOT = 0.3048
DISTRICT_BY_TAG = {
    "residence": "residential", "other_area": "other", "business": "business"
}
REQUIRED_SOURCE_FIELDS = (
    "highway_source", "district_source", "frontage_source",
    "building_use_source", "freight_zone_source", "route_source",
    "vehicle_source", "driver_source", "speed_source", "weather_source",
)


def _point(value: object) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("original route point must be xyz")
    point = tuple(float(v) for v in value)
    if not all(isfinite(v) for v in point):
        raise ValueError("nonfinite original route point")
    return point


def validate(site: dict, case_tag: str, *, allow_diagnostic: bool = False) -> dict:
    """Validate a source packet before any CARLA import or world mutation."""
    from signal_controller import TARGETS_FT

    if case_tag not in TARGETS_FT:
        raise ValueError("unknown exact case")
    if site.get("source_kind") != "original_local_left_turn_site_inventory":
        raise ValueError("unverified original site inventory")
    if site.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic packet is not original source")
    for key in ("map_name", "ego_blueprint_id", "district_kind", "maneuver",
                "freight_zone_actor_id", "approach_start_xyz", "turn_vertex_xyz",
                "outgoing_target_xyz", "reviewer", "drive_speed_m_s",
                "camera_rig_source", "camera_rigs",
                *REQUIRED_SOURCE_FIELDS):
        if not site.get(key):
            raise ValueError("missing original site field: " + key)
    expected_district = next((district for prefix, district in DISTRICT_BY_TAG.items()
                              if case_tag.startswith(prefix)), None)
    if site["district_kind"] != expected_district or site["maneuver"] != "left_turn":
        raise ValueError("selected district or turn differs from reviewed site")
    speed = float(site["drive_speed_m_s"])
    # One 20 Hz speed step must resolve one foot between below/at/above requests.
    # This is capture resolution and does not impose a legal speed limit.
    if not isfinite(speed) or not 0.5 <= speed < METRES_PER_FOOT / 0.05:
        raise ValueError("source speed cannot resolve one-foot probe")
    from native_capture_contract import CAMERAS, DIMENSIONS
    if set(site["camera_rigs"]) != set(CAMERAS):
        raise ValueError("original four-camera rig incomplete")
    for name, rig in site["camera_rigs"].items():
        if (not isinstance(rig, dict) or not isinstance(rig.get("relative_xyz"), list)
                or not isinstance(rig.get("relative_ypr_deg"), list)
                or len(rig["relative_ypr_deg"]) != 3
                or list(rig.get("dimensions", [])) != list(DIMENSIONS[name])):
            raise ValueError("original camera rig differs: " + name)
        _point(rig["relative_xyz"])
    start, turn, end = (_point(site[k]) for k in
                        ("approach_start_xyz", "turn_vertex_xyz", "outgoing_target_xyz"))
    incoming = (turn[0] - start[0], turn[1] - start[1])
    outgoing = (end[0] - turn[0], end[1] - turn[1])
    approach_m = hypot(*incoming)
    departure_m = hypot(*outgoing)
    angle = degrees(atan2(incoming[0] * outgoing[1] - incoming[1] * outgoing[0],
                          incoming[0] * outgoing[0] + incoming[1] * outgoing[1]))
    if approach_m < 320 * METRES_PER_FOOT or departure_m < 10:
        raise ValueError("original left-turn route too short for 300-foot probe")
    if not 35 <= angle <= 135:
        raise ValueError("reviewed route is not a left turn")
    review = site.get("district_review")
    if not isinstance(review, dict) or not all(review.get(k) for k in
                                               ("jurisdiction", "frontage_bounds",
                                                "building_uses", "reviewer")):
        raise ValueError("district frontage and building-use review required")
    return {"district_kind": expected_district, "approach_length_m": approach_m,
            "departure_length_m": departure_m, "signed_turn_angle_deg": angle,
            "source_citations": {k: site[k] for k in REQUIRED_SOURCE_FIELDS}}


def read_site(path: Path, expected_sha256: str, case_tag: str,
              *, allow_diagnostic: bool = False) -> dict:
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original site hash mismatch")
    site = json.loads(raw)
    validate(site, case_tag, allow_diagnostic=allow_diagnostic)
    return site
