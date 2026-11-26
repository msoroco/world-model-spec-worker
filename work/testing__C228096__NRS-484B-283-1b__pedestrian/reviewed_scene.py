"""Load original reviewed curb geometry for one exact pedestrian case."""
from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from curb_entry import CASES, validate_scene
from delivery_audit import CAMERAS, SOURCES, linked


def plan(authority_root: Path, site_ref: dict, case_id: str) -> dict:
    root = Path(authority_root).resolve()
    case = next((item for item in CASES if case_id.endswith("__" + item.name) and
                 case_id == "testing__C228096__NRS-484B-283-1b__pedestrian__" + item.name), None)
    if case is None:
        raise ValueError("exact selected pedestrian case required")
    site_path = linked(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("reviewed original curb site required")
    map_path = linked(root, site.get("map_ref"))
    try:
        document = ElementTree.fromstring(map_path.read_text(encoding="utf-8"))
    except ElementTree.ParseError as error:
        raise ValueError("reviewed OpenDRIVE map malformed") from error
    if document.tag != "OpenDRIVE" or not document.findall("road"):
        raise ValueError("reviewed roadway absent from OpenDRIVE")
    scene = site.get("scenes", {}).get(case.name)
    if not isinstance(scene, dict):
        raise ValueError("reviewed exact curb scene missing")
    for name in SOURCES:
        ref = site.get("source_refs", {}).get(name)
        linked(root, ref)
        if scene.get(name + "_source_sha256") != ref["sha256"]:
            raise ValueError("reviewed scene source differs: " + name)
    validate_scene(scene, case)
    cameras = site.get("camera_profiles")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("reviewed four-camera profiles missing")
    for profile in cameras.values():
        if (not isinstance(profile, dict) or
                not isinstance(profile.get("width"), int) or profile["width"] < 640 or
                not isinstance(profile.get("height"), int) or profile["height"] < 360 or
                not isinstance(profile.get("pose"), dict) or
                any(key not in profile["pose"] for key in
                    ("x", "y", "z", "pitch", "yaw", "roll"))):
            raise ValueError("reviewed camera profile incomplete")
    controls = site.get("motion_controls", {})
    if (not all(type(controls.get(key)) in (int, float) and controls[key] > 0
                for key in ("walk_speed_mps", "run_speed_mps", "vehicle_speed_mps")) or
            controls["run_speed_mps"] <= controls["walk_speed_mps"]):
        raise ValueError("reviewed pedestrian and vehicle controls missing")
    return {"format": "c228096-reviewed-native-scene-v1", "case_id": case_id,
            "case": case, "site_sha256": site_ref["sha256"],
            "map_path": str(map_path), "map_sha256": site["map_ref"]["sha256"],
            "scene": scene, "cameras": cameras, "motion_controls": controls,
            "frames": 900, "hz": 20, "physical_acceptance": False,
            "legal_verdict": None}
