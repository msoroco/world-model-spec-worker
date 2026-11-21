"""Validate a source-bound Native junction candidate before Off-state capture.

The packet is a reviewed construction candidate. Its hashes bind planning
claims; original Native pixels and physical geometry still need GPU review.
"""

import hashlib
import json
import math
from pathlib import Path


REQUIRED_SOURCES = ("map_geometry", "signal_governance", "signal_heads",
                    "stop_boundary", "approach_visibility")
SOURCE_CLAIMS = {
    "map_geometry": {"native_map_name", "intersection_id", "intersection_polygon_xy_m"},
    "signal_governance": {"native_signal_id", "other_native_signal_id", "entrance_road_lanes"},
    "signal_heads": {"installed_uncovered_vehicular_heads"},
    "stop_boundary": {"stop_line_exists", "crosswalk_exists", "stop_boundary",
                      "other_stop_line_exists", "other_crosswalk_exists", "other_stop_boundary"},
    "approach_visibility": {"approach_visibility_source"},
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_bound(base, binding, label):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("Hashed " + label + " binding required")
    if (not isinstance(binding["path"], str) or not binding["path"] or
            not isinstance(binding["sha256"], str) or len(binding["sha256"]) != 64):
        raise ValueError("Hashed " + label + " binding required")
    reference = Path(binding["path"])
    if reference.is_absolute() or ".." in reference.parts:
        raise ValueError("Junction source path escapes packet root")
    root = Path(base).resolve()
    path = (root / reference).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Junction source path escapes packet root")
    if not path.is_file() or _sha(path) != binding["sha256"]:
        raise ValueError(label + " source missing or changed")
    return json.loads(path.read_text())


def validate_site(config, base_dir):
    site = config.get("site")
    if not isinstance(site, dict):
        raise ValueError("Native junction site required")
    packet = _read_bound(base_dir, config.get("site_review"), "Junction review")
    if packet.get("format") != "worker-inoperative-junction-review" or packet.get("site") != site:
        raise ValueError("Selected junction differs from bound review packet")
    if packet.get("review_status") != "reviewed_candidate":
        raise ValueError("Reviewed candidate required")
    docs = packet.get("source_documents")
    if not isinstance(docs, dict) or set(docs) != set(REQUIRED_SOURCES):
        raise ValueError("Complete junction source inventory required")
    for role in REQUIRED_SOURCES:
        document = _read_bound(base_dir, docs[role], role)
        if (document.get("format") != "worker-inoperative-junction-source" or
                document.get("source_role") != role or
                not document.get("review_basis") or
                not isinstance(document.get("reviewed_site_fields"), dict) or
                not document["reviewed_site_fields"]):
            raise ValueError("Structured junction source review required: " + role)
        if not SOURCE_CLAIMS[role] <= set(document["reviewed_site_fields"]):
            raise ValueError("Missing required junction source claims: " + role)
        for field, value in document["reviewed_site_fields"].items():
            if site.get(field) != value:
                raise ValueError("Junction claim differs from source: " + field)
    for field in ("native_map_name", "intersection_id", "native_signal_id", "other_native_signal_id",
                  "installed_uncovered_vehicular_heads", "intersection_polygon_xy_m",
                  "entrance_road_lanes", "stop_boundary", "other_stop_boundary"):
        if field not in site:
            raise ValueError("Missing junction construction field: " + field)
    if site["installed_uncovered_vehicular_heads"] is not True:
        raise ValueError("Uncovered installed heads must be sourced")
    if (type(site["native_signal_id"]) is not int or
            type(site["other_native_signal_id"]) is not int or
            site["native_signal_id"] == site["other_native_signal_id"]):
        raise ValueError("Two distinct sourced Native signal IDs required")
    lanes = site["entrance_road_lanes"]
    if (not isinstance(lanes, list) or len(lanes) != 2 or
            any(not isinstance(lane, list) or len(lane) != 2 or
                any(type(number) is not int for number in lane) for lane in lanes) or
            len({tuple(lane) for lane in lanes}) != len(lanes)):
        raise ValueError("Distinct governed Native entrance lanes required")
    boundary = site["stop_boundary"]
    expected = ("stop_line" if site.get("stop_line_exists") is True else
                "crosswalk" if site.get("stop_line_exists") is False and site.get("crosswalk_exists") is True else
                "nearest_view" if site.get("stop_line_exists") is False and site.get("crosswalk_exists") is False else None)
    if not expected or not isinstance(boundary, dict) or boundary.get("kind") != expected or not boundary.get("source"):
        raise ValueError("Statutory stopping-reference hierarchy differs from source")
    other_expected = ("stop_line" if site.get("other_stop_line_exists") is True else
                      "crosswalk" if site.get("other_stop_line_exists") is False and site.get("other_crosswalk_exists") is True else
                      "nearest_view" if site.get("other_stop_line_exists") is False and site.get("other_crosswalk_exists") is False else None)
    if (other_expected is None or not isinstance(site["other_stop_boundary"], dict) or
            site["other_stop_boundary"].get("kind") != other_expected):
        raise ValueError("Other approach stopping-reference hierarchy differs from source")
    for who, candidate in (("ego", boundary), ("other", site["other_stop_boundary"])):
        if (not isinstance(candidate, dict) or candidate.get("kind") not in
                ("stop_line", "crosswalk", "nearest_view") or not candidate.get("source")):
            raise ValueError("Sourced " + who + " boundary required")
        point, normal = candidate.get("point_xy_m"), candidate.get("upstream_normal_xy")
        if (not isinstance(point, list) or len(point) != 2 or
                not isinstance(normal, list) or len(normal) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in point + normal) or
                abs(math.hypot(*normal) - 1) > 1e-5):
            raise ValueError("Finite sourced " + who + " boundary geometry required")
    if expected == "nearest_view" and not site.get("approach_visibility_source"):
        raise ValueError("Nearest-view approach visibility source required")
    return {"site_review_sha256": config["site_review"]["sha256"],
            "selected_boundary": expected, "native_site_verified": False,
            "physical_head_visibility_verified": False}
