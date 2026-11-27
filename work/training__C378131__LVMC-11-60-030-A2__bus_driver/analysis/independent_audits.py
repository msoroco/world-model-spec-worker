"""Independent source and comparison predicates for bus-loading review.

These predicates reject absent original evidence. A positive CPU fixture proves
the implementation only; it cannot certify a physical recording or designation.
"""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCE_FILES = ("native_map", "motion", "bus_body", "passenger_body", "camera_manifest")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FIXED = ("cell_id", "street_id", "route_id", "vehicle_class", "weather_id",
         "controller_id", "capture_profile", "loading_purpose")


def _lines(path):
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def audit_source(attempt, context, *, fixture=False):
    attempt = Path(attempt)
    if context.get("source_kind") != ("synthetic_native_sample" if fixture else
                                      "original_native_bus_readback"):
        raise ValueError("original Native source kind missing")
    if context.get("physical_acceptance_claimed"):
        raise ValueError("source context cannot claim acceptance")
    sources = context.get("source_files")
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_FILES):
        raise ValueError("missing source inventory")
    for key in SOURCE_FILES:
        name = sources[key]
        path = attempt / name
        if not path.is_file() or path.resolve().parent != attempt.resolve():
            raise ValueError("missing source file: " + key)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != context.get(key + "_sha256"):
            raise ValueError("stale source hash: " + key)
    map_root = ET.fromstring((attempt / sources["native_map"]).read_text())
    markers = map_root.findall("road/objects/object")
    if (map_root.tag != "OpenDRIVE" or len(markers) != 1 or
            markers[0].get("id") != context.get("zone_id")):
        raise ValueError("original bus loading marker missing")
    motion = _lines(attempt / sources["motion"])
    bus = _lines(attempt / sources["bus_body"])
    passenger = _lines(attempt / sources["passenger_body"])
    frame_map = _lines(attempt / sources["camera_manifest"])
    if any(len(rows) != 600 for rows in (motion, bus, passenger, frame_map)):
        raise ValueError("incomplete 600-frame source join")
    for i, (m, b, p, frame) in enumerate(zip(motion, bus, passenger, frame_map)):
        native = m.get("native_frame")
        if not isinstance(native, int) or any(row.get("native_frame") != native for row in
                                               (b, p, frame)):
            raise ValueError("original Native frame join differs")
        if frame.get("video_frame") != i or abs(m.get("time_s", -1) - i / 20) > .005:
            raise ValueError("20 Hz frame map differs")
        cameras = frame.get("source_cameras")
        hashes = frame.get("camera_rgb_sha256")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(
                cameras[name] != native for name in CAMERAS):
            raise ValueError("four original camera frames missing")
        if not isinstance(hashes, dict) or set(hashes) != set(CAMERAS) or any(
                not isinstance(hashes[name], str) or len(hashes[name]) != 64 for name in CAMERAS):
            raise ValueError("four camera raw pixel hashes missing")
        if any(not isinstance(row.get("body_vertices_m"), list) or
               len(row["body_vertices_m"]) < 4 or
               any(not isinstance(point, list) or len(point) < 3 for point in
                   row["body_vertices_m"]) for row in (b, p)):
            raise ValueError("participant body geometry missing")
        if not isinstance(m.get("bus_speed_mps"), (int, float)):
            raise ValueError("original bus motion missing")
    if not fixture and not (attempt / "capture-seal.json").is_file():
        raise ValueError("sealed Native result missing")
    return {"source_kind": context["source_kind"], "frame_count": 600,
            "source_sha256": {key: context[key + "_sha256"] for key in SOURCE_FILES},
            "original_native_verified": not fixture,
            "physical_completion": "requires_independent_original_pixel_review"}


def audit_comparison(left, right, *, difference):
    if difference not in ("zone_kind", "emergency_context", "vehicle_class"):
        raise ValueError("undeclared comparison variable")
    for report in (left, right):
        if report.get("source_kind") != "original_native_bus_readback" or not report.get("source_audit_sha256"):
            raise ValueError("original audited source missing")
        if report.get("physical_completion") != "reviewed_original":
            raise ValueError("physical completion review missing")
        if not report.get("designation_authority_source_sha256"):
            raise ValueError("designation authority source missing")
    fixed_keys = tuple(key for key in FIXED if key != difference)
    for key in fixed_keys:
        if left.get(key) is None or left[key] != right.get(key):
            raise ValueError("fixed condition differs: " + key)
    for key in ("zone_kind", "emergency_context", "vehicle_class"):
        if key == difference:
            if left.get(key) is None or left[key] == right.get(key):
                raise ValueError("declared difference absent: " + key)
        elif left.get(key) is None or left[key] != right.get(key):
            raise ValueError("undeclared difference: " + key)
    for report in (left, right):
        if not report.get("stopped_loading_reviewed") or not report.get("passenger_exchange_reviewed"):
            raise ValueError("reviewed loading event missing")
    return {"comparison": difference, "source_audits": [left["source_audit_sha256"],
                                                        right["source_audit_sha256"]],
            "fixed_conditions_checked": list(fixed_keys),
            "legal_outcome": "unresolved"}
