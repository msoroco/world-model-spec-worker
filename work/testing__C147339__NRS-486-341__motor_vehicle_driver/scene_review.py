"""Reject unsourced or synthetic Native protected-lane scene requests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lane_use import CASES, require, validate_site


SOURCE_KEYS = (
    "map", "lane_geometry", "highway", "public_maintenance", "public_vehicle_access",
    "ego_blueprint", "motorcycle_class", "moped_class", "motorcycle_exclusion_review",
    "protected_route", "ego_route_adjacent", "ego_route_edge", "ego_route_deep",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_scene(path, case_id):
    """Validate the operator's original evidence before opening a CARLA client."""
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding="utf-8"))
    require(scene.get("format") == "c147339-reviewed-original-v1", "reviewed scene format missing")
    require(scene.get("source_kind") == "original_reviewed" and
            scene.get("diagnostic_fixture") is False, "original reviewed source required")
    require(scene.get("case_id") == case_id and scene.get("reviewer"),
            "reviewed exact case identity missing")
    case_name = case_id.split("__")[-1]
    require(case_name in {item.case_id for item in CASES}, "unknown exact case")
    require(scene.get("map_id") and scene.get("opendrive_sha256"),
            "reviewed map identity missing")
    require(scene.get("ego_blueprint_id") and scene.get("protected_blueprint_id"),
            "reviewed participant blueprints missing")
    sources = scene.get("sources", {})
    require(set(SOURCE_KEYS) <= set(sources), "reviewed original source inventory incomplete")
    for key in SOURCE_KEYS:
        item = sources[key]
        require(isinstance(item, dict) and item.get("path") and item.get("sha256"),
                "reviewed source missing: " + key)
        candidate = path.parent / item["path"]
        resolved = candidate.resolve()
        require(not candidate.is_symlink() and resolved.is_relative_to(path.parent) and
                resolved.is_file(), "reviewed source path invalid: " + key)
        require(sha(resolved) == item["sha256"], "reviewed source hash changed: " + key)
    site = scene.get("site", {})
    bindings = {
        "map_source_sha256": "map", "lane_source_sha256": "lane_geometry",
        "highway_source_sha256": "highway",
        "public_maintenance_source_sha256": "public_maintenance",
        "public_vehicle_access_source_sha256": "public_vehicle_access",
        "ego_blueprint_source_sha256": "ego_blueprint",
        "motorcycle_class_source_sha256": "motorcycle_class",
        "moped_class_source_sha256": "moped_class",
        "motorcycle_exclusion_review_sha256": "motorcycle_exclusion_review",
    }
    for field, key in bindings.items():
        require(site.get(field) == sources[key]["sha256"], "site source binding differs: " + field)
    require(site.get("protected_route", {}).get("source_sha256") ==
            sources["protected_route"]["sha256"], "protected route source binding differs")
    for route in ("adjacent", "edge", "deep"):
        require(site.get("ego_routes", {}).get(route, {}).get("source_sha256") ==
                sources["ego_route_" + route]["sha256"], "ego route source binding differs: " + route)
    validate_site(site)
    require(scene.get("protected_vehicle_class") == next(item.protected_kind for item in CASES
            if item.case_id == case_name), "protected vehicle class differs")
    require(scene.get("ego_vehicle_class") == "motor_vehicle", "ego motor vehicle class differs")
    return scene
