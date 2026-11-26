"""Require independently reviewed original map, actor, and operator sources.

The source packet is supplied by the local operator. Synthetic fixture packets
are deliberately rejected here; case expectation flags do not prove duty status.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lane_split import construction, require

SOURCE_KEYS = (
    "map", "lane_geometry", "route_geometry", "clearance", "ego_blueprint",
    "left_blueprint", "right_blueprint", "operator_identity",
    "police_status", "performance_of_duty", "moped_classification",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_scene(path, case_id, parameters):
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding="utf-8"))
    require(scene.get("format") == "c145696-reviewed-original-v1", "reviewed scene format missing")
    require(scene.get("source_kind") == "original_reviewed" and scene.get("diagnostic_fixture") is False,
            "original reviewed source required")
    require(scene.get("case_id") == case_id and scene.get("reviewer"), "reviewed case identity missing")
    require(scene.get("map_id") and scene.get("opendrive_sha256"), "reviewed original map missing")
    require(scene.get("ego_blueprint_id") and scene.get("left_blueprint_id") and
            scene.get("right_blueprint_id"), "reviewed participant blueprint missing")
    sources = scene.get("sources", {})
    require(set(SOURCE_KEYS) <= set(sources), "reviewed source inventory incomplete")
    for key in SOURCE_KEYS:
        entry = sources[key]
        require(isinstance(entry, dict) and entry.get("path") and entry.get("sha256"),
                "reviewed original source missing: " + key)
        source = path.parent / entry["path"]
        resolved = source.resolve()
        require(not source.is_symlink() and resolved.is_relative_to(path.parent) and resolved.is_file(),
                "reviewed source path invalid: " + key)
        require(sha(resolved) == entry["sha256"], "reviewed source hash changed: " + key)
    require(scene.get("operator_status") == parameters["operator_status"], "operator status differs")
    require(scene.get("performance_of_duty") == parameters["performance_of_duty"],
            "performance of duty differs")
    require(scene.get("ego_vehicle_class") == parameters["vehicle_class"], "chapter vehicle class differs")
    require(scene.get("classification_source_sha256") == sources["moped_classification"]["sha256"],
            "chapter vehicle classification source differs")
    require(scene.get("operator_identity_source_sha256") == sources["operator_identity"]["sha256"],
            "operator identity source differs")
    require(scene.get("police_status_source_sha256") == sources["police_status"]["sha256"],
            "police status source differs")
    require(scene.get("performance_of_duty_source_sha256") == sources["performance_of_duty"]["sha256"],
            "performance of duty source differs")
    construction(scene["survey"], parameters)
    return scene
