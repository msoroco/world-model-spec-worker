"""Bind a reviewed original yield site and its proposed Native construction."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from yield_site import ASSIGNMENT, select_stop_reference

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
SUFFIXES = ("fallback_nearest_view_stop", "fallback_earlier_obscured_stop",
            "marked_line_stop", "nearest_crosswalk_stop", "no_safety_stop_required")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reviewed(path, case_id):
    path = Path(path).resolve()
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact yield case")
    review = json.loads(path.read_text(encoding="utf-8"))
    if review.get("case_id") != case_id or review.get("review_status") != "reviewed_original":
        raise ValueError("exact independently reviewed original yield source required")
    references = review.get("sources")
    if not isinstance(references, dict) or set(references) != {"opendrive", "site_packet", "camera_placement"}:
        raise ValueError("original map, yield site and four-camera placement sources required")
    sources = {}
    for name, ref in references.items():
        source = Path(ref["path"])
        source = (source if source.is_absolute() else path.parent / source).resolve()
        if not source.is_file() or sha(source) != ref.get("sha256"):
            raise ValueError("reviewed original source hash changed: " + name)
        sources[name] = source
    site = json.loads(sources["site_packet"].read_text(encoding="utf-8"))
    if (site.get("case_id") != case_id or site.get("source_review_status") != "reviewed_original" or
            not site.get("source_records") or site.get("map_sha256") != sha(sources["opendrive"])):
        raise ValueError("original site, map or source-review binding differs")
    required_records = {"yield_sign", "crosswalk_and_line_inventory", "highway_boundary",
                        "occluder_geometry", "driver_viewpoint", "approaching_traffic",
                        "safety_necessity"}
    if not required_records <= set(site["source_records"]):
        raise ValueError("original yield statutory source inventory incomplete")
    for name, ref in site["source_records"].items():
        if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
            raise ValueError("source-hashed original yield record required: " + str(name))
        source = Path(ref["path"])
        source = (source if source.is_absolute() else sources["site_packet"].parent / source).resolve()
        if not source.is_file() or sha(source) != ref["sha256"]:
            raise ValueError("original yield source record changed: " + str(name))
    reference = select_stop_reference(sources["site_packet"])
    suffix = case_id.rsplit("__", 1)[1]
    expected = {"fallback_nearest_view_stop": ("nearest_point_with_geometric_view", "yes"),
                "fallback_earlier_obscured_stop": ("nearest_point_with_geometric_view", "yes"),
                "marked_line_stop": ("marked_stop_line", "yes"),
                "nearest_crosswalk_stop": ("nearest_crosswalk", "yes"),
                "no_safety_stop_required": ("nearest_point_with_geometric_view", "no")}
    if (reference["reference_kind"], site["stopping_required_for_safety"]) != expected[suffix]:
        raise ValueError("original stop reference or reviewed safety context differs from exact case")
    if not str(site.get("ego_blueprint", "")).startswith("vehicle.") or not site.get("ego_spawn"):
        raise ValueError("reviewed motor-vehicle spawn required")
    if not isinstance(site.get("occluder_actor_specs"), list) or not site["occluder_actor_specs"]:
        raise ValueError("source-selected original occluder actor construction required")
    if len(site["occluder_actor_specs"]) != len(site["occluders"]):
        raise ValueError("original occluder actor/geometry count differs")
    for spec, rectangle in zip(site["occluder_actor_specs"], site["occluders"]):
        if (not spec.get("blueprint") or not isinstance(spec.get("transform"), dict) or
                spec.get("expected_rectangle_xy_m") != rectangle):
            raise ValueError("original occluder blueprint and transform required")
    sign = site.get("yield_sign_actor_spec")
    if not isinstance(sign, dict) or not sign.get("blueprint") or not isinstance(sign.get("transform"), dict):
        raise ValueError("source-selected original yield-sign actor construction required")
    route = site.get("ego_route")
    if not isinstance(route, list) or len(route) < 3:
        raise ValueError("source-selected original ego route required")
    for point in route:
        if not isinstance(point, dict) or any(type(point.get(key)) not in (float, int) or
                not math.isfinite(point[key]) for key in ("x", "y", "speed_mps")):
            raise ValueError("finite original route point required")
    placement = json.loads(sources["camera_placement"].read_text(encoding="utf-8"))
    if set(placement.get("cameras", {})) != set(CAMERAS):
        raise ValueError("four original camera placements required")
    for name in CAMERAS:
        row = placement["cameras"][name]
        for key in ("location_xyz_m", "pitch_yaw_roll_deg"):
            vector = row.get(key)
            if not isinstance(vector, list) or len(vector) != 3 or any(
                    type(value) not in (float, int) or not math.isfinite(value) for value in vector):
                raise ValueError("finite original camera pose required: " + name)
    return {"review_sha256": sha(path), "sources": sources, "site": site,
            "reference": reference, "placement": placement}
