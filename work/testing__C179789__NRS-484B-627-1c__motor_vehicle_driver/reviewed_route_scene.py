"""Source-gated route plans for the four NRS 484B.627(1)(c) probes.

An open alternate is a construction request, not a legal finding that it was
possible for this journey. The reviewed source packet is required before any
Native adapter is imported or a vehicle is spawned.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from alternate_route import CASES, validate_scene


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _linked(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
        raise ValueError("reviewed source reference missing")
    candidate = root / ref["path"]
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("reviewed source path missing or escaping root")
    if _sha(path) != ref["sha256"]:
        raise ValueError("reviewed source hash changed")
    return path


def plan(authority_root: Path, site_ref: dict, case_id: str) -> dict:
    root = Path(authority_root).resolve()
    case = next((item for item in CASES if case_id.endswith("__" + item.case_id)), None)
    if case is None or case_id != "testing__C179789__NRS-484B-627-1c__motor_vehicle_driver__" + case.case_id:
        raise ValueError("unselected exact route case")
    site_path = _linked(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("original reviewed route site missing")
    map_path = _linked(root, site.get("map_ref"))
    restriction_path = _linked(root, site.get("restriction_ref"))
    review = json.loads(restriction_path.read_text(encoding="utf-8"))
    try:
        map_xml = ElementTree.fromstring(map_path.read_text(encoding="utf-8"))
    except ElementTree.ParseError as error:
        raise ValueError("reviewed OpenDRIVE malformed") from error
    if map_xml.tag != "OpenDRIVE":
        raise ValueError("reviewed OpenDRIVE missing")
    if not isinstance(site.get("highway_legal_review"), dict) or not site["highway_legal_review"].get("source"):
        raise ValueError("legal highway classification source missing")
    if not isinstance(site.get("controlled_access_legal_review"), dict) or not site["controlled_access_legal_review"].get("source"):
        raise ValueError("controlled-access classification source missing")
    if site["controlled_access_legal_review"].get("declared") is not case.controlled_access:
        raise ValueError("case controlled-access classification differs from reviewed site")
    if review.get("alternate_restriction_state") != ("open" if case.alternate_declared else "restricted"):
        raise ValueError("case alternate restriction differs from reviewed source")
    if not review.get("journey_destination") or not review.get("restriction_source"):
        raise ValueError("reviewed journey or restriction source missing")
    scene = dict(site.get("scene", {}))
    scene.update(cell_id="C179789", actor="motor_vehicle_driver",
                 controlled_access=case.controlled_access,
                 alternate_declared=case.alternate_declared,
                 alternate_restriction_state=review["alternate_restriction_state"],
                 journey_destination=review["journey_destination"])
    validate_scene(scene, case)
    cameras = site.get("camera_profiles")
    if not isinstance(cameras, dict) or set(cameras) != {
            "overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four reviewed camera views missing")
    if any(not isinstance(view, dict) or not view.get("pose") or not view.get("fov_deg")
           for view in cameras.values()):
        raise ValueError("reviewed camera pose or field of view missing")
    return {"format": "c179789-source-gated-route-plan-v1", "case_id": case_id,
            "site_sha256": site_ref["sha256"], "map_sha256": _sha(map_path),
            "restriction_sha256": _sha(restriction_path), "map_path": str(map_path),
            "scene": scene, "cameras": cameras, "hz": 20, "frames": 900,
            "physical_acceptance": False, "legal_judgment": None,
            "possible_route_judgment": None}
