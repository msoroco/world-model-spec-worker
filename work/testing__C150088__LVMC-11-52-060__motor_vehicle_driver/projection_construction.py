"""Parked assembly construction and original Native geometry readback.

The local Native adapter owns CARLA actors. This module requires reviewed curb
geometry and checks what was spawned; requested dimensions are never evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite

from projection_measurement import ASSIGNMENT, LIMIT_M


@dataclass(frozen=True)
class Case:
    suffix: str
    projection_m: float
    controlling_part: str

    @property
    def case_id(self):
        return ASSIGNMENT + "__" + self.suffix


CASES = (
    Case("vehicle_below", 4.2, "vehicle"),
    Case("vehicle_equal", LIMIT_M, "vehicle"),
    Case("vehicle_above", 5.0, "vehicle"),
    Case("load_above", 5.0, "load"),
    Case("trailer_above", 5.0, "trailer"),
)


def _point(value, name):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) not in (float, int) or not isfinite(v) for v in value)):
        raise ValueError("reviewed finite " + name + " required")
    return tuple(float(v) for v in value)


def curb_frame(site):
    """Return original curb origin, streetward unit normal and tangent."""
    if not site.get("reviewer") or not site.get("opendrive_sha256"):
        raise ValueError("reviewed source and OpenDRIVE binding required")
    a = _point(site.get("curb_segment_start_m"), "curb start")
    b = _point(site.get("curb_segment_end_m"), "curb end")
    street = _point(site.get("street_side_reference_m"), "street side")
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = hypot(dx, dy)
    if length < 5:
        raise ValueError("reviewed curb segment too short for full assembly")
    tangent = (dx / length, dy / length)
    normal = (-tangent[1], tangent[0])
    signed = ((street[0] - a[0]) * normal[0] +
              (street[1] - a[1]) * normal[1])
    if abs(signed) < 1:
        raise ValueError("street-side reference too close to curb")
    if signed < 0:
        normal = (-normal[0], -normal[1])
    return a, tangent, normal


def _outer_projection(outline, origin, normal):
    if not isinstance(outline, list) or len(outline) < 3:
        raise ValueError("original complete outline required")
    return max((_point(p, "outline")[0] - origin[0]) * normal[0] +
               (_point(p, "outline")[1] - origin[1]) * normal[1] for p in outline)


def build_and_readback(adapter, site, case_id, *, candidate="primary"):
    """Create the exact parked body, optional load/trailer and verify readback.

    The adapter API is intentionally small and explicit. The site's curb line
    and map hash must have been independently reviewed. The adapter must reject
    any unsupported physical load or attached trailer; a tag alone is invalid.
    """
    case = next((item for item in CASES if item.case_id == case_id), None)
    if case is None:
        raise ValueError("unknown exact projection case")
    if candidate not in ("primary", "fallback1"):
        raise ValueError("unknown candidate")
    origin, tangent, normal = curb_frame(site)
    if adapter.provenance() != "original_native":
        raise ValueError("original Native adapter required")
    if adapter.verify_loaded_map(site["opendrive_sha256"]) is not True:
        raise ValueError("loaded Native map differs from reviewed OpenDRIVE")
    if adapter.verify_curb(site, origin, tangent, normal) is not True:
        raise ValueError("real curb and street-side geometry readback failed")
    # The low vehicle position remains fixed for both part-extension pairs.
    vehicle_target = case.projection_m if case.controlling_part == "vehicle" else 4.2
    # Fallback changes only a camera-neutral parking station, not curb offset.
    station_m = 15.0 if candidate == "primary" else 18.0
    owned = []
    try:
        vehicle = adapter.spawn_parked_vehicle(
            station_m=station_m, outer_projection_m=vehicle_target,
            curb_origin_m=origin, curb_tangent=tangent, street_normal=normal,
            blueprint=site["vehicle_blueprint"], parking_brake=True)
        owned.append(vehicle)
        if adapter.parking_brake_readback(vehicle) is not True:
            raise ValueError("parking brake Native readback failed")
        parts = [("vehicle", vehicle)]
        if case.controlling_part == "load":
            load = adapter.attach_physical_load(
                vehicle, outer_projection_m=case.projection_m,
                source_blueprint=site["load_blueprint"])
            owned.append(load)
            if adapter.attachment_parent(load) != vehicle:
                raise ValueError("load is not physically attached to vehicle")
            parts.append(("load", load))
        if case.controlling_part == "trailer":
            trailer = adapter.attach_physical_trailer(
                vehicle, outer_projection_m=case.projection_m,
                source_blueprint=site["trailer_blueprint"])
            owned.append(trailer)
            if adapter.attachment_parent(trailer) != vehicle or not adapter.hitch_readback(vehicle, trailer):
                raise ValueError("trailer hitch Native readback failed")
            parts.append(("trailer", trailer))
        readbacks = []
        for category, actor in parts:
            identity = adapter.actor_identity(actor)
            outline = adapter.world_outline_xy(actor)
            if not identity:
                raise ValueError("original actor identity required")
            readbacks.append({"category": category, "source_actor_id": identity,
                              "outline_vertices_m": outline})
        projections = {part["category"]: _outer_projection(
            part["outline_vertices_m"], origin, normal) for part in readbacks}
        controlling = max(projections, key=projections.get)
        if controlling != case.controlling_part:
            raise ValueError("realized controlling physical part differs")
        # This is a construction tolerance, not a legal equality claim.
        if abs(projections[controlling] - case.projection_m) > 0.08:
            raise ValueError("original projection differs from engineering target")
        return {"case_id": case_id, "candidate": candidate, "owned": owned,
                "station_m": station_m, "curb_origin_m": origin,
                "curb_tangent": tangent, "street_normal": normal,
                "physical_parts": readbacks,
                "original_projection_m": projections[controlling],
                "construction_tolerance_m": 0.08,
                "legal_equality_claimed": False}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
