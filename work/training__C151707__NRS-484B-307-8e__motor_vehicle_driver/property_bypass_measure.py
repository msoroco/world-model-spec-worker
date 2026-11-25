"""Saved-source route diagnostic for NRS 484B.307(8)(e).

No route geometry alone can prove a driver's purpose. This reducer preserves
the purpose declaration and its source separately from observed movement.
"""
from __future__ import annotations

import hashlib
import json

ASSIGNMENT = "training__C151707__NRS-484B-307-8e__motor_vehicle_driver"
ASSIGNMENT_SHA = "8c5ac6b6cfba329e4f933ebb5286c802fbc7abbb89c79cc0cb53a0db532b043d"
WITNESS_SHA = "e0d290f07c0d6c4a196500cbfede67a5f1d34b7adece923f7e4a4f3ca534c072"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def measure(frame_bytes: bytes, map_bytes: bytes, purpose_bytes: bytes) -> dict:
    frames_source = json.loads(frame_bytes)
    site = json.loads(map_bytes)
    intent = json.loads(purpose_bytes)
    require(all(x["assignment_id"] == ASSIGNMENT for x in (frames_source, site, intent)), "assignment mismatch")
    kind = frames_source["source_kind"]
    require(kind in {"synthetic_native_sample", "native_saved_sample"}, "source kind missing")
    require(site["source_kind"] == kind and intent["source_kind"] == kind, "source kind mismatch")
    require(site["approach_lane_id"] and site["intersecting_street_id"], "lane topology missing")
    require(site["private_or_public_property_id"] and site["property_boundary_source_id"], "property boundary source missing")
    require(site["cross_street_signal_id"] and site["approach_signal_id"], "signal inventory missing")
    require(intent["declaration_source_id"] and intent["declared_purpose"] in {"avoid_red_signal", "other", "unknown"}, "purpose source missing")
    frames = frames_source["frames"]
    require(len(frames) >= 600, "recording shorter than 30 seconds")
    require(all(f["frame"] == i and abs(f["t_s"] - i / 20) < 1e-8 for i, f in enumerate(frames)), "noncontiguous 20 Hz frames")
    require(all(f["vehicle_id"] == frames_source["vehicle_id"] for f in frames), "vehicle identity changed")
    require(all(f["zone"] in {"approach_road", "property", "intersecting_street"} for f in frames), "unknown route zone")
    require(all(f["approach_signal"] in {"steady_red_alone", "green", "yellow", "unknown"} and f["cross_street_signal"] in {"red", "not_red", "unknown"} for f in frames), "signal state missing")
    property_frames = [f["frame"] for f in frames if f["zone"] == "property"]
    cross_frames = [f["frame"] for f in frames if f["zone"] == "intersecting_street"]
    first_property = property_frames[0] if property_frames else None
    first_cross = cross_frames[0] if cross_frames else None
    ordered_path = first_property is not None and first_cross is not None and first_property < first_cross
    at_property = frames[first_property] if first_property is not None else None
    before_property = frames[first_property - 1] if first_property is not None and first_property > 0 else None
    at_cross = frames[first_cross] if first_cross is not None else None
    return {
        "format": "c151707-saved-property-bypass-diagnostic-v1",
        "assignment_id": ASSIGNMENT,
        "source_kind": kind,
        "frame_source_sha256": digest(frame_bytes),
        "map_inventory_sha256": digest(map_bytes),
        "purpose_declaration_sha256": digest(purpose_bytes),
        "frame_count": len(frames),
        "duration_s": len(frames) / 20,
        "approach_lane_id": site["approach_lane_id"],
        "property_id": site["private_or_public_property_id"],
        "property_boundary_source_id": site["property_boundary_source_id"],
        "intersecting_street_id": site["intersecting_street_id"],
        "first_property_frame": first_property,
        "first_intersecting_street_frame": first_cross,
        "property_then_intersecting_street": ordered_path,
        "steady_red_alone_at_property_entry": at_property["approach_signal"] == "steady_red_alone" if at_property else None,
        "steady_red_alone_before_property_entry": before_property["approach_signal"] == "steady_red_alone" if before_property else None,
        "cross_street_not_red_at_entry": at_cross["cross_street_signal"] == "not_red" if at_cross else None,
        "declared_purpose": intent["declared_purpose"],
        "declaration_source_id": intent["declaration_source_id"],
        "legal_result": None,
        "unresolved": ["physical property boundary and authority", "signal facing and temporal continuity", "purpose authenticity", "physical source validity"],
    }
