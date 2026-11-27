"""Fail-closed reviewed-site admission for exact angle-parking construction.

The review records are source claims, not an original recording or legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C377875__NRS-484B-460__motor_vehicle_driver"
SOURCE_NAMES = ("map", "roadway", "official_device", "authority", "vehicle", "purpose")


def _point(value: object) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("finite two-coordinate point required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("finite two-coordinate point required")
    return float(value[0]), float(value[1])


def _polygon(value: object) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("governed-space polygon required")
    return [_point(v) for v in value]


def _inside(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    hit = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            hit = not hit
    return hit


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_site(path: Path, case_id: str) -> tuple[dict, dict]:
    path = path.resolve()
    site = json.loads(path.read_text(encoding="utf-8"))
    if site.get("assignment_id") != ASSIGNMENT or site.get("case_id") != case_id:
        raise ValueError("wrong angle-parking assignment or exact case")
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("case ID outside exact assignment")
    sources = site.get("sources")
    if not isinstance(sources, dict) or set(SOURCE_NAMES) - set(sources):
        raise ValueError("all reviewed original site source packets required")
    records = {}
    for name in SOURCE_NAMES:
        ref = sources[name]
        rel = ref.get("path") if isinstance(ref, dict) else None
        if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("source path must be relative and contained: " + name)
        target = (path.parent / rel).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file():
            raise ValueError("original site source absent: " + name)
        if _hash(target) != ref.get("sha256"):
            raise ValueError("original site source hash differs: " + name)
        records[name] = json.loads(target.read_text(encoding="utf-8"))
    road = records["roadway"]
    if road.get("district") != "business" or road.get("highway_status") != "reviewed_original":
        raise ValueError("original business-district highway review required")
    edge = road.get("curb_edge_xy")
    if not isinstance(edge, list) or len(edge) != 2:
        raise ValueError("source-backed curb edge required")
    a, b = _point(edge[0]), _point(edge[1])
    if math.dist(a, b) < 1:
        raise ValueError("curb edge degenerate")
    device = records["official_device"]
    if device.get("official_status") != "reviewed_original" or not device.get("content_review"):
        raise ValueError("source-backed official angle-parking device required")
    indicated = device.get("indicated_angle_degrees")
    if isinstance(indicated, bool) or not isinstance(indicated, (int, float)) or not math.isfinite(indicated) or not 0 <= indicated <= 90:
        raise ValueError("reviewed indicated geometric angle required")
    space = _polygon(device.get("governed_space_polygon_xy"))
    target = _point(site.get("target_xy"))
    approach = _point(site.get("approach_xy"))
    if not _inside(target, space) or math.dist(target, approach) < 8:
        raise ValueError("target must be within governed space and have approach")
    suffix = case_id.rsplit("__", 1)[-1]
    expected_activity, expected_orientation = suffix.split("_", 1)
    if site.get("requested_activity") != expected_activity or site.get("requested_orientation") != expected_orientation:
        raise ValueError("reviewed site differs from exact activity or angle contrast")
    if expected_activity not in {"stop", "stand", "park"} or expected_orientation not in {"indicated", "offset"}:
        raise ValueError("unsupported exact case")
    if records["purpose"].get("activity_review") != "reviewed_original":
        raise ValueError("original halt purpose and service review required")
    if not records["authority"].get("source") or not records["vehicle"].get("source"):
        raise ValueError("source-backed authority and vehicle required")
    if not isinstance(records["map"].get("opendrive_sha256"), str) or len(records["map"]["opendrive_sha256"]) != 64:
        raise ValueError("original OpenDRIVE hash required")
    if not isinstance(site.get("map_id"), str) or not isinstance(site.get("road_id"), int):
        raise ValueError("Native map and road identity required")
    if not isinstance(site.get("vehicle_blueprint_id"), str) or not site["vehicle_blueprint_id"]:
        raise ValueError("reviewed vehicle blueprint required")
    if not isinstance(device.get("prop_blueprint_id"), str) or not isinstance(device.get("prop_pose"), dict):
        raise ValueError("reviewed device prop construction required")
    pose = device["prop_pose"]
    if any(isinstance(pose.get(k), bool) or not isinstance(pose.get(k), (int, float)) or not math.isfinite(pose[k]) for k in ("x", "y", "z", "yaw_deg")):
        raise ValueError("finite reviewed device prop pose required")
    approach_heading = site.get("approach_heading_degrees")
    if isinstance(approach_heading, bool) or not isinstance(approach_heading, (int, float)) or not math.isfinite(approach_heading):
        raise ValueError("finite construction approach heading required")
    heading = site.get("target_heading_degrees")
    if isinstance(heading, bool) or not isinstance(heading, (int, float)) or not math.isfinite(heading):
        raise ValueError("finite construction target heading required")
    ux, uy = (b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b)
    radians = math.radians(heading)
    target_angle = math.degrees(math.acos(min(1.0, max(0.0, abs(math.cos(radians) * ux + math.sin(radians) * uy)))))
    requested_angle = float(indicated) if expected_orientation == "indicated" else float(site.get("offset_angle_degrees", -1))
    if expected_orientation == "offset" and not (0 <= requested_angle <= 90 and abs(requested_angle - indicated) >= 5):
        raise ValueError("bounded engineering offset contrast required")
    if abs(target_angle - requested_angle) > 1:
        raise ValueError("target heading does not construct requested angle")
    return site, records
