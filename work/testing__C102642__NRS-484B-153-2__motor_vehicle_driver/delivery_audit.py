"""Independent saved-source audit for a Native door interaction attempt."""
from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path

from PIL import Image

from delivery_measure import measure, read_sealed_trace
from native_capture import CAMERAS, FRAME_COUNT
from site_contract import read_packet, validate_site


def audit_site_binding(trace: dict, *, survey_path: Path, survey_sha256: str,
                       case_id: str, act: str, side: str) -> dict:
    """Reopen the original survey and join its exact site to saved observations."""
    packet = read_packet(survey_path, survey_sha256)
    key = case_id.rsplit("__", 1)[-1]
    site = validate_site(packet, key)
    if site["selected_act"] != act or site["selected_door_side"] != side:
        raise ValueError("selected act or side differs from surveyed site")
    context = trace.get("fixed_context", {})
    expected = {
        "map_sha256": packet["map_sha256"],
        "survey_sha256": survey_sha256,
        "loading_site_id": packet["loading_site_id"],
        "driver_id": packet["driver_actor_id"],
        "traffic_route_id": packet.get("traffic_route_id", packet["lane_id"]),
    }
    if not isinstance(context, dict) or any(context.get(k) != v for k, v in expected.items()):
        raise ValueError("saved trace differs from original site or actor source")
    if trace.get("parked_center_xy") != packet["parked_center_xy"] or (
            trace.get("parked_heading_xy") != packet["parked_heading_xy"]):
        raise ValueError("saved parked pose differs from original survey")
    return {"survey_sha256": survey_sha256,
            "loading_site_id": packet["loading_site_id"],
            "selected_act": act, "selected_door_side": side,
            "original_site_binding_checked": True}


def audit_saved(attempt: Path, *, trace_sha256: str, case_id: str,
                act: str, side: str, expected_dimensions: dict,
                survey_path: Path | None = None, survey_sha256: str | None = None) -> dict:
    """Decode all original camera PNGs and remeasure the sealed actor trace.

    Expected dimensions are explicit per view because a diagnostic fixture can
    be small. A production attempt must supply the actual capture profile.
    """
    if set(expected_dimensions) != set(CAMERAS):
        raise ValueError("four expected camera dimensions are required")
    trace = read_sealed_trace(attempt / "native-trace.json", trace_sha256)
    frames = trace.get("frames")
    if not isinstance(frames, list) or len(frames) != FRAME_COUNT:
        raise ValueError("full 900-frame original trace is required")
    measurement = measure(trace, expected_case_id=case_id,
                          expected_act=act, expected_side=side)
    if (survey_path is None) != (survey_sha256 is None):
        raise ValueError("survey path and hash must be supplied together")
    site_binding = (audit_site_binding(trace, survey_path=survey_path,
                                      survey_sha256=survey_sha256, case_id=case_id,
                                      act=act, side=side)
                    if survey_path is not None else None)
    expected = set()
    for frame in frames:
        frame_id = frame["frame_id"]
        for view in CAMERAS:
            location = attempt / "cameras" / view / f"{frame_id:06d}.png"
            expected.add(location)
            data = location.read_bytes()
            if hashlib.sha256(data).hexdigest() != frame.get("camera_sha256", {}).get(view):
                raise ValueError("camera bytes differ from sealed original trace: " + view)
            with Image.open(BytesIO(data)) as image:
                if image.format != "PNG" or image.size != tuple(expected_dimensions[view]):
                    raise ValueError("camera format or dimensions changed: " + view)
                image.load()
    observed = set((attempt / "cameras").rglob("*.png"))
    if observed != expected:
        raise ValueError("camera frame inventory differs from original trace")
    return {"case_id": case_id, "original_trace_sha256": trace_sha256,
            "frame_count": FRAME_COUNT, "decoded_camera_frames": len(expected),
            "original_site_binding": site_binding,
            "act_on_closest_side": measurement["act_on_closest_side"],
            "minimum_body_gap_m": measurement["minimum_body_gap_m"],
            "legal_interference": "unresolved_judgment",
            "physical_visibility": "requires_human_review"}
