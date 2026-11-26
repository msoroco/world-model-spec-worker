"""Derive source-gated driveway parking targets for the sixteen exact cases.

The geometry is an engineering request. Legal frontage, activity, necessity,
relationship and postal conclusions remain for original-source review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from driveway_measurements import ASSIGNMENT_ID, footprint_to_mouth_distance


HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _point(value, name):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("surveyed " + name + " point required")
    return (float(value[0]), float(value[1]))


def _number(value, name, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("surveyed " + name + " invalid")
    return float(value)


def _source(root, item, name):
    if not isinstance(item, dict):
        raise ValueError(name + " source required")
    relative = item.get("path")
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute() or
            ".." in Path(relative).parts or not item.get("reviewer") or
            not item.get("citation")):
        raise ValueError(name + " retained review provenance required")
    retained = root / relative
    path = retained.resolve()
    if root not in path.parents or retained.is_symlink() or not path.is_file():
        raise ValueError(name + " source escapes reviewed packet")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != item.get("sha256"):
        raise ValueError(name + " source bytes changed")
    return digest


def validate_survey(packet_path):
    """Require reviewed original map, mouth, frontage, use and actor facts."""
    packet_path = Path(packet_path).resolve()
    root = packet_path.parent
    survey = json.loads(packet_path.read_text(encoding="utf-8"))
    if survey.get("review_status") != "reviewed" or not survey.get("reviewer"):
        raise ValueError("reviewed driveway survey required")
    if survey.get("driveway_kind") not in ("public", "private"):
        raise ValueError("reviewed driveway kind required")
    sources = survey.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed source inventory required")
    hashes = {name: _source(root, sources.get(name), name) for name in
              ("opendrive", "mouth", "frontage", "driveway_use", "responsible_person",
               "relationship", "purpose", "traffic_direction", "postal_status")}
    a = _point(survey.get("road_start_xy_m"), "road start")
    b = _point(survey.get("road_end_xy_m"), "road end")
    mouth_a = _point(survey.get("mouth_start_xy_m"), "mouth start")
    mouth_b = _point(survey.get("mouth_end_xy_m"), "mouth end")
    length = math.dist(a, b)
    if length < 70 or math.dist(mouth_a, mouth_b) < 1:
        raise ValueError("surveyed road or mouth geometry insufficient")
    vehicle_length = _number(survey.get("vehicle_length_m"), "vehicle length", 3, 8)
    vehicle_width = _number(survey.get("vehicle_width_m"), "vehicle width", 1, 3)
    if not survey.get("vehicle_blueprint_id") or not survey.get("driveway_id"):
        raise ValueError("reviewed vehicle or driveway identity required")
    return survey, hashes, (a, b), (mouth_a, mouth_b), (vehicle_length, vehicle_width)


def _body(center, axis, length, width):
    normal = (-axis[1], axis[0])
    corners = [[center[0] + sx * axis[0] * length / 2 + sy * normal[0] * width / 2,
                center[1] + sx * axis[1] * length / 2 + sy * normal[1] * width / 2]
               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return [[x, y, z] for x, y in corners for z in (0, 1.5)]


def build_plan(packet_path, case_id, *, approach_direction=1):
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    matches = [case for case in plan["cases"] if case["case_id"] == case_id]
    if len(matches) != 1 or not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("unknown exact driveway case")
    if approach_direction not in (-1, 1):
        raise ValueError("approach direction invalid")
    case = matches[0]
    survey, hashes, (a, b), (mouth_a, mouth_b), (length, width) = validate_survey(packet_path)
    if survey["driveway_kind"] != case["driveway_kind"]:
        raise ValueError("surveyed driveway kind differs from exact case")
    road_length = math.dist(a, b)
    axis = ((b[0] - a[0]) / road_length, (b[1] - a[1]) / road_length)
    mouth_middle = ((mouth_a[0] + mouth_b[0]) / 2, (mouth_a[1] + mouth_b[1]) / 2)
    center_s = (mouth_middle[0] - a[0]) * axis[0] + (mouth_middle[1] - a[1]) * axis[1]
    def at(s):
        return [a[0] + axis[0] * s, a[1] + axis[1] * s]
    def distance(s):
        return footprint_to_mouth_distance(_body(at(s), axis, length, width), mouth_a, mouth_b)
    position = case["position_target"]
    if position == "front":
        target_s = center_s
        if distance(target_s) > 0.05:
            raise ValueError("surveyed road does not put vehicle in front of mouth")
    else:
        # Search on one surveyed side of the mouth. The brackets are engineering
        # targets around the statutory distance, not legal frontage findings.
        desired = 0.75 if position == "within_5ft" else 2.5
        candidates = [(abs(distance(center_s + sign * step / 20) - desired),
                       center_s + sign * step / 20)
                      for sign in (-1, 1) for step in range(1, 501)
                      if 5 <= center_s + sign * step / 20 <= road_length - 5]
        if not candidates:
            raise ValueError("no surveyed driveway placement candidates")
        _, target_s = min(candidates)
        observed = distance(target_s)
        if (position == "within_5ft" and not 0 < observed < 1.524 or
                position == "outside_5ft" and not observed > 1.524):
            raise ValueError("survey cannot realize exact distance branch")
    start_s = target_s - approach_direction * 20
    depart_s = target_s + approach_direction * 15
    if not all(4 <= s <= road_length - 4 for s in (start_s, target_s, depart_s)):
        raise ValueError("surveyed road cannot support approach and departure")
    return {"case_id": case_id, "survey_sha256": hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(),
            "source_sha256": hashes, "driveway_kind": case["driveway_kind"],
            "activity_request": case["activity"], "position_request": position,
            "relationship_context_request": case["driver_relationship"],
            "necessity_or_postal_context_request": case["necessity_or_postal_context"],
            "approach_direction": approach_direction, "start_xy_m": at(start_s),
            "target_xy_m": at(target_s), "depart_xy_m": at(depart_s),
            "route_axis_xy": list(axis),
            "vehicle_blueprint_id": survey["vehicle_blueprint_id"],
            "planned_full_footprint_to_mouth_m": distance(target_s),
            "controller": {"kind": "route_tracking_then_activity_hold", "activity": case["activity"],
                           "hold_min_s": 20, "target_tolerance_m": 0.5},
            "capture": {"rate_hz": 20, "duration_s": 45, "cameras": list(CAMERAS)},
            "frontage_judgment": "unresolved", "necessity_judgment": "unresolved",
            "private_relationship_judgment": "unresolved", "postal_judgment": "unresolved",
            "physical_acceptance_claimed": False}
