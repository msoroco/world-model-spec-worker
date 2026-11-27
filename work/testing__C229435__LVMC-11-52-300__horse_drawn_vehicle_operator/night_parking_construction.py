"""Source-gated physical construction of a street parking episode.

The reviewed packet is an external original site/vehicle dossier. A package
cannot turn an actor name or a car blueprint into proof of a horse-drawn vehicle.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FPS = 20
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inside(point, polygon):
    x, y = point
    odd = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < crossing:
                odd = not odd
    return odd


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2 or not all(type(x) in (int, float) and math.isfinite(x) for x in value):
        raise ValueError(label + " needs finite XY coordinates")
    return value


def _polygon(value, label):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError(label + " needs three or more vertices")
    for point in value:
        _point(point, label)
    if len({tuple(point) for point in value}) < 3:
        raise ValueError(label + " is degenerate")
    return value


def _source(root, item, label):
    if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
        raise ValueError(label + " needs source path and SHA256")
    rel = Path(item["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(label + " path escapes source root")
    path = root / rel
    if not path.is_file() or _sha(path) != item["sha256"]:
        raise ValueError(label + " original source hash mismatch")
    return path


def validate_site(packet_path, source_root):
    packet_path = Path(packet_path)
    root = Path(source_root)
    packet = json.loads(packet_path.read_text())
    if packet.get("format") != "night-parking-reviewed-site-v1":
        raise ValueError("reviewed site format required")
    sources = packet.get("sources")
    for label in ("opendrive", "municipal_boundary", "street_status", "vehicle_build", "person_activity"):
        _source(root, sources.get(label) if isinstance(sources, dict) else None, label)
    if not packet.get("native_map_name") or not packet.get("native_opendrive_sha256"):
        raise ValueError("Native map identity required")
    if packet["native_opendrive_sha256"] != sources["opendrive"]["sha256"]:
        raise ValueError("OpenDRIVE map hash conflicts with reviewed source")
    geometry = packet.get("geometry", {})
    street = _polygon(geometry.get("street_polygon_xy_m"), "street")
    city = _polygon(geometry.get("municipal_polygon_xy_m"), "municipality")
    carriage = _point(geometry.get("carriage_park_xy_m"), "carriage location")
    other = _point(geometry.get("other_vehicle_xy_m"), "other vehicle location")
    if not all(_inside(point, street) and _inside(point, city) for point in (carriage, other)):
        raise ValueError("both vehicles need original street and city placement")
    if carriage == other:
        raise ValueError("vehicles overlap at center")
    if not geometry.get("carriage_body_dimensions_m") or not geometry.get("other_vehicle_body_dimensions_m"):
        raise ValueError("both physical body dimensions required")
    source_review = packet.get("source_review", {})
    for label in ("carriage_transport_capable", "carriage_motive_power", "vehicle_exclusions", "responsible_person", "street_public_access", "municipal_jurisdiction"):
        if not source_review.get(label):
            raise ValueError("missing independent source review: " + label)
    native = packet.get("native_actors", {})
    for label in ("carriage_blueprint", "other_vehicle_blueprint", "responsible_person_blueprint"):
        if not native.get(label):
            raise ValueError("missing Native actor blueprint: " + label)
    if native["carriage_blueprint"] == native["other_vehicle_blueprint"] and not native.get("carriage_physical_customization_source"):
        raise ValueError("carriage needs physical differentiation and provenance")
    return packet


def plan_case(case, packet):
    design = case["design"]
    if design["duration_s"] < 0 or design["duration_s"] > 3600:
        raise ValueError("unbounded parking duration")
    duration = design["duration_s"]
    # Fixed 1805 s physical window isolates parked duration while retaining
    # 2 s before and at least 2 s after the 1801 s longest episode.
    frames = round(1805 * FPS) + 1
    parked_first_index = 2 * FPS
    parked_last_index = parked_first_index + round(duration * FPS)
    if frames < 2:
        raise ValueError("parking episode needs at least two frames")
    return {
        "case_id": case["case_id"],
        "site_sha256": hashlib.sha256(json.dumps(packet, sort_keys=True).encode()).hexdigest(),
        "native_map_name": packet["native_map_name"],
        "native_opendrive_sha256": packet["native_opendrive_sha256"],
        "fps": FPS,
        "duration_s": duration,
        "capture_duration_s": frames / FPS,
        "original_frame_count": frames,
        "parked_first_index": parked_first_index,
        "parked_last_index": parked_last_index,
        "civil_start_local_request": design["start_local"],
        "vehicle_class_request": design["vehicle_class"],
        "activity_request": design["purpose"],
        "carriage_park_xy_m": packet["geometry"]["carriage_park_xy_m"],
        "other_vehicle_xy_m": packet["geometry"]["other_vehicle_xy_m"],
        "cameras": list(VIEWS),
        "required_saved_sources": ["four_synchronized_original_video_streams", "frame_map", "original_actors", "reviewed_site", "classification", "activity_events", "civil_clock"],
        "legal_outcome_request": None,
    }
