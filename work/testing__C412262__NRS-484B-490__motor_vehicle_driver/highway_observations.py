"""Source-bound geometry checks for NRS 484B.490; no legal width cutoff."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point(value):
    if not isinstance(value, list) or len(value) != 2 or any(not isinstance(v, (int, float)) for v in value):
        raise ValueError("finite planar point required")
    return tuple(float(v) for v in value)


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def inside(p, polygon):
    vertices = [point(v) for v in polygon]
    if len(vertices) < 3:
        raise ValueError("full highway boundary polygon required")
    contained = False
    for index, a in enumerate(vertices):
        b = vertices[(index + 1) % len(vertices)]
        area = cross(a, b, p)
        if abs(area) <= 1e-8 and min(a[0], b[0]) - 1e-8 <= p[0] <= max(a[0], b[0]) + 1e-8 and min(a[1], b[1]) - 1e-8 <= p[1] <= max(a[1], b[1]) + 1e-8:
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < x:
                contained = not contained
    return contained


def observe(case_id: str, context_path: Path, trace_path: Path, receipt_path: Path) -> dict:
    from highway_scene_construction import load_case, validate_site

    case = load_case(case_id)
    context = json.loads(context_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if context.get("assignment_id") != case_id.rsplit("__", 1)[0] or context.get("case_id") != case_id:
        raise ValueError("original highway context identity mismatch")
    for key in ("highway_width_request", "device_request", "activity_request", "parking_location_request"):
        if context.get(key) != case[key]:
            raise ValueError("original highway context differs from exact case: " + key)
    if (receipt.get("assignment_id") != case_id.rsplit("__", 1)[0] or
            receipt.get("case_id") != case_id or receipt.get("source_kind") != "original_native_capture" or
            receipt.get("context_sha256") != sha(context_path) or
            receipt.get("trace_sha256") != sha(trace_path)):
        raise ValueError("original highway context or trace seal mismatch")
    if context.get("source_kind") != "original_reviewed_highway_site":
        raise ValueError("original reviewed highway source required")
    site_path = context_path.parent / "reviewed-source/reviewed-site.json"
    if not site_path.is_file() or site_path.is_symlink() or context.get("site_sha256") != sha(site_path):
        raise ValueError("original reviewed highway source packet missing or changed")
    reviewed_site = validate_site(site_path, case_id)
    if reviewed_site["_source_sha256"] != context["site_sha256"]:
        raise ValueError("original reviewed highway source packet seal mismatch")
    for key in ("map_sha256", "dedication_sha256", "boundary_sha256", "public_access_sha256",
                "width_survey_sha256", "device_erection_sha256", "device_authority_sha256",
                "device_content_sha256", "device_conformity_sha256", "device_extent_sha256",
                "person_identity_sha256", "vehicle_identity_sha256", "activity_source_sha256"):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("reviewed source hash required: " + key)
        if value != reviewed_site[key]:
            raise ValueError("original context differs from reviewed source: " + key)
    highway = context.get("highway_boundary_xy_m")
    extent = context.get("device_extent_xy_m")
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    if len(rows) != receipt.get("frame_count") or not rows:
        raise ValueError("original highway frame count mismatch")
    samples = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or abs(row.get("time_s", -1) - index / 20) > 0.002:
            raise ValueError("original highway 20 Hz cadence mismatch")
        body = [point(v) for v in row.get("vehicle_body_polygon_xy_m", [])]
        if len(body) < 4:
            raise ValueError("full subject body footprint required")
        speed = row.get("vehicle_speed_mps", row.get("speed_mps"))
        if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not math.isfinite(speed):
            raise ValueError("actual subject speed missing")
        samples.append({"frame": index, "time_s": row["time_s"], "speed_mps": speed,
                        "body_on_highway": all(inside(p, highway) for p in body),
                        "body_in_device_extent": all(inside(p, extent) for p in body)})
    return {"case_id": case_id, "samples": samples,
            "full_highway_width_profile_m": context.get("full_highway_width_profile_m"),
            "highway_status_source_label": context.get("highway_status"),
            "device_source_label": context.get("device_status"),
            "activity_source_label": context.get("activity_status"),
            "narrow_highway_judgment": "unresolved",
            "official_device_judgment": "unresolved",
            "parking_judgment": "unresolved",
            "statutory_disposition": "unresolved_pending_original_review",
            "physical_acceptance": "unverified"}
