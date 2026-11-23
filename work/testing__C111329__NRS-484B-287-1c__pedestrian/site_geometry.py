"""Source-bound, CPU-only checks for the proposed pedestrian crossing site.

These checks describe recorded geometry and device operation. They do not decide
whether a device is legally official, intersections legally adjacent, or an
exception under NRS 484B.290 applies.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _source(packet: dict, key: str) -> dict:
    source = packet.get("sources", {}).get(key)
    if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
        raise ValueError(f"missing source binding: {key}")
    path = Path(source["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError(f"source hash mismatch: {key}")
    expected = {
        "map": {"junctions": packet.get("junctions"), "between_edge": packet.get("between_edge"), "intervening_junction_ids": packet.get("intervening_junction_ids"), "highway_banks": packet.get("highway_banks")},
        "route": {"pedestrian_route": packet.get("pedestrian_route"), "crossing": packet.get("crossing")},
        "devices": packet.get("devices"),
        "markings": packet.get("markings"),
        "highway": packet.get("highway"),
    }[key]
    try:
        actual = json.loads(path.read_text())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid source content: {key}") from exc
    if actual != expected:
        raise ValueError(f"source content mismatch: {key}")
    return source


def _point(value) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("expected planar point")
    point = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in point):
        raise ValueError("nonfinite point")
    return point


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersects(a, b, c, d) -> bool:
    # Collinear or endpoint contact is deliberately inconclusive for this probe.
    x, y = _cross(a, b, c), _cross(a, b, d)
    z, w = _cross(c, d, a), _cross(c, d, b)
    return x * y < 0 and z * w < 0


def assess_site(packet: dict, *, require_operating: bool = True) -> dict:
    for name in ("map", "route", "devices", "markings", "highway"):
        _source(packet, name)
    if packet.get("coordinate_frame") != "map_xy_m":
        raise ValueError("unsupported coordinate frame")
    highway = packet["highway"]
    if not highway.get("boundary_document_id") or not highway.get("public_access_document_id"):
        raise ValueError("highway status provenance missing")
    junctions = packet["junctions"]
    if len(junctions) != 2 or len({j["id"] for j in junctions}) != 2:
        raise ValueError("two distinct junctions required")
    a, b = junctions
    if packet.get("between_edge") != [a["id"], b["id"]] or packet.get("intervening_junction_ids") != []:
        raise ValueError("no source-supported direct segment between junctions")
    aa, bb = _point(a["center"]), _point(b["center"])
    segment = (bb[0] - aa[0], bb[1] - aa[1])
    norm = segment[0] ** 2 + segment[1] ** 2
    if norm <= 0:
        raise ValueError("coincident junctions")
    route = [_point(p) for p in packet["pedestrian_route"]]
    if len(route) < 2:
        raise ValueError("route too short")
    crossing = packet["crossing"]
    entry, exit = _point(crossing["entry"]), _point(crossing["exit"])
    if entry not in route or exit not in route or route.index(entry) >= route.index(exit):
        raise ValueError("crossing not an ordered part of route")
    # The midpoint must lie strictly between source-defined junction envelope radii.
    mid = ((entry[0] + exit[0]) / 2, (entry[1] + exit[1]) / 2)
    t = ((mid[0] - aa[0]) * segment[0] + (mid[1] - aa[1]) * segment[1]) / norm
    distance = math.sqrt(norm)
    if not float(a["envelope_radius_m"]) / distance < t < 1 - float(b["envelope_radius_m"]) / distance:
        raise ValueError("crossing midpoint not between intersection envelopes")
    banks = [(_point(x), _point(y)) for x, y in packet["highway_banks"]]
    if len(banks) != 2 or not all(_intersects(entry, exit, x, y) for x, y in banks):
        raise ValueError("route does not cross both highway banks")
    devices = packet["devices"]
    if {d["junction_id"] for d in devices} != {a["id"], b["id"]} or len(devices) != 2:
        raise ValueError("device required at each junction")
    start, end = (float(v) for v in crossing["time_s"])
    if not math.isfinite(start) or not math.isfinite(end) or start >= end:
        raise ValueError("invalid crossing interval")
    operation = []
    for device in devices:
        if not all(device.get(k) for k in ("device_id", "authority_record_id", "placement_record_id", "purpose_record_id", "governing_participants", "instructions")):
            raise ValueError("device provenance or governance missing")
        windows = device.get("operating_intervals_s", [])
        observed = any(float(lo) <= start and float(hi) >= end for lo, hi in windows)
        operation.append(observed)
        if require_operating and not observed:
            raise ValueError("device operation not established throughout crossing")
    markings = packet["markings"]
    if markings.get("survey_complete") is not True:
        raise ValueError("marked-crosswalk survey incomplete")
    marked_ids = []
    for m in markings.get("marked_crosswalks", []):
        if not m.get("marking_id") or not m.get("survey_record_id"):
            raise ValueError("marking provenance missing")
        lo, hi = (float(v) for v in m["between_edge_station_fraction"])
        if lo <= t <= hi:
            marked_ids.append(m["marking_id"])
    return {
        "between_junction_ids": [a["id"], b["id"]],
        "crossing_station_fraction": t,
        "crosses_both_highway_banks": True,
        "device_ids": sorted(d["device_id"] for d in devices),
        "device_operation_observed": all(operation),
        "marked_crosswalk_ids_at_crossing": sorted(marked_ids),
        "marked_crosswalk_present": bool(marked_ids),
        "legal_adjacency": "undetermined",
        "legal_official_status": "undetermined",
        "nrs_484b_290_exception": "undetermined",
        "source_sha256": {k: packet["sources"][k]["sha256"] for k in ("map", "route", "devices", "markings", "highway")},
    }


def assess_file(path: str | Path) -> dict:
    return assess_site(json.loads(Path(path).read_text()))
