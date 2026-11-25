"""Fail closed on unsupported production pedestrian signal authority.

The engineering OpenDRIVE map and diagnostic fixtures cannot establish an
official route-facing signal or a governing pedestrian device. A production
scene must bind reviewed source text for its map, signal, device driver, and
full public-highway boundary before CARLA is contacted. This is a source
preflight, not a physical or legal acceptance decision.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def _source(root, entry, label):
    if not isinstance(entry, dict):
        raise ValueError(label + " source binding missing")
    name = entry.get("path")
    digest = entry.get("sha256")
    if (not isinstance(name, str) or not name or Path(name).is_absolute()
            or ".." in Path(name).parts or not isinstance(digest, str)
            or len(digest) != 64):
        raise ValueError(label + " source binding invalid")
    source = root / name
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
        raise ValueError(label + " source absent or escapes attempt")
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(label + " source hash differs")
    return data


def verify(scene, attempt):
    """Require source-backed authority declarations before Native acquisition."""
    root = Path(attempt).resolve()
    if scene.get("diagnostic_fixture") is True:
        raise ValueError("diagnostic fixture cannot be a production signal source")
    review = scene.get("production_source_review")
    if not isinstance(review, dict) or review.get("complete") is not True:
        raise ValueError("production source review missing")
    if review.get("route_id") != scene.get("route_id"):
        raise ValueError("production route identity differs")
    map_data = _source(root, {"path": "candidate-corridor.xodr",
                              "sha256": scene.get("map_source_sha256")}, "OpenDRIVE map")
    try:
        map_root = ET.fromstring(map_data)
    except ET.ParseError as exc:
        raise ValueError("production OpenDRIVE map invalid") from exc
    if map_root.tag != "OpenDRIVE":
        raise ValueError("production OpenDRIVE root differs")
    signals = {item.get("id") for item in map_root.findall(".//signal")}
    controllers = {item.get("id"): item for item in map_root.findall(".//controller")}
    signal_id = review.get("facing_signal_source_id")
    controller_id = review.get("controller_source_id")
    if not signal_id or signal_id not in signals or not controller_id or controller_id not in controllers:
        raise ValueError("production map lacks reviewed signal/controller")
    controlled = {item.get("signalId") for item in controllers[controller_id].findall("control")}
    if signal_id not in controlled:
        raise ValueError("reviewed controller does not govern facing signal")
    for label, review_key, source_key, expected in (
        ("governing-device inventory", "device_inventory_review", "device_ids",
         scene.get("governing_pedestrian_device_ids")),
        ("camera placement", "camera_placement_review", "camera_placements",
         scene.get("camera_placements")),
    ):
        binding = scene.get(review_key)
        if not isinstance(binding, dict) or binding.get("complete") is not True:
            raise ValueError(label + " review missing")
        data = _source(root, {"path": binding.get("source_path"),
                              "sha256": binding.get("source_sha256")}, label)
        try:
            declaration = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(label + " review is not JSON") from exc
        if (not isinstance(declaration, dict) or
                declaration.get("diagnostic_fixture") is True or
                declaration.get("route_id") != scene.get("route_id") or
                not declaration.get("source_evidence") or
                declaration.get(source_key) != expected):
            raise ValueError(label + " review differs from original scene")
    for label in ("official_signal", "pedestrian_device_driver", "highway_boundary_survey"):
        data = _source(root, review.get(label), label)
        try:
            declaration = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(label + " source is not review JSON") from exc
        if not isinstance(declaration, dict) or declaration.get("diagnostic_fixture") is True:
            raise ValueError(label + " source is diagnostic or invalid")
        if declaration.get("route_id") != scene.get("route_id"):
            raise ValueError(label + " route identity differs")
        if not declaration.get("source_evidence"):
            raise ValueError(label + " independent source evidence missing")
        if label == "official_signal" and declaration.get("signal_source_id") != signal_id:
            raise ValueError("official signal source identity differs")
        if label == "pedestrian_device_driver":
            if declaration.get("governing_device_ids") != scene.get("governing_pedestrian_device_ids"):
                raise ValueError("pedestrian device inventory differs")
            if declaration.get("readback_api") != "set_pedestrian_indication,get_state,get_countdown":
                raise ValueError("pedestrian indication/countdown driver not reviewed")
        if label == "highway_boundary_survey":
            if declaration.get("polygon_xy_m") != scene.get("highway_polygon_xy_m"):
                raise ValueError("public highway polygon differs from survey")
    return {"route_id": scene["route_id"], "signal_source_id": signal_id,
            "controller_source_id": controller_id, "source_reviewed": True,
            "physical_acceptance_claimed": False}
