"""Source-gated NRS 484B.560(7)(a) railway geometry and original-frame measures.

This module exposes physical measurements, never a legal verdict. Native capture
must supply the original actor, track, road-profile, obstacle and contact records.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

LAW = "NRS-484B-560-7a"
CELL = "C410753"
ACTOR = "heavy_vehicle_driver"
FOOT_M = 0.3048
CASE_AXES = {
    "space_halt_before_15ft": ("opposite_space", "halt"),
    "space_clear_beyond_15ft": ("opposite_space", "clear"),
    "clearance_grounded_before_15ft": ("undercarriage", "halt"),
    "clearance_pass_beyond_15ft": ("undercarriage", "clear"),
    "trailing_end_14_9ft": ("boundary", "below"),
    "trailing_end_15_0ft": ("boundary", "at"),
    "trailing_end_15_1ft": ("boundary", "above"),
}


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("missing finite original value: " + name)
    return float(value)


def _vector(value, name):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("missing original xyz: " + name)
    return [_number(v, name) for v in value]


def load_source(path: str | Path, expected_sha256: str):
    path = Path(path)
    if not path.is_file() or not path.resolve().is_relative_to(Path.cwd().resolve()):
        raise ValueError("reviewed source packet path missing or outside repository")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed source packet hash mismatch")
    return json.loads(raw)


def validate_site(site: dict, case_name: str):
    if case_name not in CASE_AXES:
        raise ValueError("unselected railway case")
    if (site.get("law_id"), site.get("cell_id"), site.get("actor")) != (LAW, CELL, ACTOR):
        raise ValueError("railway source identity mismatch")
    if site.get("layout") != "paved_road" or site.get("maneuver") != "cross_railway" or site.get("control") != "rail_track":
        raise ValueError("frozen railway cell mismatch")
    track = site.get("track")
    if not isinstance(track, dict) or track.get("grade_crossing") is not True:
        raise ValueError("original grade crossing required")
    rails = track.get("rails")
    if not isinstance(rails, list) or not rails:
        raise ValueError("original rail geometry required")
    ids = set()
    for rail in rails:
        if not isinstance(rail, dict) or not rail.get("rail_id") or rail["rail_id"] in ids:
            raise ValueError("rail identity missing or repeated")
        ids.add(rail["rail_id"])
        _vector(rail.get("point_m"), "rail point")
        _vector(rail.get("tangent_unit"), "rail tangent")
        if not rail.get("original_geometry_ref"):
            raise ValueError("rail geometry source missing")
    if not track.get("crossing_profile_ref") or not track.get("source_sha256"):
        raise ValueError("crossing profile source missing")
    vehicle = site.get("vehicle")
    if not isinstance(vehicle, dict) or vehicle.get("driver_role") != ACTOR:
        raise ValueError("actual heavy-vehicle driver required")
    for key in ("blueprint_id", "blueprint_source_ref", "bounding_box_source_ref", "undercarriage_geometry_ref"):
        if not vehicle.get(key):
            raise ValueError("heavy vehicle source missing: " + key)
    dims = _vector(vehicle.get("dimensions_m"), "vehicle dimensions")
    if min(dims) <= 0:
        raise ValueError("invalid actual vehicle dimensions")
    coupled = vehicle.get("coupled_units")
    if not isinstance(coupled, list):
        raise ValueError("coupled-unit inventory required")
    for unit in coupled:
        if not all(unit.get(k) for k in ("actor_id", "dimensions_source_ref", "coupling_source_ref")):
            raise ValueError("coupled-unit source missing")
    if not site.get("route_clearance_source_ref") or not site.get("approach_visibility_source_ref"):
        raise ValueError("road route and approach-visibility sources required")
    axis, mode = CASE_AXES[case_name]
    case = site.get("case")
    if not isinstance(case, dict) or case.get("name") != case_name or case.get("axis") != axis or case.get("mode") != mode:
        raise ValueError("selected railway construction mismatch")
    if axis == "opposite_space":
        for key in ("downstream_occupancy_source_ref", "available_space_m", "opposite_side_boundary_ref"):
            if case.get(key) is None or case.get(key) == "":
                raise ValueError("opposite-side-space construction missing: " + key)
        if _number(case["available_space_m"], "available opposite-side space") < 0:
            raise ValueError("negative opposite-side space")
    elif axis == "undercarriage":
        for key in ("road_profile_source_ref", "undercarriage_source_ref", "minimum_clearance_m"):
            if case.get(key) is None or case.get(key) == "":
                raise ValueError("undercarriage construction missing: " + key)
        _number(case["minimum_clearance_m"], "undercarriage clearance")
    else:
        if case.get("target_trailing_end_ft") != {"below": 14.9, "at": 15.0, "above": 15.1}[mode]:
            raise ValueError("statutory boundary engineering target mismatch")
    return site


def projection(point, origin, unit):
    return sum((p - o) * u for p, o, u in zip(point, origin, unit))


def measure_frames(site: dict, rows: list[dict]):
    """Measure source-observed trailing end, stops and possible causes.

    `crossing_axis_unit` points in the travel direction. Each original row has
    per-unit rear body vertices, actual speed, rail geometry, obstruction gaps
    and contact/grounding records. No authored label substitutes for these.
    """
    if not rows:
        raise ValueError("original railway frame history missing")
    axis = _vector(site.get("crossing_axis_unit"), "crossing axis")
    norm = math.sqrt(sum(x * x for x in axis))
    if abs(norm - 1.0) > 1e-4:
        raise ValueError("crossing axis must be a source-derived unit vector")
    rails = site["track"]["rails"]
    rail_positions = [projection(_vector(r["point_m"], "rail point"), [0., 0., 0.], axis) for r in rails]
    nearest_rail = max(rail_positions)
    prior_frame = None
    prior_time = None
    samples = []
    for row in rows:
        frame = row.get("source_frame")
        time = _number(row.get("time_s"), "frame time")
        if type(frame) is not int or (prior_frame is not None and frame != prior_frame + 1):
            raise ValueError("original Native frames are not consecutive")
        if prior_time is not None and not .049 <= time - prior_time <= .051:
            raise ValueError("original Native cadence is not 20 Hz")
        prior_frame, prior_time = frame, time
        if row.get("source_site_sha256") != site.get("source_sha256"):
            raise ValueError("original frame is not joined to reviewed site")
        units = row.get("vehicle_units")
        if not isinstance(units, list) or len(units) != 1 + len(site["vehicle"]["coupled_units"]):
            raise ValueError("original heavy-vehicle/coupled-unit samples missing")
        vertices = []
        for unit in units:
            if not unit.get("actor_id") or not unit.get("blueprint_id") or not unit.get("body_source_ref"):
                raise ValueError("original body source missing")
            body = unit.get("body_vertices_m")
            if not isinstance(body, list) or len(body) < 8:
                raise ValueError("original body vertices missing")
            vertices += [_vector(v, "body vertex") for v in body]
        tail = min(projection(v, [0., 0., 0.], axis) for v in vertices)
        dist_ft = (tail - nearest_rail) / FOOT_M
        speed = _number(row.get("speed_mps"), "actual speed")
        gap = _number(row.get("downstream_body_gap_m"), "downstream body gap")
        contact = row.get("undercarriage_contact")
        if type(contact) is not bool or not row.get("contact_source_ref"):
            raise ValueError("original undercarriage contact evidence missing")
        if row.get("control_source_ref") is None or row.get("traffic_conflict_source_ref") is None:
            raise ValueError("original stop-cause sources missing")
        samples.append({"source_frame": frame, "time_s": time,
                        "trailing_end_past_nearest_rail_ft": dist_ft,
                        "speed_mps": speed, "downstream_body_gap_m": gap,
                        "undercarriage_contact": contact,
                        "traffic_conflict": row.get("traffic_conflict"),
                        "brake_applied": row.get("brake_applied")})
    halt = any(x["speed_mps"] <= .1 and x["trailing_end_past_nearest_rail_ft"] < 15.0 for x in samples)
    return {"samples": samples, "halt_before_15ft_observed": halt,
            "maximum_trailing_end_ft": max(x["trailing_end_past_nearest_rail_ft"] for x in samples),
            "space_evidence": any(x["downstream_body_gap_m"] <= 0 for x in samples),
            "contact_evidence": any(x["undercarriage_contact"] for x in samples),
            "causal_attribution": "requires independent source review",
            "legal_judgment": "unresolved"}
