"""Load a SHA-bound reviewed signal/highway scene for one exact case."""
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from ped_entry import CASES, validate_scene
from delivery_audit import ASSIGNMENT, CAMERAS, SOURCES, linked


def plan(authority_root: Path, site_ref: dict, case_id: str) -> dict:
    root = Path(authority_root).resolve()
    case = next((item for item in CASES if case_id == ASSIGNMENT + "__" + item.case_id), None)
    if case is None:
        raise ValueError("exact selected signal case required")
    site_path = linked(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("reviewed original signal/highway site required")
    map_path = linked(root, site.get("map_ref"))
    try:
        document = ElementTree.fromstring(map_path.read_text(encoding="utf-8"))
    except ElementTree.ParseError as error:
        raise ValueError("reviewed OpenDRIVE malformed") from error
    if document.tag != "OpenDRIVE" or not document.findall("road"):
        raise ValueError("reviewed highway missing from OpenDRIVE")
    scene = site.get("scenes", {}).get(case.case_id)
    if not isinstance(scene, dict):
        raise ValueError("reviewed exact pedestrian signal scene missing")
    for name in SOURCES:
        ref = site.get("source_refs", {}).get(name)
        linked(root, ref)
        if scene.get(name + "_source_sha256") != ref["sha256"]:
            raise ValueError("reviewed signal scene source differs: " + name)
    validate_scene(scene, case)
    if (not isinstance(scene.get("signal_facing_xy"), list) or
            len(scene["signal_facing_xy"]) != 2 or
            any(type(value) not in (int, float) for value in scene["signal_facing_xy"])):
        raise ValueError("reviewed pedestrian-facing signal position missing")
    assets = site.get("native_signal_assets")
    if (not isinstance(assets, dict) or
            not all(type(assets.get(name)) is int and assets[name] > 0 for name in
                    ("red_signal_actor_id", "green_arrow_actor_id", "other_device_actor_id")) or
            len(set(assets.values())) != 3):
        raise ValueError("reviewed distinct Native red/arrow/other-device assets required")
    cameras = site.get("camera_profiles")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("reviewed four-camera profiles missing")
    for profile in cameras.values():
        if (not isinstance(profile, dict) or type(profile.get("width")) is not int or
                profile["width"] < 640 or type(profile.get("height")) is not int or
                profile["height"] < 360 or not isinstance(profile.get("pose"), dict) or
                any(key not in profile["pose"] for key in
                    ("x", "y", "z", "pitch", "yaw", "roll"))):
            raise ValueError("reviewed camera profile incomplete")
    controls = site.get("motion_controls", {})
    if type(controls.get("walk_speed_mps")) not in (int, float) or controls["walk_speed_mps"] <= 0:
        raise ValueError("reviewed pedestrian walking control missing")
    return {"format": "c227824-reviewed-native-scene-v1", "case_id": case_id,
            "case": case, "site_sha256": site_ref["sha256"],
            "map_path": str(map_path), "map_sha256": site["map_ref"]["sha256"],
            "scene": scene, "cameras": cameras, "motion_controls": controls,
            "native_signal_assets": assets, "frames": 900, "hz": 20,
            "physical_acceptance": False, "legal_verdict": None}
